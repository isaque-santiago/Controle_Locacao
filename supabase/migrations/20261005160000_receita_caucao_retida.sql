-- =====================================================================
-- 20261005160000_receita_caucao_retida.sql
-- Decisão de negócio (seção 14.3 do plano): a parte da caução retida para cobrir danos
-- (`contratos.caucao_desconto_danos`) conta como RECEITA da moto, como a cobrança de dano
-- paga pelo cliente. O restante da caução continua fora da receita (é devolvido).
-- Mesma regra de src/domain/relatorios.py (consolidar). As colunas da view não mudam.
-- =====================================================================
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
) doc on true;

notify pgrst, 'reload schema';
