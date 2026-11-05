-- Executar no SQL Editor de DESENVOLVIMENTO (nunca em produção) após aplicar a migration
--   20261105130000_vistoria_por_moto.sql
-- Verifica a vistoria por moto: entrega e devolução de cada moto do contrato, km das vinculadas, moto de fora do contrato,
--   duplicidade por moto e tipo, e as chamadas antigas (contrato de uma moto, sem o parâmetro novo).
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  cliente uuid; m1 uuid; m2 uuid; m3 uuid; m4 uuid; m5 uuid;
  r jsonb; ct uuid; ct2 uuid; falhou boolean;
  vist jsonb := '{"km": 100, "checklist": {"farol_dianteiro": "ok"}}';
begin
  insert into clientes(nome, cpf) values ('Teste vistoria por moto', '00000000004') returning id into cliente;
  insert into motos(placa, marca, modelo, km_atual) values ('TSM1A11', 'Teste', 'Principal', 100) returning id into m1;
  insert into motos(placa, marca, modelo, km_atual) values ('TSM2A22', 'Teste', 'Vinculada', 500) returning id into m2;
  insert into motos(placa, marca, modelo, km_atual) values ('TSM3A33', 'Teste', 'Fora', 0) returning id into m3;
  insert into motos(placa, marca, modelo, km_atual) values ('TSM4A44', 'Teste', 'Unica', 10) returning id into m4;
  insert into motos(placa, marca, modelo, km_atual) values ('TSM5A55', 'Teste', 'Outra', 0) returning id into m5;

  -- Contrato com duas motos: entrega das duas
  r := rpc_criar_contrato_com_vistoria(
    jsonb_build_object('moto_id', m1, 'cliente_id', cliente, 'data_inicio', hoje_br(), 'periodicidade', 'semanal',
      'valor_periodo', 350, 'caucao_valor', 0, 'km_inicial', 100, 'motos_vinculadas', jsonb_build_array(m2)),
    vist,
    jsonb_build_array(jsonb_build_object('moto_id', m2, 'km', 520, 'checklist', jsonb_build_object('farol_dianteiro', 'avaria'))));
  ct := (r->>'contrato_id')::uuid;
  assert (select count(*) from vistorias where contrato_id = ct and tipo = 'entrega') = 2, 'Deveria haver 2 vistorias de entrega';
  assert (select moto_id from vistorias where contrato_id = ct and checklist->>'farol_dianteiro' = 'avaria') = m2, 'A vistoria da vinculada deveria ser da vinculada';
  assert (select km_atual from motos where id = m2) = 520, 'O km da vinculada deveria subir para 520';

  -- Vistoria de moto fora do contrato
  falhou := false;
  begin
    perform rpc_registrar_vistoria(jsonb_build_object('contrato_id', ct, 'moto_id', m3, 'tipo', 'devolucao', 'km', 5, 'checklist', '{}'::jsonb));
  exception when others then falhou := sqlerrm like '%incompatíveis%'; end;
  assert falhou, 'Moto fora do contrato não deveria aceitar vistoria (RPC)';
  falhou := false;
  begin
    insert into vistorias (contrato_id, moto_id, tipo, km) values (ct, m3, 'devolucao', 5);
  exception when others then falhou := sqlerrm like '%não pertence ao contrato%'; end;
  assert falhou, 'Moto fora do contrato não deveria aceitar vistoria (inserção direta)';

  -- Duplicidade da mesma moto e tipo
  falhou := false;
  begin
    perform rpc_registrar_vistoria(jsonb_build_object('contrato_id', ct, 'moto_id', m2, 'tipo', 'entrega', 'km', 530, 'checklist', '{}'::jsonb));
  exception when unique_violation then falhou := true; end;
  assert falhou, 'A mesma moto não pode ter duas entregas no contrato';

  -- Encerramento com km da vinculada menor que o atual
  falhou := false;
  begin
    perform rpc_encerrar_contrato_com_vistoria(ct, hoje_br(), '{"km": 150, "checklist": {}}'::jsonb, 0, null,
      jsonb_build_array(jsonb_build_object('moto_id', m2, 'km', 100, 'checklist', '{}'::jsonb)));
  exception when others then falhou := sqlerrm like '%menor que a atual%'; end;
  assert falhou, 'Km da vinculada menor que o atual deveria ser recusado';

  -- Encerramento com moto que não é vinculada do contrato
  falhou := false;
  begin
    perform rpc_encerrar_contrato_com_vistoria(ct, hoje_br(), '{"km": 150, "checklist": {}}'::jsonb, 0, null,
      jsonb_build_array(jsonb_build_object('moto_id', m3, 'km', 9, 'checklist', '{}'::jsonb)));
  exception when others then falhou := sqlerrm like '%não é uma moto vinculada%'; end;
  assert falhou, 'Moto de fora do contrato deveria ser recusada na devolução';

  -- Encerramento correto: devolução das duas
  perform rpc_encerrar_contrato_com_vistoria(ct, hoje_br(), '{"km": 150, "checklist": {}}'::jsonb, 0, null,
    jsonb_build_array(jsonb_build_object('moto_id', m2, 'km', 560, 'checklist', jsonb_build_object('farol_dianteiro', 'ok'))));
  assert (select count(*) from vistorias where contrato_id = ct and tipo = 'devolucao') = 2, 'Deveria haver 2 vistorias de devolução';
  assert (select km_atual from motos where id = m2) = 560, 'O km da vinculada deveria subir para 560';
  assert (select km_atual from motos where id = m1) = 150, 'O km da principal deveria subir para 150';
  assert (select status from motos where id = m1) = 'disponivel' and (select status from motos where id = m2) = 'disponivel', 'As duas motos deveriam voltar a disponível';
  assert (select status from contratos where id = ct) = 'encerrado', 'O contrato deveria estar encerrado';

  -- Chamadas antigas: contrato de uma moto, sem o parâmetro novo, entrega e devolução
  r := rpc_criar_contrato_com_vistoria(
    jsonb_build_object('moto_id', m4, 'cliente_id', cliente, 'data_inicio', hoje_br(), 'periodicidade', 'semanal',
      'valor_periodo', 200, 'caucao_valor', 0, 'km_inicial', 10), '{"km": 10, "checklist": {}}'::jsonb);
  ct2 := (r->>'contrato_id')::uuid;
  assert (select count(*) from vistorias where contrato_id = ct2) = 1, 'Contrato de uma moto: uma vistoria de entrega';
  perform rpc_encerrar_contrato_com_vistoria(ct2, hoje_br(), '{"km": 40, "checklist": {}}'::jsonb);
  assert (select count(*) from vistorias where contrato_id = ct2) = 2, 'Contrato de uma moto: entrega e devolução';

  -- Vistoria retroativa da vinculada de um contrato ativo (por rpc_registrar_vistoria)
  r := rpc_criar_contrato(jsonb_build_object('moto_id', m1, 'cliente_id', cliente, 'data_inicio', hoje_br(), 'periodicidade', 'semanal',
      'valor_periodo', 100, 'caucao_valor', 0, 'km_inicial', 150, 'motos_vinculadas', jsonb_build_array(m5)));
  perform rpc_registrar_vistoria(jsonb_build_object('contrato_id', r->>'contrato_id', 'moto_id', m5, 'tipo', 'entrega', 'km', 5, 'checklist', '{}'::jsonb));
  assert (select count(*) from vistorias where contrato_id = (r->>'contrato_id')::uuid and moto_id = m5) = 1, 'A entrega retroativa da vinculada deveria ser aceita';

  raise notice 'Verificação da vistoria por moto: OK';
end $$;
rollback;
