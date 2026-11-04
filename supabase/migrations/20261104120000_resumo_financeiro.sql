-- =====================================================================
-- 20261104120000_resumo_financeiro.sql
-- Dashboard financeiro (Etapa 1): totais por mês, numa leitura só.
--   rpc_resumo_financeiro(p_mes, p_meses) devolve os `p_meses` meses terminando em p_mes
--   (do mais antigo para o mais recente), cada um com:
--     receita          pagamentos em dinheiro (principal + multa/juros) de cobranças que não são caução,
--                      sem as formas "abatimento" (desconto, não entra dinheiro), por data do pagamento;
--                      mais a caução retida para danos dos contratos encerrados no mês
--                      (mesma regra de vw_resultado_moto);
--     despesas         custo operacional: despesas pagas pela locadora (menos "aquisicao"), manutenções
--                      concluídas (data de saída) e documentos regularizados (data da regularização);
--     investimento     despesas "aquisicao" pagas pela locadora (capital em veículo, fora do resultado);
--     parcelas_divida  pagamentos de dívidas (pagamentos_divida), contados só aqui, nunca em despesas;
--     retiradas, aportes  movimentos do sócio.
--   Resultado = receita - despesas.
--   Caixa = receita - despesas - investimento - parcelas_divida - retiradas + aportes.
-- Só leitura, security invoker (vale o RLS de quem chama). Compatível com a versão anterior do app.
-- =====================================================================

create or replace function rpc_resumo_financeiro(p_mes date, p_meses int default 6) returns jsonb
language plpgsql stable security invoker set search_path = public as $$
declare
  v_resultado jsonb;
begin
  if p_mes is null then
    raise exception 'Informe o mês.';
  end if;
  if p_meses is null or p_meses < 1 or p_meses > 24 then
    raise exception 'Informe de 1 a 24 meses.';
  end if;

  with meses as (
    select (date_trunc('month', p_mes)::date - make_interval(months => g))::date as inicio
    from generate_series(p_meses - 1, 0, -1) as g
  ), faixas as (
    select inicio, (inicio + interval '1 month')::date as fim from meses
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'mes',             f.inicio,
    'receita',         coalesce(rec.total, 0) + coalesce(cau.total, 0),
    'despesas',        coalesce(des.total, 0) + coalesce(man.total, 0) + coalesce(doc.total, 0),
    'investimento',    coalesce(inv.total, 0),
    'parcelas_divida', coalesce(div.total, 0),
    'retiradas',       coalesce(ret.total, 0),
    'aportes',         coalesce(apo.total, 0)
  ) order by f.inicio), '[]'::jsonb)
  into v_resultado
  from faixas f
  left join lateral (
    select sum(p.valor + p.multa_juros) as total
    from pagamentos p
    join cobrancas c on c.id = p.cobranca_id and c.tipo <> 'caucao'
    where p.forma <> 'abatimento' and p.data_pagamento >= f.inicio and p.data_pagamento < f.fim
  ) rec on true
  left join lateral (
    select sum(caucao_desconto_danos) as total
    from contratos
    where status = 'encerrado' and data_encerramento >= f.inicio and data_encerramento < f.fim
  ) cau on true
  left join lateral (
    select sum(valor) as total
    from despesas
    where categoria <> 'aquisicao' and pago_por = 'locadora' and data >= f.inicio and data < f.fim
  ) des on true
  left join lateral (
    select sum(custo_total) as total
    from manutencoes
    where status = 'concluida' and coalesce(data_saida, data_entrada) >= f.inicio
      and coalesce(data_saida, data_entrada) < f.fim
  ) man on true
  left join lateral (
    select sum(valor) as total
    from documentos_moto
    where regularizado and data_regularizacao >= f.inicio and data_regularizacao < f.fim
  ) doc on true
  left join lateral (
    select sum(valor) as total
    from despesas
    where categoria = 'aquisicao' and pago_por = 'locadora' and data >= f.inicio and data < f.fim
  ) inv on true
  left join lateral (
    select sum(valor) as total
    from pagamentos_divida
    where data >= f.inicio and data < f.fim
  ) div on true
  left join lateral (
    select sum(valor) as total
    from movimentos_socio
    where tipo = 'retirada' and data >= f.inicio and data < f.fim
  ) ret on true
  left join lateral (
    select sum(valor) as total
    from movimentos_socio
    where tipo = 'aporte' and data >= f.inicio and data < f.fim
  ) apo on true;

  return jsonb_build_object('meses', v_resultado);
end $$;

grant execute on function rpc_resumo_financeiro(date, int) to authenticated;

notify pgrst, 'reload schema';
