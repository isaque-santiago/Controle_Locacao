-- =====================================================================
-- 20261022160000_importacao_capital_veiculos.sql
-- Migration 5 da importação dos dados reais (Arquivos/Importacao_Dados_Reais.md):
-- veículos ainda sem operação (Etios) ou sem placa conhecida (Celta) e o capital investido neles.
--   * motos.placa_provisoria: placa provisória (ex.: PROV-ETIOS) a ser corrigida depois;
--   * despesas: categoria "aquisicao" (compra e reforma até o veículo render), pago_por
--     (locadora, locatário ou terceiro) e a_confirmar (valor lançado de memória);
--   * dividas.tipo "emprestimo" e tabela dividas_vencimentos (parcelas futuras, com ou sem data);
--   * movimentos_socio.moto_id: aporte ligado a um veículo;
--   * vw_capital_veiculo: custo total, pago pelo locatário, a pagar, saiu do bolso e saldo por veículo;
--   * vw_resultado_moto: custo_despesas e resultado_com_despesas passam a ignorar a categoria
--     "aquisicao" (capital, acompanhado em vw_capital_veiculo) e o que não foi a locadora que pagou.
-- Compatível com a versão anterior do app: só colunas com padrão, tabela e view novas.
-- =====================================================================

alter table motos
  add column if not exists placa_provisoria boolean not null default false;

-- ---------- Despesas ----------
alter table despesas drop constraint if exists despesas_categoria_check;
alter table despesas add constraint despesas_categoria_check
  check (categoria in ('manutencao','documentacao','seguro_rastreador','multas','combustivel','outros','aquisicao'));

alter table despesas
  add column if not exists pago_por    text not null default 'locadora'
    check (pago_por in ('locadora','locatario','terceiro')),
  add column if not exists a_confirmar boolean not null default false;

-- ---------- Dívidas ----------
alter table dividas drop constraint if exists dividas_tipo_check;
alter table dividas add constraint dividas_tipo_check
  check (tipo in ('moto_fiado','financiamento','fornecedor','rastreador','emprestimo'));

-- Parcelas futuras de uma dívida (a data pode ainda não ser conhecida).
create table if not exists dividas_vencimentos (
  id           uuid primary key default gen_random_uuid(),
  divida_id    uuid not null references dividas(id) on delete cascade,
  vencimento   date,                                   -- nulo = data ainda não informada
  valor        numeric(12,2) not null check (valor > 0),
  paga_em      date,
  observacoes  text,
  criado_em    timestamptz not null default now()
);
create index if not exists ix_dividas_venc_divida on dividas_vencimentos (divida_id);
create index if not exists ix_dividas_venc_data on dividas_vencimentos (vencimento) where paga_em is null;

alter table dividas_vencimentos enable row level security;
drop policy if exists "dono_total" on dividas_vencimentos;
create policy "dono_total" on dividas_vencimentos for all to authenticated using (is_dono()) with check (is_dono());
grant select, insert, update, delete on dividas_vencimentos to authenticated;

-- ---------- Aportes ligados a um veículo ----------
alter table movimentos_socio
  add column if not exists moto_id uuid references motos(id);
create index if not exists ix_movimentos_socio_moto on movimentos_socio (moto_id) where moto_id is not null;

-- ---------- Resultado por moto: capital (aquisicao) e custos de terceiros ficam de fora ----------
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
  select sum(valor) as total
  from despesas
  where moto_id = m.id and categoria <> 'aquisicao' and pago_por = 'locadora'
) des on true;

-- ---------- Capital investido por veículo (resumo da aba "Capital de fora") ----------
-- Só entram veículos com despesas de "aquisicao". a_pagar = saldo confirmado (ou, sem ele, o calculado)
-- das dívidas de empréstimo/fornecedor ligadas ao veículo. saiu_do_bolso = custo - pago pelo locatário - a pagar.
create or replace view vw_capital_veiculo with (security_invoker = true) as
select
  m.id as moto_id,
  m.placa,
  m.placa_provisoria,
  m.modelo,
  c.custo_total,
  c.pago_pelo_locatario,
  coalesce(dv.a_pagar, 0)                                          as a_pagar,
  c.custo_total - c.pago_pelo_locatario - coalesce(dv.a_pagar, 0)  as saiu_do_bolso,
  coalesce(r.receita_recebida, 0)                                  as recebido,
  coalesce(r.receita_recebida, 0) - c.custo_total                  as saldo,
  c.tem_valor_a_confirmar
from motos m
join lateral (
  select
    sum(d.valor)                                          as custo_total,
    coalesce(sum(d.valor) filter (where d.pago_por = 'locatario'), 0) as pago_pelo_locatario,
    bool_or(d.a_confirmar)                                as tem_valor_a_confirmar
  from despesas d
  where d.moto_id = m.id and d.categoria = 'aquisicao'
) c on c.custo_total is not null
left join lateral (
  select sum(coalesce(s.saldo_confirmado, s.saldo_calculado)) as a_pagar
  from vw_saldo_dividas s
  where s.moto_id = m.id and s.tipo in ('emprestimo', 'fornecedor')
) dv on true
left join vw_resultado_moto r on r.moto_id = m.id;

notify pgrst, 'reload schema';
