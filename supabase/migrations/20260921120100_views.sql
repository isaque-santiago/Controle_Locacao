-- =====================================================================
-- 20260921120100_views.sql : cobranças com situação, alertas e resultado por moto
-- Todas as views usam security_invoker = true para respeitar o RLS.
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
