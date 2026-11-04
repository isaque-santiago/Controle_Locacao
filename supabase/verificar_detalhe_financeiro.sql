-- Executar no SQL Editor de DESENVOLVIMENTO (nunca em produção) após aplicar a migration
--   20261104130000_detalhe_financeiro.sql
-- Verifica rpc_detalhe_financeiro: entradas por conta (com e sem conta, sem abatimento), despesas por categoria
-- (despesas da locadora, manutenção concluída e documento regularizado), despesas a repassar e receita da semana.
-- Compara com a leitura feita antes dos lançamentos de teste, então vale com ou sem dados no banco.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  antes jsonb; depois jsonb; moto uuid; cliente uuid; contrato jsonb; parcela uuid; conta uuid;
  hoje date := hoje_br();
begin
  antes := rpc_detalhe_financeiro(hoje);

  insert into motos(placa, marca, modelo, km_atual) values ('TST6D66', 'Teste', 'Teste', 100) returning id into moto;
  insert into clientes(nome, cpf) values ('Teste detalhe financeiro', '00000000002') returning id into cliente;
  insert into contas(nome) values ('Conta de teste') returning id into conta;
  contrato := rpc_criar_contrato_com_vistoria(jsonb_build_object('moto_id', moto, 'cliente_id', cliente,
    'data_inicio', hoje, 'data_fim_prevista', hoje + 30, 'periodicidade', 'semanal',
    'valor_periodo', 500, 'km_inicial', 100), '{"km":100,"checklist":{"farol":"ok"}}');
  select id into parcela from cobrancas where contrato_id = (contrato->>'contrato_id')::uuid and tipo = 'locacao' order by numero limit 1;

  insert into pagamentos(cobranca_id, data_pagamento, valor, multa_juros, forma, conta_id) values (parcela, hoje, 100, 20, 'pix', conta);
  insert into pagamentos(cobranca_id, data_pagamento, valor, forma) values (parcela, hoje, 50, 'dinheiro');
  insert into pagamentos(cobranca_id, data_pagamento, valor, forma) values (parcela, hoje, 30, 'abatimento');

  insert into despesas(data, moto_id, categoria, valor) values (hoje, moto, 'combustivel', 40);
  insert into despesas(data, moto_id, categoria, valor) values (hoje, moto, 'aquisicao', 300);
  insert into despesas(data, moto_id, categoria, valor, pago_por) values (hoje, moto, 'combustivel', 999, 'locatario');
  insert into despesas(data, moto_id, categoria, valor, repassar_locatario) values (hoje, moto, 'multas', 70, true);
  insert into manutencoes(moto_id, tipo, status, data_entrada, data_saida, km, descricao, custo_mao_obra)
  values (moto, 'preventiva', 'concluida', hoje, hoje, 100, 'Concluída', 25);
  insert into documentos_moto(moto_id, tipo, vencimento, valor, regularizado, data_regularizacao) values (moto, 'ipva', hoje, 35, true, hoje);

  depois := rpc_detalhe_financeiro(hoje);

  assert (select coalesce(sum((e->>'valor')::numeric), 0) from jsonb_array_elements(depois->'entradas_por_conta') e where e->>'conta' = 'Conta de teste') = 120,
    'A conta de teste deveria ter recebido 100 + 20 de multa/juros';
  assert (select coalesce(sum((e->>'valor')::numeric), 0) from jsonb_array_elements(depois->'entradas_por_conta') e where e->>'conta' is null)
       - (select coalesce(sum((e->>'valor')::numeric), 0) from jsonb_array_elements(antes->'entradas_por_conta') e where e->>'conta' is null) = 50,
    'Sem conta: só os 50 em dinheiro, sem o abatimento';

  assert (select coalesce(sum((e->>'valor')::numeric), 0) from jsonb_array_elements(depois->'despesas_por_categoria') e where e->>'categoria' = 'combustivel')
       - (select coalesce(sum((e->>'valor')::numeric), 0) from jsonb_array_elements(antes->'despesas_por_categoria') e where e->>'categoria' = 'combustivel') = 40,
    'Combustível: só o que a locadora pagou (40), sem o pago pelo locatário';
  assert (select coalesce(sum((e->>'valor')::numeric), 0) from jsonb_array_elements(depois->'despesas_por_categoria') e where e->>'categoria' = 'aquisicao')
       - (select coalesce(sum((e->>'valor')::numeric), 0) from jsonb_array_elements(antes->'despesas_por_categoria') e where e->>'categoria' = 'aquisicao') = 300,
    'A aquisição paga pela locadora aparece como categoria';
  assert (select coalesce(sum((e->>'valor')::numeric), 0) from jsonb_array_elements(depois->'despesas_por_categoria') e where e->>'categoria' = 'manutencao')
       - (select coalesce(sum((e->>'valor')::numeric), 0) from jsonb_array_elements(antes->'despesas_por_categoria') e where e->>'categoria' = 'manutencao') = 25,
    'A manutenção concluída entra como manutencao';
  assert (select coalesce(sum((e->>'valor')::numeric), 0) from jsonb_array_elements(depois->'despesas_por_categoria') e where e->>'categoria' = 'documentacao')
       - (select coalesce(sum((e->>'valor')::numeric), 0) from jsonb_array_elements(antes->'despesas_por_categoria') e where e->>'categoria' = 'documentacao') = 35,
    'O documento regularizado entra como documentacao';

  assert (select (e->>'valor')::numeric from jsonb_array_elements(depois->'despesas_por_categoria') with ordinality t(e, i) order by i limit 1)
       >= (select (e->>'valor')::numeric from jsonb_array_elements(depois->'despesas_por_categoria') with ordinality t(e, i) order by i desc limit 1),
    'As categorias vêm da maior para a menor';

  assert (depois->>'a_repassar')::numeric - (antes->>'a_repassar')::numeric = 70, 'A repassar: só a despesa marcada (70)';
  assert (depois->>'receita_semana')::numeric - (antes->>'receita_semana')::numeric = 170, 'Receita da semana: 100 + 20 + 50, sem o abatimento';

  begin
    perform rpc_detalhe_financeiro(null);
    raise exception 'Deveria recusar mês nulo';
  exception when others then
    if sqlerrm = 'Deveria recusar mês nulo' then raise; end if;
  end;

  raise notice 'Detalhe financeiro: OK';
end $$;
rollback;
