# Testes de navegador (Playwright): app web (FastAPI + HTMX)

Suíte separada dos testes Python (`tests/`). Mede overflow horizontal, controles fora da janela, alvos menores que
44 × 44 px, diálogos que não cabem, erros de console e respostas 5xx, roda o **axe-core** (impacto crítico = P0, grave = P1)
e a navegação por **teclado**, em cinco larguras, dois temas e quatro perfis de navegador, e gera capturas de tela. Também
executa os **10 fluxos de homologação** gravando no banco de desenvolvimento. Por padrão ela **registra achados** (não
reprova); use `--e2e-estrito` para reprovar quando houver P0 ou violação crítica/grave do axe.

## Preparação (uma vez)

Os comandos abaixo são para o PowerShell, executados na raiz do projeto (`cd C:\Controle_Locacao`); o prefixo `.\` é obrigatório.

```bash
.\.venv\Scripts\python.exe -m pip install -r e2e/requirements-e2e.txt
.\.venv\Scripts\python.exe -m playwright install chromium firefox webkit
```

## Ambiente: sempre o de desenvolvimento

A suíte só roda contra `localhost` e usa o usuário de teste do projeto Supabase de **desenvolvimento** (dados fictícios; ver
"Como a IA acessa o app" no `CLAUDE.md`). Os fluxos 4 a 10 **gravam** nesse banco (contrato, pagamento, manutenção, documento,
vistoria, configurações); o que criam leva "E2E" na descrição. Recrie o banco de dev quando quiser limpar.

1. Aponte o `.streamlit/secrets.toml` para o projeto de dev e suba o app novo (`.venv\Scripts\python.exe executar_web.py`,
   que escuta na porta 8000, ou a configuração `locacao-web` do preview).
2. Defina as variáveis de ambiente na sua sessão (nada disso vai para o repositório; a IA nunca digita nem lê estes valores):

   | Variável | Significado |
   |---|---|
   | `E2E_BASE_URL` | URL do app local (padrão `http://localhost:8000`) |
   | `E2E_EMAIL`, `E2E_SENHA` | usuário **dono** de teste do projeto de dev; sem elas, só a tela de acesso é testada |
   | `E2E_DADOS` | `vazio`, `normal` ou `extremo`: rótulo do estado do banco (ver `Arquivos/Inventario_UI_UX.md`) |

PowerShell:

```powershell
$env:E2E_BASE_URL = "http://localhost:8000"
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
.\.venv\Scripts\python.exe -m pytest e2e -k fluxo             # só os fluxos de homologação
.\.venv\Scripts\python.exe -m pytest e2e --e2e-estrito        # reprova se houver P0
```

`pytest` sem argumentos roda apenas `tests/`, por causa do `pytest.ini`.

| Perfil | Navegador | Observação |
|---|---|---|
| `chromium-desktop` | Chromium | padrão; todas as larguras |
| `chromium-movel` | Chromium | toque e UA de celular; só 320, 390 e 768 px |
| `firefox`, `webkit` | Firefox, WebKit | desktop |

Cada cenário é `perfil-largura-tema` (ex.: `chromium-desktop-390-escuro`). O login por senha é feito **uma vez por perfil** e
reaproveitado (largura e tema mudam no mesmo contexto). O tema vem do cookie `tema` (`claro` ou `escuro`), que o servidor lê.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `test_login.py` | tela de acesso: layout, axe, teclado (sem credenciais) |
| `test_paginas.py` | fluxo 1: as 10 páginas do menu e o logout |
| `test_fluxos.py` | fluxos 2 a 10; os de 4 a 10 gravam (uma vez por perfil Chromium, largura de referência, tema claro) |
| `test_homologacao.py` | zoom 200%, reflow a 320 px, paisagem, texto 200%, espaçamento WCAG, teclado e rede/CPU reduzidas |
| `test_regressao_visual.py` | compara com `e2e/referencia/web/<sistema>/...` (ignorado pelo git) |
| `test_cobertura_dos_fluxos.py` | garante os 10 fluxos e que o inventário de páginas espelha `src/web/navegacao.py` |
| `roteiro.py`, `ajudas.py`, `verificacoes.py` | apoio: contexto dos fluxos, medições no navegador, achados |

## O que é gerado

- `e2e/resultados/achados.md` e `achados.json`: achados agrupados por página, severidade e onde reproduzir (perfil, largura,
  tema, estado de dados, fluxo). Ignorados pelo git.
- `e2e/capturas/<dados>/<perfil>/<tema>/<largura>/<tela>.png`: capturas de página inteira. Ignoradas pelo git.
- O registro curado fica em `Arquivos/Achados_UI_UX.md`.

## Regressão visual

A primeira execução grava a referência; `--atualizar-referencia` a substitui; `--tolerancia-visual 0.3` é o percentual de
pixels aceito. As referências do Streamlit (`e2e/referencia/<sistema>/`) deixaram de valer e podem ser apagadas.

## Limites conhecidos

- Os fluxos que gravam rodam só nos perfis Chromium (desktop e celular emulado), para não multiplicar dados no banco.
- Botões e campos são localizados por nome acessível e por `id`; se o rótulo mudar, o fluxo registra um achado INFO ou P0.
- Emulação não substitui aparelho real nem leitor de tela: a homologação final usa o `Arquivos/Roteiro_Homologacao_Manual.md`.
- O app só é testado em `localhost`.
