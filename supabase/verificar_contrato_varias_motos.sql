-- Executar no SQL Editor de DESENVOLVIMENTO (nunca em produção) após aplicar a migration
--   20261103120000_contrato_varias_motos.sql
-- Verifica o contrato com mais de uma moto (moto principal + vinculadas):
--   criação, status das motos, unicidade em contrato ativo, limites, inativação, receita na principal e encerramento.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  cliente uuid; m1 uuid; m2 uuid; m3 uuid; m4 uuid; m5 uuid; m6 uuid; m7 uuid;
  c1 jsonb; ct1 uuid; ct2 uuid; cob uuid; n int; r jsonb;
begin
  insert into clientes(nome, cpf) values ('Teste varias motos', '00000000003') returning id into cliente;
  insert into motos(placa, marca, modelo) values ('TSV1A11', 'Teste', 'Principal') returning id into m1;
  insert into motos(placa, marca, modelo) values ('TSV2A22', 'Teste', 'Vinculada') returning id into m2;
  insert into motos(placa, marca, modelo) values ('TSV3A33', 'Teste', 'Outra') returning id into m3;
  insert into motos(placa, marca, modelo) values ('TSV4A44', 'Teste', 'Extra4') returning id into m4;
  insert into motos(placa, marca, modelo) values ('TSV5A55', 'Teste', 'Extra5') returning id into m5;
  insert into motos(placa, marca, modelo) values ('TSV6A66', 'Teste', 'Extra6') returning id into m6;
  insert into motos(placa, marca, modelo, status) values ('TSV7A77', 'Teste', 'EmOficina', 'manutencao') returning id into m7;

  -- Contrato com duas motos: parcela e receita na principal
  c1 := rpc_criar_contrato(jsonb_build_object('moto_id', m1, 'cliente_id', cliente, 'data_inicio', hoje_br(),
    'periodicidade', 'semanal', 'valor_periodo', 350, 'caucao_valor', 500, 'km_inicial', 0, 'motos_vinculadas', jsonb_build_array(m2)));
  ct1 := (c1->>'contrato_id')::uuid;
  assert (c1->>'motos_vinculadas')::int = 1, 'Resposta deveria informar 1 moto vinculada';
  assert (select count(*) from contrato_motos where contrato_id = ct1 and moto_id = m2) = 1, 'Moto vinculada não gravada';
  assert (select status from motos where id = m1) = 'alugada' and (select status from motos where id = m2) = 'alugada', 'As duas motos deveriam ficar alugadas';
  assert (select count(*) from historico_km where moto_id = m2 and origem = 'contrato') = 1, 'Km da vinculada não registrado';
  assert (select count(*) from vw_contrato_motos where contrato_id = ct1) = 2, 'vw_contrato_motos deveria ter 2 motos';
  assert (select principal from vw_contrato_motos where contrato_id = ct1 and moto_id = m1), 'A principal deveria estar marcada';
  assert not (select principal from vw_contrato_motos where contrato_id = ct1 and moto_id = m2), 'A vinculada não deveria ser principal';
  -- uma só cobrança de locação por período (a parcela vale pelas duas motos)
  assert (select count(*) from cobrancas where contrato_id = ct1 and tipo = 'locacao' and numero = 1) = 1, 'Deveria haver uma cobrança de locação por período';

  -- Receita na moto principal
  select id into cob from cobrancas where contrato_id = ct1 and tipo = 'locacao' and numero = 1;
  insert into pagamentos(cobranca_id, data_pagamento, valor) values (cob, hoje_br(), 350);
  assert (select receita_recebida from vw_resultado_moto where moto_id = m1) = 350, 'A receita deveria ficar na principal';
  assert (select receita_recebida from vw_resultado_moto where moto_id = m2) = 0, 'A vinculada não deveria receber receita';

  -- A vinculada está ocupada
  begin
    perform rpc_criar_contrato(jsonb_build_object('moto_id', m2, 'cliente_id', cliente, 'data_inicio', hoje_br(),
      'periodicidade', 'semanal', 'valor_periodo', 100, 'km_inicial', 0));
    raise exception using errcode = 'ZX301', message = 'Moto vinculada aceita como principal de outro contrato';
  exception when raise_exception then null;
  end;
  insert into motos(placa, marca, modelo) values ('TSV8A88', 'Teste', 'Livre') returning id into m3;
  ct2 := (rpc_criar_contrato(jsonb_build_object('moto_id', m3, 'cliente_id', cliente, 'data_inicio', hoje_br(),
    'periodicidade', 'semanal', 'valor_periodo', 100, 'km_inicial', 0))->>'contrato_id')::uuid;
  begin
    insert into contrato_motos(contrato_id, moto_id) values (ct2, m2);
    raise exception using errcode = 'ZX302', message = 'Moto de contrato ativo foi vinculada a outro contrato ativo';
  exception when raise_exception then null;
  end;
  begin
    insert into contrato_motos(contrato_id, moto_id) values (ct1, m1);
    raise exception using errcode = 'ZX303', message = 'Moto principal foi aceita como vinculada do próprio contrato';
  exception when raise_exception then null;
  end;

  -- Inativar moto vinculada a contrato ativo é recusado
  begin
    update motos set status = 'inativa' where id = m2;
    raise exception using errcode = 'ZX304', message = 'Inativou moto vinculada a contrato ativo';
  exception when raise_exception then null;
  end;

  -- Entradas inválidas na criação
  begin
    perform rpc_criar_contrato(jsonb_build_object('moto_id', m4, 'cliente_id', cliente, 'data_inicio', hoje_br(),
      'periodicidade', 'semanal', 'valor_periodo', 100, 'km_inicial', 0, 'motos_vinculadas', jsonb_build_array(m5, m5)));
    raise exception using errcode = 'ZX305', message = 'Moto repetida na lista foi aceita';
  exception when raise_exception then null;
  end;
  begin
    perform rpc_criar_contrato(jsonb_build_object('moto_id', m4, 'cliente_id', cliente, 'data_inicio', hoje_br(),
      'periodicidade', 'semanal', 'valor_periodo', 100, 'km_inicial', 0, 'motos_vinculadas', jsonb_build_array(m4)));
    raise exception using errcode = 'ZX306', message = 'Principal na lista de vinculadas foi aceita';
  exception when raise_exception then null;
  end;
  begin
    perform rpc_criar_contrato(jsonb_build_object('moto_id', m4, 'cliente_id', cliente, 'data_inicio', hoje_br(),
      'periodicidade', 'semanal', 'valor_periodo', 100, 'km_inicial', 0, 'motos_vinculadas', jsonb_build_array(m7)));
    raise exception using errcode = 'ZX307', message = 'Moto em manutenção foi aceita como vinculada';
  exception when raise_exception then null;
  end;
  assert (select status from motos where id = m4) = 'disponivel', 'Uma criação recusada não pode alterar a moto principal';
  begin
    perform rpc_criar_contrato(jsonb_build_object('moto_id', m4, 'cliente_id', cliente, 'data_inicio', hoje_br(),
      'periodicidade', 'semanal', 'valor_periodo', 100, 'km_inicial', 0,
      'motos_vinculadas', jsonb_build_array(m5, m6, m1, m2, m3)));
    raise exception using errcode = 'ZX308', message = 'Mais de 5 motos foram aceitas';
  exception when raise_exception then null;
  end;

  -- Sem a lista tudo continua como antes
  assert (select count(*) from contrato_motos where contrato_id = ct2) = 0, 'Contrato sem lista não deveria ter vinculadas';

  -- Encerramento libera todas as motos; a vinculada pode ser usada em outro contrato
  r := rpc_encerrar_contrato(ct1, hoje_br(), 10, 0, null);
  assert (select status from motos where id = m1) = 'disponivel' and (select status from motos where id = m2) = 'disponivel', 'As duas motos deveriam voltar disponíveis';
  assert (select count(*) from contrato_motos where contrato_id = ct1) = 1, 'O vínculo do contrato encerrado deve ficar no histórico';
  perform rpc_criar_contrato(jsonb_build_object('moto_id', m2, 'cliente_id', cliente, 'data_inicio', hoje_br(),
    'periodicidade', 'semanal', 'valor_periodo', 100, 'km_inicial', 0));

  raise notice 'Verificação do contrato com várias motos: OK';
end $$;
rollback;
