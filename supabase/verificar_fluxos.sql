-- Executar no SQL Editor de homologação após todas as migrations e seed.sql.
-- Todas as alterações deste roteiro são desfeitas ao final.
begin;
do $$
declare moto uuid; cliente uuid; contrato jsonb; parcela uuid; total numeric; plano int; resultado jsonb; item uuid; item_outro uuid; manutencao jsonb; ultima_outra int;
begin
  insert into motos(placa, marca, modelo, km_atual) values ('TST9Z99', 'Teste', 'Teste', 100) returning id into moto;
  select count(*) into plano from moto_plano_manutencao where moto_id = moto;
  assert plano = (select count(*) from itens_manutencao where ativo), 'Plano automático incompleto';
  insert into clientes(nome, cpf) values ('Teste transacional', '00000000000') returning id into cliente;
  contrato := rpc_criar_contrato_com_vistoria(jsonb_build_object('moto_id', moto, 'cliente_id', cliente,
    'data_inicio', hoje_br(), 'data_fim_prevista', hoje_br() + 30, 'periodicidade', 'semanal',
    'valor_periodo', 100, 'km_inicial', 100), '{"km":100,"checklist":{"farol":"ok"}}');
  assert (select count(*) from vistorias where contrato_id = (contrato->>'contrato_id')::uuid) = 1, 'Entrega não registrada';
  begin
    perform rpc_criar_contrato(jsonb_build_object('moto_id', moto, 'cliente_id', cliente, 'data_inicio', hoje_br(), 'periodicidade', 'semanal', 'valor_periodo', 100));
    raise exception using errcode = 'ZX001', message = 'Contrato duplicado foi aceito';
  exception when raise_exception then null;
  end;
  select id into parcela from cobrancas where contrato_id = (contrato->>'contrato_id')::uuid and numero = 2;
  insert into pagamentos(cobranca_id, data_pagamento, valor) values(parcela, hoje_br(), 40);
  select saldo into total from vw_cobrancas where id = parcela;
  assert total = 60, 'Saldo parcial incorreto';
  resultado := rpc_encerrar_contrato_com_vistoria((contrato->>'contrato_id')::uuid, hoje_br(), '{"km":150,"checklist":{"farol":"avaria"}}');
  assert (select status from cobrancas where id = parcela) = 'aberta', 'Parcial indevidamente cancelada';
  assert (select count(*) from cobrancas where contrato_id = (contrato->>'contrato_id')::uuid and numero > 2 and status <> 'cancelada') = 0, 'Futuras não canceladas';
  insert into pagamentos(cobranca_id, data_pagamento, valor) values(parcela, hoje_br(), 60);
  assert (select status from cobrancas where id = parcela) = 'paga', 'Pagamento total não quitou';
  assert (select km_atual from motos where id = moto) = 150, 'Km não atualizado';
  assert (select count(*) from vistorias where contrato_id = (contrato->>'contrato_id')::uuid) = 2, 'Devolução não registrada';
  select item_id into item from moto_plano_manutencao where moto_id = moto order by item_id limit 1;
  select item_id, ultima_km into item_outro, ultima_outra from moto_plano_manutencao where moto_id = moto and item_id <> item order by item_id limit 1;
  manutencao := rpc_registrar_manutencao(jsonb_build_object('moto_id', moto, 'tipo', 'preventiva',
    'status', 'aberta', 'data_entrada', hoje_br(), 'km', 150, 'descricao', 'Teste óleo', 'custo_mao_obra', 25,
    'itens', jsonb_build_array(jsonb_build_object('item_id', item, 'descricao', 'Óleo', 'quantidade', 2, 'valor_unitario', 15))));
  assert (select status from motos where id = moto) = 'manutencao', 'Manutenção aberta não bloqueou a moto';
  assert (select custo_total from manutencoes where id = (manutencao->>'manutencao_id')::uuid) = 55, 'Custo incorreto';
  perform rpc_finalizar_manutencao(jsonb_build_object('id', manutencao->>'manutencao_id',
    'status', 'concluida', 'data', hoje_br(), 'km', 160));
  assert (select ultima_km from moto_plano_manutencao where moto_id = moto and item_id = item) = 160, 'Item não reiniciado';
  assert (select ultima_km from moto_plano_manutencao where moto_id = moto and item_id = item_outro) = ultima_outra, 'Outro item alterado indevidamente';
  assert (select status from motos where id = moto) = 'disponivel', 'Moto não liberada';
  assert (select custo_manutencao from vw_resultado_moto where moto_id = moto) = 55, 'Resultado não contabilizou manutenção';
  assert (select receita_recebida from vw_resultado_moto where moto_id = moto) = 100, 'Resultado não contabilizou recebimento';
  begin
    perform rpc_registrar_vistoria(jsonb_build_object('contrato_id', contrato->>'contrato_id', 'moto_id', moto, 'tipo', 'devolucao', 'km', 160));
    raise exception using errcode = 'ZX002', message = 'Vistoria duplicada aceita';
  exception when unique_violation then null;
  end;
  begin
    insert into pagamentos(cobranca_id, data_pagamento, valor) values(parcela, hoje_br(), 1);
    raise exception using errcode = 'ZX003', message = 'Pagamento excedente aceito';
  exception when raise_exception then null;
  end;
  raise notice 'Contratos, pagamentos, vistorias, manutenção e relatórios verificados.';
end $$;
rollback;
