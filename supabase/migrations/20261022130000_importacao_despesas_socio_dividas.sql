-- =====================================================================
-- 20261022130000_importacao_despesas_socio_dividas.sql
-- Migration 2 da importação dos dados reais (Arquivos/Importacao_Dados_Reais.md):
--   * fornecedores e despesas (manutenção, seguro, combustível etc.), com repasse ao locatário;
--   * movimentos_socio: retiradas e aportes;
--   * dividas (motos compradas fiado, financiamento, fornecedor, rastreador) e pagamentos_divida;
--   * vw_saldo_dividas: saldo calculado ao lado do confirmado (expõe divergências);
--   * vw_resultado_moto ganha custo_despesas e resultado_com_despesas (colunas novas no fim;
--     as colunas existentes e "resultado" não mudam, para não divergir de src/domain/relatorios.py).
-- Compatível com a versão anterior do app: só tabelas e colunas novas.
-- =====================================================================

create table if not exists fornecedores (
  id         uuid primary key default gen_random_uuid(),
  nome       text not null unique,
  criado_em  timestamptz not null default now()
);

-- ---------- Despesas ----------
create table if not exists despesas (
  id                  uuid primary key default gen_random_uuid(),
  data                date not null,
  data_estimada       boolean not null default false,
  moto_id             uuid references motos(id),
  descricao_veiculo   text,                          -- quando não há placa (ex.: "Biz Yangry")
  categoria           text not null
                      check (categoria in ('manutencao','documentacao','seguro_rastreador','multas','combustivel','outros')),
  valor               numeric(12,2) not null check (valor > 0),
  fornecedor_id       uuid references fornecedores(id),
  conta_id            uuid references contas(id),    -- conta que pagou
  repassar_locatario  boolean not null default false,
  repassado           boolean not null default false,
  contrato_id         uuid references contratos(id),
  observacoes         text,
  criado_em           timestamptz not null default now(),
  check (not repassado or repassar_locatario)
);
create index if not exists ix_despesas_moto on despesas (moto_id, data desc);
create index if not exists ix_despesas_fornecedor on despesas (fornecedor_id);

-- ---------- Retiradas e aportes do sócio ----------
create table if not exists movimentos_socio (
  id             uuid primary key default gen_random_uuid(),
  tipo           text not null check (tipo in ('retirada','aporte')),
  data           date not null,
  data_estimada  boolean not null default false,
  valor          numeric(12,2) not null check (valor > 0),
  conta_id       uuid references contas(id),
  origem_destino text,                               -- retirada: tipo/destino; aporte: origem do dinheiro de fora
  excecao        boolean not null default false,     -- fora do padrão (ex.: dívida pessoal paga com dinheiro da empresa)
  observacoes    text,
  criado_em      timestamptz not null default now()
);
create index if not exists ix_movimentos_socio_data on movimentos_socio (data desc);

-- ---------- Dívidas ----------
create table if not exists dividas (
  id                uuid primary key default gen_random_uuid(),
  tipo              text not null check (tipo in ('moto_fiado','financiamento','fornecedor','rastreador')),
  credor            text not null,
  fornecedor_id     uuid references fornecedores(id),
  moto_id           uuid references motos(id),
  descricao         text,
  valor_original    numeric(12,2) not null check (valor_original >= 0),
  numero_parcelas   int check (numero_parcelas > 0),
  valor_parcela     numeric(12,2) check (valor_parcela > 0),
  dia_vencimento    int check (dia_vencimento between 1 and 31),
  saldo_confirmado  numeric(12,2) check (saldo_confirmado >= 0),   -- informado pelo responsável
  confirmado_em     date,
  observacoes       text,
  criado_em         timestamptz not null default now()
);
create index if not exists ix_dividas_moto on dividas (moto_id);

