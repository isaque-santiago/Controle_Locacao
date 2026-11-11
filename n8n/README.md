# Executor do envio de WhatsApp no n8n

O **n8n só envia**. Quem decide *quem recebe o quê e quando* (regras, textos, fila, janela de horário, feriados, modo teste) continua
no app, em Python, com testes. O n8n reserva as mensagens que já estão prontas na fila, manda pela Evolution e registra o
resultado. Visão geral e decisões: seção 20 de `Arquivos/Projeto_Locação.md`; operação: `Arquivos/Deploy_VPS.md`, seção 8.2.

```
Coolify (a cada 20 min)                              n8n local (a cada 5 min)
WHATSAPP_EXECUTOR=n8n                                n8n/enviar-mensagens-whatsapp.json
┌───────────────────────────────┐                    ┌──────────────────────────────────────────────┐
│ lê, aplica as regras,         │   fila no Supabase │ entra (usuário de serviço) → estado da       │
│ enfileira as mensagens,       │ ─────────────────▶ │ instância → rpc_whatsapp_reservar (5) →      │
│ abre o "portão" da janela     │                    │ para cada uma: número tem WhatsApp? → envia  │
└───────────────────────────────┘                    │ → rpc_whatsapp_registrar_resultado → pausa   │
                                                     └──────────────────────────────────────────────┘
```

- **Portão da janela:** o preparo grava no banco até quando o envio está liberado (no máximo 25 minutos à frente e nunca depois das
  19h; fechado à noite, domingo e feriado). `rpc_whatsapp_reservar` não entrega nada com o portão fechado, com o envio desligado em
  Configurações ou em modo teste sem número de teste. O n8n **não tem regra de horário própria**: se nada sai, veja o portão.
- **Modo teste:** o banco devolve `numero_envio` e `texto_envio` já resolvidos (número de teste e «[TESTE] …»). O n8n envia o que recebe.
- **Quem pode o quê:** o n8n entra com o **usuário de serviço** (o mesmo do script), que só executa as RPCs `rpc_whatsapp_*`. A
  `service_role` do Supabase **não é usada** e não deve ser colocada no n8n.

## 1. Subir o n8n local

Exemplo de `docker-compose.yml` (**não foi testado**: o Docker não subia na máquina onde o fluxo foi feito; o fluxo foi testado no
n8n 2.47.4 instalado por `npm`, veja a seção 5). Fixe a versão da imagem e **não** a deixe aberta na internet:

```yaml
services:
  n8n-db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment: { POSTGRES_USER: n8n, POSTGRES_PASSWORD: ${N8N_DB_SENHA}, POSTGRES_DB: n8n }
    volumes: [ n8n_db:/var/lib/postgresql/data ]
  n8n:
    image: docker.n8n.io/n8nio/n8n:2.47.4        # ajuste para a versão mais recente e corrigida
    restart: unless-stopped
    depends_on: [ n8n-db ]
    ports: [ "127.0.0.1:5678:5678" ]               # só neste computador; nada de 0.0.0.0
    environment:
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: n8n-db
      DB_POSTGRESDB_USER: n8n
      DB_POSTGRESDB_PASSWORD: ${N8N_DB_SENHA}
      DB_POSTGRESDB_DATABASE: n8n
      N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY}    # GUARDE FORA DO REPOSITÓRIO e faça cópia: sem ela as credenciais se perdem
      GENERIC_TIMEZONE: America/Sao_Paulo          # o padrão do n8n é America/New_York
      TZ: America/Sao_Paulo
      N8N_DIAGNOSTICS_ENABLED: "false"
      N8N_VERSION_NOTIFICATIONS_ENABLED: "false"
      N8N_PERSONALIZATION_ENABLED: "false"
      N8N_BLOCK_ENV_ACCESS_IN_NODE: "true"
      EXECUTIONS_DATA_PRUNE: "true"
      EXECUTIONS_DATA_MAX_AGE: "24"                # horas: execuções com erro guardam números e textos (dados pessoais)
    volumes: [ n8n_dados:/home/node/.n8n ]
volumes: { n8n_db: {}, n8n_dados: {} }
```

Os valores `${...}` vêm de um `.env` **fora do repositório**. Só ligue o n8n a uma URL pública se for indispensável (ex.: webhook de
respostas, que não faz parte deste fluxo): em 2026 houve várias falhas críticas de execução remota de código no n8n, uma delas sem
login em webhooks expostos. Mantenha-o atualizado, com poucas contas e senhas fortes. Este fluxo só faz conexões **de saída**
(Supabase e Evolution), então não precisa de porta aberta.

