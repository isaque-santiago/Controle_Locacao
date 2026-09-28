# Testes de navegador (Playwright): linha de base de UI/UX

Suíte separada dos testes Python (`tests/`). Mede overflow horizontal, controles fora da
janela, alvos menores que 44 × 44 px, diálogos que não cabem e erros de console, em cinco
larguras, dois temas e quatro perfis de navegador, e gera capturas de tela. Na Etapa 0 ela
**registra achados** (não reprova); use `--e2e-estrito` para reprovar quando houver P0.

## Preparação (uma vez)

Os comandos abaixo são para o PowerShell, executados na raiz do projeto
(`cd C:\Controle_Locacao`); o prefixo `.\` é obrigatório.

```bash
.\.venv\Scripts\python.exe -m pip install -r e2e/requirements-e2e.txt
.\.venv\Scripts\python.exe -m playwright install chromium firefox webkit
```

## Ambiente: sempre o de desenvolvimento

A suíte só roda contra `localhost` e usa o usuário de teste do projeto Supabase de
**desenvolvimento** (dados fictícios; ver "Como a IA acessa o app" no `CLAUDE.md`). Assim
as capturas nunca contêm dados reais.

1. Aponte `.streamlit/secrets.toml` para o projeto de dev e suba o app
   (`.venv\Scripts\streamlit.exe run app.py`).
2. Defina as variáveis de ambiente na sua sessão (nada disso vai para o repositório):

   | Variável | Significado |
   |---|---|
   | `E2E_BASE_URL` | URL do app local (padrão `http://localhost:8501`) |
   | `E2E_EMAIL`, `E2E_SENHA` | usuário de teste do projeto de dev; sem elas, só o login é testado |
   | `E2E_DADOS` | `vazio`, `normal` ou `extremo`: rótulo do estado do banco (ver `Arquivos/Inventario_UI_UX.md`) |

PowerShell:

```powershell
$env:E2E_BASE_URL = "http://localhost:8501"
$env:E2E_EMAIL = "e-mail-do-usuario-de-teste"   # valor real, sem < >
$env:E2E_SENHA = "senha-do-usuario-de-teste"    # valor real, sem < >
$env:E2E_DADOS = "normal"
```

## Execução

```bash
.\.venv\Scripts\python.exe -m pytest e2e                      # Chromium desktop, 5 larguras, 2 temas
.\.venv\Scripts\python.exe -m pytest e2e --capturas           # também salva PNGs em e2e/capturas/
.\.venv\Scripts\python.exe -m pytest e2e --larguras 320,390 --temas claro
.\.venv\Scripts\python.exe -m pytest e2e --perfil chromium-desktop --perfil chromium-movel --perfil firefox --perfil webkit --capturas
.\.venv\Scripts\python.exe -m pytest e2e -k login             # só a tela de acesso (não precisa de credenciais)
.\.venv\Scripts\python.exe -m pytest e2e --e2e-estrito        # reprova se houver P0
```

`pytest` sem argumentos roda apenas `tests/` (240 testes), por causa do `pytest.ini`.

| Perfil | Navegador | Observação |
|---|---|---|
| `chromium-desktop` | Chromium | padrão; todas as larguras |
| `chromium-movel` | Chromium | toque e UA de celular; só 320, 390 e 768 px |
| `firefox`, `webkit` | Firefox, WebKit | desktop |

Cada cenário é `perfil-largura-tema` (ex.: `chromium-desktop-390-escuro`); o login é feito
uma vez por cenário. O tema é escolhido pelo cookie `tema_escuro` (o app não segue o tema
do sistema, pois o `config.toml` fixa `base = "light"`).

## O que é gerado

- `e2e/resultados/achados.md` e `achados.json`: achados agrupados por página, severidade e
  onde reproduzir (perfil, largura, tema, estado de dados, fluxo). Ignorados pelo git.
- `e2e/capturas/<dados>/<perfil>/<tema>/<largura>/<tela>.png`: capturas de página inteira.
  Ignoradas pelo git; regenere quando precisar comparar.
- O registro curado fica em `Arquivos/Achados_UI_UX.md`.

## Limites conhecidos da Etapa 0

- Os fluxos 4 a 8 param antes de gravar (abrem o assistente ou o diálogo e fecham). A
  submissão real entra nas Etapas 5 e 9.
- Botões de ação por ícone são localizados por nome acessível (`pagamento`, `‹ Motos` etc.).
  Se o rótulo mudar ou a lista estiver vazia, o cenário registra `INFO` em vez de falhar.
- Emulação não substitui aparelho real; a homologação final (Etapa 9) usa telefone físico.
