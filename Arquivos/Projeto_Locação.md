# PLANO DO PROJETO: Sistema de Locação e Manutenção de Motos

> Documento pensado para ser colocado na raiz do repositório e seguido pelo Claude Code, fase por fase.
> Idioma da interface, dos nomes de tabelas/colunas e dos comentários: português (pt-BR). Fuso: America/Sao_Paulo. Moeda: BRL.

---

## 1. Visão geral

Sistema web para o dono de uma frota de motos de aluguel controlar, em um só lugar:

1. **Locação**: cadastro de clientes (locatários), contratos, cobranças recorrentes, pagamentos e inadimplência.
2. **Manutenção**: plano preventivo por km/tempo com alertas, registro de manutenções preventivas e corretivas, custos por moto.
3. **Documentação e vencimentos**: IPVA, licenciamento, seguro e CNH do locatário, com alertas.
4. **Vistoria**: checklist com fotos na entrega e na devolução da moto.
5. **Dashboard e relatórios**: ocupação da frota, receita, inadimplência, custo de manutenção e resultado por moto.

### Perfil de uso (definido)

- Frota **média** (20 a 100 motos).
- **Um único usuário: o dono.** Só ele registra locações, pagamentos e manutenções. Não há perfis de mecânico ou financeiro na v1.
- Alertas aparecem **dentro do sistema** (dashboard). Envio por WhatsApp/e-mail fica para a v2.
- A quilometragem é **informada manualmente** pelo dono (vistoria, manutenção ou atualização avulsa). Não há rastreador/GPS na v1.

### Fora do escopo da v1

Portal do cliente, integração com WhatsApp, gestão de multas de trânsito, emissão de contrato em PDF, integração com rastreadores, multi-filial, múltiplos usuários com permissões. Ver seção 12 (backlog).

---

## 2. Stack

| Camada | Escolha | Observação |
|---|---|---|
| Interface | **Python 3.11+ e Streamlit** (multipage) | Mesmo padrão do LeilãoCE |
| Banco | **Supabase (PostgreSQL)** | Views para alertas, RPCs para operações atômicas |
| Autenticação | **Supabase Auth** (e-mail e senha) | Cadastro público **desativado**; só o dono existe |
| Arquivos | **Supabase Storage** (buckets privados) | Fotos de vistoria e comprovantes de documentos |
| Gráficos | Plotly | Seguir as boas práticas de visualização do projeto |
| Testes | pytest | Regras de negócio em módulos puros, sem dependência de banco |
| Deploy | Streamlit Community Cloud via GitHub | Segredos em `st.secrets` |

Bibliotecas: `streamlit`, `supabase`, `pandas`, `plotly`, `python-dateutil`, `pydantic`, `openpyxl`, `pytest`.

---

## 3. Estrutura de pastas

```
locacao-motos/
├── app.py                      # entrada: login + Dashboard
├── pages/
│   ├── 1_Dashboard.py
│   ├── 2_Motos.py
│   ├── 3_Clientes.py
│   ├── 4_Contratos.py
│   ├── 5_Cobrancas.py
│   ├── 6_Manutencao.py
│   ├── 7_Documentos.py
│   ├── 8_Vistorias.py
│   ├── 9_Relatorios.py
│   └── 10_Configuracoes.py
├── src/
│   ├── config.py               # leitura de st.secrets / variáveis de ambiente
│   ├── db.py                   # fábrica do cliente Supabase (com sessão do usuário)
│   ├── auth.py                 # login, logout, guarda de página (require_login)
│   ├── domain/                 # REGRAS PURAS (sem streamlit, sem supabase)
│   │   ├── validadores.py      # CPF, placa (antiga e Mercosul), telefone
│   │   ├── agenda_cobrancas.py # geração das datas/valores das cobranças
│   │   ├── encargos.py         # multa e juros por atraso
│   │   └── manutencao_regras.py# próxima manutenção, situação do alerta
│   ├── repositories/           # 1 arquivo por tabela: CRUD simples
│   ├── services/               # orquestram repositórios + RPCs
│   │   ├── contratos.py
│   │   ├── cobrancas.py
│   │   ├── manutencao.py
│   │   ├── alertas.py
│   │   ├── vistorias.py
│   │   └── relatorios.py
│   └── ui/
│       ├── formatadores.py     # R$ 1.234,56 / dd/mm/aaaa / placa / CPF mascarado
│       └── componentes.py      # tabelas, cartões de KPI, formulários reutilizáveis
├── supabase/
│   ├── migrations/
│   │   ├── 0001_schema.sql
│   │   ├── 0002_views.sql
│   │   ├── 0003_rls_storage.sql
│   │   └── 0004_rpc.sql
│   └── seed.sql                # catálogo padrão de itens de manutenção
├── tests/
├── .streamlit/secrets.toml.example
├── .gitignore                  # inclui secrets.toml e .env
├── requirements.txt
├── CLAUDE.md                   # regras de trabalho para o Code (seção 13)
└── README.md
```

Regra de arquitetura: **páginas não falam com o banco diretamente**. Página chama `services`, que chamam `repositories`/RPCs. Regras de negócio ficam em `domain/` para serem testáveis.

---

## 4. Modelo de dados

### 4.1 Visão resumida

