-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar a migration
--   20261111120000_whatsapp_executor_n8n.sql
-- Verifica: o portão da janela e o envio ligado controlam `rpc_whatsapp_reservar`; o modo teste vem resolvido do banco (número
--   de teste, aviso «[TESTE]» e nada reservado sem número de teste); o resultado `enviada` guarda `teste:<id>` em modo teste e o
--   id da Evolution fora dele; `rpc_whatsapp_registrar_preparo` só aceita usuário de serviço e administrador, recusa portão
--   além de 30 minutos e grava o batimento.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  dono     uuid;
  robo     uuid := gen_random_uuid();
  estranho uuid := gen_random_uuid();
  cli      uuid;
  cobr     uuid := gen_random_uuid();
  lista    jsonb;
  m        jsonb;
  id1      uuid;
  c        configuracoes%rowtype;
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'Precisa existir um administrador (dono)';
  insert into servico_mensagens (user_id) values (robo);
  insert into clientes (nome, cpf, whatsapp) values ('Cliente Executor', '90000000031', '(11) 98888-7777') returning id into cli;

  -- um usuário qualquer não registra o preparo
  perform set_config('request.jwt.claim.sub', estranho::text, true);
  set local role authenticated;
  begin
    perform rpc_whatsapp_registrar_preparo(now() + interval '10 minutes', '{}'::jsonb);
    raise exception 'Usuário qualquer não deveria registrar o preparo';
  exception when insufficient_privilege then null;
  end;
  reset role;

  -- o robô enfileira uma mensagem
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  perform rpc_whatsapp_enfileirar(jsonb_build_object('mensagens', jsonb_build_array(
    jsonb_build_object('cliente_id', cli, 'numero', '5511988887777', 'texto', 'Olá, Cliente!',
      'itens', jsonb_build_array(jsonb_build_object('tipo','atraso','referencia_id',cobr,'data_referencia', hoje_br()))))));

  -- portão: sem o envio ligado, sem portão aberto ou com o portão vencido, nada é reservado
  reset role;
  update configuracoes set whatsapp_ativo = false, whatsapp_modo_teste = false, whatsapp_envio_liberado_ate = now() + interval '10 minutes' where id = 1;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  assert rpc_whatsapp_reservar(5) = '[]'::jsonb, 'Com o envio desligado nada deveria ser reservado';
  reset role;
  update configuracoes set whatsapp_ativo = true, whatsapp_envio_liberado_ate = null where id = 1;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  assert rpc_whatsapp_reservar(5) = '[]'::jsonb, 'Sem portão aberto nada deveria ser reservado';
  reset role;
  update configuracoes set whatsapp_envio_liberado_ate = now() - interval '1 minute' where id = 1;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  assert rpc_whatsapp_reservar(5) = '[]'::jsonb, 'Portão vencido: nada deveria ser reservado';
  reset role;
  assert (select count(*) from mensagens_whatsapp where cliente_id = cli and reservada_ate is not null) = 0, 'Nada deveria ter sido reservado';

  -- envio real (modo teste desligado) com o portão aberto: números e texto originais
  update configuracoes set whatsapp_envio_liberado_ate = now() + interval '10 minutes' where id = 1;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  lista := rpc_whatsapp_reservar(5);
  reset role;
  assert jsonb_array_length(lista) = 1, 'Com o portão aberto deveria haver 1 mensagem: ' || lista::text;
  m := lista->0;
  id1 := (m->>'id')::uuid;
  assert m->>'numero' = '5511988887777' and m->>'texto' = 'Olá, Cliente!' and (m->>'tentativas')::int = 0, 'Campos antigos devem continuar';
  assert m->>'numero_envio' = '5511988887777' and m->>'texto_envio' = 'Olá, Cliente!' and (m->>'modo_teste')::boolean = false,
    'Fora do modo teste o envio usa o número e o texto do cliente: ' || m::text;

  -- registrar o resultado fora do modo teste guarda o id da Evolution
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  perform rpc_whatsapp_registrar_resultado(id1, 'enviada', null, 'EVO-1');
  reset role;
  assert (select evolution_id from mensagens_whatsapp where id = id1) = 'EVO-1', 'Fora do modo teste guarda o id da Evolution';

  -- modo teste sem número de teste: nada é reservado, mesmo com o portão aberto
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  perform rpc_whatsapp_enfileirar(jsonb_build_object('mensagens', jsonb_build_array(
    jsonb_build_object('cliente_id', cli, 'numero', '5511988887777', 'texto', 'Segunda mensagem',
      'itens', jsonb_build_array(jsonb_build_object('tipo','cnh_vencida','referencia_id',cli,'data_referencia', hoje_br()))))));
  reset role;
  update configuracoes set whatsapp_modo_teste = true, whatsapp_numero_teste = null where id = 1;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  assert rpc_whatsapp_reservar(5) = '[]'::jsonb, 'Modo teste sem número de teste não deveria reservar';
  reset role;

  -- modo teste com número de teste: número de teste e aviso resolvidos no banco
  update configuracoes set whatsapp_numero_teste = '5511977776666' where id = 1;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  lista := rpc_whatsapp_reservar(5);
  reset role;
  m := lista->0;
  assert jsonb_array_length(lista) = 1 and (m->>'modo_teste')::boolean, 'Deveria reservar 1 em modo teste: ' || lista::text;
  assert m->>'numero_envio' = '5511977776666', 'Em modo teste vai para o número de teste';
  assert m->>'texto_envio' like '[TESTE] Esta mensagem iria para 55119****7777.' || E'\n\n' || 'Segunda mensagem', 'Aviso de teste: ' || (m->>'texto_envio');
  assert m->>'numero' = '5511988887777' and m->>'texto' = 'Segunda mensagem', 'Os campos originais não mudam';
  id1 := (m->>'id')::uuid;

  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  perform rpc_whatsapp_registrar_resultado(id1, 'enviada', null, 'EVO-2');
  reset role;
  assert (select evolution_id from mensagens_whatsapp where id = id1) = 'teste:' || id1::text, 'Em modo teste guarda teste:<id>';

  -- cliente bloqueado depois de enfileirada: cancelada na reserva, com o portão aberto
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  perform rpc_whatsapp_enfileirar(jsonb_build_object('mensagens', jsonb_build_array(
    jsonb_build_object('cliente_id', cli, 'numero', '5511988887777', 'texto', 'Vai ser cancelada',
      'itens', jsonb_build_array(jsonb_build_object('tipo','portal_acesso','referencia_id',cli,'data_referencia', hoje_br()))))));
  reset role;
  update clientes set nao_enviar_whatsapp = true, motivo_bloqueio_whatsapp = 'Pediu ao dono', bloqueio_whatsapp_em = now() where id = cli;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  assert rpc_whatsapp_reservar(5) = '[]'::jsonb, 'Cliente bloqueado não deveria ser entregue';
  reset role;
  assert (select count(*) from mensagens_whatsapp where cliente_id = cli and status = 'cancelada') = 1, 'A mensagem do bloqueado deveria ser cancelada';

  -- registrar o preparo: o robô grava o portão e o batimento; mais de 30 minutos é recusado; nulo fecha o portão
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  perform rpc_whatsapp_registrar_preparo(now() + interval '25 minutes', '{"fila": {"enfileiradas": 2}}'::jsonb);
  begin
    perform rpc_whatsapp_registrar_preparo(now() + interval '31 minutes', null);
    raise exception 'Portão além de 30 minutos deveria ser recusado';
  exception when others then
    if sqlerrm like 'Portão além%' then raise; end if;
  end;
  reset role;
  select * into c from configuracoes where id = 1;
  assert c.whatsapp_envio_liberado_ate > now() + interval '20 minutes' and c.whatsapp_ultimo_enfileiramento_em is not null
     and c.whatsapp_ultimo_preparo->'fila'->>'enfileiradas' = '2', 'O preparo deveria gravar portão, batimento e resumo';
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  perform rpc_whatsapp_registrar_preparo(null, null);
  reset role;
  assert (select whatsapp_envio_liberado_ate from configuracoes where id = 1) is null, 'Nulo deveria fechar o portão';

  -- o administrador também registra o preparo
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  perform rpc_whatsapp_registrar_preparo(now() + interval '5 minutes', '{}'::jsonb);
  reset role;
  assert (select whatsapp_envio_liberado_ate from configuracoes where id = 1) is not null, 'O administrador também registra o preparo';

  raise notice 'Verificação do executor n8n: OK';
end $$;
rollback;