## 2. Importar o fluxo e criar as credenciais

1. No n8n: *Workflows > Import from file* e escolha `n8n/enviar-mensagens-whatsapp.json` (vem **inativo**).
2. Crie 3 credenciais (os valores são segredos: não vão para o repositório):

| Nome sugerido | Tipo | Conteúdo |
|---|---|---|
| Supabase — chave anônima (apikey) | Header Auth | Name `apikey`, Value = a anon key do projeto |
| Evolution — apikey | Header Auth | Name `apikey`, Value = a apikey da instância |
| Supabase — usuário de serviço (login) | Custom Auth | `{"headers": {"apikey": "<anon key>"}, "body": {"email": "<usuário de serviço>", "password": "<senha>"}}` |

3. Abra cada nó HTTP e escolha a credencial: **Entrar** usa a de login; **Estado da instância**, **Número tem WhatsApp?** e **Enviar texto**
   usam a da Evolution; os demais (**Reservar**, **Registrar …**) usam a chave anônima.
4. No nó **Configuração** preencha `supabase_url`, `evolution_url` e `evolution_instancia`; `evolution_versao` é 1 ou 2 (o corpo do
   envio muda). **Não mude** `lote`, as pausas nem o tempo limite sem refazer a conta (próxima seção).
5. Teste com *Execute workflow* (com o envio em **modo teste** e o seu número de teste em Configurações) e só então ative o fluxo.
6. No Coolify defina `WHATSAPP_EXECUTOR=n8n` no app (a tarefa passa a só preparar). Aplique a migration
   `20261111120000_whatsapp_executor_n8n.sql` junto com a publicação do app (ver `Arquivos/Deploy_VPS.md`, seção 8.2).

## 3. Por que 5 mensagens, 20 s e 540 s

A reserva de uma mensagem dura 10 minutos no banco (`rpc_whatsapp_reservar`). Se uma execução passasse disso, a seguinte poderia
pegar as mesmas mensagens e enviá-las de novo. O pior caso: 4 pausas de 60 s + 5 mensagens × 2 chamadas × 20 s = 440 s. O fluxo
tem tempo máximo de 540 s e cada chamada, 20 s. Os testes (`tests/test_fluxo_n8n.py`) conferem que o arquivo continua batendo com
`src/services/whatsapp.py`.

## 4. O que o fluxo faz com cada erro da Evolution

Igual ao cliente Python (`src/services/evolution.py`):

| Resposta | O que acontece |
|---|---|
| 408, 429, 5xx, sem resposta | a mensagem **volta para a fila** (com espera crescente, até 3 tentativas) e o fluxo **para** |
| 401, 403, 404 (chave ou instância inválida) | o fluxo **para sem registrar**; a reserva vence sozinha e o Dashboard avisa «Evolution recusou a chave ou a instância» |
| outros 4xx | falha só desta mensagem; registra e **segue** |
| número sem WhatsApp | mensagem marcada «não enviada» e segue |
| login ou reserva recusados | a **execução falha** (aparece em vermelho nas execuções do n8n) e nada é enviado |

A cada execução (com a reserva feita) o fluxo registra o batimento (`rpc_whatsapp_registrar_rodada`). Se o n8n parar, em 1h30 o
Dashboard mostra «Envio automático parado»; se só o preparo (Python) parar, «Preparação dos avisos parada».

## 5. Testar o fluxo

- **Estático (pytest):** `tests/test_fluxo_n8n.py`, roda junto da suíte.
- **Num n8n de verdade, contra um servidor falso** (`n8n/teste/`): instale o n8n uma vez fora do repositório (`npm init -y && npm i n8n`,
  ~3 GB) e rode `python n8n/teste/executar_cenarios.py --n8n-dir <pasta da instalação>`. São 16 verificações (sucesso, sem WhatsApp,
  429, chave recusada, instância fechada, modo teste, Evolution v1, pausa…). Rode de novo **sempre que editar o fluxo**.
- **Nunca testado** com uma Evolution real nem com o Supabase real: só o teste em modo teste com o seu número prova os endpoints.

## 6. Editar o fluxo com cuidado

Edite no n8n, exporte (*Download*) e substitua `n8n/enviar-mensagens-whatsapp.json` por um commit. Antes, confira que o arquivo
exportado **não** tem credenciais (o n8n exporta só nomes e ids) nem URLs reais; troque as URLs de volta para os modelos
(`https://SEU-PROJETO.supabase.co` e `https://evolution.SEU-DOMINIO.com.br`). Depois rode o pytest e os cenários da seção 5.
