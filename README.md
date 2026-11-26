# LA Locadora: controle de locação e manutenção de veículos

Sistema web para controlar locação, manutenção, documentação e vistorias de uma frota de veículos de aluguel (hoje, motos).
Publicado em `https://lamotos.duckdns.org`.

## O que o sistema faz

- **Frota e clientes:** cadastro de veículos e locatários, plano de manutenção, documentos e arquivamento de vendidos e ex-locatários.
- **Contratos:** locação ou promessa de compra, com uma ou várias motos, vistorias de entrega e devolução, caução e contrato em PDF.
- **Financeiro:** cobranças e encargos, pagamentos, dívidas, Dashboard e relatórios com exportação em CSV e Excel.
- **Portal do locatário:** troca de óleo, envio de comprovantes de documentos e troca de senha.
- **Integrações (desligadas até serem configuradas):** avisos automáticos por WhatsApp e conector do claude.ai.

## Documentação

| Documento | Para que serve |
|---|---|
| [Referência técnica](Arquivos/Referencia_Tecnica.md) | Como o sistema funciona hoje: telas, regras, segurança e integrações. |
| [Histórico do desenvolvimento](Arquivos/Historico_Desenvolvimento.md) | Fases, entregas, correções, validações e cargas de dados, com datas. |
| [Plano do projeto](Arquivos/Projeto_Locação.md) | Fases, regras de negócio e decisões do dono. |
| [Deploy na VPS](Arquivos/Deploy_VPS.md) | Implantação no Coolify, variáveis, backup e tarefa agendada. |
| [Guia de uso](Arquivos/Guia_de_Uso_LA_Locadora.docx) | Para novos funcionários (edição de novembro de 2026; dados das telas fictícios, valores ilustrativos). Revise quando telas ou regras mudarem. |
| [Índice completo](Arquivos/README.md) | Demais documentos (interface, dados, homologação). |

As regras para contribuir, inclusive com assistentes de IA, estão no [CLAUDE.md](CLAUDE.md).

## Stack

Python 3.12 ou mais recente, FastAPI + Jinja2 + HTMX + Tailwind, Supabase (PostgreSQL + Auth + Storage) e pytest.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `src/domain/` | Regras de negócio (funções puras). |
| `src/services/`, `src/repositories/` | Casos de uso e acesso ao Supabase (página → service → repository/RPC). |
| `src/web/` | Rotas (`rotas/`), templates Jinja2 (`templates/`) e CSS-fonte (`estilos/app.css`). |
| `static/` | CSS compilado, fontes, JavaScript e ícones. |
| `supabase/` | Migrations, Edge Function, seeds e roteiros de verificação. |
| `tests/`, `e2e/` | Testes automatizados e suíte de navegador. |
| `scripts/` | Utilitários (CSS, ícones, extração de chat exportado). |
| `Arquivos/` | Documentação. |

A organização planejada está na seção 3 do [plano](Arquivos/Projeto_Locação.md).

## Instalação

Use um projeto Supabase de **desenvolvimento** para trabalhar no código; nunca o de produção.

1. Crie um projeto no Supabase.
2. Desative o cadastro público em Authentication > Providers > Email e crie manualmente o usuário do dono. Copie o UUID dele (Authentication > Users).
3. Aplique as migrations de `supabase/migrations/`, na ordem dos timestamps. **Antes** de aplicar a `20260922000000_restringe_rls_ao_dono.sql`,
   troque o UUID dentro de `is_dono()` pelo do seu usuário: com um UUID errado, ninguém consegue ler nem gravar dados.
   Faça a troca numa cópia, sem alterar o arquivo versionado (o UUID dele é o de produção).
4. Rode `supabase/seed.sql` manualmente no SQL Editor (a integração com o GitHub não o aplica).
5. Copie `.env.example` para `.env` (ignorado pelo git) e preencha `SUPABASE_URL` e `SUPABASE_ANON_KEY`. Em produção, use variáveis de ambiente.
   A chave `service_role` nunca é usada pelo app.
6. Crie o ambiente virtual e instale as dependências (`requirements.txt` é só produção; `requirements-dev.txt` inclui os testes):

