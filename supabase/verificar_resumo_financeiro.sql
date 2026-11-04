-- Executar no SQL Editor de DESENVOLVIMENTO (nunca em produção) após aplicar a migration
--   20261104120000_resumo_financeiro.sql
-- Verifica rpc_resumo_financeiro: receita (sem caução nem abatimento), despesas operacionais, investimento,
-- parcelas de dívida, retiradas e aportes do mês, a ordem dos meses e as recusas.
-- Compara com a leitura feita antes dos lançamentos de teste, então vale com ou sem dados no banco.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  antes jsonb; depois jsonb; serie jsonb; moto uuid; cliente uuid; contrato jsonb; parcela uuid; divida uuid;
  hoje date := hoje_br();
begin
  antes := (rpc_resumo_financeiro(hoje, 1)->'meses')->0;

  insert into motos(placa, marca, modelo, km_atual) values ('TST8R88', 'Teste', 'Teste', 100) returning id into moto;
  insert into clientes(nome, cpf) values ('Teste resumo financeiro', '00000000001') returning id into cliente;
  contrato := rpc_criar_contrato_com_vistoria(jsonb_build_object('moto_id', moto, 'cliente_id', cliente,
    'data_inicio', hoje, 'data_fim_prevista', hoje + 30, 'periodicidade', 'semanal',
    'valor_periodo', 100, 'km_inicial', 100), '{"km":100,"checklist":{"farol":"ok"}}');
  select id into parcela from cobrancas where contrato_id = (contrato->>'contrato_id')::uuid and tipo = 'locacao' order by numero limit 1;

  insert into pagamentos(cobranca_id, data_pagamento, valor, multa_juros, forma) values (parcela, hoje, 60, 10, 'pix');
  insert into pagamentos(cobranca_id, data_pagamento, valor, forma) values (parcela, hoje, 20, 'abatimento');

  insert into despesas(data, moto_id, categoria, valor) values (hoje, moto, 'outros', 30);
  insert into despesas(data, moto_id, categoria, valor) values (hoje, moto, 'aquisicao', 500);
  insert into despesas(data, moto_id, categoria, valor, pago_por) values (hoje, moto, 'manutencao', 40, 'locatario');

  insert into manutencoes(moto_id, tipo, status, data_entrada, data_saida, km, descricao, custo_mao_obra)
  values (moto, 'preventiva', 'concluida', hoje, hoje, 100, 'Concluída', 25);
  insert into manutencoes(moto_id, tipo, status, data_entrada, km, descricao, custo_mao_obra)
  values (moto, 'preventiva', 'aberta', hoje, 100, 'Aberta (não conta)', 99);
  insert into documentos_moto(moto_id, tipo, vencimento, valor, regularizado, data_regularizacao) values (moto, 'ipva', hoje, 35, true, hoje);
  insert into documentos_moto(moto_id, tipo, vencimento, valor, regularizado) values (moto, 'ipva', hoje, 77, false);

  insert into dividas(tipo, credor, valor_original) values ('emprestimo', 'Credor de teste', 1000) returning id into divida;
  insert into pagamentos_divida(divida_id, data, valor) values (divida, hoje, 200);

  insert into movimentos_socio(tipo, data, valor) values ('retirada', hoje, 50);
  insert into movimentos_socio(tipo, data, valor) values ('aporte', hoje, 80);

  depois := (rpc_resumo_financeiro(hoje, 1)->'meses')->0;
  assert (depois->>'receita')::numeric - (antes->>'receita')::numeric = 70, 'Receita: só o dinheiro recebido (60 + 10), sem o abatimento';
  assert (depois->>'despesas')::numeric - (antes->>'despesas')::numeric = 90, 'Despesas: 30 da locadora + 25 de manutenção concluída + 35 de documento regularizado';
  assert (depois->>'investimento')::numeric - (antes->>'investimento')::numeric = 500, 'Investimento: a aquisição paga pela locadora';
  assert (depois->>'parcelas_divida')::numeric - (antes->>'parcelas_divida')::numeric = 200, 'Parcelas de dívida incorretas';
  assert (depois->>'retiradas')::numeric - (antes->>'retiradas')::numeric = 50, 'Retiradas incorretas';
  assert (depois->>'aportes')::numeric - (antes->>'aportes')::numeric = 80, 'Aportes incorretos';
  assert (depois->>'mes')::date = date_trunc('month', hoje)::date, 'O mês deve ser o primeiro dia do mês';

  serie := rpc_resumo_financeiro(hoje, 3)->'meses';
  assert jsonb_array_length(serie) = 3, 'Deveria devolver 3 meses';
  assert (serie->2->>'mes')::date = date_trunc('month', hoje)::date, 'O último mês deve ser o mês pedido';
  assert (serie->0->>'mes')::date = (date_trunc('month', hoje) - interval '2 months')::date, 'O primeiro mês deve ser o mais antigo';
  assert (serie->2->>'receita')::numeric = (depois->>'receita')::numeric, 'A série e o mês isolado devem coincidir';
  assert jsonb_array_length(rpc_resumo_financeiro(date '2026-11-17', 1)->'meses') = 1, 'Qualquer dia do mês vale';
  assert ((rpc_resumo_financeiro(date '2026-11-17', 1)->'meses')->0->>'mes')::date = date '2026-11-01', 'O mês deve ser normalizado para o dia 1';

  begin
    perform rpc_resumo_financeiro(hoje, 0);
    raise exception 'Deveria recusar 0 meses';
  exception when others then
    if sqlerrm = 'Deveria recusar 0 meses' then raise; end if;
  end;
  begin
    perform rpc_resumo_financeiro(hoje, 25);
    raise exception 'Deveria recusar 25 meses';
  exception when others then
    if sqlerrm = 'Deveria recusar 25 meses' then raise; end if;
  end;
  begin
    perform rpc_resumo_financeiro(null, 6);
    raise exception 'Deveria recusar mês nulo';
  exception when others then
    if sqlerrm = 'Deveria recusar mês nulo' then raise; end if;
  end;

  raise notice 'Resumo financeiro: OK';
end $$;
rollback;