- `motos` 1—N `contratos` (uma moto só pode ter **um contrato ativo** por vez)
- `clientes` 1—N `contratos`
- `contratos` 1—N `cobrancas` 1—N `pagamentos`
- `contratos` 1—N `vistorias` (entrega e devolução) 1—N `vistoria_fotos`
- `motos` 1—N `manutencoes` 1—N `manutencao_itens`
- `itens_manutencao` (catálogo) N—N `motos` via `moto_plano_manutencao`
- `motos` 1—N `documentos_moto`
- `motos` 1—N `historico_km`
- `configuracoes` (linha única com parâmetros e limites de alerta)

### 4.2 `supabase/migrations/0001_schema.sql`

```sql
-- =====================================================================
-- 0001_schema.sql : tabelas, índices e triggers
-- =====================================================================

create or replace function hoje_br() returns date
language sql stable as $$
  select (now() at time zone 'America/Sao_Paulo')::date
$$;

create or replace function fn_set_atualizado_em() returns trigger
language plpgsql as $$
begin
  new.atualizado_em := now();
  return new;
end $$;

-- ---------- Configurações (linha única) ----------
create table configuracoes (
  id                        int primary key default 1 check (id = 1),
  multa_atraso_percentual   numeric(5,2) not null default 2.00,   -- multa única sobre o valor em atraso
  juros_mensal_percentual   numeric(5,2) not null default 1.00,   -- juros simples, pro rata por dia
  carencia_dias             int          not null default 0,      -- dias sem encargos após o vencimento
  alerta_manutencao_km      int          not null default 300,    -- avisar X km antes
  alerta_manutencao_dias    int          not null default 15,     -- avisar X dias antes
  alerta_documento_dias     int          not null default 30,
  alerta_cnh_dias           int          not null default 30,
  atualizado_em             timestamptz  not null default now()
);
insert into configuracoes (id) values (1);

-- ---------- Motos ----------
create table motos (
  id                       uuid primary key default gen_random_uuid(),
  placa                    text not null unique check (placa = upper(placa)),
  renavam                  text,
  chassi                   text,
  marca                    text not null,
  modelo                   text not null,
  ano_fabricacao           int,
  ano_modelo               int,
  cor                      text,
  km_atual                 int not null default 0 check (km_atual >= 0),
  status                   text not null default 'disponivel'
                           check (status in ('disponivel','alugada','manutencao','inativa')),
  valor_aquisicao          numeric(12,2),
  data_aquisicao           date,
  valor_locacao_sugerido   numeric(12,2),
  observacoes              text,
  criado_em                timestamptz not null default now(),
  atualizado_em            timestamptz not null default now()
);

-- ---------- Clientes (locatários) ----------
create table clientes (
  id              uuid primary key default gen_random_uuid(),
  nome            text not null,
  cpf             text not null unique,            -- somente dígitos
  telefone        text,
  whatsapp        text,
  email           text,
  endereco        text,
  cnh_numero      text,
  cnh_categoria   text,
  cnh_validade    date,
  status          text not null default 'ativo' check (status in ('ativo','bloqueado','inativo')),
  observacoes     text,
  criado_em       timestamptz not null default now(),
  atualizado_em   timestamptz not null default now()
);

-- ---------- Contratos ----------
create table contratos (
  id                   uuid primary key default gen_random_uuid(),
  moto_id              uuid not null references motos(id),
  cliente_id           uuid not null references clientes(id),
  data_inicio          date not null,
  data_fim_prevista    date,                        -- null = prazo indeterminado
  data_encerramento    date,
  periodicidade        text not null check (periodicidade in ('diario','semanal','quinzenal','mensal')),
  valor_periodo        numeric(12,2) not null check (valor_periodo > 0),
  caucao_valor         numeric(12,2) not null default 0 check (caucao_valor >= 0),
  caucao_devolvida     boolean not null default false,
  km_inicial           int not null check (km_inicial >= 0),
  km_final             int,
  status               text not null default 'ativo' check (status in ('ativo','encerrado','cancelado')),
  observacoes          text,
  criado_em            timestamptz not null default now(),
  atualizado_em        timestamptz not null default now(),
  check (data_fim_prevista is null or data_fim_prevista >= data_inicio),
  check (km_final is null or km_final >= km_inicial)
);
-- Uma moto só pode ter um contrato ativo por vez
create unique index uq_contrato_ativo_por_moto on contratos (moto_id) where status = 'ativo';
create index ix_contratos_cliente on contratos (cliente_id);

-- ---------- Cobranças e pagamentos ----------
create table cobrancas (
  id           uuid primary key default gen_random_uuid(),
  contrato_id  uuid not null references contratos(id) on delete cascade,
  tipo         text not null default 'locacao'
               check (tipo in ('locacao','caucao','dano','multa_transito','outros')),
  numero       int,                                  -- nº da parcela (tipo locacao)
  vencimento   date not null,
  valor        numeric(12,2) not null check (valor >= 0),
  status       text not null default 'aberta' check (status in ('aberta','paga','cancelada')),
  descricao    text,
  criado_em    timestamptz not null default now()
);
create index ix_cobrancas_contrato   on cobrancas (contrato_id);
create index ix_cobrancas_vencimento on cobrancas (vencimento) where status = 'aberta';

create table pagamentos (
  id              uuid primary key default gen_random_uuid(),
  cobranca_id     uuid not null references cobrancas(id) on delete cascade,
  data_pagamento  date not null,
  valor           numeric(12,2) not null check (valor > 0),      -- abate o principal
  multa_juros     numeric(12,2) not null default 0 check (multa_juros >= 0),
  forma           text not null default 'pix'
                  check (forma in ('pix','dinheiro','cartao','transferencia','outro')),
  observacoes     text,
  criado_em       timestamptz not null default now()
);
create index ix_pagamentos_cobranca on pagamentos (cobranca_id);

-- Marca a cobrança como paga quando a soma dos pagamentos cobre o valor
create or replace function fn_atualiza_status_cobranca() returns trigger
language plpgsql as $$
declare
  v_cobranca uuid;
  v_total    numeric;
  v_valor    numeric;
begin
  v_cobranca := coalesce(new.cobranca_id, old.cobranca_id);
  select coalesce(sum(valor), 0) into v_total from pagamentos where cobranca_id = v_cobranca;
  select valor into v_valor from cobrancas where id = v_cobranca;
  update cobrancas
     set status = case when v_total >= v_valor then 'paga' else 'aberta' end
   where id = v_cobranca and status <> 'cancelada';
  return null;
end $$;

create trigger trg_pagamentos_status
after insert or update or delete on pagamentos
for each row execute function fn_atualiza_status_cobranca();

-- ---------- Histórico de quilometragem ----------
create table historico_km (
  id        uuid primary key default gen_random_uuid(),
  moto_id   uuid not null references motos(id) on delete cascade,
  km        int  not null check (km >= 0),
  data      date not null default hoje_br(),
  origem    text not null default 'manual'
            check (origem in ('manual','contrato','vistoria','manutencao')),
  criado_em timestamptz not null default now()
);
create index ix_historico_km_moto on historico_km (moto_id, data desc);

-- Mantém motos.km_atual sempre igual ao maior km já registrado
create or replace function fn_sync_km_moto() returns trigger
language plpgsql as $$
begin
  update motos set km_atual = new.km where id = new.moto_id and new.km > km_atual;
  return new;
end $$;

create trigger trg_historico_km_sync
after insert on historico_km
for each row execute function fn_sync_km_moto();

-- ---------- Manutenção ----------
-- Catálogo de itens do plano preventivo (troca de óleo, pneus, relação...)
create table itens_manutencao (
  id              uuid primary key default gen_random_uuid(),
  nome            text not null unique,
  intervalo_km    int check (intervalo_km > 0),
  intervalo_dias  int check (intervalo_dias > 0),
  ativo           boolean not null default true,
  check (intervalo_km is not null or intervalo_dias is not null)
);

-- Plano de cada moto: intervalo pode ser sobrescrito por moto
create table moto_plano_manutencao (
  id              uuid primary key default gen_random_uuid(),
  moto_id         uuid not null references motos(id) on delete cascade,
  item_id         uuid not null references itens_manutencao(id),
  intervalo_km    int check (intervalo_km > 0),      -- null = usa o do catálogo
  intervalo_dias  int check (intervalo_dias > 0),    -- null = usa o do catálogo
  ultima_km       int,
  ultima_data     date,
  unique (moto_id, item_id)
);

create table manutencoes (
  id                     uuid primary key default gen_random_uuid(),
  moto_id                uuid not null references motos(id),
  contrato_id            uuid references contratos(id),   -- contrato vigente (opcional, p/ atribuir dano)
  tipo                   text not null check (tipo in ('preventiva','corretiva')),
  status                 text not null default 'concluida'
                         check (status in ('aberta','concluida','cancelada')),
  data_entrada           date not null,
  data_saida             date,
  km                     int not null check (km >= 0),
  oficina                text,
  descricao              text not null,
  custo_mao_obra         numeric(12,2) not null default 0 check (custo_mao_obra >= 0),
  custo_pecas            numeric(12,2) not null default 0 check (custo_pecas >= 0),  -- soma dos itens (feita pela RPC)
  custo_total            numeric(12,2) generated always as (custo_mao_obra + custo_pecas) stored,
  cobrar_do_cliente      boolean not null default false,
  observacoes            text,
  criado_em              timestamptz not null default now(),
  atualizado_em          timestamptz not null default now(),
  check (data_saida is null or data_saida >= data_entrada)
);
create index ix_manutencoes_moto on manutencoes (moto_id, data_entrada desc);

create table manutencao_itens (
  id              uuid primary key default gen_random_uuid(),
  manutencao_id   uuid not null references manutencoes(id) on delete cascade,
  item_id         uuid references itens_manutencao(id),   -- preenchido => zera o contador do plano
  descricao       text not null,
  quantidade      numeric(10,2) not null default 1 check (quantidade > 0),
  valor_unitario  numeric(12,2) not null default 0 check (valor_unitario >= 0)
);
create index ix_manut_itens_manut on manutencao_itens (manutencao_id);

-- ---------- Documentos da moto ----------
create table documentos_moto (
  id               uuid primary key default gen_random_uuid(),
  moto_id          uuid not null references motos(id) on delete cascade,
  tipo             text not null check (tipo in ('ipva','licenciamento','seguro','vistoria_detran','outro')),
  descricao        text,
  ano_referencia   int,
  vencimento       date not null,
  valor            numeric(12,2),
  regularizado     boolean not null default false,   -- pago / renovado
  data_regularizacao date,
  arquivo_path     text,                             -- caminho no Storage (comprovante)
  observacoes      text,
  criado_em        timestamptz not null default now()
);
create index ix_documentos_venc on documentos_moto (vencimento) where regularizado = false;

-- ---------- Vistorias ----------
create table vistorias (
  id                  uuid primary key default gen_random_uuid(),
  contrato_id         uuid not null references contratos(id) on delete cascade,
  moto_id             uuid not null references motos(id),
  tipo                text not null check (tipo in ('entrega','devolucao')),
  data                timestamptz not null default now(),
  km                  int not null check (km >= 0),
  nivel_combustivel   text check (nivel_combustivel in ('vazio','1/4','1/2','3/4','cheio')),
  checklist           jsonb not null default '{}'::jsonb,   -- {"farol":"ok","freio":"avaria",...}
  avarias             text,
  observacoes         text,
  unique (contrato_id, tipo)
);

create table vistoria_fotos (
  id            uuid primary key default gen_random_uuid(),
  vistoria_id   uuid not null references vistorias(id) on delete cascade,
  storage_path  text not null,
  legenda       text
);

-- ---------- Triggers de atualizado_em ----------
create trigger trg_motos_upd       before update on motos       for each row execute function fn_set_atualizado_em();
create trigger trg_clientes_upd    before update on clientes    for each row execute function fn_set_atualizado_em();
create trigger trg_contratos_upd   before update on contratos   for each row execute function fn_set_atualizado_em();
create trigger trg_manutencoes_upd before update on manutencoes for each row execute function fn_set_atualizado_em();
```