```bash
python -m venv .venv
```

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
```

No Windows, use `.venv\Scripts\python.exe` no lugar de `.venv/bin/python`.

## Rodar em desenvolvimento

```bash
.venv/bin/python executar_web.py
```

Abre em `http://localhost:8000`.

- O servidor reinicia ao salvar um `.py` de `src/` e o login continua valendo: em desenvolvimento, as sessões ficam também em
  `.sessoes_dev.json`. O arquivo contém tokens: não compartilhe nem versione; apagá-lo encerra as sessões.
- `--sem-recarga` sobe sem a recarga automática (no preview, a configuração `locacao-web-estavel`).
- Com `LOCACAO_AMBIENTE=dev` (já definido por esse script) existe também `/componentes`, o catálogo visual dos componentes, sem login e com dados fictícios.

## Testes

```bash
.venv/bin/python -m pytest
```

Roda só `tests/`. A suíte de navegador (`pytest e2e`, Playwright) usa o Supabase de desenvolvimento; instalação e opções em [e2e/README.md](e2e/README.md).

## CSS (Tailwind)

Edite apenas `src/web/estilos/app.css`. O `static/css/app.css` é gerado a partir dele e **fica versionado** (a VPS não precisa do Tailwind).
Depois de mudar templates ou estilos, recompile (`--watch` recompila a cada vez que um arquivo é salvo):

```bash
.venv/bin/python scripts/construir_css.py
```

