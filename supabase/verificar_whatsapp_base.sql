-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar a migration
--   20261106120000_whatsapp_base.sql
-- Verifica: só o usuário de serviço e o administrador chamam as RPCs; o usuário de serviço não lê nenhuma tabela;
--   o mesmo aviso não é enfileirado duas vezes; cliente bloqueado é pulado (e cancelado se bloqueado depois);
--   número ausente ou inválido vira 'ignorada'; a reserva não entrega a mesma mensagem duas vezes;
--   falha volta para a fila até a 3ª tentativa; mensagem já enviada não aceita novo resultado.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  dono     uuid;
  robo     uuid := gen_random_uuid();
  estranho uuid := gen_random_uuid();
  c1       uuid;
  c2       uuid;
  cobr     uuid := gen_random_uuid();
  r        jsonb;
  lista    jsonb;
  id1      uuid;
  n        int;
  st       text;
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'Precisa existir um administrador (dono)';

  insert into clientes (nome, cpf, whatsapp) values ('Cliente Zap Um', '90000000001', '(11) 98888-7777') returning id into c1;
  insert into clientes (nome, cpf) values ('Cliente Zap Dois', '90000000002') returning id into c2;
  insert into servico_mensagens (user_id) values (robo);
  -- Depois da migration 20261111120000 a reserva só entrega com o envio ligado e o portão da janela aberto:
  -- este roteiro testa a fila em si, então liga o envio de verdade e abre o portão.
  update configuracoes set whatsapp_ativo = true, whatsapp_modo_teste = false, whatsapp_envio_liberado_ate = now() + interval '1 hour' where id = 1;

  -- um usuário qualquer não chama nenhuma RPC
  perform set_config('request.jwt.claim.sub', estranho::text, true);
  set local role authenticated;
  begin
    perform rpc_whatsapp_enfileirar('{"mensagens": []}'::jsonb);
    raise exception 'Usuário qualquer não deveria enfileirar';
  exception when insufficient_privilege then null;
  end;
  begin
    perform rpc_whatsapp_reservar(5);
    raise exception 'Usuário qualquer não deveria reservar';
  exception when insufficient_privilege then null;
  end;
  reset role;

  -- o robô: chama as RPCs, mas não lê tabelas
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  assert is_servico_mensagens(), 'O robô deveria ser is_servico_mensagens()';
  assert not is_dono(), 'O robô não é administrador';
  assert (select count(*) from mensagens_whatsapp) = 0, 'O robô não deveria enxergar a fila pela tabela';
  assert (select count(*) from clientes) = 0, 'O robô não deveria enxergar clientes';
  begin
    insert into mensagens_whatsapp (cliente_id, texto) values (c1, 'x');
    raise exception 'O robô não deveria gravar direto na tabela';
  exception when insufficient_privilege or others then
    if sqlerrm like 'O robô não deveria%' then raise; end if;
  end;

  -- enfileirar: uma com número válido, uma sem número
  r := rpc_whatsapp_enfileirar(jsonb_build_object('mensagens', jsonb_build_array(
    jsonb_build_object('cliente_id', c1, 'numero', '5511988887777', 'texto', 'Olá, Cliente Zap Um.',
      'itens', jsonb_build_array(jsonb_build_object('tipo','lembrete_vespera','referencia_id',cobr,'data_referencia','2026-11-10'))),
    jsonb_build_object('cliente_id', c2, 'numero', null, 'texto', 'Olá, Cliente Zap Dois.',
      'itens', jsonb_build_array(jsonb_build_object('tipo','atraso','referencia_id',cobr,'data_referencia','2026-11-10')))
  )));
  assert (r->>'enfileiradas')::int = 1 and (r->>'sem_numero')::int = 1, 'Esperava 1 enfileirada e 1 sem número: ' || r::text;

  -- repetir o mesmo aviso: duplicada
  r := rpc_whatsapp_enfileirar(jsonb_build_object('mensagens', jsonb_build_array(
    jsonb_build_object('cliente_id', c1, 'numero', '5511988887777', 'texto', 'Outra vez',
      'itens', jsonb_build_array(
        jsonb_build_object('tipo','lembrete_vespera','referencia_id',cobr,'data_referencia','2026-11-10'),
        jsonb_build_object('tipo','cnh_proxima','referencia_id',c1,'data_referencia','2026-11-10'))))));
  assert (r->>'duplicadas')::int = 1 and (r->>'enfileiradas')::int = 0, 'Mensagem com item repetido deveria ser pulada: ' || r::text;

  -- número inválido vira ignorada
  r := rpc_whatsapp_enfileirar(jsonb_build_object('mensagens', jsonb_build_array(
    jsonb_build_object('cliente_id', c1, 'numero', '123', 'texto', 'Número ruim',
      'itens', jsonb_build_array(jsonb_build_object('tipo','cnh_vencida','referencia_id',c1,'data_referencia','2026-11-10'))))));
  assert (r->>'sem_numero')::int = 1, 'Número inválido deveria virar ignorada: ' || r::text;

  -- sem itens: erro
  begin
    perform rpc_whatsapp_enfileirar(jsonb_build_object('mensagens', jsonb_build_array(
      jsonb_build_object('cliente_id', c1, 'numero', '5511988887777', 'texto', 'Sem itens', 'itens', '[]'::jsonb))));
    raise exception 'Mensagem sem itens deveria ser recusada';
  exception when others then
    if sqlerrm like 'Mensagem sem itens deveria%' then raise; end if;
  end;

  -- reservar: entrega a pendente e não entrega de novo
  lista := rpc_whatsapp_reservar(10);
  assert jsonb_array_length(lista) = 1, 'Deveria haver 1 pendente: ' || lista::text;
  id1 := (lista->0->>'id')::uuid;
  assert lista->0->>'numero' = '5511988887777', 'Número da pendente errado';
  assert jsonb_array_length(rpc_whatsapp_reservar(10)) = 0, 'A reserva não pode entregar a mesma mensagem duas vezes';

  -- falha 1 e 2 voltam para a fila (com espera); a 3ª encerra como 'falhou'
  r := rpc_whatsapp_registrar_resultado(id1, 'falhou', 'Evolution fora do ar');
  assert r->>'status' = 'pendente' and (r->>'tentativas')::int = 1, '1ª falha deveria voltar para a fila: ' || r::text;
  reset role;
  select enviar_apos > now() + interval '25 minutes' into strict st from mensagens_whatsapp where id = id1;
  assert st::boolean, 'A espera após a 1ª falha deveria ser de ~30 min';
  update mensagens_whatsapp set enviar_apos = now() - interval '1 minute' where id = id1;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  perform rpc_whatsapp_reservar(10);
  r := rpc_whatsapp_registrar_resultado(id1, 'falhou', 'Evolution fora do ar');
  assert r->>'status' = 'pendente' and (r->>'tentativas')::int = 2, '2ª falha deveria voltar para a fila: ' || r::text;
  reset role;
  update mensagens_whatsapp set enviar_apos = now() - interval '1 minute' where id = id1;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  perform rpc_whatsapp_reservar(10);
  r := rpc_whatsapp_registrar_resultado(id1, 'falhou', 'Evolution fora do ar');
  assert r->>'status' = 'falhou' and (r->>'tentativas')::int = 3, '3ª falha deveria encerrar: ' || r::text;
  begin
    perform rpc_whatsapp_registrar_resultado(id1, 'enviada', null, 'abc');
    raise exception 'Mensagem encerrada não deveria aceitar novo resultado';
  exception when others then
    if sqlerrm like 'Mensagem encerrada%' then raise; end if;
  end;
  reset role;

  -- envio bem-sucedido
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  r := rpc_whatsapp_enfileirar(jsonb_build_object('mensagens', jsonb_build_array(
    jsonb_build_object('cliente_id', c1, 'numero', '5511988887777', 'texto', 'Pagamento recebido',
      'itens', jsonb_build_array(jsonb_build_object('tipo','recibo_pagamento','referencia_id',cobr,'data_referencia','2026-11-10'))))));
  lista := rpc_whatsapp_reservar(10);
  id1 := (lista->0->>'id')::uuid;
  r := rpc_whatsapp_registrar_resultado(id1, 'enviada', null, 'EVO-123');
  assert r->>'status' = 'enviada', 'Deveria ficar enviada: ' || r::text;
  reset role;
  select count(*) into n from mensagens_whatsapp where id = id1 and status = 'enviada' and enviada_em is not null and evolution_id = 'EVO-123';
  assert n = 1, 'Envio deveria gravar enviada_em e o id da Evolution';

  -- bloqueio: enfileirar pula; bloqueado depois de enfileirada é cancelada na reserva
  update clientes set nao_enviar_whatsapp = true, motivo_bloqueio_whatsapp = 'Pediu ao dono', bloqueio_whatsapp_em = now() where id = c2;
  begin
    update clientes set nao_enviar_whatsapp = true, motivo_bloqueio_whatsapp = null where id = c1;
    raise exception 'Bloqueio sem motivo deveria ser recusado';
  exception when check_violation then null;
  end;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  r := rpc_whatsapp_enfileirar(jsonb_build_object('mensagens', jsonb_build_array(
    jsonb_build_object('cliente_id', c2, 'numero', '5511977776666', 'texto', 'Bloqueado',
      'itens', jsonb_build_array(jsonb_build_object('tipo','portal_acesso','referencia_id',c2,'data_referencia','2026-11-10'))))));
  assert (r->>'bloqueadas')::int = 1, 'Cliente bloqueado deveria ser pulado: ' || r::text;
  reset role;

  update clientes set nao_enviar_whatsapp = false, motivo_bloqueio_whatsapp = null, bloqueio_whatsapp_em = null where id = c2;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  perform rpc_whatsapp_enfileirar(jsonb_build_object('mensagens', jsonb_build_array(
    jsonb_build_object('cliente_id', c2, 'numero', '5511977776666', 'texto', 'Vai ser cancelada',
      'itens', jsonb_build_array(jsonb_build_object('tipo','portal_senha_alterada','referencia_id',c2,'data_referencia','2026-11-10'))))));
  reset role;
  update clientes set nao_enviar_whatsapp = true, motivo_bloqueio_whatsapp = 'Pediu ao dono', bloqueio_whatsapp_em = now() where id = c2;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  assert jsonb_array_length(rpc_whatsapp_reservar(10)) = 0, 'Mensagem de cliente bloqueado não pode ser entregue';
  reset role;
  select count(*) into n from mensagens_whatsapp where cliente_id = c2 and status = 'cancelada';
  assert n = 1, 'A mensagem do cliente bloqueado deveria ser cancelada';

  -- o administrador também chama as RPCs e enxerga a fila pela tabela
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  perform rpc_whatsapp_reservar(1);
  assert (select count(*) from mensagens_whatsapp) >= 4, 'O dono deveria ver o histórico';
  reset role;

  raise notice 'Verificação da base do WhatsApp: OK';
end $$;
rollback;
