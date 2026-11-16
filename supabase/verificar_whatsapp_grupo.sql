-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar a migration
--   20261117130000_whatsapp_grupo.sql
-- Verifica: o ID do grupo só aceita o formato `...@g.us` e é único por cliente; a fila aceita grupo (pendente), recusa destino
--   inválido e marca como `ignorada` o cliente sem grupo, com o motivo; `rpc_whatsapp_grupos_clientes` devolve só quem tem grupo;
--   `rpc_whatsapp_gravar_grupos` guarda a lista exata (o que saiu some) e ignora IDs que não são de grupo; o dono lê a lista;
--   quem não é dono nem usuário de serviço é barrado.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  dono uuid;
  u1   uuid := gen_random_uuid();
  c1   uuid;
  c2   uuid;
  r    jsonb;
  n    int;
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'Precisa existir um administrador (dono)';

  insert into clientes (nome, cpf, whatsapp_grupo_id) values ('Com Grupo', '90000000071', '120363025246125486@g.us') returning id into c1;
  insert into clientes (nome, cpf) values ('Sem Grupo', '90000000072') returning id into c2;

  -- formato e unicidade
  begin
    update clientes set whatsapp_grupo_id = '5511988887777' where id = c2;
    raise exception 'Um número individual não deveria ser aceito como grupo';
  exception when check_violation then null;
  end;
  begin
    update clientes set whatsapp_grupo_id = '120363025246125486@g.us' where id = c2;
    raise exception 'O mesmo grupo não deveria servir a dois clientes';
  exception when unique_violation then null;
  end;

  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;

  -- fila: grupo vira pendente; sem destino e destino inválido ficam ignorados com o motivo
  r := rpc_whatsapp_enfileirar(jsonb_build_object('mensagens', jsonb_build_array(
    jsonb_build_object('cliente_id', c1, 'numero', '120363025246125486@g.us', 'texto', 'Olá',
      'itens', jsonb_build_array(jsonb_build_object('tipo', 'atraso', 'referencia_id', gen_random_uuid(), 'data_referencia', '2026-11-17'))),
    jsonb_build_object('cliente_id', c2, 'numero', null, 'texto', 'Olá',
      'itens', jsonb_build_array(jsonb_build_object('tipo', 'atraso', 'referencia_id', gen_random_uuid(), 'data_referencia', '2026-11-17'))),
    jsonb_build_object('cliente_id', c2, 'numero', 'lixo@g.us', 'texto', 'Olá',
      'itens', jsonb_build_array(jsonb_build_object('tipo', 'atraso', 'referencia_id', gen_random_uuid(), 'data_referencia', '2026-11-17'))))));
  assert (r->>'enfileiradas')::int = 1 and (r->>'sem_numero')::int = 2, 'Deveria enfileirar 1 e ignorar 2: ' || r::text;
  assert (select status from mensagens_whatsapp where cliente_id = c1) = 'pendente', 'A mensagem do grupo deveria ficar pendente';
  assert (select numero from mensagens_whatsapp where cliente_id = c1) = '120363025246125486@g.us', 'O destino deveria ser o grupo';
  assert (select count(*) from mensagens_whatsapp where cliente_id = c2 and status = 'ignorada' and erro like 'Cliente sem grupo%') = 1,
         'Sem grupo deveria ficar ignorada, com o motivo';
  assert (select count(*) from mensagens_whatsapp where cliente_id = c2 and status = 'ignorada' and erro like '%inválido%') = 1,
         'Destino inválido deveria ficar ignorado, com o motivo';

  -- grupos dos clientes
  r := rpc_whatsapp_grupos_clientes();
  assert r->>(c1::text) = '120363025246125486@g.us' and not (r ? (c2::text)), 'Só o cliente com grupo deveria aparecer';

  -- lista de grupos da instância
  n := rpc_whatsapp_gravar_grupos(jsonb_build_object('grupos', jsonb_build_array(
    jsonb_build_object('id', '120363025246125486@g.us', 'nome', 'Com Grupo - ABC1D23', 'participantes', 5),
    jsonb_build_object('id', '120363111111111111@g.us', 'nome', ' ', 'participantes', null),
    jsonb_build_object('id', '5511988887777@s.whatsapp.net', 'nome', 'não é grupo'))));
  assert n = 2, 'Deveriam ficar 2 grupos';
  assert (select nome from whatsapp_grupos where id = '120363111111111111@g.us') = '(sem nome)', 'Nome vazio vira (sem nome)';
  n := rpc_whatsapp_gravar_grupos(jsonb_build_object('grupos', jsonb_build_array(
    jsonb_build_object('id', '120363025246125486@g.us', 'nome', 'Novo nome', 'participantes', 4))));
  assert n = 1 and (select count(*) from whatsapp_grupos) = 1, 'Quem saiu da lista deveria sumir';
  assert (select count(*) from whatsapp_grupos) = 1, 'O dono deveria ler a lista';
  reset role;

  -- quem não é dono nem usuário de serviço é barrado
  perform set_config('request.jwt.claim.sub', u1::text, true);
  set local role authenticated;
  begin
    perform rpc_whatsapp_gravar_grupos(jsonb_build_object('grupos', '[]'::jsonb));
    raise exception 'Um usuário comum não deveria gravar grupos';
  exception when insufficient_privilege then null;
  end;
  begin
    perform rpc_whatsapp_grupos_clientes();
    raise exception 'Um usuário comum não deveria ler os grupos dos clientes';
  exception when insufficient_privilege then null;
  end;
  reset role;
end $$;
rollback;