É preciso o Tailwind CLI standalone (sem Node) em `tools/tailwindcss` (`tools/tailwindcss.exe` no Windows), baixado das
[releases do Tailwind](https://github.com/tailwindlabs/tailwindcss/releases). A pasta `tools/` não vai para o git.

## Banco de dados

- **Migrations:** `supabase/migrations/AAAAMMDDHHMMSS_descricao.sql`, formato exigido pela integração Supabase ↔ GitHub, que aplica cada push
  automaticamente. Uma migration nova usa um timestamp maior que o da última.
- **Roteiros de verificação:** `supabase/verificar_*.sql` terminam em `ROLLBACK`. Rode em desenvolvimento ou homologação.

### Atualizar uma instalação existente

1. Faça backup antes de alterar o projeto de produção.
2. Aplique somente as migrations pendentes, na ordem dos timestamps. Aplique primeiro no desenvolvimento e confira a regra de ordem entre migration e
   deploy em [Deploy na VPS](Arquivos/Deploy_VPS.md).
3. Se a integração com o GitHub já aplica as migrations, confira o histórico antes de executar algo manualmente e não reaplique as antigas. Pela CLI,
   revise o projeto conectado com `supabase link` e use `supabase db push`
   ([documentação do Supabase](https://supabase.com/docs/guides/deployment/database-migrations)).
4. Rode `supabase/seed.sql` para o catálogo, caso ainda não tenha sido aplicado.
5. Em homologação, execute os roteiros `supabase/verificar_*.sql` ligados ao que mudou.
6. Atualize as dependências e reinicie o aplicativo.

### Dados de demonstração

Rode no SQL Editor depois das migrations e do `seed.sql`. **Nunca em produção.** Os dois são idempotentes pela placa.

| Arquivo | Cenário | Placa de controle |
|---|---|---|
| `supabase/seed_demo.sql` | Uma moto, um cliente fictício, contrato, cobranças, pagamentos e documento vencido. | `DEM1A23` |
| `supabase/seed_exemplos.sql` | 6 motos (uma em cada status), 5 clientes, 3 contratos com vistorias, cobranças em várias situações, manutenções e documentos. | `EXA1A11` |

## Usuários e acessos

### Administradores

Quem está na tabela `administradores` tem o mesmo acesso do dono (`is_dono()` consulta essa tabela). Ela só é alterada pelo SQL Editor.
Crie o usuário em Authentication > Users (com "Auto Confirm User") e rode:

```sql
insert into administradores (user_id) select id from auth.users where email = 'fulano@exemplo.com';
```

Para remover o acesso:

```sql
delete from administradores where user_id = (select id from auth.users where email = 'fulano@exemplo.com');
```

Roteiro de teste: `supabase/verificar_administradores.sql` (só em dev). Nunca coloque senhas ou e-mails reais no repositório.

### Portal do locatário

O acesso de cada locatário é criado na ficha do cliente (aba "Portal"). Isso depende da Edge Function `criar-locatario`, publicada uma vez em cada
projeto Supabase (desenvolvimento e produção são projetos diferentes):

```bash
supabase login
```

```bash
supabase functions deploy criar-locatario --project-ref <ref-do-projeto>
```

Sem a função, "Criar acesso" mostra um erro. Confira no painel (Edge Functions > `criar-locatario`) que "Verify JWT" está ligado.
Logins, senhas e segurança: [Referência técnica](Arquivos/Referencia_Tecnica.md#portal-do-locatário).

### Usuários de serviço

Os robôs entram com um usuário próprio, criado em Authentication > Users (com "Auto Confirm User"), que não lê tabelas: só executa as RPCs dele.
Registre-o na tabela correspondente pelo SQL Editor:

| Integração | Tabela | Variáveis |
|---|---|---|
| WhatsApp | `servico_mensagens` | `SERVICO_MENSAGENS_EMAIL`, `SERVICO_MENSAGENS_SENHA` |
| Conector do claude.ai | `servico_conector` | `SERVICO_CONECTOR_EMAIL`, `SERVICO_CONECTOR_SENHA` |

```sql
insert into servico_mensagens (user_id) select id from auth.users where email = 'robo@exemplo.com';
```

Para o conector, troque a tabela por `servico_conector`. Para remover o acesso, apague a linha do usuário na mesma tabela.

## Configuração opcional

A lista comentada de variáveis do app está em `.env.example`; em produção elas ficam no Coolify.

### Sessão longa

`SESSAO_CHAVE` (chave Fernet) mantém o login depois de um deploy. Sem ela, reiniciar o app desconecta todos; trocá-la também. Gere com:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Contrato em PDF

Os dados do locador vêm das variáveis `LOCADOR_*`, fora do git. O que faltar sai como linha em branco para preencher à mão. O texto é um modelo
padrão: revise-o com um advogado antes de usar.

### Envio por WhatsApp

Usa a Evolution API e nasce desligado; o dono o liga em Configurações. Variáveis e tarefa agendada estão na seção 8.1 do
[Deploy na VPS](Arquivos/Deploy_VPS.md).

### Conector do claude.ai

| Variável | Uso |
|---|---|
| `CONECTOR_CHAVE` | Chave Fernet própria. Sem ela o conector fica desligado; trocá-la revoga todos os tokens. |
| `CONECTOR_URL_BASE` | Endereço público do app, ex.: `https://SEU-SUBDOMINIO.duckdns.org`. |
| `SERVICO_CONECTOR_EMAIL`, `SERVICO_CONECTOR_SENHA` | Usuário de serviço. Sem elas, só a ferramenta `ping` funciona. |
| `CONECTOR_PERMITE_LOOPBACK` | `1` somente em testes locais. |

Para conectar: Claude > Personalizar > Conectores > Adicionar conector personalizado, com a URL `https://SEU-SUBDOMINIO.duckdns.org/mcp`,
deixando a autenticação como detectada (registro automático).

## Publicação

O deploy usa o `Dockerfile` no Coolify da VPS e só sai pela CI, no push para a `main`, depois do `pytest` verde (job `deploy` de
`.github/workflows/ci.yml`). A reversão é o Rollback do Coolify. O passo a passo está em [Deploy na VPS](Arquivos/Deploy_VPS.md) e os requisitos de
segurança, na [Revisão de segurança](Arquivos/Revisao_Seguranca.md). Em resumo:

- **um único worker** (as sessões ficam na memória do processo), com `--proxy-headers` e `--forwarded-allow-ips` restrito ao proxy;
- `LOCACAO_AMBIENTE` diferente de `dev`;
- `SUPABASE_URL` e `SUPABASE_ANON_KEY` por variável de ambiente, nunca a chave `service_role`;
- migrations aplicadas, cadastro público do Supabase desativado, usuário do dono criado e buckets privados.