### 4.3 `supabase/migrations/0002_views.sql`

Todas as views usam `security_invoker = true` para respeitar o RLS.

```sql
-- =====================================================================
-- 0002_views.sql : cobranças com situação, alertas e resultado por moto
-- =====================================================================

-- Cobranças com saldo, situação efetiva e dias de atraso
create or replace view vw_cobrancas with (security_invoker = true) as
select
  c.id,
  c.contrato_id,
  ct.moto_id,
  ct.cliente_id,
  c.tipo,
  c.numero,
  c.vencimento,
  c.valor,
  coalesce(p.pago, 0)                          as valor_pago,
  greatest(c.valor - coalesce(p.pago, 0), 0)   as saldo,
  case
    when c.status = 'cancelada'          then 'cancelada'
    when c.status = 'paga'               then 'paga'
    when c.vencimento < hoje_br()        then 'atrasada'
    else 'aberta'
  end                                          as situacao,
  greatest(hoje_br() - c.vencimento, 0)        as dias_atraso
from cobrancas c
join contratos ct on ct.id = c.contrato_id
left join lateral (
  select sum(valor) as pago from pagamentos where cobranca_id = c.id
) p on true;

-- Alertas de manutenção preventiva por moto e item
create or replace view vw_alertas_manutencao with (security_invoker = true) as
with base as (
  select
    m.id   as moto_id,
    m.placa,
    m.modelo,
    m.km_atual,
    i.id   as item_id,
    i.nome as item,
    pl.ultima_km,
    pl.ultima_data,
    coalesce(pl.intervalo_km,   i.intervalo_km)   as intervalo_km,
    coalesce(pl.intervalo_dias, i.intervalo_dias) as intervalo_dias
  from moto_plano_manutencao pl
  join motos m            on m.id = pl.moto_id and m.status <> 'inativa'
  join itens_manutencao i on i.id = pl.item_id and i.ativo
),
calc as (
  select b.*,
    case when b.intervalo_km is not null
         then coalesce(b.ultima_km, 0) + b.intervalo_km end                as proxima_km,
    case when b.intervalo_dias is not null and b.ultima_data is not null
         then b.ultima_data + b.intervalo_dias end                          as proxima_data
  from base b
)
select
  c.*,
  (c.proxima_km - c.km_atual)     as km_restantes,
  (c.proxima_data - hoje_br())    as dias_restantes,
  case
    when (c.proxima_km   is not null and c.km_atual >= c.proxima_km)
      or (c.proxima_data is not null and hoje_br() >= c.proxima_data)
      then 'vencida'
    when (c.proxima_km   is not null and c.proxima_km - c.km_atual   <= cfg.alerta_manutencao_km)
      or (c.proxima_data is not null and c.proxima_data - hoje_br() <= cfg.alerta_manutencao_dias)
      then 'proxima'
    else 'em_dia'
  end as situacao
from calc c
cross join configuracoes cfg;

-- Alertas de documentos da moto (IPVA, licenciamento, seguro...)
create or replace view vw_alertas_documentos with (security_invoker = true) as
select
  d.id,
  d.moto_id,
  m.placa,
  m.modelo,
  d.tipo,
  d.descricao,
  d.vencimento,
  (d.vencimento - hoje_br()) as dias_restantes,
  case
    when d.vencimento < hoje_br()                              then 'vencido'
    when d.vencimento - hoje_br() <= cfg.alerta_documento_dias then 'a_vencer'
    else 'ok'
  end as situacao
from documentos_moto d
join motos m on m.id = d.moto_id
cross join configuracoes cfg
where d.regularizado = false;

-- Alertas de CNH de clientes com contrato ativo
create or replace view vw_alertas_cnh with (security_invoker = true) as
select
  cl.id as cliente_id,
  cl.nome,
  cl.cnh_validade,
  (cl.cnh_validade - hoje_br()) as dias_restantes,
  case
    when cl.cnh_validade < hoje_br()                        then 'vencida'
    when cl.cnh_validade - hoje_br() <= cfg.alerta_cnh_dias then 'a_vencer'
    else 'ok'
  end as situacao
from clientes cl
cross join configuracoes cfg
where cl.cnh_validade is not null
  and exists (select 1 from contratos ct where ct.cliente_id = cl.id and ct.status = 'ativo');

-- Resultado financeiro acumulado por moto
create or replace view vw_resultado_moto with (security_invoker = true) as
select
  m.id as moto_id,
  m.placa,
  m.modelo,
  m.valor_aquisicao,
  coalesce(rec.total, 0)  as receita_recebida,
  coalesce(man.total, 0)  as custo_manutencao,
  coalesce(doc.total, 0)  as custo_documentos,
  coalesce(rec.total, 0) - coalesce(man.total, 0) - coalesce(doc.total, 0) as resultado
from motos m
left join lateral (
  select sum(p.valor + p.multa_juros) as total
  from pagamentos p
  join cobrancas c  on c.id  = p.cobranca_id and c.tipo <> 'caucao'
  join contratos ct on ct.id = c.contrato_id
  where ct.moto_id = m.id
) rec on true
left join lateral (
  select sum(custo_total) as total
  from manutencoes where moto_id = m.id and status = 'concluida'
) man on true
left join lateral (
  select sum(valor) as total
  from documentos_moto where moto_id = m.id and regularizado
) doc on true;
```

