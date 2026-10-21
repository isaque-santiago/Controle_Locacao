-- =====================================================================
-- 20261022140000_importacao_multas.sql
-- Migration 3 da importação dos dados reais (Arquivos/Importacao_Dados_Reais.md):
--   * multas_transito: multas por veículo, com responsável, repasse e vencimento;
--   * vw_multas_locatario: locatário na data da infração, por sobreposição com os contratos.
-- A carga NÃO gera cobranças a partir das multas (depende de decisão de negócio).
-- Compatível com a versão anterior do app: só tabela e view novas.
-- =====================================================================

create table if not exists multas_transito (
  id                uuid primary key default gen_random_uuid(),
  moto_id           uuid not null references motos(id),
  data_infracao     date not null,
  ait               text not null,
  descricao         text,
  valor             numeric(12,2) not null check (valor >= 0),
  valor_atual       numeric(12,2) check (valor_atual >= 0),    -- valor a pagar na última consulta
  vencimento        date,
  situacao          text not null default 'em_aberto' check (situacao in ('em_aberto','paga','cancelada')),
  responsabilidade  text not null default 'a_definir' check (responsabilidade in ('locatario','locadora','a_definir')),
  cliente_id        uuid references clientes(id),
  responsavel_nome  text,                                      -- ex-locatário sem cadastro (texto livre)
  repasse           text not null default 'nao' check (repasse in ('nao','parcial','sim')),
  valor_repassado   numeric(12,2) not null default 0 check (valor_repassado >= 0),
  observacoes       text,
  criado_em         timestamptz not null default now(),
  unique (moto_id, ait)
);
create index if not exists ix_multas_moto on multas_transito (moto_id, data_infracao desc);
create index if not exists ix_multas_vencimento on multas_transito (vencimento) where situacao = 'em_aberto';

-- Locatário vigente na data da infração (null = sem contrato nessa data / dono anterior).
create or replace view vw_multas_locatario with (security_invoker = true) as
select
  mu.id as multa_id,
  mu.moto_id,
  mu.data_infracao,
  ct.id as contrato_id,
  cl.id as cliente_id,
  cl.nome as locatario_na_data
from multas_transito mu
left join lateral (
  select c.*
    from contratos c
   where c.moto_id = mu.moto_id
     and c.data_inicio <= mu.data_infracao
     and (c.data_encerramento is null or c.data_encerramento >= mu.data_infracao)
     and c.status <> 'cancelado'
   order by c.data_inicio desc
   limit 1
) ct on true
left join clientes cl on cl.id = ct.cliente_id;

alter table multas_transito enable row level security;
drop policy if exists "dono_total" on multas_transito;
create policy "dono_total" on multas_transito for all to authenticated using (is_dono()) with check (is_dono());
grant select, insert, update, delete on multas_transito to authenticated;

notify pgrst, 'reload schema';
