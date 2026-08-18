# AutoTask Bot

[Versão em português](README.md)

Configurable Python automation for filling out web forms that support keyboard navigation, using data stored in CSV files.

The core concept of this study is: **pandas reads and validates the data, while PyAutoGUI controls the browser through keyboard and mouse input**. The **AutoTask** website included in the repository serves as a demonstration environment and does not define the automation engine's logic.

![AutoTask dashboard](docs/autotask-dashboard.png)

## Features

- CSV file reading and validation with pandas.
- Sequential form filling with PyAutoGUI.
- External configuration for the URL, login process, fields, and submission method.
- Support for values from CSV files, fixed text, and environment variables.
- Focus-based and `Tab`-based navigation without website-specific image anchors.
- Relative-position calibration for external pages.
- Demonstration website with its own visual identity.
- Dedicated browser window to prevent extra tabs and accidental layout changes.
- Preventive suppression of first-run, default-browser, and password-saving prompts.
- Login and submission confirmation through the window title.
- Protection against two simultaneous executions.
- Safe interruption through PyAutoGUI's `FAILSAFE` mechanism.

## Workflow

```text
produtos.csv ──► pandas ──► config.json ──► PyAutoGUI ──► web form
```

## Repository structure

```text
autotask-bot/
├── bot.py
├── config.json
├── produtos.csv
├── requirements.txt
├── setup.bat
├── run.bat
├── calibrate.bat
├── preview-site.bat
├── README.md
├── README.en.md
├── CHANGELOG.md
├── LICENSE
├── .gitignore
├── .gitattributes
├── .editorconfig
├── docs/
│   ├── autotask-login.png
│   └── autotask-dashboard.png
└── site-demo/
    ├── index.html
    ├── produtos.html
    ├── login.js
    ├── produtos.js
    ├── styles.css
    └── assets/
        ├── logo.svg
        └── favicon.svg
```

## Requirements

- Windows 10 or Windows 11.
- Python 3.10 or later.
- A browser that supports keyboard navigation.

When installing Python on Windows, enabling **Add Python to PATH** is recommended.

## Quick start

Run:

```text
run.bat
```

The script looks for Python in the following order:

1. Python Launcher: `py -3`.
2. The `python` command.
3. The `python3` command.

On the first run, it creates the `.venv` virtual environment, installs the dependencies, and starts the automation. The demonstration website opens in a dedicated browser window without using `Win + ↑`, resetting the zoom, or automatically creating multiple tabs. Startup also disables the default-browser notice, first-run prompts, and password-saving offers in compatible Chromium-based browsers.