### 4.4 `supabase/migrations/0003_rls_storage.sql`

```sql
-- =====================================================================
-- 0003_rls_storage.sql : RLS em todas as tabelas + buckets privados
-- Sistema de usuário único: qualquer usuário autenticado é o dono.
-- (Desative o cadastro público em Authentication > Providers > Email)
-- =====================================================================
do $$
declare t text;
begin
  foreach t in array array[
    'configuracoes','motos','clientes','contratos','cobrancas','pagamentos',
    'historico_km','itens_manutencao','moto_plano_manutencao','manutencoes',
    'manutencao_itens','documentos_moto','vistorias','vistoria_fotos'
  ] loop
    execute format('alter table %I enable row level security', t);
    execute format(
      'create policy "dono_total" on %I for all to authenticated using (true) with check (true)', t);
  end loop;
end $$;

insert into storage.buckets (id, name, public)
values ('vistorias', 'vistorias', false), ('documentos', 'documentos', false)
on conflict (id) do nothing;

create policy "dono_storage_vistorias" on storage.objects
  for all to authenticated
  using (bucket_id in ('vistorias','documentos'))
  with check (bucket_id in ('vistorias','documentos'));
```

### 4.5 `supabase/migrations/0004_rpc.sql` (o Code escreve; especificação)

