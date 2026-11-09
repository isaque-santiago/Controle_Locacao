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
- **Um único usuário: o dono, até a fase 7** Só ele registra locações, pagamentos e manutenções. Não há perfis de mecânico ou financeiro na v1. (ver Fase 8 para o acesso do locatário)
- Alertas aparecem **dentro do sistema** (dashboard). Envio por WhatsApp/e-mail fica para a v2.
- A quilometragem é **informada manualmente** pelo dono (vistoria, manutenção ou atualização avulsa). Não há rastreador/GPS na v1.

### Fora do escopo da v1

Portal do cliente, integração com WhatsApp, gestão de multas de trânsito, emissão de contrato em PDF, integração com rastreadores, multi-filial, múltiplos usuários com permissões. Ver seção 12 (backlog).

---

## 2. Stack

| Camada | Escolha | Observação |
|---|---|---|
| Interface | **Python 3.11+, FastAPI + Jinja2 + HTMX + Tailwind** | Substituiu o Streamlit original na Fase 4 (seção 15) |
| Banco | **Supabase (PostgreSQL)** | Views para alertas, RPCs para operações atômicas |
| Autenticação | **Supabase Auth** (e-mail e senha) | Cadastro público **desativado**; só o dono existe |
| Arquivos | **Supabase Storage** (buckets privados) | Fotos de vistoria e comprovantes de documentos |
| Gráficos | SVG gerado no servidor | O Plotly saiu junto com o Streamlit |
| Testes | pytest | Regras de negócio em módulos puros, sem dependência de banco |
| Deploy | VPS com Coolify (Docker), HTTPS pelo Traefik e domínio DuckDNS | Segredos em variáveis de ambiente; CI no GitHub Actions (seção 10) |

Bibliotecas: consulte `requirements.txt` (produção) e `requirements-dev.txt` (testes). O plano original previa `streamlit`, `pandas` e `plotly`, removidos na Fase 4.

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
│   │   ├── encargos.py         # encargo fixo por atraso (R$ 15 + R$ 7/dia)
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
  multa_atraso_valor        numeric(12,2) not null default 15.00 check (multa_atraso_valor >= 0),    -- valor fixo cobrado já no dia do vencimento
  encargo_diario_valor      numeric(12,2) not null default 7.00  check (encargo_diario_valor >= 0),  -- valor fixo por dia após o vencimento
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
  data_fim_prevista    date,                        -- null = prazo indeterminado (regra da operação, ver seção 14.4)
  data_encerramento    date,
  periodicidade        text not null check (periodicidade in ('diario','semanal','quinzenal','mensal')),
  valor_periodo        numeric(12,2) not null check (valor_periodo > 0),
  caucao_valor         numeric(12,2) not null default 0 check (caucao_valor >= 0),
  caucao_devolvida     boolean not null default false,
  caucao_desconto_danos numeric(12,2) not null default 0 check (caucao_desconto_danos >= 0),  -- danos abatidos da caução no encerramento
  caucao_valor_devolvido numeric(12,2) check (caucao_valor_devolvido >= 0),                   -- caução − danos (mínimo 0), preenchido no encerramento
  descricao_danos      text,                                                                  -- descrição dos danos abatidos
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
  intervalo_km    int check (intervalo_km > 0),            -- máximo: vencida ao ultrapassar
  intervalo_minimo_km int check (intervalo_minimo_km > 0), -- mínimo: alerta a partir daqui (null = usa alerta_manutencao_km)
  intervalo_dias  int check (intervalo_dias > 0),
  ativo           boolean not null default true,
  check (intervalo_km is not null or intervalo_dias is not null),
  check (intervalo_minimo_km is null or (intervalo_km is not null and intervalo_minimo_km < intervalo_km))
);

