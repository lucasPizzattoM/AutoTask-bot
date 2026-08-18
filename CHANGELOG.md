# Changelog

## 1.0.3 — 2026-08-17

### Fixed

- O perfil dedicado agora desativa `credentials_enable_service` e `profile.password_manager_enabled` antes de iniciar o navegador.
- O navegador deixa de oferecer o salvamento da senha usada no login demonstrativo.
- Após a confirmação do login, um `Esc` controlado fecha avisos residuais e a janela AutoTask recupera o foco antes do primeiro cadastro.
- O formulário demonstrativo declara `autocomplete="off"` e usa `autocomplete="new-password"` como proteção complementar.

### Changed

- A prevenção do popup de senha pode ser configurada por `browser.suppress_password_save_prompt` e `browser.dismiss_post_login_prompts`.

## 1.0.2 — 2026-08-17

### Fixed

- Adicionada prevenção ao popup de definição de navegador padrão antes do login.
- A janela Chromium agora é iniciada com `--no-default-browser-check`, `--no-first-run` e `--disable-default-apps`.
- O AutoTask utiliza um perfil de navegador dedicado, evitando que preferências e prompts do perfil pessoal interfiram na automação.
- Após a abertura, o bot envia `Esc` de forma controlada e recupera a janela AutoTask antes de preencher qualquer campo.

### Changed

- Argumentos adicionais do navegador podem ser definidos em `browser.extra_arguments`.
- O modo `system` exibe um aviso porque navegadores abertos pelo sistema não aceitam garantia de supressão do popup.

## 1.0.1 — 2026-08-17

### Fixed

- Removidos os atalhos `Win + ↑` e `Ctrl + 0`, que podiam redimensionar ou reorganizar a janela errada.
- A abertura padrão agora usa uma janela Chromium dedicada, evitando múltiplas abas e divisão acidental da tela.
- O login só é considerado concluído após a página de produtos ser identificada pelo título da janela.
- Cada cadastro precisa ser confirmado antes do início da próxima linha do CSV.
- Duas instâncias do AutoTask não podem mais ser executadas simultaneamente.

### Changed

- A detecção automática de navegador prioriza Edge, Chrome, Opera GX e Opera.
- O site-demo atualiza o título da janela com a quantidade de registros processados.
- Falhas de foco ou confirmação interrompem a automação em vez de permitir que ela continue fora de sequência.

## 1.0.0 — 2026-08-17

### Added

- Identidade visual AutoTask com logo, favicon, login e dashboard.
- Arquivo `config.json` para dados, URL, login, campos, foco e envio.
- `setup.bat` com detecção automática de `py -3`, `python` e `python3`.
- Calibração opcional por coordenadas relativas à janela.
- Suporte a valores vindos do CSV, texto literal e variável de ambiente.
- Arquivos `.gitattributes` e `.editorconfig` para padronização do repositório.

### Changed

- O site-demo passa a ser apenas um ambiente demonstrativo independente.
- O motor não depende de imagens ou elementos visuais exclusivos do site.
- Os scripts do Windows compartilham o mesmo fluxo de preparação do ambiente.
- A documentação foi revisada para publicação pública no GitHub.

### Removed

- Dependência do site original usado durante o estudo.
- Imagens-âncora específicas de login e formulário.
- OpenCV, Pillow e NumPy como dependências diretas.
- Script separado de teste e artefatos locais de execução.