Operações que mexem em várias tabelas devem ser **funções PL/pgSQL** (transação única), pois o cliente Python do Supabase não tem transações. Cada função com `security invoker` e retorno em `jsonb`.

| Função | O que faz (tudo atômico) |
|---|---|
| `rpc_criar_contrato(payload jsonb)` | Valida que a moto está `disponivel` e o cliente `ativo`; insere o contrato com `km_inicial = motos.km_atual` (ou o informado, se maior); grava `historico_km` (origem `contrato`); muda a moto para `alugada`; gera a cobrança da caução (se houver) e as cobranças da agenda inicial (regra 6.2). |
| `rpc_encerrar_contrato(contrato_id, data, km_final, caucao_devolvida)` | Exige `km_final >= km_inicial`; fecha o contrato; cancela cobranças `aberta` com vencimento posterior à data de encerramento e sem pagamento; grava `historico_km`; muda a moto para `disponivel`. |
| `rpc_gerar_cobrancas_pendentes(horizonte_dias int default 30)` | Idempotente. Para contratos ativos, cria as cobranças que faltam até `hoje + horizonte`, sem duplicar (chave contrato + número). Chamada ao abrir o Dashboard. |
| `rpc_registrar_manutencao(payload jsonb)` | Insere a manutenção e seus itens; soma `custo_pecas`; se `concluida`, atualiza `ultima_km`/`ultima_data` em `moto_plano_manutencao` para cada item com `item_id`; grava `historico_km` (só se `km >= km_atual`); se `aberta`, moto vai para `manutencao`; ao concluir, volta para `alugada` (se houver contrato ativo) ou `disponivel`; se `cobrar_do_cliente`, cria cobrança tipo `dano` no contrato vigente. |
| `rpc_aplicar_plano_padrao(moto_id)` | Cria as linhas de `moto_plano_manutencao` para todos os itens ativos do catálogo, com **baseline**: `ultima_km = km_atual` e `ultima_data = hoje` (evita moto nova nascer com tudo "vencido"). O usuário pode ajustar para o histórico real. |

### 4.6 `supabase/seed.sql` (catálogo inicial sugerido)

Valores iniciais para o dono ajustar por modelo em Configurações (referência comum para motos de 125-160cc; conferir o manual de cada modelo):

