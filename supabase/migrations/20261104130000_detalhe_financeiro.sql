-- =====================================================================
-- 20261104130000_detalhe_financeiro.sql
-- Dashboard financeiro (Etapa 2): detalhes de um mês, numa leitura só.
--   rpc_detalhe_financeiro(p_mes) devolve:
--     entradas_por_conta       dinheiro recebido no mês por conta (pagamentos que não são caução nem "abatimento",
--                              principal + multa/juros); os sem conta vêm com conta nula;
--     despesas_por_categoria   o que a locadora gastou no mês por categoria (maior primeiro): despesas pagas por ela
--                              (inclui "aquisicao"), manutenções concluídas (como "manutencao") e documentos
--                              regularizados (como "documentacao"), as mesmas fontes de rpc_resumo_financeiro;
--     a_repassar               despesas a repassar ao locatário ainda não repassadas (todas as datas);
--     receita_semana           dinheiro recebido de segunda-feira até hoje (semana corrente, fuso de São Paulo).
-- Só leitura, security invoker (vale o RLS de quem chama). Compatível com a versão anterior do app.
-- =====================================================================

create or replace function rpc_detalhe_financeiro(p_mes date) returns jsonb
language plpgsql stable security invoker set search_path = public as $$
declare
  v_inicio date;
  v_fim    date;
  v_semana date := date_trunc('week', hoje_br())::date;
  v_entradas jsonb;
  v_categorias jsonb;
  v_repassar numeric;
  v_receita_semana numeric;
begin
  if p_mes is null then
    raise exception 'Informe o mês.';
  end if;
  v_inicio := date_trunc('month', p_mes)::date;
  v_fim := (v_inicio + interval '1 month')::date;

  select coalesce(jsonb_agg(jsonb_build_object('conta', t.conta, 'valor', t.valor) order by t.valor desc), '[]'::jsonb)
    into v_entradas
  from (
    select co.nome as conta, sum(p.valor + p.multa_juros) as valor
    from pagamentos p
    join cobrancas c on c.id = p.cobranca_id and c.tipo <> 'caucao'
    left join contas co on co.id = p.conta_id
    where p.forma <> 'abatimento' and p.data_pagamento >= v_inicio and p.data_pagamento < v_fim
    group by co.nome
  ) t;

  select coalesce(jsonb_agg(jsonb_build_object('categoria', t.categoria, 'valor', t.valor) order by t.valor desc), '[]'::jsonb)
    into v_categorias
  from (
    select categoria, sum(valor) as valor
    from (
      select categoria, valor from despesas
      where pago_por = 'locadora' and data >= v_inicio and data < v_fim
      union all
      select 'manutencao', custo_total from manutencoes
      where status = 'concluida' and coalesce(data_saida, data_entrada) >= v_inicio
        and coalesce(data_saida, data_entrada) < v_fim
      union all
      select 'documentacao', valor from documentos_moto
      where regularizado and data_regularizacao >= v_inicio and data_regularizacao < v_fim and valor is not null
    ) u
    group by categoria
    having sum(valor) > 0
  ) t;

  select coalesce(sum(valor), 0) into v_repassar from despesas where repassar_locatario and not repassado;

  select coalesce(sum(p.valor + p.multa_juros), 0) into v_receita_semana
  from pagamentos p
  join cobrancas c on c.id = p.cobranca_id and c.tipo <> 'caucao'
  where p.forma <> 'abatimento' and p.data_pagamento >= v_semana and p.data_pagamento <= hoje_br();

  return jsonb_build_object(
    'entradas_por_conta', v_entradas,
    'despesas_por_categoria', v_categorias,
    'a_repassar', v_repassar,
    'receita_semana', v_receita_semana
  );
end $$;

grant execute on function rpc_detalhe_financeiro(date) to authenticated;

notify pgrst, 'reload schema';
