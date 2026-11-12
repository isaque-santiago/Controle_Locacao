-- =====================================================================
-- 20261112150000_pedidos_senha_portal.sql : «esqueci minha senha» do portal do locatário (pendência da Fase 7)
--
-- O e-mail do portal é fictício (<cpf>@portal.example.com): o Supabase não tem para onde mandar um link de redefinição. Decisão do dono
-- (12/11/2026): o locatário informa o CPF na tela de login e isso registra um PEDIDO, que aparece para o dono (Dashboard e aba Portal da
-- ficha do cliente); o dono gera a senha nova e entrega pessoalmente, como já faz. Nada é enviado ao locatário.
--   * `pedidos_senha_portal`: cada pedido, `aberto`, `atendido` (o dono gerou a senha nova) ou `dispensado` (o dono descartou).
--     No máximo UM pedido aberto por cliente, então repetir o pedido não acumula nada. Só o dono lê e altera (RLS);
--   * `rpc_portal_pedir_redefinicao(p_cpf)`: chamada SEM login (papel `anon`) pela tela «Esqueci minha senha». Só registra pedido para CPF que
--     tem acesso ao portal e a resposta é SEMPRE a mesma (`{"ok": true}`), para não revelar a ninguém quais CPFs são clientes.
-- Compatível com a versão anterior do app: só tabela e função novas.
-- =====================================================================

create table if not exists pedidos_senha_portal (
  id          uuid primary key default gen_random_uuid(),
  cliente_id  uuid not null references clientes(id) on delete cascade,
  status      text not null default 'aberto' check (status in ('aberto', 'atendido', 'dispensado')),
  pedido_em   timestamptz not null default now(),
  fechado_em  timestamptz,
  check (status = 'aberto' or fechado_em is not null)
);
create unique index if not exists uq_pedido_senha_aberto_por_cliente on pedidos_senha_portal (cliente_id) where status = 'aberto';
create index if not exists ix_pedidos_senha_portal_cliente on pedidos_senha_portal (cliente_id, pedido_em desc);

alter table pedidos_senha_portal enable row level security;
drop policy if exists "dono_total" on pedidos_senha_portal;
create policy "dono_total" on pedidos_senha_portal for all to authenticated using (is_dono()) with check (is_dono());

create or replace function rpc_portal_pedir_redefinicao(p_cpf text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_cpf     text := regexp_replace(coalesce(p_cpf, ''), '\D', '', 'g');
  v_cliente uuid;
begin
  if char_length(v_cpf) = 11 then
    select id into v_cliente from clientes where cpf = v_cpf and auth_user_id is not null;
    if found then
      insert into pedidos_senha_portal (cliente_id) values (v_cliente) on conflict (cliente_id) where status = 'aberto' do nothing;
    end if;
  end if;
  -- Mesma resposta para CPF inválido, desconhecido, sem acesso ou já pedido: ninguém descobre quem é cliente.
  return jsonb_build_object('ok', true);
end $$;

revoke all on function rpc_portal_pedir_redefinicao(text) from public;
grant execute on function rpc_portal_pedir_redefinicao(text) to anon, authenticated;