| Item | Intervalo km | Intervalo dias |
|---|---|---|
| Troca de óleo do motor | 1.000 | 90 |
| Filtro de ar | 6.000 | 180 |
| Kit relação (corrente, coroa, pinhão) | 15.000 | — |
| Pastilhas / lonas de freio | 8.000 | — |
| Pneu dianteiro | 15.000 | — |
| Pneu traseiro | 10.000 | — |
| Vela de ignição | 8.000 | — |
| Fluido de freio | — | 365 |
| Revisão geral | 5.000 | 180 |

---

## 5. Regras de negócio

### 5.1 Motos e contratos

1. Moto só pode ser locada se `status = 'disponivel'`. Garantido por índice único parcial **e** validação na RPC.
2. Cliente `bloqueado` ou `inativo` não pode receber novo contrato. Cliente com cobrança atrasada há mais de N dias exibe aviso ao criar contrato (não bloqueia; decisão do dono).
3. Quilometragem nunca diminui: `km_atual` é sempre o maior valor registrado. Ao informar km menor que o atual, a tela pede confirmação e **não** atualiza `km_atual` (serve para lançar manutenção antiga).
4. Encerrar contrato exige `km_final >= km_inicial`.
5. Placa é normalizada (maiúscula, sem hífen) e validada nos formatos antigo (ABC1234) e Mercosul (ABC1D23). CPF é validado por dígito verificador e salvo só com dígitos.

### 5.2 Agenda de cobranças

- Periodicidade soma ao vencimento anterior: diário +1 dia, semanal +7 dias, quinzenal +15 dias, mensal +1 mês (`relativedelta`, preservando o dia; em meses curtos usa o último dia do mês).
- **Primeira cobrança vence na `data_inicio`** (pagamento antecipado do período). Deixar como parâmetro do contrato se o dono preferir pagamento postecipado.
- Contrato com prazo definido: gera todas as parcelas até `data_fim_prevista`.
- Contrato indeterminado: gera janela móvel (30 dias à frente) via `rpc_gerar_cobrancas_pendentes`, chamada ao abrir o Dashboard.
- Caução é uma cobrança `tipo = 'caucao'`, não entra em receita e é marcada como devolvida no encerramento.

### 5.3 Encargos por atraso (`domain/encargos.py`)

Padrão (configurável em `configuracoes`): **multa de 2% única** + **juros simples de 1% ao mês, proporcional aos dias** (pro rata), após a carência.

```
dias = max(hoje - vencimento - carencia, 0)
multa = saldo * multa% se dias > 0 senão 0
juros = saldo * (juros_mensal% / 30) * dias
total = saldo + multa + juros
```

Os encargos são **calculados na tela** e gravados em `pagamentos.multa_juros` quando o pagamento é registrado (o dono pode editar o valor, por exemplo para dar desconto). Função pura, com testes de arredondamento (2 casas, `Decimal`).

### 5.4 Manutenção preventiva (`domain/manutencao_regras.py`)

- Próxima manutenção do item = o que vencer **primeiro** entre `ultima_km + intervalo_km` e `ultima_data + intervalo_dias`.
- Situação: `vencida` (passou), `proxima` (dentro do limite de alerta), `em_dia`.
- Registrar manutenção com itens do plano zera o contador daquele item.
- Manutenção corretiva não mexe no plano, salvo se o dono marcar um item do plano naquela manutenção.
- Moto com contrato ativo e manutenção `vencida` gera destaque vermelho no Dashboard.

### 5.5 Documentos e vistorias

- Documento com `regularizado = false` entra nos alertas: `a_vencer` dentro de `alerta_documento_dias`, `vencido` depois.
- Ao marcar como regularizado, o sistema sugere criar o do próximo ano (ex.: IPVA 2027) com vencimento em branco para preencher.
- Vistoria de entrega é criada no início do contrato; a de devolução, no encerramento. Uma de cada tipo por contrato. Comparação lado a lado (entrega x devolução) na ficha do contrato.

---

## 6. Telas

| Página | Conteúdo principal |
|---|---|
| **Dashboard** | KPIs: motos por status e % de ocupação; recebido x previsto no mês; total em atraso e maiores devedores; manutenções vencidas/próximas; documentos a vencer; CNHs a vencer; custo de manutenção do mês. Lista "Hoje": cobranças que vencem hoje e atrasadas. |
| **Motos** | Lista com filtros (status, modelo). **Ficha da moto** com abas: Resumo, Plano de manutenção, Histórico de manutenções, Documentos, Contratos, Financeiro (resultado e custo por km). Atualização rápida de km. |
| **Clientes** | Lista e cadastro; CPF mascarado na listagem; histórico de contratos e pagamentos; alerta de CNH. |
| **Contratos** | Novo contrato (assistente: cliente, moto, condições, prévia da agenda de cobranças); encerrar; ficha com cobranças, vistorias e manutenções do período. |
| **Cobranças** | Abas "Hoje", "Atrasadas", "Próximos 7 dias", "Pagas". Registrar pagamento (total ou parcial) com encargos calculados. Botão "Copiar mensagem de cobrança" (texto pronto para colar no WhatsApp; o envio automático fica para a v2). |
| **Manutenção** | Painel de alertas (vencidas/próximas); registrar manutenção (preventiva/corretiva, itens, custos, oficina); catálogo de itens e intervalos; histórico filtrável. |
| **Documentos** | Lista por vencimento; cadastro com anexo de comprovante; marcar como regularizado. |
| **Vistorias** | Checklist padrão, nível de combustível, km, avarias e upload de fotos; visualização por contrato. |
| **Relatórios** | Resultado por moto; custo de manutenção por moto/modelo/período; inadimplência; fluxo de caixa mensal. Exportar CSV/Excel. |
| **Configurações** | Multa, juros, carência, limites de alerta, backup manual (ZIP de CSVs). |