-- Plano de cada moto: intervalo pode ser sobrescrito por moto
create table moto_plano_manutencao (
  id              uuid primary key default gen_random_uuid(),
  moto_id         uuid not null references motos(id) on delete cascade,
  item_id         uuid not null references itens_manutencao(id),
  intervalo_km    int check (intervalo_km > 0),      -- null = usa o do catálogo
  intervalo_minimo_km int check (intervalo_minimo_km > 0), -- null = usa o do catálogo
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
    coalesce(pl.intervalo_km,        i.intervalo_km)        as intervalo_km,
    coalesce(pl.intervalo_minimo_km, i.intervalo_minimo_km) as intervalo_minimo_km,
    coalesce(pl.intervalo_dias,      i.intervalo_dias)      as intervalo_dias
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
      or (c.proxima_km   is not null and c.intervalo_minimo_km is not null
          and c.km_atual >= coalesce(c.ultima_km, 0) + c.intervalo_minimo_km)
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
| `rpc_criar_contrato(payload jsonb)` | Valida que a moto está `disponivel` e o cliente `ativo`; insere o contrato com `km_inicial = motos.km_atual` (ou o informado, se maior); grava `historico_km` (origem `contrato`); muda a moto para `alugada`; gera, na `data_inicio`, a cobrança da caução (se houver) e a da primeira semana, e as demais cobranças da agenda (regra 5.2; contrato indeterminado usa janela móvel). |
| `rpc_encerrar_contrato(contrato_id, data, km_final, valor_danos, descricao_danos)` | Exige `km_final >= km_inicial`; fecha o contrato; cancela cobranças `aberta` com vencimento posterior à data de encerramento e sem pagamento; **calcula a devolução da caução** (`max(caução recebida − valor_danos, 0)`), grava `caucao_desconto_danos`, `caucao_valor_devolvido` e `caucao_devolvida`; se `valor_danos` exceder a caução, cria cobrança `tipo = 'dano'` com o excedente (regra 5.2); grava `historico_km`; muda a moto para `disponivel`. |
| `rpc_gerar_cobrancas_pendentes(horizonte_dias int default 30)` | Idempotente. Para contratos ativos, cria as cobranças que faltam até `hoje + horizonte`, sem duplicar (chave contrato + número). Chamada ao abrir o Dashboard. |
| `rpc_registrar_manutencao(payload jsonb)` | Insere a manutenção e seus itens; soma `custo_pecas`; se `concluida`, atualiza `ultima_km`/`ultima_data` em `moto_plano_manutencao` para cada item com `item_id`; grava `historico_km` (só se `km >= km_atual`); se `aberta`, moto vai para `manutencao`; ao concluir, volta para `alugada` (se houver contrato ativo) ou `disponivel`; se `cobrar_do_cliente`, cria cobrança tipo `dano` no contrato vigente. |
| `rpc_aplicar_plano_padrao(moto_id)` | Cria as linhas de `moto_plano_manutencao` para todos os itens ativos do catálogo, com **baseline**: `ultima_km = km_atual` e `ultima_data = hoje` (evita moto nova nascer com tudo "vencido"). O usuário pode ajustar para o histórico real. |

### 4.6 `supabase/seed.sql` (catálogo inicial sugerido)

Valores iniciais para o dono ajustar por modelo em Configurações (referência comum para motos de 125-160cc; conferir o manual de cada modelo):

| Item | Alerta a partir de (km mín.) | Intervalo km (máx.) | Intervalo dias |
|---|---|---|---|
| Troca de óleo do motor | — (usa `alerta_manutencao_km`) | 1.000 | 90 |
| Kit de tração (corrente, coroa, pinhão) | 3.000 | 5.000 | — |
| Patins de freio | 3.000 | 5.000 | — |
| Filtro de ar | — | 6.000 | 180 |
| Pneu dianteiro | — | 15.000 | — |
| Pneu traseiro | — | 10.000 | — |
| Vela de ignição | — | 8.000 | — |
| Fluido de freio | — | — | 365 |
| Revisão geral | — | 5.000 | 180 |

Óleo, kit de tração e patins de freio vêm da operação real (seção 14.5); os demais itens são referência genérica a conferir.

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
- A locação é, em regra, **semanal**, com pagamento **antecipado** (seção 14.2).
- **Na `data_inicio` o cliente paga a caução e a primeira semana**: a primeira cobrança de locação vence na própria `data_inicio`, junto com a cobrança da caução.
- **Contrato indeterminado é a regra** (seção 14.4): gera janela móvel (30 dias à frente) via `rpc_gerar_cobrancas_pendentes`, chamada ao abrir o Dashboard. A cobrança só deixa de ser gerada quando o contrato é encerrado.
- Contrato com prazo definido (exceção): gera todas as parcelas até `data_fim_prevista`.
- Caução é uma cobrança `tipo = 'caucao'` e não entra em receita.
- **Devolução da caução no encerramento:** `devolução = max(caução recebida − danos, 0)`. A base é a caução efetivamente recebida (soma dos pagamentos da cobrança de caução): caução não paga não se devolve. Se os danos excederem a caução, a devolução é R$ 0,00 e o excedente é cobrado do cliente em uma cobrança `tipo = 'dano'`.

### 5.3 Encargos por atraso (`domain/encargos.py`)

Regra da operação (seção 14.1), com os valores configuráveis em `configuracoes`: **R$ 15,00 fixos já no dia do vencimento** + **R$ 7,00 fixos por dia** a partir do dia seguinte. Sem carência. Incide **apenas sobre cobranças `tipo = 'locacao'`** e não depende do saldo. As parcelas de **promessa de compra** também são cobranças `tipo = 'locacao'` (decisão D3, 22/10/2026), portanto também pagam encargos; entrada, caução e saldo anterior (`outros`/`caucao`) não.

```
se cobranca.tipo != 'locacao' ou saldo == 0 ou hoje < vencimento: encargo = 0
senão:
  dias = max(hoje - vencimento, 0)
  encargo = multa_atraso_valor + encargo_diario_valor * dias
total = saldo + encargo
```

Exemplo: vencimento → R$ 15,00; 1 dia → R$ 22,00; 2 dias → R$ 29,00; 3 dias → R$ 36,00.

Os encargos são **calculados na tela** e gravados em `pagamentos.multa_juros` quando o pagamento é registrado (o dono pode editar o valor, por exemplo para dar desconto). Função pura, com testes em `Decimal` (valores fixos, sem percentual).

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
| **Contratos** | Novo contrato (assistente: cliente, moto, condições, prévia da agenda de cobranças; prazo indeterminado por padrão); encerrar (com registro de danos e cálculo da devolução da caução); ficha com cobranças, vistorias e manutenções do período. |
| **Cobranças** | Abas "Hoje", "Atrasadas", "Próximos 7 dias", "Pagas". Registrar pagamento (total ou parcial) com encargos calculados (R$ 15 + R$ 7/dia, só locação). Botão "Copiar mensagem de cobrança" (texto pronto para colar no WhatsApp; o envio automático fica para a v2). |
| **Manutenção** | Painel de alertas (vencidas/próximas); registrar manutenção (preventiva/corretiva, itens, custos, oficina); catálogo de itens e intervalos; histórico filtrável. |
| **Documentos** | Lista por vencimento; cadastro com anexo de comprovante; marcar como regularizado. |
| **Vistorias** | Checklist padrão, nível de combustível, km, avarias e upload de fotos; visualização por contrato. |
| **Relatórios** | Resultado por moto; custo de manutenção por moto/modelo/período; inadimplência; fluxo de caixa mensal. Exportar CSV/Excel. |
| **Configurações** | Multa fixa de atraso (R$ 15,00), valor diário de atraso (R$ 7,00), limites de alerta, backup manual (ZIP de CSVs). |

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
- `domain/agenda_cobrancas.py` e `domain/encargos.py` com testes (agenda semanal com caução + 1ª semana na `data_inicio`, contrato indeterminado, viradas de mês, 29/02, 31 de cada mês; encargo fixo R$ 15 + R$ 7/dia, só locação).
- Migration 0004 com `rpc_criar_contrato`, `rpc_encerrar_contrato`, `rpc_gerar_cobrancas_pendentes`.
- Páginas Contratos e Cobranças; registro de pagamento total/parcial com encargos; caução, com devolução já descontando os danos informados no encerramento.
- **Aceite:** não é possível criar dois contratos ativos para a mesma moto; agenda prévia bate com as cobranças geradas; pagamento parcial mantém a cobrança em aberto com saldo correto; encerrar cancela cobranças futuras; contrato sem `data_fim_prevista` gera a janela móvel; encerrar com dano de R$ 300 sobre caução de R$ 1.000 devolve R$ 700 e, com dano maior que a caução, devolve R$ 0 e gera cobrança do excedente.

### Fase 3: Manutenção
- `domain/manutencao_regras.py` com testes (inclui a faixa mínimo/máximo: kit de tração e patins alertam a partir de 3.000 km e vencem em 5.000 km).
- RPCs `rpc_registrar_manutencao` e `rpc_aplicar_plano_padrao` (aplicada automaticamente ao cadastrar moto).
- Página Manutenção (alertas, registro, catálogo) e aba de plano na ficha da moto.
- **Aceite:** registrar troca de óleo zera o contador só daquele item; alerta muda de `em_dia` para `proxima` e `vencida` conforme o km sobe; manutenção aberta coloca a moto em `manutencao`; custo total = mão de obra + peças.

### Fase 4: Documentos e vencimentos
- Página Documentos com upload no bucket `documentos`; views de alerta de documentos e CNH.
- Sugestão do documento do ano seguinte ao regularizar.
- **Aceite:** documento vencido aparece em vermelho no Dashboard; anexos só abrem via URL assinada temporária.

### Fase 5: Vistorias
- Checklist padrão configurável, upload de várias fotos (bucket `vistorias`), comparação entrega x devolução.
- Integração com Contratos: vistoria de entrega no assistente de novo contrato; devolução no encerramento, onde as avarias registradas servem de base para o valor de danos descontado da caução (seção 14.3).
- **Aceite:** uma vistoria de cada tipo por contrato; fotos exibidas por URL assinada; km da vistoria entra no histórico.

### Fase 6: Dashboard e relatórios
- Dashboard completo (seção 6) e página Relatórios com exportação CSV/Excel.
- `vw_resultado_moto` e custo por km rodado.
- **Aceite:** números do Dashboard conferem com consultas manuais no banco (teste com dados de exemplo); exportação abre corretamente no Excel com acentos.

### Fase 7: Portal do locatário e controle de troca de óleo

> ⚠️ Esta fase quebra a premissa da seção 1 ("Um único usuário: o dono"): passa a
> existir um segundo papel, o **locatário**, com login próprio.

- Reaproveita cadastro de Motos e Clientes (Fase 1) e o plano preventivo já
  existente (Fase 3 — troca de óleo já configurada em 1.000 km / 90 dias).
- **Controle de acesso: login completo por CPF + senha** (Supabase Auth). O app
  converte o CPF no e-mail interno `<cpf>@portal.example.com` (domínio reservado,
  nunca recebe e-mail); o dono continua com e-mail. Não existe senha padrão geral:
  cada cliente recebe uma **senha aleatória e individual**, mostrada uma vez ao
  dono. A troca de senha pelo locatário é **opcional**.
- **Criação do acesso automatizada por Edge Function** (`criar-locatario`, em
  `supabase/functions`): o dono clica em "Criar acesso" na aba "Portal" da ficha e a
  função cria/redefine/exclui o usuário no Auth e o vincula ao cliente
  (`clientes.auth_user_id`). A `service_role` existe só dentro do Supabase (segredo
  injetado na função); o app nunca a usa nem a guarda. A função só atende o dono
  (`rpc_meu_papel() = 'dono'` com o JWT de quem chamou). Publicada com
  `supabase functions deploy` em cada projeto (dev e produção).
  O papel vem de `rpc_meu_papel()` (`dono`, `locatario` ou nenhum) e define o menu:
  o locatário só vê a tela "Troca de óleo".
- **RLS:** as tabelas continuam só com a política do dono (`is_dono()`); o
  locatário não tem acesso direto a nenhuma tabela. Lê e grava apenas por RPCs
  `SECURITY DEFINER` que o identificam por `auth.uid()` e só alcançam o contrato
  **ativo** dele: `rpc_portal_locatario` (dados mínimos: placa, modelo, km,
  plano de óleo, últimas trocas) e `rpc_registrar_troca_oleo_locatario`.
- Tela simplificada (mobile-first) para o locatário: informa o hodômetro e anexa
  a **foto do painel** e a **foto da nota fiscal do óleo** (cláusula 4.13 do
  contrato: "será exigido foto do painel do veículo e nota fiscal da compra do
  óleo").
- `rpc_registrar_troca_oleo_locatario` (transação única):
  - valida hodômetro informado >= último registrado (km nunca regride, regra
    já usada na Fase 1) e recusa o mesmo hodômetro duas vezes no contrato;
  - exige as duas imagens já enviadas ao Storage, dentro da pasta do próprio
    cliente;
  - grava a manutenção preventiva concluída (custo zero) e a troca em
    `trocas_oleo`, vinculada ao cliente que reportou, reinicia o item de troca
    de óleo do plano da moto e lança o km em `historico_km`;
  - a situação/próxima troca seguem a lógica de `manutencao_regras`
    (`calcular_proxima_manutencao` / `calcular_situacao`), replicada no domínio
    `src/domain/troca_oleo.py` para a prévia na tela e os testes;
  - se o km reportado ultrapassar `última km + intervalo` do plano (trocar
    exatamente na km prevista não multa), gera a cobrança de **multa fixa**
    (tabela `cobrancas`, novo tipo `multa_manutencao` — é `cobrancas` que guarda
    o tipo, não `pagamentos`), **cobrada direto**, sem conferência prévia do dono.
- **Multa: valor fixo único**, definido em Configurações
  (`configuracoes.multa_troca_oleo_valor`), com padrão de **R$ 12,50**. O dono pode
  alterá-lo; enquanto for 0,00 o excesso é registrado, mas nada é cobrado.
  Como o hodômetro é informado pelo próprio locatário, a foto é a evidência.
- Bucket de fotos privado `trocas_oleo` (só imagem, até 10 MB), acesso do dono
  por URL assinada — mesmo padrão da Fase 5. O locatário só insere na própria
  pasta `<cliente_id>/`; não lista, não lê e não sobrescreve.
- Backup manual passa a incluir `trocas_oleo` (15 tabelas).

**Aceite:**
- `pytest` passa (`tests/test_troca_oleo.py`, `tests/test_portal_locatario.py`);
- `supabase/verificar_portal_locatario.sql` roda sem erro em homologação:
  locatário não lê nenhuma tabela, km regredido/arquivo de outro cliente/arquivo
  inexistente/troca duplicada são recusados, troca dentro do intervalo não gera
  multa e troca acima gera exatamente uma `multa_manutencao` com o valor fixo;
- função `criar-locatario` publicada no projeto de dev; teste manual em dev: dono
  clica em "Criar acesso"; o locatário loga com o CPF e a senha mostrada, vê só a
  tela "Troca de óleo" e envia troca com as duas fotos; "Gerar nova senha" e
  "Remover acesso" funcionam; o dono vê troca,
  fotos e multa na ficha do cliente.

**Fora do escopo desta fase:** tela para cancelar cobrança (hoje só direto no
banco), recuperação de senha (esqueci minha senha; o dono redefine) e exclusão de fotos órfãs
(enviadas ao Storage quando o registro da troca falha).

### Fase 8: Acabamento e publicação
- Backup manual (ZIP com CSV de todas as tabelas), tratamento de erros amigável, estados vazios, paginação das listas grandes, revisão de responsividade no celular.
- Deploy (previsto no Streamlit Community Cloud; feito depois na VPS com Coolify, ver `Deploy_VPS.md`); README com passo a passo.
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
- **Roteiro manual de ponta a ponta** (executar antes do deploy): cadastrar moto → aplicar plano → cadastrar cliente → criar contrato com caução e vistoria → registrar pagamentos (em dia, atrasado, parcial) → subir o km até disparar alerta → registrar manutenção → cadastrar IPVA a vencer → encerrar contrato com vistoria de devolução e desconto de dano na caução → conferir Dashboard e Relatórios.

---

## 10. Deploy e operação

- Repositório no GitHub; deploy na VPS (Coolify) a partir do `Dockerfile`, só pela CI com o `pytest` verde; segredos por variável de ambiente: `SUPABASE_URL`, `SUPABASE_ANON_KEY` (guia em `Deploy_VPS.md`).
- Migrations versionadas em `supabase/migrations/`, aplicadas em ordem (SQL Editor do Supabase ou Supabase CLI).
- Verificar os limites do plano gratuito do Supabase (por exemplo, pausa de projetos sem uso por certo período e ausência de backup automático de ponto no tempo) e decidir se o volume de dados/fotos justifica plano pago. Enquanto isso, usar o **backup manual** da Fase 7 com frequência semanal. **Decidido em 29/10/2026:** ficar só com o backup manual semanal (sem `pg_dump` agendado nem plano pago); rotina em `Deploy_VPS.md`, seção 8.

---

## 11. Critérios de sucesso da v1

- O dono consegue, em menos de 2 minutos, ver quais motos precisam de manutenção, quem está atrasado e quais documentos vencem.
- Nenhuma moto fica com dois contratos ativos e nenhum km regride.
- Todo real recebido e todo real gasto em manutenção está atribuído a uma moto.
- Resultado por moto (receita menos manutenção e documentos) disponível a qualquer momento.

---

## 12. Backlog (v2 em diante)

1. Envio automático de cobrança por WhatsApp (API oficial ou provedor) e resumo diário de vencimentos. *(desenho do envio automático pela Evolution API na seção 20; o resumo diário por WhatsApp foi descartado, o Dashboard cumpre o papel)*
2. Gestão de multas de trânsito com identificação do condutor e repasse ao locatário.
3. Contrato em PDF gerado a partir de modelo (revisar o modelo com advogado).
4. Portal do cliente para ver contrato, cobranças e enviar comprovante Pix. *(acesso básico do locatário — foto/hodômetro de troca de óleo — antecipado na Fase 7)*
5. Conciliação de Pix (extrato) e geração de cobrança Pix.
6. Integração com rastreador para km automático.
7. Perfis de usuário (mecânico, financeiro) e trilha de auditoria. *(papel de locatário antecipado na Fase 7; mecânico/financeiro seguem em backlog)*
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

## 14. Decisões de negócio confirmadas com o responsável

As cinco perguntas desta seção foram respondidas pelo responsável pela operação. As respostas abaixo **substituem os padrões assumidos antes** (multa de 2% + juros de 1% ao mês, etc.). As seções 4 (modelo de dados), 5 (regras de negócio), 6 (telas) e 7 (fases) foram alinhadas a estas decisões; se algum trecho divergir, vale esta seção.

### 14.1 Encargos de atraso — CONFIRMADO (substitui a regra de 2% + 1% a.m.)

- **R$ 15,00 fixos** já no **dia do vencimento** (dia 0, ainda sem atraso corrido);
- **+ R$ 7,00 fixos por dia** a partir do dia seguinte ao vencimento;
- **sem carência**: o encargo começa no próprio dia do vencimento;
- incide **somente sobre cobranças de locação** (`tipo = 'locacao'`).

Fórmula: `encargo = 15,00 + 7,00 × dias_após_vencimento`, com `dias_após_vencimento = max(hoje − vencimento, 0)`. Exemplo (valores acumulados): vencimento → R$ 15,00; +1 dia → R$ 22,00; +2 dias → R$ 29,00; +3 dias → R$ 36,00.

Impacto: reescrever `src/domain/encargos.py` e seus testes (valores fixos em `Decimal`, sem percentual nem carência); em `configuracoes`, trocar `multa_atraso_percentual` e `juros_mensal_percentual` por valores em reais (`multa_atraso_valor numeric(12,2)` = 15,00 e `encargo_diario_valor numeric(12,2)` = 7,00) e remover `carencia_dias`; ajustar a tela de Configurações. O modelo e as regras já estão refletidos nas seções 4.2 e 5.3.

**Observação:** a restrição "só sobre a locação" foi respondida com incerteza ("acho que"); confirmar com o responsável quando houver oportunidade. Até lá vale a regra acima, e é coerente com a caução não ser receita (seção 5.2).

### 14.2 Primeiro vencimento — CONFIRMADO

O pagamento é **antecipado**: no dia do início do contrato o cliente já paga a **caução + a primeira semana** de locação. A periodicidade da locação é semanal. A agenda continua começando em `data_inicio`.

### 14.3 Caução e danos — CONFIRMADO

A caução é cobrança separada (`tipo = 'caucao'`) e **o valor dos danos é descontado dela** na devolução (sobre a caução efetivamente recebida). Exemplo: caução R$ 1.000,00, dano R$ 300,00 → devolução de R$ 700,00.

Impacto (Fase 5): o encerramento deve registrar o(s) dano(s) e calcular o valor a devolver (`caução − danos`) numa única RPC transacional (`rpc_encerrar_contrato`); regra pura em `src/domain` com testes.

Se o dano for **maior que a caução**, a caução é inteiramente consumida (devolução = R$ 0,00) e o **excedente é cobrado do cliente** em uma cobrança `tipo = 'dano'`. Exemplo: caução R$ 1.000,00, dano R$ 1.300,00 → devolução R$ 0,00 e cobrança de R$ 300,00.

### 14.4 Duração do contrato — CONFIRMADO

O contrato é **por prazo indeterminado**: segue aberto enquanto o cliente estiver com a moto e pagando, até o encerramento. `data_fim_prevista = null` passa a ser o caso normal, e as cobranças devem ser geradas pela janela móvel da seção 5.2 (não por uma data final).

Impacto: conferir se o fluxo de criação de contrato e a prévia da agenda funcionam sem `data_fim_prevista` (a data final não pode ser obrigatória).

### 14.5 Manutenção — CONFIRMADO

| Item | Alerta a partir de (mín.) | Limite / vencido em (máx.) |
| --- | --- | --- |
| Troca de óleo | 700 km (limite − `alerta_manutencao_km` padrão de 300) | 1.000 km |
| Kit de tração | 3.000 km | 5.000 km |
| Patins de freio | 3.000 km | 5.000 km |

Os intervalos foram dados sem distinção de modelo; portanto o plano padrão com sobrescrita por moto continua suficiente, sem "planos por modelo" por ora.

**Decisão de modelagem (delegada ao desenvolvimento):** a faixa de 3.000 a 5.000 km é tratada como **mínimo = início do alerta** e **máximo = km previsto/limite** (o item fica "vencido" ao ultrapassar o máximo desde a última troca). Para isso, `itens_manutencao` e `moto_plano_manutencao` ganham a coluna opcional `intervalo_minimo_km` (null = usa a antecedência global `alerta_manutencao_km`); `intervalo_km` continua sendo o máximo, e `proxima_km = ultima_km + intervalo_km`. A view `vw_alertas_manutencao` e `manutencao_regras.py` passam a considerar `intervalo_minimo_km` quando preenchido. A troca de óleo segue só com `intervalo_km = 1000`.

---

## 15. Migração da camada de interface (aprovada em 05/10/2026)

A interface em Streamlit será **substituída por inteiro** por **FastAPI + Jinja2 + HTMX + Tailwind**, em Python.
Motivo: limites de layout, navegação e responsividade do Streamlit. Detalhes, arquitetura-alvo, plano por fases,
decisões e riscos: [Analise_Migracao_Frontend.md](Analise_Migracao_Frontend.md). Protótipo aprovado do layout: pasta `prototipo/`.

- **Mantidos sem alteração de regra:** `src/domain`, `src/repositories`, `src/services` (salvo os ajustes de
  acoplamento listados na seção 4 do documento de migração), `supabase/` (migrations, RPCs, seeds) e a RLS.
- **Substituídos:** `src/ui`, `pages/`, `app.py`, `src/auth.py` e `src/db.py` (sessão passa a ser cookie `httpOnly` no
  servidor), `.streamlit/` e as dependências do Streamlit.
- O Portal do Locatário (Fase 7) fica **no mesmo app**, com login por CPF e papel separado.
- As regras de trabalho do `CLAUDE.md` continuam valendo (fase por fase, `pytest`, README, commit por fase).
- Hospedagem decidida: **VPS com acesso público e HTTPS** (os locatários usam o portal pelo celular). Provedor: KingHost (VPS pequena); domínio gratuito (DuckDNS, confirmado); contratação da VPS (a partir de R$ 32,90/mês) adiada para antes do primeiro deploy; deploy automático por GitHub Actions; administração: Alisson (seção 10.1 do documento de migração).

---

## 16. Importação dos dados reais (desenho aprovado em 21/10/2026; migrations 1 a 5 e carga parcial aplicadas no dev em 22 e 23/10/2026; produção pendente)

Os dados reais da operação estão na planilha "PAGAMENTO MOTOS" (Google Sheets). O desenho completo, a lista de conflitos
e a ordem de execução estão em [Importacao_Dados_Reais.md](Importacao_Dados_Reais.md). Resumo do que muda no modelo:

- **Promessa de compra** passa a existir: `contratos` ganha `tipo_contrato` (`locacao` ou `promessa_compra`), `numero_parcelas`,
  `valor_total`, `valor_entrada`, `parcelas_pagas_inicial`, `dia_cobranca` e `primeira_cobranca`. A agenda (seção 5.2) passa a ancorar
  no dia da semana ou do mês, respeitar o número de parcelas e começar após as parcelas já pagas.
- **Veículos:** `motos` ganha `tipo` (`moto` ou `carro`), `proprietario_documento`, `link_documento`, `possui_rastreador` e dados de seguro.
- **Pagamentos:** `conta_id`, `data_estimada` e a forma `abatimento` (desconto sem dinheiro). Nova tabela `contas`.
- **Tabelas novas:** `fornecedores`, `despesas`, `movimentos_socio` (retiradas e aportes), `dividas`, `pagamentos_divida`,
  `multas_transito` e `importacoes_lote`; views `vw_saldo_dividas` e a de locatário na data da multa. `vw_resultado_moto` passa a somar as despesas.
- **Início do controle de cobrança:** 12/10/2026. O que veio antes entra como cobrança única de "saldo anterior".
- **Decisões:** promessa como coluna de `contratos`; pagamento sem data fica em 12/10/2026 com `data_estimada`; `km_inicial` = 0 com
  observação; ex-locatários sem CPF só como texto em `multas_transito`; escopo inicial só banco e carga em dev (telas depois).
- **Capital em veículos sem operação (Etios, Celta; aprovado em 22/10/2026):** `motos.placa_provisoria`; `despesas` com categoria `aquisicao`,
  `pago_por` e `a_confirmar`; dívida `emprestimo`; `dividas_vencimentos`; aporte ligado ao veículo e a view `vw_capital_veiculo`.
- **Contrato com várias motos e compra a prazo (03/11/2026; banco, regras e testes; as telas vieram em 04/11/2026, ver a seção 18):** `contrato_motos` (moto principal em
  `contratos.moto_id`, receita toda na principal) e dívida `compra_parcelada` com entrada, calendário de parcelas e pagamento por parcela.
  Ver `Arquivos/Importacao_Dados_Reais.md` (migrations 6 e 7).
- **D3 (decidida em 22/10/2026):** os encargos de atraso (seção 5.3) também valem para as parcelas de promessa de compra. Como elas são cobranças `tipo = 'locacao'`, não houve mudança de código.
- **CPF e telefone** não existem na planilha: a carga de `clientes` e `contratos` espera a planilha ser completada.
- **Ensaio** sempre no banco de dev; produção só depois de backup e autorização do dono. A carga é um SQL colado no SQL Editor
  (sem `service_role`), idempotente e numa transação única.

---

## 17. Dashboard financeiro (Etapa 1 em 04/11/2026; Etapa 2 em 04/11/2026)

A aba "Dashboard" da planilha "PAGAMENTO MOTOS" vira a seção **Financeiro** do `/` do app, por etapas e só para o dono.

- **Etapa 1 (feita, PR 142):** migration `20261104120000_resumo_financeiro.sql` (`rpc_resumo_financeiro`, só leitura), regras em
  `src/domain/financeiro.py`, serviço e repositório `financeiro`, e a seção no `dashboard.html` com seletor de mês (`?mes=aaaa-mm`; futuro ou
  inválido vale o mês atual). Mostra receita, despesas, resultado, caixa, investimento em veículos, parcelas de dívida, retiradas e aportes,
  receita mensal estimada, a receber, encargos, em atraso (até 14 dias), inadimplentes (15 dias ou mais), dívidas, a tabela dos últimos 6 meses
  e o ranking dos 8 maiores devedores.
- **Etapa 2 (feita):** migration `20261104130000_detalhe_financeiro.sql` (`rpc_detalhe_financeiro`: entradas por conta, despesas por categoria,
  despesas a repassar e receita da semana), resultado por veículo (`vw_resultado_moto`, desde o início, com o locatário do contrato ativo), alertas
  com semáforo (crítico, atenção, ok, info), gráfico de colunas (receita x despesas) em SVG, **modo compacto** e **ocultar dados pessoais**
  (`?compacto=1`, `?ocultar=1`; a troca por pontos é feita no servidor e os gráficos somem nesse modo).
- **Definições:** resultado = receita - despesas operacionais (sem `aquisicao`); caixa = receita - despesas - investimento - parcelas de dívida
  - retiradas + aportes. A receita só conta dinheiro recebido (principal + multa/juros), sem caução nem a forma `abatimento`; as parcelas de
  dívida entram só pelos pagamentos de dívida, nunca em despesas (na planilha o risco de contar em dobro existia). As despesas por categoria
  são do mês escolhido (a planilha mostrava todo o período).
- **Corte de inadimplência (04/11/2026):** deixou de ser constante: `configuracoes.dias_inadimplencia` (migration `20261104140000_corte_inadimplencia.sql`, padrão 15, de 1 a 100000), campo em Configurações; sem a coluna no banco o Dashboard usa 15.
- **Limitações conhecidas:** `vw_resultado_moto`
  e o relatório por moto ainda somam a forma `abatimento` como receita (o total do mês no Dashboard não); os modos compacto e ocultar valem só pela URL
  (não há preferência salva por usuário).

---

## 18. Telas de dívidas (04/11/2026)

O contrato com várias motos já tinha tela (etapa Moto do novo contrato, lista e ficha do contrato). Faltavam as **dívidas**, agora no menu
(grupo "Gestão e sistema", folha "Mais" no celular), só para o dono:

- `/dividas`: indicadores (total em aberto, motos fiado, parcelas atrasadas, próximo vencimento) e a tabela de dívidas com saldo (o confirmado
  pelo responsável vale sobre o calculado), próxima parcela e situação; atrasadas primeiro, quitadas por último.
- `/dividas/{id}`: resumo, aviso quando o saldo confirmado difere do calculado, parcelas com situação (paga, atrasada, a vencer, sem data) e os pagamentos.
- `/dividas/parcelas/{id}/pagar`: paga uma parcela (valor de 0,01 até o saldo; pagamento parcial deixa o resto em aberto; conta opcional) pela
  RPC `rpc_pagar_parcela_divida`.
- `/dividas/nova`: compra parcelada (entrada, parcelas, primeira parcela, parcelas já pagas, conta e moto opcionais). O total é calculado
  (entrada + parcelas) e o botão **Conferir** mostra total, saldo e calendário antes de **Cadastrar** (sem JavaScript), pela RPC `rpc_criar_compra_parcelada`.
- Não há migration nova. Regras em `src/domain/dividas_lista.py` e `src/domain/formulario_divida.py`.
- **Complemento (04/11/2026):** `/dividas/nova-divida` cadastra moto fiado, financiamento, fornecedor, rastreador e empréstimo (saldo confirmado opcional, com a data de hoje) e `/dividas/{id}/pagar` registra pagamento direto de dívida sem parcelas (valor até o saldo; dívida com parcelas paga-se pela parcela). Ambos são inserção em uma tabela só, sem RPC.
- **Editar, confirmar saldo e apagar (05/11/2026):** `/dividas/{id}/editar` (na compra parcelada só credor, moto, descrição e observações), `/dividas/{id}/saldo` (confirmar com valor e data até hoje, ou remover a confirmação) e `/dividas/{id}/confirmar-exclusao` (página de confirmação, só leitura, com o que sai junto; o POST fica em `/dividas/{id}/apagar`, porque o guarda de segurança não aceita GET com `/apagar` no caminho; `on delete cascade` leva parcelas e pagamentos num comando só). Uma tabela cada, sem RPC. Observação: apagar não remove a linha correspondente de `importacoes_lote`; se a dívida veio de uma carga, refazer a carga não a recria, porque a carga é idempotente por lote (desfaça pelo SQL de desfazer a carga, que limpa os dois).
- **Tipo, parcela e pagamento (05/11/2026):** `/dividas/{id}/editar` passa a trocar o tipo entre os cinco (a compra parcelada não troca, nem se vira uma); `/dividas/parcelas/{id}/editar` muda o vencimento (vazio = sem data) e, só sem pagamento, o valor (a parcela é marcada como paga pela soma dos pagamentos, então com pagamento corrige-se o pagamento); `/dividas/pagamentos/{id}/editar` corrige data (com opção de aproximada), valor (de 0,01 até o que falta mais o próprio valor), conta e observações. Atualizações de uma tabela cada, sem RPC; os gatilhos `fn_valida_pagamento_parcela` e `fn_atualiza_parcela_divida` recusam valor acima do saldo da parcela e reavaliam `paga_em` (conferido num Postgres de teste). Trocar o tipo não mexe em parcelas nem pagamentos, e só o tipo fornecedor soma ao saldo calculado os pedidos novos do fornecedor.
- **Fora desta entrega:** apagar ou criar parcelas e pagamentos individuais, e mover um pagamento de uma parcela para outra.


## 19. Vistoria por moto em contrato com várias motos (desenho aprovado em 05/11/2026)

**Problema.** `vistorias` aceitava uma entrega e uma devolução por contrato (`unique (contrato_id, tipo)`), feitas na moto principal. A moto vinculada de um
contrato com várias motos (ex.: Plano Conquista) ficava sem vistoria, sem fotos e sem km de devolução; o `km_atual` dela e os alertas de manutenção
ficavam defasados.

**Decisões (dono, 05/11/2026).**
1. A tela **exige** a vistoria de todas as motos quando o contrato tem vinculadas; o banco aceita sem (contratos antigos não quebram).
2. Contratos já carregados (ex.: Yangry) ganham a vistoria da vinculada de forma **retroativa pela tela**, que já lista os pendentes.
3. Duas entregas: **PR 1** banco, regras, serviços e testes (resolve o km de devolução e os alertas); **PR 2** telas (formulários de novo contrato e de
   encerramento com um bloco por moto, lista, comparação por moto e pendentes por moto).

**PR 1.**
- Migration: `unique (contrato_id, moto_id, tipo)`; gatilho que só aceita vistoria de moto do contrato (principal ou vinculada);
  `rpc_criar_contrato_com_vistoria` e `rpc_encerrar_contrato_com_vistoria` ganham `p_vistorias_vinculadas jsonb default '[]'` (chamadas antigas seguem valendo).
- Regras puras em `src/domain/vistorias_por_moto.py`: validar a lista (moto do contrato, sem repetição, km não menor que o atual), exigir todas as motos
  e calcular as motos sem vistoria de cada tipo.
- Repositório e serviços: as leituras de vistoria de um contrato continuam devolvendo as da moto principal por padrão (telas atuais não mudam) e aceitam
  `moto_id` ou `todas` para as demais; criar e encerrar passam a receber as vistorias das vinculadas.
- Fora do PR 1: telas. Até o PR 2, a lista de vistorias ainda mostra a placa da principal.

**PR 2 (telas, entregue em 05/11/2026).**
- Novo contrato (etapa Confirmar) e encerramento: um bloco de vistoria por moto vinculada, obrigatório (`exigir_todas`); campos `vinc<n>_...` e id da moto escondido para o formulário não descasar da lista; o texto digitado volta em caso de erro.
- Vistorias: placa da moto da própria vistoria na lista; comparação com um grupo por moto vinculada; "Registrar vistoria" lista cada par contrato-moto pendente (`contrato` ou `contrato:moto`), o que dá a entrega retroativa dos contratos já carregados.
- Ficha do contrato, aba Vistorias: um grupo por moto.
- Fotos: só na moto principal na criação do contrato; as das outras motos entram depois, por "Adicionar fotos" na vistoria.


## 20. Envio automático de mensagens por WhatsApp (desenho aprovado em 06/11/2026; nada implementado)

Tira do backlog (seção 12, item 1) o envio automático por WhatsApp pela **Evolution API**. Hoje o dono só copia um texto de cobrança e cola no
WhatsApp (`/cobrancas/{id}/mensagem`). A automação passa a ser o canal oficial dos avisos ao locatário: por isso ela não pode falhar em silêncio.

### 20.1 Decisões do dono (05 e 06/11/2026)

1. **Destinatário:** sempre o locatário. O dono acompanha tudo pelo sistema (Dashboard e alertas), não por WhatsApp.
2. **Número:** só `clientes.whatsapp` (nunca `telefone`). Sem número, a mensagem fica `ignorada`, com o motivo.
3. **Janela de envio:** 8h às 19h (America/Sao_Paulo), de segunda a sábado, sem feriados **nacionais** (calculados no código: fixos, Carnaval,
   Sexta-feira Santa, Páscoa e Corpus Christi). O que cair fora da janela vai para o próximo horário válido. Feriados estaduais e municipais: fora.
4. **Textos fixos no código** (um módulo só, para que ficar editável em Configurações seja fácil no futuro).
5. **Uma mensagem por cliente por dia:** tudo o que for devido ao mesmo cliente no mesmo dia vai agrupado em um único texto, fácil de ler (ver 20.4).
6. **Sem opt-out pelo cliente.** Os avisos são a automação da empresa; se o cliente pudesse desligá-los, o dono não saberia. Só o dono bloqueia o
   envio, no cadastro do cliente (`nao_enviar_whatsapp`, com motivo e data). Resposta do cliente ("PARAR" etc.) não faz nada sozinha.
7. **Sem resumo diário por WhatsApp ao dono.** O Dashboard cumpre esse papel (decisão adiada).
8. **Chip dedicado e instância nova** na Evolution (a existente é de outro projeto). Instância e chip: a definir pelo dono.
9. **Pix:** o texto de cobrança terá um espaço para a chave Pix estática do Cora, preenchido por configuração. Decisão de usar e de onde guardar: adiada.

### 20.2 Quando cada mensagem sai

| Tipo | Gatilho | Repetição |
|---|---|---|
| `lembrete_vespera` | Cobrança aberta que vence amanhã. Contrato `diario`: não envia. | Uma vez |
| `lembrete_vencimento` | Cobrança aberta que vence hoje (todas as periodicidades). | Uma vez |
| `atraso` | Cobrança atrasada, com o total **com encargos** (`domain/encargos.py`: multa + adicional por dia). | Dias 1, 3 e 7 de atraso; depois a cada 3 dias, até pagar, o contrato encerrar ou chegar ao máximo (padrão 10 mensagens, configurável) |
| `inadimplencia` | Cobrança que atinge o corte `dias_inadimplencia` (Configurações). Aviso formal. | Uma vez |
| `recibo_pagamento` | Pagamento registrado: valor pago e, se parcial, o saldo restante. | Uma vez por pagamento |
| `cnh_proxima` / `cnh_vencida` | `vw_alertas_cnh`; antecedência = `alerta_cnh_dias`. | Próxima: uma vez. Vencida: como o atraso (1, 3, 7 e a cada 3 dias) |
| `oleo_proxima` / `oleo_vencida` | `vw_alertas_manutencao` (troca de óleo); antecedência = `alerta_manutencao_dias` e `alerta_manutencao_km`. Leva o **link do portal** para registrar foto e hodômetro. | Como CNH |
| `documento_proximo` / `documento_vencido` | `vw_alertas_documentos`; antecedência = `alerta_documento_dias`. Para quando o dono marca o documento como regularizado. | Como CNH |
| `portal_acesso` / `portal_senha_alterada` | Criação do acesso ao portal (link) e troca de senha (aviso). Nunca leva a senha no texto. | Uma vez |

**Documentos da moto (decisão do dono, 06/11/2026).** O aviso é ao locatário e **o instrui a regularizar**, não a falar com o dono. A instrução muda
com o tipo: IPVA e licenciamento (pagar a guia), seguro (renovar), vistoria Detran (agendar e realizar), outro (usa a descrição). Como ainda não está
definido quem paga o custo, o texto traz as duas formas, de modo neutro ("se o custo for seu, regularize; se for do proprietário, combine com ele").
O texto pede o **comprovante**, que o locatário pode mandar pelo portal (quando existir, ver Etapa 6) ou pelo WhatsApp ao dono. Só o dono dá baixa no
sistema; enviar o comprovante não baixa o documento sozinho.

### 20.3 Arquitetura

- **Fila e histórico:** tabela `mensagens_whatsapp` (cliente, número, texto, `status` em `pendente|enviada|falhou|ignorada|cancelada`,
  tentativas, erro, `enviar_apos`, `reservada_ate`, `enviada_em`, `evolution_id`) e a tabela `mensagens_whatsapp_itens`, com os assuntos de cada
  mensagem agrupada (tipo, referência, data de referência). A chave única (tipo, referência, data) dos itens impede duplicar o mesmo aviso se o job
  rodar duas vezes. *(Etapa 1 entregue em 06/11/2026: migration `20261106120000_whatsapp_base.sql`; a reserva por 10 min evita que dois scripts
  peguem a mesma mensagem.)* `clientes` ganha `nao_enviar_whatsapp`, `motivo_bloqueio_whatsapp` e `bloqueio_whatsapp_em`.
- **Regras puras em `src/domain`** (com testes em `tests/`): quais mensagens são devidas hoje; textos e agrupamento; janela de horário e feriados;
  normalização do número (`55` + DDD + número); quando parar de repetir.
- **Cliente da Evolution** (`src/services/whatsapp.py`, `httpx`): `POST /message/sendText/{instância}` com o cabeçalho `apikey`. **Conferir** a versão
  da Evolution da instância nova (v1 e v2 diferem no corpo da requisição) no Swagger dela antes de implementar. Testes com transporte falso; nenhum
  teste chama a Evolution de verdade.
- **Agendamento:** script `python -m scripts.enviar_mensagens` (gera as mensagens devidas, enfileira e envia), rodado como **Tarefa Agendada do
  Coolify** a cada 15 a 30 minutos, em processo separado. Nada de laço dentro do processo web (1 worker, sessões em memória).
- **Acesso ao banco sem usuário logado:** sem `service_role` (regra do projeto). Um usuário de serviço do Supabase Auth, sem acesso às tabelas, só
  executa RPCs `SECURITY DEFINER` específicas (`rpc_mensagens_devidas`, `rpc_registrar_envio` etc.) que verificam o `auth.uid()` dele e devolvem só as
  colunas necessárias. Operações em mais de uma tabela continuam em RPC (transação única).
- **Segredos:** `EVOLUTION_URL`, `EVOLUTION_APIKEY`, `EVOLUTION_INSTANCIA` e a senha do usuário de serviço, como variáveis de ambiente do Coolify.
  Nunca no repositório.
- **Proteção do número:** intervalo aleatório de 20 a 60 s entre envios, textos com dados do cliente, só dentro da janela, verificação prévia de que o
  número tem WhatsApp, chip dedicado, **modo teste** (tudo vai só para o número do dono) e chave geral liga/desliga em Configurações.
- **Visibilidade para o dono (o sistema é o único canal de falha):** alerta no Dashboard de mensagens `falhou` ou `ignorada`, com o motivo (sem
  WhatsApp, número inválido, Evolution fora do ar) e aviso de instância desconectada; histórico no detalhe do cliente; reenviar e cancelar pendentes.

### 20.4 Texto das mensagens agrupadas

Fácil de ler para o locatário, mesmo com vários assuntos: saudação curta com o nome; um bloco por assunto, o mais urgente primeiro (cobranças,
depois documentos, depois manutenção e CNH); uma linha de ação em cada bloco; valores em `R$ 1.234,56` e datas em `dd/mm/aaaa`; teto de uns 5
assuntos por mensagem, com os mais urgentes em destaque e um pedido para falar com o dono quando passar disso.

### 20.5 Etapas (um PR por etapa; não avançar sem os critérios de aceite)

1. **Base:** migration (`mensagens_whatsapp`, campos de bloqueio, usuário de serviço e RPCs). *Aceite:* RPC recusa outro usuário; duplicata barrada pelo índice.
2. **Regras puras** *(entregue em 06/11/2026: `feriados`, `janela_envio`, `numero_whatsapp`, `avisos_whatsapp` e `textos_whatsapp` em `src/domain`)*: devidas hoje, textos, agrupamento, janela, feriados nacionais, normalização do número, parada da repetição. *Aceite:* pytest verde com
   os casos de borda (domingo, feriado, contrato diário, parcial, mês curto, dois assuntos no mesmo dia).
3. **Cliente da Evolution e script de envio** *(entregue em 06/11/2026: `rpc_whatsapp_dados`, `services/evolution.py`, `services/whatsapp.py` e `python -m src.enviar_mensagens_whatsapp`; guia em `Deploy_VPS.md`, seção 8.1)*. *Aceite:* testes com transporte falso (sucesso, falha, número sem WhatsApp, API fora do ar); script idempotente.
4. **Telas:** histórico no cliente, bloqueio pelo dono, alertas de falha no Dashboard, Configurações (chave geral, modo teste, máximo de repetições). *(entregue em 06/11/2026: migration `20261106140000_whatsapp_painel.sql`, página Mensagens, aba WhatsApp na ficha do cliente, seção em Configurações e alertas no Dashboard; o estado da instância e da última rodada é gravado a cada rodada. As tabelas de mensagens ficam fora do backup manual.)* *Aceite:* só o dono vê e altera.
5. **Implantação:** instância nova, tarefa agendada no Coolify, modo teste com o número do dono e liberação gradual. *Aceite:* uma semana em modo teste sem duplicata nem envio fora da janela.
6. **Portal:** o locatário envia o comprovante de documento da moto; gera um aviso no sistema para o dono conferir e dar baixa (reaproveita
   `privacidade_imagem.py`, validação de arquivo e Storage). Até lá, o texto cita só o WhatsApp.
7. **Depois:** webhook da Evolution só para exibir respostas e status de entrega no sistema (sem agir sozinho), Pix do Cora nos textos e textos editáveis.

### 20.6 Pendências

- Instância e chip da Evolution (decisão do dono); versão da Evolution a conferir.
- Uso e local da chave Pix do Cora nos textos.
- Quem paga cada documento da moto (o texto cobre as duas formas por enquanto).
- Texto final de cada mensagem: revisar com o dono antes da Etapa 3.
- Aviso de **senha do portal alterada**: resolvido em 09/11/2026 (migration `20261109120000_portal_eventos_senha.sql`): `portal_eventos` guarda a troca
  feita pelo locatário e `rpc_whatsapp_dados` a entrega ao envio. A redefinição feita pelo dono **não** gera aviso (decisão do dono: ele entrega a senha pessoalmente).
- Ao sair do modo teste, cancelar o histórico de teste (SQL no guia de deploy, seção 8.1, passo 6).
- Confirmar a versão da Evolution da instância nova (`EVOLUTION_VERSAO`) conferindo o corpo do envio no Swagger dela.
- Escolhas da Etapa 2 que o dono ainda deve confirmar (todas mudam em um lugar só):
  - o nome da empresa na saudação e **como falar com o dono** (nome e telefone), que aparecem em quase todo texto (`OpcoesTexto.empresa` e `contato`).
    O chip é dedicado e ninguém lê as respostas dele: sem um contato no texto, a resposta do locatário se perde;
  - o lembrete de **véspera** sai no último dia de envio antes do vencimento (vencimento de segunda é lembrado no sábado);
  - os avisos "próxima" (CNH, documento, óleo) repetem, se continuarem pendentes, só depois de 30 dias;
  - recibo e avisos do portal só saem para o que aconteceu nos últimos 2 dias (ao ligar o envio, o passado não vira mensagem);
  - passando de 5 assuntos num dia, os mais urgentes vão e o resto fica para o dia seguinte;
  - o aviso de atraso informa o total com encargos **do dia do envio**, e o texto diz que o valor aumenta a cada dia.

---

## 21. Redesenho do Dashboard, Fase 1 (09/11/2026)

Decisões e estudo em [Estudo_Dashboard.md](Estudo_Dashboard.md) (seção 4.9). A Fase 1 é "só verdade e ordem":

- **Abas** `/?aba=hoje|dinheiro|frota` (Hoje por padrão; cada uma com URL própria, sem JavaScript, mantendo `compacto` e `ocultar`; o seletor de mês só na aba Dinheiro).
- **Um cálculo por indicador:** o Dashboard lê só de `services/financeiro` (`painel_hoje`, `painel_dinheiro`, `painel_frota`, cada um com a versão `*_seguro` que só avisa
  "indisponível"). O cálculo antigo (`services/dashboard`) saiu; o caixa da aba Hoje é o mesmo número da aba Dinheiro (há teste), e o gasto com manutenção da aba Frota
  é a categoria Manutenção da aba Dinheiro.
- **Listas únicas:** *Cobrar agora* (`domain/cobrar_agora.analisar_cobranca`: por contrato, vencido + vence hoje + encargos, do maior atraso para o menor, com a cobrança
  mais antiga para o botão Pagar e o link do WhatsApp) une "Hoje" e "Quem está devendo"; *Atenção* une "Precisa de atenção" e "Alertas e pendências"
  (`atencao_financeira`: parcela de dívida atrasada, despesa a repassar, entrada sem conta; perigo antes de atenção).
- **Cabeçalho:** os dois botões grandes viram o menu **Opções** (modo compacto, ocultar dados pessoais).
- **Indicadores do topo (aba Hoje):** A cobrar, Em atraso, Frota e Caixa do mês, decididos em 05/11/2026.
- **Medido no preview (dados do dev):** a página inteira tinha 10,3 telas no desktop e 15,9 no celular, com 17 indicadores e 6 tabelas; a aba Hoje tem 4 indicadores e 1 tabela
  (1,9 tela no desktop de 1440 px; 5,9 no celular, com as abas e os quatro indicadores na primeira tela).
- **Fica para as próximas fases** (Estudo, 4.8): variação e sparkline nos cartões, barra de faixas de atraso (1-6, 7-14, 15-30, 31+ dias), barra segmentada da frota, bullet de receita
  contra previsto (Fase 2); próximos 7 dias, motos paradas, receita por moto, tempo parado (Fase 3). Abaixo de 1500 px a aba Hoje mostra *Atenção* abaixo de *Cobrar agora*
  (o layout em duas colunas já existia e só começa em 1500 px, porque a tabela tem seis colunas).