### Running from the terminal

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python bot.py
```

## Demonstration website

The repository includes a local interface with a login screen, registration form, and product table.

Credentials:

```text
Email:    usuario@demo.com
Password: demo123
```

To open only the interface:

```text
preview-site.bat
```

## Configuration

Automation rules are stored in `config.json`. You can configure:

- CSV file path.
- Form URL.
- Local demonstration server.
- Login step.
- Field order.
- Value sources.
- Number of `Tab` key presses after each field.
- Initial focus.
- Submission method.
- Browser launch mode.
- Expected title at each stage.
- Completion confirmation for each submission.
- Intervals and delays.

### Value from a CSV column

```json
{
  "source": "column",
  "name": "codigo",
  "tabs_after": 1
}
```

### Fixed text

```json
{
  "source": "literal",
  "value": "fixed text",
  "tabs_after": 1
}
```

### Environment variable

```json
{
  "source": "env",
  "name": "AUTOTASK_EMAIL",
  "tabs_after": 1
}
```

In PowerShell:

```powershell
$env:AUTOTASK_EMAIL = "your-email@example.com"
```

Real credentials should not be stored in `config.json` or committed to GitHub.

## Adapting the bot to another form

1. Change `browser.url` in `config.json`.
2. Set `browser.demo_server.enabled` to `false`.
3. Set `browser.ready_title_contains` to part of the initial page title.
4. Configure the login step and `login.success_title_contains`, when required.
5. Arrange `form.fields` in the same order as the page's keyboard navigation sequence.
6. Choose a confirmation method in `form.confirmation`.
7. Run `calibrate.bat` if the form does not automatically focus its first field.

Calibration stores the first field's position as a proportion of the window, avoiding absolute coordinates tied to a specific display resolution.

### Browser launch

The default mode is `app`, which opens a dedicated Chromium window without tabs. AutoTask automatically looks for Microsoft Edge, Google Chrome, Opera GX, or Opera.

```json
{
  "launch_mode": "app",
  "executable": "auto",
  "suppress_default_browser_prompt": true,
  "suppress_password_save_prompt": true,
  "use_dedicated_profile": true,
  "profile_directory": "%LOCALAPPDATA%\\AutoTaskBot\\BrowserProfile",
  "dismiss_startup_prompts": true,
  "dismiss_post_login_prompts": true
}
```

The dedicated profile is stored outside the repository and is used only while AutoTask is running. This prevents tabs, previous sessions, and personal-profile settings from interfering with the workflow. Before opening the browser, the bot records in this profile that credential services and password saving are disabled—a safeguard added after recurring issues observed during testing. It also sends controlled `Esc` key presses before and after login and confirms that the AutoTask window has regained focus.

The following preventive arguments are enabled by default:

```text
--no-first-run
--no-default-browser-check
--disable-default-apps
--disable-session-crashed-bubble
```

Additional arguments can be added to the `browser.extra_arguments` list.

The following preferences are automatically applied to the dedicated profile when `suppress_password_save_prompt` is enabled:

```text
credentials_enable_service = false
credentials_enable_autosignin = false
profile.password_manager_enabled = false
profile.password_manager_leak_detection = false
```

These changes affect only AutoTask's dedicated profile and do not modify passwords or preferences in the user's personal browser profile.

The following modes are also available:

- `new_window`: opens a separate standard browser window.
- `system`: uses the system's default browser, without guaranteed prompt suppression.
- An explicit path in `browser.executable`, when required.

### Stage confirmation

The bot does not continue after login until it finds the title configured in `login.success_title_contains`. On the demonstration website, each submission changes the counter displayed in the window title; the next record starts only after this change is detected.

```json
{
  "confirmation": {
    "method": "title_change",
    "timeout_seconds": 4.0
  }
}
```

For external pages, you can also use `title_contains` or a controlled `wait` delay.

## Focus methods

Preserve the focus set by the page itself:

```json
{
  "method": "current"
}
```

Move forward using the keyboard:

```json
{
  "method": "tab",
  "count": 1
}
```

Use a position relative to the window:

```json
{
  "method": "click_relative",
  "relative_to": "window",
  "x": 0.426,
  "y": 0.368
}
```

## Safety during execution

Move the cursor to the upper-left corner of the screen to trigger PyAutoGUI's `FAILSAFE` mechanism and interrupt the bot.

You can also stop the process from the terminal with `Ctrl+C`.

## Limitations

The technically accurate project description is:

> Configurable automation for web forms that support keyboard navigation.

CAPTCHAs, iframes, custom components, asynchronous validations, and anti-automation mechanisms may require additional configuration or prevent the current version from working.

Additionally:

- The browser must remain visible.
- Pop-up prevention is more reliable in `app` and `new_window` modes when a Chromium-based browser is detected.
- Title-based confirmation depends on predictable window titles.
- The mouse and keyboard remain occupied during execution.
- Changes to field order require updates to `config.json`.
- Calibration may need to be repeated after significant window changes.
- This is an educational project and should not be used to bypass access controls.

## License

Distributed under the MIT License. See [LICENSE](LICENSE).

## Project history

This project is the natural evolution of an initial version created in 2023. Because that version was developed and maintained only in a local environment, there is no public history showing every stage of the code's evolution over the years.

However, I published images of the 2023 study version on my portfolio, making it possible to compare both stages of the project: [view the original project on my portfolio](https://lucasmori.com/projeto/rpa-cadastro-automatico).
