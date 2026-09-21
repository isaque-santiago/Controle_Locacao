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
