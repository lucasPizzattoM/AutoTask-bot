from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.request
import webbrowser
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pandas as pd
import pyautogui as pa

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.json"
WINDOWS_ALREADY_EXISTS = 183

pa.FAILSAFE = True


@dataclass(frozen=True)
class WindowGeometry:
    left: int
    top: int
    width: int
    height: int


class SingleInstanceLock:
    """Impedir duplicacao de bots."""

    def __init__(self, name: str = "Local\\AutoTaskBot") -> None:
        self._handle: int | None = None
        self._kernel32: Any | None = None

        if os.name != "nt":
            return

        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateMutexW.restype = ctypes.c_void_p
        self._kernel32.CreateMutexW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_bool,
            ctypes.c_wchar_p,
        ]
        self._kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

        handle = self._kernel32.CreateMutexW(None, False, name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())

        if ctypes.get_last_error() == WINDOWS_ALREADY_EXISTS:
            self._kernel32.CloseHandle(handle)
            raise RuntimeError(
                "O AutoTask Bot já está em execução. Feche a outra janela antes de iniciar novamente."
            )

        self._handle = int(handle)

    def close(self) -> None:
        if self._handle is not None and self._kernel32 is not None:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self) -> SingleInstanceLock:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class QuietHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Chama a demo com HTTP sem registrar cada requisicaozinha no terminal."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preenche formulários web compatíveis com navegação por teclado "
            "usando dados de um arquivo CSV."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Caminho do arquivo de configuração JSON.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Processa somente as primeiras N linhas do CSV.",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Recalibra os pontos iniciais do login e do formulário.",
    )
    parser.add_argument(
        "--site-only",
        action="store_true",
        help="Abre somente o site-demo, sem controlar mouse e teclado.",
    )
    return parser.parse_args()


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.is_absolute():
        config_path = (BASE_DIR / config_path).resolve()

    if not config_path.is_file():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"JSON inválido em {config_path}, linha {error.lineno}: {error.msg}"
        ) from error

    validate_config(config)
    config["_config_path"] = str(config_path)
    return config


def validate_config(config: dict[str, Any]) -> None:
    required_sections = {"data", "browser", "form", "automation"}
    missing_sections = required_sections - set(config)
    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        raise ValueError(f"Seções ausentes no config.json: {missing}")

    launch_mode = config["browser"].get("launch_mode", "system")
    if launch_mode not in {"app", "new_window", "system"}:
        raise ValueError("browser.launch_mode deve ser 'app', 'new_window' ou 'system'.")

    extra_arguments = config["browser"].get("extra_arguments", [])
    if not isinstance(extra_arguments, list):
        raise ValueError("browser.extra_arguments deve ser uma lista.")

    escape_presses = config["browser"].get("startup_prompt_escape_presses", 2)
    if not isinstance(escape_presses, int) or escape_presses < 0:
        raise ValueError(
            "browser.startup_prompt_escape_presses deve ser um inteiro não negativo."
        )

    post_login_escape_presses = config["browser"].get(
        "post_login_prompt_escape_presses",
        1,
    )
    if not isinstance(post_login_escape_presses, int) or post_login_escape_presses < 0:
        raise ValueError(
            "browser.post_login_prompt_escape_presses deve ser um inteiro não negativo."
        )

    form_fields = config["form"].get("fields", [])
    if not form_fields:
        raise ValueError("A seção 'form.fields' precisa ter ao menos um campo.")

    for section_name in ("login", "form"):
        section = config.get(section_name, {})
        if section_name == "login" and not section.get("enabled", False):
            continue

        focus = section.get("focus")
        if not isinstance(focus, dict):
            raise ValueError(f"A seção '{section_name}.focus' é obrigatória.")

        method = focus.get("method", "click_relative")
        if method not in {"click_relative", "tab", "current"}:
            raise ValueError(
                f"Método de foco não suportado em '{section_name}.focus': {method}"
            )

        if method == "click_relative":
            for coordinate in ("x", "y"):
                value = focus.get(coordinate)
                if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                    raise ValueError(
                        f"'{section_name}.focus.{coordinate}' deve estar entre 0 e 1."
                    )

    confirmation = config["form"].get("confirmation", {"method": "wait"})
    if confirmation.get("method", "wait") not in {
        "wait",
        "title_change",
        "title_contains",
    }:
        raise ValueError(
            "form.confirmation.method deve ser 'wait', 'title_change' ou 'title_contains'."
        )


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