create table if not exists pagamentos_divida (
  id             uuid primary key default gen_random_uuid(),
  divida_id      uuid not null references dividas(id) on delete cascade,
  data           date not null,
  data_estimada  boolean not null default false,
  valor          numeric(12,2) not null check (valor > 0),
  conta_id       uuid references contas(id),
  observacoes    text,
  criado_em      timestamptz not null default now()
);
create index if not exists ix_pagamentos_divida_divida on pagamentos_divida (divida_id, data);

-- Saldo calculado = original + pedidos novos (despesas do fornecedor, só dívida de fornecedor) - pagamentos.
-- diferenca = confirmado - calculado (nulo se não houver saldo confirmado).
create or replace view vw_saldo_dividas with (security_invoker = true) as
select
  d.id as divida_id,
  d.tipo,
  d.credor,
  d.moto_id,
  d.valor_original,
  coalesce(ped.total, 0)  as pedidos_novos,
  coalesce(pag.total, 0)  as total_pago,
  d.valor_original + coalesce(ped.total, 0) - coalesce(pag.total, 0) as saldo_calculado,
  d.saldo_confirmado,
  d.confirmado_em,
  d.saldo_confirmado - (d.valor_original + coalesce(ped.total, 0) - coalesce(pag.total, 0)) as diferenca
from dividas d
left join lateral (
  select sum(valor) as total from pagamentos_divida where divida_id = d.id
) pag on true
left join lateral (
  select sum(valor) as total from despesas
   where d.tipo = 'fornecedor' and d.fornecedor_id is not null and fornecedor_id = d.fornecedor_id
) ped on true;

-- Resultado por moto com despesas lançadas na nova tabela (colunas novas ao final da view).
create or replace view vw_resultado_moto with (security_invoker = true) as
select
  m.id as moto_id,
  m.placa,
  m.modelo,
  m.valor_aquisicao,
  coalesce(rec.total, 0)  as receita_recebida,
  coalesce(man.total, 0)  as custo_manutencao,
  coalesce(doc.total, 0)  as custo_documentos,
  coalesce(rec.total, 0) - coalesce(man.total, 0) - coalesce(doc.total, 0) as resultado,
  greatest(m.km_atual - coalesce((select min(km) from historico_km where moto_id = m.id), m.km_atual), 0) as km_rodados,
  round(coalesce(man.total, 0) / nullif(greatest(m.km_atual - coalesce((select min(km) from historico_km where moto_id = m.id), m.km_atual), 0), 0), 2) as custo_por_km,
  coalesce(des.total, 0)  as custo_despesas,
  coalesce(rec.total, 0) - coalesce(man.total, 0) - coalesce(doc.total, 0) - coalesce(des.total, 0) as resultado_com_despesas
from motos m
left join lateral (
  select
    coalesce((
      select sum(p.valor + p.multa_juros)
      from pagamentos p
      join cobrancas c  on c.id  = p.cobranca_id and c.tipo <> 'caucao'
      join contratos ct on ct.id = c.contrato_id
      where ct.moto_id = m.id
    ), 0)
    + coalesce((
      select sum(ct.caucao_desconto_danos)
      from contratos ct
      where ct.moto_id = m.id and ct.status = 'encerrado'
    ), 0) as total
) rec on true
left join lateral (
  select sum(custo_total) as total
  from manutencoes where moto_id = m.id and status = 'concluida'
) man on true
left join lateral (
  select sum(valor) as total
  from documentos_moto where moto_id = m.id and regularizado
) doc on true
left join lateral (
  select sum(valor) as total from despesas where moto_id = m.id
) des on true;

-- ---------- RLS e permissões ----------
do $$
declare t text;
begin
  foreach t in array array['fornecedores','despesas','movimentos_socio','dividas','pagamentos_divida'] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists "dono_total" on %I', t);
    execute format(
      'create policy "dono_total" on %I for all to authenticated using (is_dono()) with check (is_dono())', t);
    execute format('grant select, insert, update, delete on %I to authenticated', t);
  end loop;
end $$;

notify pgrst, 'reload schema';