Padrão visual: layout `wide`, tema escuro/claro do Streamlit, cores de status consistentes em todo o app (verde = ok, amarelo = próxima/a vencer, vermelho = vencida/atrasada, cinza = inativa).

---

## 7. Fases de implementação

Cada fase termina com **app funcionando, testes verdes e commit**. O Code não deve começar a próxima antes de cumprir os critérios da atual.

### Fase 0: Fundação
- Criar o repositório, estrutura de pastas, `requirements.txt`, `.gitignore`, `.streamlit/secrets.toml.example`, `README.md` e `CLAUDE.md` (seção 13).
- Criar projeto no Supabase, aplicar migrations 0001 a 0003 e o `seed.sql`. Desativar cadastro público e criar manualmente o usuário do dono.
- `src/config.py`, `src/db.py`, `src/auth.py` (login com e-mail/senha, sessão em `st.session_state`, `require_login()` no topo de cada página, o cliente Supabase usa o token do usuário para o RLS valer).
- `src/ui/formatadores.py`.
- **Aceite:** sem login nada é exibido; com login aparece a home; segredos fora do Git.

### Fase 1: Cadastros de motos e clientes
- `domain/validadores.py` com testes (CPF, placa antiga/Mercosul, telefone).
- Páginas Motos e Clientes: listar, filtrar, criar, editar, inativar.
- `historico_km` e atualização rápida de km.
- **Aceite:** placa e CPF duplicados/inválidos são recusados com mensagem clara; km nunca diminui.

### Fase 2: Contratos e cobranças
- `domain/agenda_cobrancas.py` e `domain/encargos.py` com testes (viradas de mês, 29/02, 31 de cada mês, arredondamento).
- Migration 0004 com `rpc_criar_contrato`, `rpc_encerrar_contrato`, `rpc_gerar_cobrancas_pendentes`.
- Páginas Contratos e Cobranças; registro de pagamento total/parcial com encargos; caução.
- **Aceite:** não é possível criar dois contratos ativos para a mesma moto; agenda prévia bate com as cobranças geradas; pagamento parcial mantém a cobrança em aberto com saldo correto; encerrar cancela cobranças futuras.

### Fase 3: Manutenção
- `domain/manutencao_regras.py` com testes.
- RPCs `rpc_registrar_manutencao` e `rpc_aplicar_plano_padrao` (aplicada automaticamente ao cadastrar moto).
- Página Manutenção (alertas, registro, catálogo) e aba de plano na ficha da moto.
- **Aceite:** registrar troca de óleo zera o contador só daquele item; alerta muda de `em_dia` para `proxima` e `vencida` conforme o km sobe; manutenção aberta coloca a moto em `manutencao`; custo total = mão de obra + peças.

### Fase 4: Documentos e vencimentos
- Página Documentos com upload no bucket `documentos`; views de alerta de documentos e CNH.
- Sugestão do documento do ano seguinte ao regularizar.
- **Aceite:** documento vencido aparece em vermelho no Dashboard; anexos só abrem via URL assinada temporária.

### Fase 5: Vistorias
- Checklist padrão configurável, upload de várias fotos (bucket `vistorias`), comparação entrega x devolução.
- Integração com Contratos: vistoria de entrega no assistente de novo contrato; devolução no encerramento.
- **Aceite:** uma vistoria de cada tipo por contrato; fotos exibidas por URL assinada; km da vistoria entra no histórico.

### Fase 6: Dashboard e relatórios
- Dashboard completo (seção 6) e página Relatórios com exportação CSV/Excel.
- `vw_resultado_moto` e custo por km rodado.
- **Aceite:** números do Dashboard conferem com consultas manuais no banco (teste com dados de exemplo); exportação abre corretamente no Excel com acentos.

### Fase 7: Acabamento e publicação
- Backup manual (ZIP com CSV de todas as tabelas), tratamento de erros amigável, estados vazios, paginação das listas grandes, revisão de responsividade no celular.
- Deploy no Streamlit Community Cloud com segredos em `st.secrets`; README com passo a passo.
- Script de dados de exemplo (`seed_demo.sql`) para demonstração.
- **Aceite:** app publicado, acessível apenas com login; roteiro de teste manual completo (seção 9) executado.

---

## 8. Segurança e LGPD

- Cadastro público do Supabase **desativado**; um único usuário.
- RLS ativo em todas as tabelas; views com `security_invoker`.
- Buckets `vistorias` e `documentos` **privados**; acesso por URL assinada de curta duração.
- Chave `service_role` **nunca** no app publicado nem no repositório. O app usa só `anon key` + sessão do usuário.
- CPF, CNH e endereço são dados pessoais: mascarar CPF nas listagens, não registrar esses campos em logs, exportar apenas quando o dono pedir.
- `.env` e `secrets.toml` no `.gitignore`; manter `secrets.toml.example` sem valores reais.
- Sessão expira após inatividade; botão "Sair" sempre visível.

