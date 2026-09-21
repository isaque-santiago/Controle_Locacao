-- Resultado acumulado, com custo de manutenção por km registrado.
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
  round(coalesce(man.total, 0) / nullif(greatest(m.km_atual - coalesce((select min(km) from historico_km where moto_id = m.id), m.km_atual), 0), 0), 2) as custo_por_km
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
