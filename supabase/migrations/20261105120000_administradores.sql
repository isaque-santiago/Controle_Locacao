-- =====================================================================
-- 20261105120000_administradores.sql
-- Mais de um administrador. Até aqui `is_dono()` comparava `auth.uid()` com UM UUID fixo,
-- então só uma conta enxergava os dados (qualquer outra entrava no app "sem permissão").
--   * tabela `administradores (user_id)`: quem está nela tem o mesmo acesso do dono;
--   * `is_dono()` passa a consultar a tabela; o nome e as políticas de RLS continuam os mesmos
--     (as políticas apontam para a função, que é redefinida no lugar);
--   * o dono atual é lido da própria função antiga (cada projeto, dev ou produção, tem o seu UUID)
--     e já entra na tabela, então nada muda para ele;
--   * a tabela só pode ser alterada pelo SQL Editor (não há política de escrita para o app);
--     cada usuário enxerga apenas a própria linha.
-- Compatível com a versão anterior do app: não muda nenhuma tabela, view ou RPC existente.
--
-- Para dar acesso de administrador a alguém (depois de criar o usuário em Authentication > Users):
--   insert into administradores (user_id) select id from auth.users where email = 'fulano@exemplo.com';
-- Para tirar o acesso:
--   delete from administradores where user_id = (select id from auth.users where email = 'fulano@exemplo.com');
-- =====================================================================

create table if not exists administradores (
  user_id   uuid primary key,
  criado_em timestamptz not null default now()
);

alter table administradores enable row level security;
drop policy if exists "ver_o_proprio" on administradores;
create policy "ver_o_proprio" on administradores for select to authenticated using (user_id = auth.uid());
revoke all on administradores from anon, authenticated;
grant select on administradores to authenticated;

-- Move o dono atual (UUID da função antiga) para a tabela e redefine is_dono().
do $$
declare
  v_corpo text := pg_get_functiondef('public.is_dono()'::regprocedure);
  v_dono  text := substring(v_corpo from '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}');
begin
  if v_dono is not null then
    insert into administradores (user_id) values (v_dono::uuid) on conflict (user_id) do nothing;
  end if;
  if not exists (select 1 from administradores) then
    raise exception 'Não foi possível identificar o dono atual em is_dono(); nada foi alterado.';
  end if;
end $$;

create or replace function is_dono() returns boolean
language sql stable security invoker set search_path = public as $$
  select exists (select 1 from administradores where user_id = auth.uid());
$$;

notify pgrst, 'reload schema';
