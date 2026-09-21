-- Garante que usuários autenticados possam usar os objetos protegidos por RLS.
-- RLS continua decidindo quais linhas ficam acessíveis; nenhuma permissão é
-- concedida ao papel anon.

grant usage on schema public to authenticated;

grant select, insert, update, delete
  on all tables in schema public
  to authenticated;

grant usage, select
  on all sequences in schema public
  to authenticated;

grant execute
  on all functions in schema public
  to authenticated;

-- Mantém as mesmas permissões para tabelas, sequências e funções criadas por
-- migrations futuras executadas pelo papel postgres.
alter default privileges for role postgres in schema public
  grant select, insert, update, delete on tables to authenticated;

alter default privileges for role postgres in schema public
  grant usage, select on sequences to authenticated;

alter default privileges for role postgres in schema public
  grant execute on functions to authenticated;