---

## 9. Testes

- **Unitários (pytest)** para tudo em `src/domain/`: validadores, agenda de cobranças, encargos e regras de manutenção. Meta: cobertura alta nessa camada, pois é onde estão os erros que custam dinheiro.
- **Banco:** roteiro SQL de verificação para as RPCs e triggers (criar contrato duplicado deve falhar; pagamento parcial e total; manutenção zera plano; encerramento cancela futuras).
- **Roteiro manual de ponta a ponta** (executar antes do deploy): cadastrar moto → aplicar plano → cadastrar cliente → criar contrato com caução e vistoria → registrar pagamentos (em dia, atrasado, parcial) → subir o km até disparar alerta → registrar manutenção → cadastrar IPVA a vencer → encerrar contrato com vistoria de devolução → conferir Dashboard e Relatórios.

---

## 10. Deploy e operação

- Repositório no GitHub; Streamlit Community Cloud apontando para `app.py`; segredos: `SUPABASE_URL`, `SUPABASE_ANON_KEY`.
- Migrations versionadas em `supabase/migrations/`, aplicadas em ordem (SQL Editor do Supabase ou Supabase CLI).
- Verificar os limites do plano gratuito do Supabase (por exemplo, pausa de projetos sem uso por certo período e ausência de backup automático de ponto no tempo) e decidir se o volume de dados/fotos justifica plano pago. Enquanto isso, usar o **backup manual** da Fase 7 com frequência semanal.

---

## 11. Critérios de sucesso da v1

- O dono consegue, em menos de 2 minutos, ver quais motos precisam de manutenção, quem está atrasado e quais documentos vencem.
- Nenhuma moto fica com dois contratos ativos e nenhum km regride.
- Todo real recebido e todo real gasto em manutenção está atribuído a uma moto.
- Resultado por moto (receita menos manutenção e documentos) disponível a qualquer momento.

---

## 12. Backlog (v2 em diante)

1. Envio automático de cobrança por WhatsApp (API oficial ou provedor) e resumo diário de vencimentos.
2. Gestão de multas de trânsito com identificação do condutor e repasse ao locatário.
3. Contrato em PDF gerado a partir de modelo (revisar o modelo com advogado).
4. Portal do cliente para ver contrato, cobranças e enviar comprovante Pix.
5. Conciliação de Pix (extrato) e geração de cobrança Pix.
6. Integração com rastreador para km automático.
7. Perfis de usuário (mecânico, financeiro) e trilha de auditoria.
8. Previsão de custo de manutenção e recomendação de venda da moto (custo acumulado x valor de mercado, cruzando com tabela FIPE).

---

## 13. Como conduzir o Claude Code

### `CLAUDE.md` (copiar para a raiz do repositório)

```markdown
# Regras de trabalho

- Interface, nomes de tabelas/colunas, mensagens e comentários em português (pt-BR).
- Siga o PLANO.md fase por fase. Não avance de fase sem cumprir os critérios de aceite.
- Ao alterar um arquivo, entregue o arquivo COMPLETO (não trechos soltos).
- Regras de negócio ficam em src/domain (funções puras) com testes em tests/.
- Páginas não acessam o banco direto: página -> service -> repository/RPC.
- Operações em mais de uma tabela devem ser RPC PL/pgSQL (transação única).
- Dinheiro sempre com Decimal / numeric(12,2); nunca float.
- Datas no fuso America/Sao_Paulo; formatos dd/mm/aaaa e R$ 1.234,56.
- Nunca commitar segredos. Nunca usar a service_role key no app.
- Ao terminar cada fase: rodar pytest, atualizar o README e fazer commit com mensagem descritiva.
- Se uma regra do PLANO.md for ambígua, pergunte antes de decidir.
```

### Prompt inicial sugerido

```
Leia o PLANO.md por inteiro. Comece pela Fase 0 (Fundação). Antes de escrever código,
liste em poucas linhas o que vai criar e me diga o que preciso fazer no Supabase
(projeto, usuário, chaves). Ao concluir a fase, mostre como validar cada critério de aceite.
```

---

## 14. Pontos para confirmar antes da Fase 2

Padrões assumidos neste plano; ajuste o que não bater com a sua operação:

1. **Encargos de atraso:** multa de 2% + juros simples de 1% ao mês (pro rata). Se você usa outra regra (por exemplo, multa diária fixa ou juros compostos por dia), é só trocar a função `encargos.py` e os parâmetros em `configuracoes`.
2. **Primeiro vencimento na data de início** (pagamento antecipado). Se cobra no fim do período, ajustar a agenda.
3. **Caução:** modelada como cobrança separada, devolvida no encerramento. Há desconto de danos sobre a caução? Se sim, incluir na Fase 5.
4. **Contrato indeterminado** é a regra na sua operação, ou quase sempre há prazo definido?
5. **Frota mista:** intervalos de manutenção por modelo (CG 160, Fan, Biz etc.) precisam de planos distintos? O plano já permite sobrescrever por moto; se for comum, vale criar "planos por modelo" na Fase 3.