def load_rows(config: dict[str, Any], limit: int | None = None) -> pd.DataFrame:
    data_config = config["data"]
    csv_path = resolve_project_path(data_config["csv_path"])

    if not csv_path.is_file():
        raise FileNotFoundError(f"Arquivo CSV não encontrado: {csv_path}")

    products = pd.read_csv(csv_path, dtype="string")
    required_columns = set(data_config.get("required_columns", []))
    required_columns.update(
        field["name"]
        for field in config["form"]["fields"]
        if field.get("source") == "column"
    )

    missing = required_columns - set(products.columns)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"O CSV não possui as colunas obrigatórias: {missing_text}")

    non_empty_columns = set(data_config.get("non_empty_columns", []))
    if non_empty_columns:
        invalid_rows = products[list(non_empty_columns)].isna().any(axis=1)
        if invalid_rows.any():
            rows = ", ".join(
                str(index + 2) for index in products.index[invalid_rows][:10]
            )
            raise ValueError(f"Valores obrigatórios vazios nas linhas do CSV: {rows}")

    if limit is not None:
        if limit <= 0:
            raise ValueError("O valor de --limit precisa ser maior que zero.")
        products = products.head(limit)

    return products


def start_demo_server(config: dict[str, Any]) -> ThreadingHTTPServer | None:
    browser = config["browser"]
    server_config = browser.get("demo_server", {})
    if not server_config.get("enabled", False):
        return None

    host = str(server_config.get("host", "127.0.0.1"))
    port = int(server_config.get("port", 8000))
    directory = resolve_project_path(server_config.get("directory", "site-demo"))

    if not directory.is_dir():
        raise FileNotFoundError(f"Pasta do site-demo não encontrada: {directory}")

    handler = partial(QuietHTTPRequestHandler, directory=str(directory))
    server = ReusableThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def wait_for_url(url: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except OSError:
            time.sleep(0.2)

    raise TimeoutError(f"A página não respondeu dentro do tempo esperado: {url}")


def get_all_windows() -> list[Any]:
    try:
        return list(pa.getAllWindows())
    except (AttributeError, NotImplementedError):
        return []


def title_matches(title: str, expected: str) -> bool:
    return expected.casefold() in title.casefold()


def find_window(title_contains: str) -> Any | None:
    matching = [
        window
        for window in get_all_windows()
        if window.title and title_matches(str(window.title), title_contains)
    ]
    if not matching:
        return None

    visible = [window for window in matching if not getattr(window, "isMinimized", False)]
    candidates = visible or matching
    return max(
        candidates,
        key=lambda window: max(0, int(window.width)) * max(0, int(window.height)),
    )


def activate_window(window: Any, maximize: bool = False) -> None:
    try:
        if getattr(window, "isMinimized", False):
            window.restore()
            time.sleep(0.2)
        if maximize and not getattr(window, "isMaximized", False):
            window.maximize()
            time.sleep(0.2)
        window.activate()
        time.sleep(0.25)
        return
    except Exception:
        pass

    # Fallback: Sem atalhos do Win.
    x = int(window.left) + max(20, int(window.width) // 2)
    y = int(window.top) + min(40, max(20, int(window.height) // 10))
    pa.click(x, y)
    time.sleep(0.25)


def wait_for_window(
    title_contains: str,
    timeout: float,
    *,
    activate: bool = True,
    maximize: bool = False,
) -> Any:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        window = find_window(title_contains)
        if window is not None:
            if activate:
                activate_window(window, maximize=maximize)
            return window
        time.sleep(0.15)

    raise TimeoutError(
        f"A janela esperada não apareceu: título contendo '{title_contains}'."
    )


def ensure_target_window(title_contains: str, timeout: float = 3.0) -> Any:
    try:
        active = pa.getActiveWindow()
    except (AttributeError, NotImplementedError):
        active = None

    if active is not None and title_matches(str(active.title or ""), title_contains):
        return active

    return wait_for_window(title_contains, timeout, activate=True)


def close_existing_windows(title_contains: str) -> None:
    for window in get_all_windows():
        if window.title and title_matches(str(window.title), title_contains):
            try:
                window.close()
            except Exception:
                continue
    time.sleep(0.4)


def browser_candidates() -> list[Path]:
    candidates: list[Path] = []

    for executable_name in ("msedge", "chrome", "opera"):
        located = shutil.which(executable_name)
        if located:
            candidates.append(Path(located))

    program_files = [
        os.getenv("PROGRAMFILES"),
        os.getenv("PROGRAMFILES(X86)"),
        os.getenv("LOCALAPPDATA"),
    ]
    relative_paths = [
        Path("Microsoft/Edge/Application/msedge.exe"),
        Path("Google/Chrome/Application/chrome.exe"),
        Path("Programs/Opera GX/opera.exe"),
        Path("Programs/Opera/opera.exe"),
    ]

    for root in program_files:
        if not root:
            continue
        for relative in relative_paths:
            candidates.append(Path(root) / relative)

    return candidates


def resolve_browser_executable(value: str) -> Path | None:
    if value and value.casefold() != "auto":
        configured = Path(os.path.expandvars(value)).expanduser()
        return configured if configured.is_file() else None

    seen: set[str] = set()
    for candidate in browser_candidates():
        normalized = str(candidate).casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        if candidate.is_file():
            return candidate
    return None


def resolve_browser_profile_directory(browser: dict[str, Any]) -> Path | None:
    if not browser.get("use_dedicated_profile", True):
        return None

    configured = str(
        browser.get(
            "profile_directory",
            r"%LOCALAPPDATA%\AutoTaskBot\BrowserProfile",
        )
    )
    expanded = os.path.expandvars(configured)

    # Se a parada nao estiver disponivel, usa uma pasta local (ignorada pelo Git).
    if "%LOCALAPPDATA%" in expanded:
        profile_directory = BASE_DIR / ".autotask" / "browser-profile"
    else:
        profile_directory = Path(expanded).expanduser()
        if not profile_directory.is_absolute():
            profile_directory = BASE_DIR / profile_directory

    profile_directory.mkdir(parents=True, exist_ok=True)
    return profile_directory.resolve()


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        backup = path.with_name(f"{path.name}.invalid")
        try:
            shutil.copy2(path, backup)
        except OSError:
            pass
        raise RuntimeError(
            f"Não foi possível ler as preferências do navegador em {path}. "
            "Uma cópia foi preservada com o sufixo '.invalid'."
        ) from error

    if not isinstance(value, dict):
        raise RuntimeError(
            f"O arquivo de preferências do navegador não contém um objeto JSON: {path}"
        )
    return value


def write_json_atomically(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    last_error: OSError | None = None
    for _ in range(20):
        try:
            temporary.write_text(payload, encoding="utf-8")
            temporary.replace(path)
            return
        except OSError as error:
            last_error = error
            time.sleep(0.1)

    try:
        temporary.unlink(missing_ok=True)
    except OSError:
        pass

    raise RuntimeError(
        "Não foi possível atualizar as preferências do perfil dedicado. "
        "Feche qualquer janela anterior do AutoTask e execute novamente."
    ) from last_error


def prepare_browser_profile(
    browser: dict[str, Any],
    profile_directory: Path | None,
) -> None:
    if profile_directory is None:
        return

    # Chrome/Chromium lê estas preferências no perfil Default. (Solucao dada pelo claude)
    # Tive que desativar o servico de credenciais, o navegador nao deve encher o saco com o salvamento da senha (outro bagulho chato pra cacete do chrome).
    if browser.get("suppress_password_save_prompt", True):
        preferences_path = profile_directory / "Default" / "Preferences"
        preferences = read_json_object(preferences_path)

        preferences["credentials_enable_service"] = False
        preferences["credentials_enable_autosignin"] = False

        profile_preferences = preferences.setdefault("profile", {})
        if not isinstance(profile_preferences, dict):
            profile_preferences = {}
            preferences["profile"] = profile_preferences

        profile_preferences["password_manager_enabled"] = False
        profile_preferences["password_manager_leak_detection"] = False

        write_json_atomically(preferences_path, preferences)


def browser_startup_arguments(
    browser: dict[str, Any],
    profile_directory: Path | None = None,
) -> list[str]:
    arguments: list[str] = []

    if browser.get("suppress_default_browser_prompt", True):
        arguments.extend(
            [
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-default-apps",
                "--disable-session-crashed-bubble",
            ]
        )

    if profile_directory is None:
        profile_directory = resolve_browser_profile_directory(browser)
    if profile_directory is not None:
        arguments.append(f"--user-data-dir={profile_directory}")

    extra_arguments = browser.get("extra_arguments", [])
    if not isinstance(extra_arguments, list):
        raise ValueError("browser.extra_arguments deve ser uma lista de argumentos.")

    arguments.extend(str(argument) for argument in extra_arguments if str(argument).strip())
    return arguments


def dismiss_browser_prompts(
    browser: dict[str, Any],
    title_contains: str,
    *,
    presses: int,
    interval: float,
    settle_seconds: float,
) -> None:
    if title_contains:
        ensure_target_window(
            title_contains,
            float(browser.get("window_timeout_seconds", 15.0)),
        )

    if presses:
        pa.press("esc", presses=max(0, presses), interval=max(0.05, interval))

    time.sleep(max(0.0, settle_seconds))

    # Solucao do claude: Vou deixar (apesar de nao ter funcionado com o salvamento de senha), é pra impedir o popup de roubar o foco do bot e manter a pagian ativa.
    if title_contains:
        ensure_target_window(title_contains, timeout=3.0)

        try:
            active = pa.getActiveWindow()
        except (AttributeError, NotImplementedError):
            active = None

        if active is not None and not title_matches(
            str(active.title or ""),
            title_contains,
        ):
            raise RuntimeError(
                "Um popup ou outra janela continua bloqueando o navegador. "
                "Feche o aviso e execute o AutoTask novamente."
            )


def dismiss_browser_startup_prompts(
    browser: dict[str, Any],
    title_contains: str,
) -> None:
    if not browser.get("dismiss_startup_prompts", True):
        return

    dismiss_browser_prompts(
        browser,
        title_contains,
        presses=int(browser.get("startup_prompt_escape_presses", 2)),
        interval=float(browser.get("startup_prompt_escape_interval", 0.15)),
        settle_seconds=float(browser.get("startup_prompt_settle_seconds", 0.35)),
    )


def dismiss_post_login_prompts(
    browser: dict[str, Any],
    title_contains: str,
) -> None:
    if not browser.get("dismiss_post_login_prompts", True):
        return

    dismiss_browser_prompts(
        browser,
        title_contains,
        presses=int(browser.get("post_login_prompt_escape_presses", 1)),
        interval=float(browser.get("post_login_prompt_escape_interval", 0.12)),
        settle_seconds=float(browser.get("post_login_prompt_settle_seconds", 0.25)),
    )


def launch_target(config: dict[str, Any], url: str) -> None:
    browser = config["browser"]
    launch_mode = str(browser.get("launch_mode", "system"))
    executable = resolve_browser_executable(str(browser.get("executable", "auto")))

    if launch_mode in {"app", "new_window"} and executable is not None:
        profile_directory = resolve_browser_profile_directory(browser)
        prepare_browser_profile(browser, profile_directory)
        arguments = [
            str(executable),
            *browser_startup_arguments(browser, profile_directory),
        ]
        if launch_mode == "app":
            arguments.extend([f"--app={url}", "--start-maximized"])
        else:
            arguments.extend(["--new-window", url])

        subprocess.Popen(
            arguments,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    if launch_mode != "system":
        print(
            "Aviso: navegador Chromium não encontrado; usando o navegador padrão do sistema. "
            "Nesse modo, a supressão do aviso de navegador padrão não pode ser garantida."
        )

    # so pra esclarecer essa parte do codigo: eu tive muito problema tentando configurar os avisos de popup do chrome(eu quero deixar o run o mais cru possivel) entao usei o chromium.
    # Contudo no caso de por algum motivo nao funcionar eu fiz esse falback, acabou que eu nunca precisei usar, testei em 3 ambientes diferentes e todos rodaram o chromium.
    webbrowser.open(url, new=0)


def open_target(config: dict[str, Any]) -> str:
    browser = config["browser"]
    url = str(browser["url"])
    launch_mode = str(browser.get("launch_mode", "system"))
    title_contains = str(browser.get("ready_title_contains", "")).strip()

    existing_title = str(
        browser.get("existing_window_title_contains", title_contains)
    ).strip()
    if (
        launch_mode == "app"
        and browser.get("close_existing_windows", True)
        and existing_title
    ):
        close_existing_windows(existing_title)

    launch_target(config, url)

    timeout = float(browser.get("window_timeout_seconds", 15.0))
    if title_contains:
        wait_for_window(
            title_contains,
            timeout,
            activate=True,
            maximize=bool(browser.get("maximize_window", True)),
        )
        dismiss_browser_startup_prompts(browser, title_contains)
    else:
        time.sleep(float(browser.get("load_wait_seconds", 3.0)))
        dismiss_browser_startup_prompts(browser, "")

    return url


def get_active_window_geometry() -> WindowGeometry:
    try:
        window = pa.getActiveWindow()
    except (AttributeError, NotImplementedError):
        window = None

    if window and window.width > 0 and window.height > 0:
        return WindowGeometry(
            left=int(window.left),
            top=int(window.top),
            width=int(window.width),
            height=int(window.height),
        )

    width, height = pa.size()
    return WindowGeometry(left=0, top=0, width=int(width), height=int(height))


def relative_position(focus: dict[str, Any]) -> tuple[int, int]:
    relative_to = focus.get("relative_to", "window")

    if relative_to == "screen":
        width, height = pa.size()
        geometry = WindowGeometry(0, 0, int(width), int(height))
    elif relative_to == "window":
        geometry = get_active_window_geometry()
    else:
        raise ValueError("focus.relative_to deve ser 'window' ou 'screen'.")

    x = geometry.left + round(geometry.width * float(focus["x"]))
    y = geometry.top + round(geometry.height * float(focus["y"]))
    return x, y


def focus_first_field(focus: dict[str, Any]) -> None:
    method = focus.get("method", "click_relative")

    if method == "click_relative":
        x, y = relative_position(focus)
        pa.click(x, y)
    elif method == "tab":
        pa.press("tab", presses=int(focus.get("count", 1)), interval=0.05)
    elif method == "current":
        return
    else:
        raise ValueError(f"Método de foco não suportado: {method}")


def clear_and_write(value: object, interval: float) -> None:
    pa.hotkey("ctrl", "a")
    pa.write(str(value), interval=interval)


def resolve_field_value(
    field: dict[str, Any],
    row: pd.Series | None,
    empty_values: dict[str, str],
) -> str:
    source = field.get("source", "column")

    if source == "column":
        if row is None:
            raise ValueError("Um campo de coluna foi usado sem uma linha do CSV.")
        name = field["name"]
        value = row[name]
        fallback = field.get("empty", empty_values.get(name, ""))
        if pd.isna(value) or not str(value).strip():
            return str(fallback)
        return str(value)

    if source == "literal":
        return str(field.get("value", ""))

    if source == "env":
        name = field["name"]
        value = os.getenv(name)
        if value is None:
            raise ValueError(f"A variável de ambiente '{name}' não foi definida.")
        return value

    raise ValueError(f"Fonte de campo não suportada: {source}")


def fill_fields(
    fields: list[dict[str, Any]],
    row: pd.Series | None,
    empty_values: dict[str, str],
    write_interval: float,
) -> None:
    for field in fields:
        value = resolve_field_value(field, row, empty_values)
        if field.get("clear", True):
            clear_and_write(value, write_interval)
        else:
            pa.write(value, interval=write_interval)

        tabs_after = int(field.get("tabs_after", 1))
        if tabs_after:
            pa.press("tab", presses=tabs_after, interval=0.03)


def perform_submit(submit: dict[str, Any]) -> None:
    method = submit.get("method", "key")

    if method == "key":
        pa.press(str(submit.get("key", "enter")))
    elif method == "hotkey":
        keys = submit.get("keys", [])
        if not keys:
            raise ValueError("submit.keys não pode ficar vazio.")
        pa.hotkey(*[str(key) for key in keys])
    elif method == "click_relative":
        x, y = relative_position(submit)
        pa.click(x, y)
    else:
        raise ValueError(f"Método de envio não suportado: {method}")


def wait_for_title_change(
    previous_title: str,
    expected_contains: str,
    timeout: float,
) -> Any:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        window = find_window(expected_contains)
        if window is not None and str(window.title) != previous_title:
            return window
        time.sleep(0.08)

    raise TimeoutError(
        "O formulário não confirmou o envio antes do tempo limite. "
        "A automação foi interrompida para evitar registros pulados."
    )


def confirm_form_submission(
    confirmation: dict[str, Any],
    previous_title: str,
    expected_window_title: str,
    fallback_wait: float,
) -> None:
    method = confirmation.get("method", "wait")
    timeout = float(confirmation.get("timeout_seconds", 3.0))

    if method == "title_change":
        wait_for_title_change(previous_title, expected_window_title, timeout)
        return

    if method == "title_contains":
        expected = str(confirmation.get("value", "")).strip()
        if not expected:
            raise ValueError("form.confirmation.value é obrigatório para title_contains.")
        wait_for_window(expected, timeout, activate=False)
        return

    time.sleep(float(confirmation.get("wait_seconds", fallback_wait)))


def perform_login(config: dict[str, Any]) -> None:
    login = config.get("login", {})
    if not login.get("enabled", False):
        return

    browser = config["browser"]
    login_title = str(
        login.get(
            "window_title_contains",
            browser.get("ready_title_contains", ""),
        )
    ).strip()
    if login_title:
        ensure_target_window(login_title, float(browser.get("window_timeout_seconds", 15)))

    time.sleep(float(config["automation"].get("focus_settle_seconds", 0.2)))
    focus_first_field(login["focus"])
    fill_fields(
        fields=login.get("fields", []),
        row=None,
        empty_values={},
        write_interval=float(config["automation"].get("write_interval", 0.01)),
    )
    perform_submit(login.get("submit", {"method": "key", "key": "enter"}))

    success_title = str(login.get("success_title_contains", "")).strip()
    if success_title:
        wait_for_window(
            success_title,
            float(login.get("success_timeout_seconds", 8.0)),
            activate=True,
        )
        dismiss_post_login_prompts(browser, success_title)
    else:
        time.sleep(float(login.get("after_submit_wait_seconds", 1.0)))
        dismiss_post_login_prompts(browser, "")


def fill_form_row(config: dict[str, Any], row: pd.Series) -> None:
    form = config["form"]
    expected_title = str(form.get("window_title_contains", "")).strip()

    if expected_title:
        window = ensure_target_window(
            expected_title,
            float(form.get("window_timeout_seconds", 4.0)),
        )
        previous_title = str(window.title)
    else:
        try:
            window = pa.getActiveWindow()
            previous_title = str(window.title if window else "")
        except (AttributeError, NotImplementedError):
            previous_title = ""

    time.sleep(float(config["automation"].get("focus_settle_seconds", 0.2)))
    focus_first_field(form["focus"])
    fill_fields(
        fields=form["fields"],
        row=row,
        empty_values=config["data"].get("empty_values", {}),
        write_interval=float(config["automation"].get("write_interval", 0.01)),
    )
    perform_submit(form.get("submit", {"method": "key", "key": "enter"}))

    confirmation = form.get("confirmation", {"method": "wait"})
    confirm_form_submission(
        confirmation,
        previous_title,
        expected_title,
        float(form.get("after_submit_wait_seconds", 0.3)),
    )


def countdown(seconds: int, message: str | None = None) -> None:
    if message:
        print(message)

    for remaining in range(seconds, 0, -1):
        print(f"{remaining}...")
        time.sleep(1)


def capture_focus_ratio(relative_to: str = "window") -> dict[str, Any]:
    mouse_x, mouse_y = pa.position()

    if relative_to == "screen":
        width, height = pa.size()
        geometry = WindowGeometry(0, 0, int(width), int(height))
    else:
        geometry = get_active_window_geometry()

    if geometry.width <= 0 or geometry.height <= 0:
        raise RuntimeError("Não foi possível obter as dimensões da janela ativa.")

    return {
        "method": "click_relative",
        "relative_to": relative_to,
        "x": round((mouse_x - geometry.left) / geometry.width, 6),
        "y": round((mouse_y - geometry.top) / geometry.height, 6),
    }


def save_config(config: dict[str, Any]) -> None:
    config_path = Path(config.pop("_config_path"))
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    config["_config_path"] = str(config_path)


def calibrate(config: dict[str, Any]) -> None:
    seconds = int(config["automation"].get("calibration_countdown_seconds", 5))
    relative_to = "window"

    if config.get("login", {}).get("enabled", False):
        countdown(
            seconds,
            "\nPosicione o mouse sobre o PRIMEIRO CAMPO DO LOGIN. "
            "A posição será capturada ao final da contagem.",
        )
        config["login"]["focus"] = capture_focus_ratio(relative_to)
        print("Ponto do login capturado.")

        perform_login(config)

    countdown(
        seconds,
        "\nPosicione o mouse sobre o PRIMEIRO CAMPO DO FORMULÁRIO. "
        "A posição será capturada ao final da contagem.",
    )
    config["form"]["focus"] = capture_focus_ratio(relative_to)
    save_config(config)
    print("\nCalibração salva em config.json.")


def run() -> None:
    args = parse_args()
    config = load_config(args.config)
    pa.PAUSE = float(config["automation"].get("pause_seconds", 0.1))

    server = start_demo_server(config)

    try:
        url = str(config["browser"]["url"])
        if server is not None:
            wait_for_url(url)

        open_target(config)

        if args.site_only:
            print(f"Site aberto em {url}")
            print("Pressione Ctrl+C para encerrar o servidor local.")
            while True:
                time.sleep(1)

        if args.calibrate:
            calibrate(config)
            return

        rows = load_rows(config, args.limit)
        countdown(
            int(config["automation"].get("start_countdown_seconds", 3)),
            "\nA automação começará em instantes.\n"
            "Para interromper, mova o mouse para o canto superior esquerdo.",
        )

        perform_login(config)

        total = len(rows)
        for position, (_, row) in enumerate(rows.iterrows(), start=1):
            fill_form_row(config, row)
            code_column = config["data"].get("display_identifier", "codigo")
            identifier = row.get(code_column, position)
            print(f"Registro {position}/{total} confirmado: {identifier}")

        print(f"\nAutomação concluída. {total} registros foram confirmados.")
    except pa.FailSafeException:
        print("\nAutomação interrompida pelo mecanismo de segurança do PyAutoGUI.")
    except KeyboardInterrupt:
        print("\nExecução encerrada pelo usuário.")
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()


def main() -> None:
    try:
        with SingleInstanceLock():
            run()
    except RuntimeError as error:
        print(f"\n{error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()

# Me levou mais tempo do que eu gostaria para Tornar esse projeto postavel no Git.
# Mas eu estou feliz com o resultado.
#                                                                        Ass. Akuma
