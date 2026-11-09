-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar a migration
--   20261109120000_portal_eventos_senha.sql
-- Verifica: o locatário registra a troca da própria senha (no máximo um evento a cada 10 minutos); quem não é locatário é
--   recusado; só o dono registra a redefinição de senha de um cliente; o locatário não lê a tabela de eventos; e
--   `rpc_whatsapp_dados` entrega o evento mais recente de cada cliente em `portal` (e continua entregando o acesso novo).
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  dono     uuid;
  robo     uuid := gen_random_uuid();
  loc_user uuid := gen_random_uuid();
  estranho uuid := gen_random_uuid();
  cli      uuid;
  cli2     uuid;
  r        jsonb;
  n        int;
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'Precisa existir um administrador (dono)';

  insert into auth.users (id, email, created_at) values (loc_user, 'portal-eventos-teste@portal.example.com', now());
  insert into clientes (nome, cpf, whatsapp, auth_user_id) values ('Locatario Portal', '90000000021', '(11) 98888-7777', loc_user) returning id into cli;
  insert into clientes (nome, cpf) values ('Outro Cliente', '90000000022') returning id into cli2;
  insert into servico_mensagens (user_id) values (robo);

  -- um usuário sem vínculo com cliente é recusado
  perform set_config('request.jwt.claim.sub', estranho::text, true);
  set local role authenticated;
  begin
    perform rpc_portal_registrar_troca_senha();
    raise exception 'Usuário sem vínculo não deveria registrar a troca';
  exception when insufficient_privilege then null;
  end;
  begin
    perform rpc_portal_registrar_redefinicao_senha(cli);
    raise exception 'Usuário qualquer não deveria registrar a redefinição';
  exception when insufficient_privilege then null;
  end;
  reset role;

  -- o locatário registra a troca da própria senha; repetir em seguida não cria outro evento
  perform set_config('request.jwt.claim.sub', loc_user::text, true);
  set local role authenticated;
  perform rpc_portal_registrar_troca_senha();
  perform rpc_portal_registrar_troca_senha();
  assert (select count(*) from portal_eventos) = 0, 'O locatário não deveria ler a tabela de eventos';
  begin
    perform rpc_portal_registrar_redefinicao_senha(cli);
    raise exception 'O locatário não deveria registrar redefinição';
  exception when insufficient_privilege then null;
  end;
  reset role;
  select count(*) into n from portal_eventos where cliente_id = cli and origem = 'locatario';
  assert n = 1, 'Deveria haver 1 evento do locatário (limite de 10 minutos), veio ' || n;

  -- o dono registra a redefinição; o dono não é locatário
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  perform rpc_portal_registrar_redefinicao_senha(cli);
  perform rpc_portal_registrar_redefinicao_senha(cli2);
  assert (select count(*) from portal_eventos) = 3, 'O dono deveria ler os eventos';
  begin
    perform rpc_portal_registrar_troca_senha();
    raise exception 'O dono não deveria registrar como locatário';
  exception when insufficient_privilege then null;
  end;
  begin
    perform rpc_portal_registrar_redefinicao_senha(gen_random_uuid());
    raise exception 'Cliente inexistente deveria ser recusado';
  exception when others then
    if sqlerrm like 'Cliente inexistente%' then raise; end if;
  end;
  reset role;

  -- a leitura do envio: um evento de senha por cliente (o mais recente) e o acesso novo continua vindo
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  r := rpc_whatsapp_dados(hoje_br());
  reset role;
  assert (select count(*) from jsonb_array_elements(r->'portal') x
           where x->>'tipo' = 'portal_senha_alterada' and x->>'cliente_id' = cli::text) = 1,
    'Deveria vir um só evento de senha do primeiro cliente: ' || (r->'portal')::text;
  assert (select count(*) from jsonb_array_elements(r->'portal') x
           where x->>'tipo' = 'portal_senha_alterada' and x->>'cliente_id' = cli2::text
             and x->>'ocorrido_em' = hoje_br()::text) = 1, 'Evento do segundo cliente com a data de hoje';
  assert (select count(*) from jsonb_array_elements(r->'portal') x
           where x->>'tipo' = 'portal_acesso' and x->>'cliente_id' = cli::text) = 1, 'O acesso novo deveria continuar vindo';
  assert (select (x->>'referencia_id')::uuid from jsonb_array_elements(r->'portal') x
           where x->>'tipo' = 'portal_senha_alterada' and x->>'cliente_id' = cli::text)
         in (select id from portal_eventos where cliente_id = cli), 'O evento entregue deveria ser um dos eventos do cliente';

  raise notice 'Verificação dos eventos de senha do portal: OK';
end $$;
rollback;
