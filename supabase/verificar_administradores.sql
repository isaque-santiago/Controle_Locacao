-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar a migration
--   20261105120000_administradores.sql
-- Verifica: o dono antigo continua administrador, uma conta que não está na tabela não tem acesso,
--   quem entra na tabela passa a enxergar os dados, o app (role authenticated) não escreve na tabela
--   e cada usuário só enxerga a própria linha.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  dono   uuid;
  novo   uuid := gen_random_uuid();
  n      int;
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'O dono antigo deveria estar em administradores';
  insert into motos (placa, marca, modelo, km_atual) values ('ADM0A00', 'Teste', 'Administradores', 0);

  -- como o dono antigo
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  assert is_dono(), 'O dono antigo deveria continuar sendo is_dono()';
  assert (select count(*) from motos where placa = 'ADM0A00') = 1, 'O dono deveria ver a moto';
  reset role;

  -- uma conta que não está na tabela
  perform set_config('request.jwt.claim.sub', novo::text, true);
  set local role authenticated;
  assert not is_dono(), 'Conta fora da tabela não pode ser is_dono()';
  assert (select count(*) from motos) = 0, 'Conta fora da tabela não pode ver dados';
  begin
    insert into administradores (user_id) values (novo);
    raise exception 'O app não deveria conseguir inserir em administradores';
  exception when insufficient_privilege or others then
    if sqlerrm like 'O app não deveria%' then raise; end if;
  end;
  reset role;

  -- passa a administrador pelo SQL Editor
  insert into administradores (user_id) values (novo);
  perform set_config('request.jwt.claim.sub', novo::text, true);
  set local role authenticated;
  assert is_dono(), 'Quem entra na tabela deveria ser is_dono()';
  assert (select count(*) from motos where placa = 'ADM0A00') = 1, 'O novo administrador deveria ver a moto';
  select count(*) into n from administradores;
  assert n = 1, 'Cada usuário deveria ver só a própria linha';
  reset role;

  -- sai da tabela, perde o acesso
  delete from administradores where user_id = novo;
  perform set_config('request.jwt.claim.sub', novo::text, true);
  set local role authenticated;
  assert not is_dono(), 'Quem sai da tabela deveria perder o acesso';
  reset role;

  raise notice 'Verificação dos administradores: OK';
end $$;
rollback;
