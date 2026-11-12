-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar a migration
--   20261112150000_pedidos_senha_portal.sql
-- Verifica: sem login (anon) o pedido por CPF registra UM pedido aberto para quem tem acesso ao portal; repetir não duplica; CPF inválido,
--   desconhecido ou de cliente sem acesso não registra nada e a resposta é a mesma; o anon e o locatário não leem a tabela; o dono lê,
--   atende e dispensa; depois de fechado, um novo pedido volta a abrir.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  dono      uuid;
  u1        uuid := gen_random_uuid();
  cli1      uuid;
  cli_sem   uuid;
  r1 jsonb; r2 jsonb; r3 jsonb; r4 jsonb;
  n         int;
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'Precisa existir um administrador (dono)';

  insert into auth.users (id, email, created_at) values (u1, 'cpf-senha@portal.example.com', now());
  insert into clientes (nome, cpf, auth_user_id) values ('Com Acesso', '90000000061', u1) returning id into cli1;
  insert into clientes (nome, cpf) values ('Sem Acesso', '90000000062') returning id into cli_sem;

  -- sem login: pede por CPF com e sem pontuação, e todas as respostas são iguais
  set local role anon;
  r1 := rpc_portal_pedir_redefinicao('900.000.000-61');
  r2 := rpc_portal_pedir_redefinicao('90000000061');       -- repetido
  r3 := rpc_portal_pedir_redefinicao('90000000099');       -- desconhecido
  r4 := rpc_portal_pedir_redefinicao('123');               -- inválido
  perform rpc_portal_pedir_redefinicao('90000000062');     -- cliente sem acesso ao portal
  perform rpc_portal_pedir_redefinicao(null);
  begin
    perform count(*) from pedidos_senha_portal;
    raise exception 'O anon não deveria ler a tabela';
  exception when insufficient_privilege then null;
  end;
  reset role;
  assert r1 = r2 and r2 = r3 and r3 = r4 and r1->>'ok' = 'true', 'A resposta deveria ser sempre a mesma';
  assert (select count(*) from pedidos_senha_portal where cliente_id = cli1 and status = 'aberto') = 1, 'Deveria haver um único pedido aberto';
  assert (select count(*) from pedidos_senha_portal where cliente_id = cli_sem) = 0, 'Cliente sem acesso não deveria ter pedido';
  assert (select count(*) from pedidos_senha_portal) = 1, 'Só o cliente com acesso deveria ter pedido';

  -- o locatário não lê a tabela
  perform set_config('request.jwt.claim.sub', u1::text, true);
  set local role authenticated;
  select count(*) into n from pedidos_senha_portal;
  reset role;
  assert n = 0, 'O locatário não deveria enxergar pedidos';

  -- o dono lê, atende e o pedido seguinte volta a abrir
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  select count(*) into n from pedidos_senha_portal;
  assert n = 1, 'O dono deveria ler o pedido';
  update pedidos_senha_portal set status = 'atendido', fechado_em = now() where cliente_id = cli1 and status = 'aberto';
  begin
    update pedidos_senha_portal set status = 'dispensado', fechado_em = null where cliente_id = cli1;
    raise exception 'Fechar sem data deveria ser recusado';
  exception when check_violation then null;
  end;
  reset role;

  set local role anon;
  perform rpc_portal_pedir_redefinicao('90000000061');
  reset role;
  assert (select count(*) from pedidos_senha_portal where cliente_id = cli1 and status = 'aberto') = 1, 'Depois de atendido, um novo pedido deveria abrir';
  assert (select count(*) from pedidos_senha_portal where cliente_id = cli1) = 2, 'O histórico deveria ter os dois pedidos';

  raise notice 'Verificação dos pedidos de senha do portal: OK';
end $$;
rollback;
