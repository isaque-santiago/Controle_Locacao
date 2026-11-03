-- =====================================================================
-- 20261103140000_capital_inclui_compra_parcelada.sql
-- vw_capital_veiculo passa a somar também as dívidas 'compra_parcelada' (ex.: Celta) no "a pagar" do veículo.
-- Só muda o filtro de tipos da view; as colunas são as mesmas.
-- =====================================================================
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
  where s.moto_id = m.id and s.tipo in ('emprestimo', 'fornecedor', 'compra_parcelada')
) dv on true
left join vw_resultado_moto r on r.moto_id = m.id;

notify pgrst, 'reload schema';
