-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar a migration
--   20261106140000_whatsapp_painel.sql
-- Verifica: o usuário de serviço e o administrador registram a rodada; um usuário qualquer é recusado; estado vazio é recusado.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  dono     uuid;
  robo     uuid := gen_random_uuid();
  estranho uuid := gen_random_uuid();
  c        configuracoes%rowtype;
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'Precisa existir um administrador (dono)';
  insert into servico_mensagens (user_id) values (robo);

  perform set_config('request.jwt.claim.sub', estranho::text, true);
  set local role authenticated;
  begin
    perform rpc_whatsapp_registrar_rodada('open', '{}'::jsonb);
    raise exception 'Usuário qualquer não deveria registrar a rodada';
  exception when insufficient_privilege then null;
  end;
  reset role;

  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  perform rpc_whatsapp_registrar_rodada('close', '{"ativo": true}'::jsonb);
  begin
    perform rpc_whatsapp_registrar_rodada('  ');
    raise exception 'Estado vazio deveria ser recusado';
  exception when others then
    if sqlerrm like 'Estado vazio%' then raise; end if;
  end;
  reset role;
  select * into c from configuracoes where id = 1;
  assert c.whatsapp_ultimo_estado = 'close' and c.whatsapp_ultima_rodada_em is not null
     and c.whatsapp_ultimo_resumo->>'ativo' = 'true', 'A rodada do robô deveria ficar registrada';

  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  perform rpc_whatsapp_registrar_rodada('open');
  reset role;
  assert (select whatsapp_ultimo_estado from configuracoes where id = 1) = 'open', 'O administrador também registra';

  raise notice 'Verificação do painel do WhatsApp: OK';
end $$;
rollback;
