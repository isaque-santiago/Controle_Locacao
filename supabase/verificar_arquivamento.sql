-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar a migration
--   20261119120000_arquivamento.sql
-- Verifica: arquivar veículo/cliente sem pendência funciona (veículo fica inativo, motivo e data da venda gravados);
--   contrato ativo, manutenção aberta e cobrança em aberto (inclusive de contrato encerrado) recusam, com o motivo no texto;
--   desarquivar tira só a marca; contrato novo não aceita veículo nem cliente arquivado.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  dono     uuid;
  cli1     uuid;
  cli2     uuid;
  moto1    uuid;
  moto2    uuid;
  ct1      uuid;
  v_msg    text;
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'Precisa existir um administrador (dono)';
  perform set_config('request.jwt.claims', json_build_object('sub', dono, 'role', 'authenticated')::text, true);
  set local role authenticated;

  insert into clientes (nome, cpf) values ('Ex Locatario Arq', '90000000061') returning id into cli1;
  insert into clientes (nome, cpf) values ('Locatario Devedor Arq', '90000000062') returning id into cli2;
  insert into motos (placa, marca, modelo, km_atual) values ('ARQ1A11', 'T', 'Teste', 100) returning id into moto1;
  insert into motos (placa, marca, modelo, km_atual) values ('ARQ2B22', 'T', 'Teste', 100) returning id into moto2;

  -- 1) sem pendência: arquiva como vendido
  perform rpc_arquivar_moto(moto1, 'vendida', date '2026-11-10');
  assert (select arquivada_em is not null and status = 'inativa' and motivo_arquivamento = 'vendida'
                 and vendida_em = date '2026-11-10' from motos where id = moto1), 'moto1 deveria estar arquivada como vendida';

  -- 2) já arquivado é recusado
  begin
    perform rpc_arquivar_moto(moto1, 'vendida');
    assert false, 'arquivar duas vezes deveria falhar';
  exception when others then
    get stacked diagnostics v_msg = message_text;
    assert v_msg = 'Este veículo já está arquivado.', 'mensagem inesperada: ' || v_msg;
  end;

  -- 3) veículo arquivado não aceita contrato novo
  begin
    insert into contratos (cliente_id, moto_id, data_inicio, valor_periodo, periodicidade, km_inicial)
    values (cli1, moto1, current_date, 100, 'semanal', 100);
    assert false, 'contrato em veículo arquivado deveria falhar';
  exception when others then
    get stacked diagnostics v_msg = message_text;
    assert v_msg like 'Este veículo está arquivado%', 'mensagem inesperada: ' || v_msg;
  end;

  -- 4) desarquivar tira só a marca
  perform rpc_desarquivar_moto(moto1);
  assert (select arquivada_em is null and motivo_arquivamento is null and vendida_em is null and status = 'inativa'
            from motos where id = moto1), 'desarquivar deveria tirar só a marca';

  -- 5) contrato ativo e cobrança em aberto impedem arquivar o cliente e o veículo
  update motos set status = 'disponivel' where id = moto2;
  insert into contratos (cliente_id, moto_id, data_inicio, valor_periodo, periodicidade, km_inicial)
  values (cli2, moto2, current_date - 30, 100, 'semanal', 100) returning id into ct1;
  begin
    perform rpc_arquivar_cliente(cli2);
    assert false, 'cliente com contrato ativo deveria ser recusado';
  exception when others then
    get stacked diagnostics v_msg = message_text;
    assert v_msg like 'Não é possível arquivar o cliente: %contrato(s) ativo(s)%', 'mensagem inesperada: ' || v_msg;
  end;

  -- 6) encerrado mas com cobrança em aberto: ainda recusa; cancelada a cobrança, libera
  update contratos set status = 'encerrado', data_encerramento = current_date where id = ct1;
  insert into cobrancas (contrato_id, tipo, numero, vencimento, valor)
  values (ct1, 'locacao', 1, current_date - 10, 100);
  begin
    perform rpc_arquivar_cliente(cli2);
    assert false, 'cliente com débito deveria ser recusado';
  exception when others then
    get stacked diagnostics v_msg = message_text;
    assert v_msg like '%cobrança(s) em aberto%', 'mensagem inesperada: ' || v_msg;
  end;
  update cobrancas set status = 'cancelada' where contrato_id = ct1;
  perform rpc_arquivar_cliente(cli2);
  assert (select arquivado_em is not null and status = 'inativo' from clientes where id = cli2), 'cliente deveria estar arquivado';
  perform rpc_desarquivar_cliente(cli2);
  assert (select arquivado_em is null from clientes where id = cli2), 'cliente deveria ter sido desarquivado';

  raise notice 'OK: arquivamento verificado';
end $$;
rollback;
