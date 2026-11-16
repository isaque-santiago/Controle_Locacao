-- Acesso padrão do locatário (16/11/2026): o e-mail deixa de ser <cpf>@portal.example.com e passa a ser
-- nome.sobrenome@locadora.com (com sufixo para homônimos). Quem escolhe o e-mail é a Edge Function
-- criar-locatario, que agora o envia no payload; a RPC deixa de derivá-lo do CPF.
-- Só o dono chama. Só aceita e-mail do domínio de acesso (locadora.com).

create or replace function rpc_vincular_locatario(payload jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_cliente_id uuid := (payload->>'cliente_id')::uuid;
  v_email      text := lower(trim(coalesce(payload->>'email', '')));
  v_user_id    uuid;
begin
  if not is_dono() then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;

  if not exists (select 1 from clientes where id = v_cliente_id) then
    raise exception 'Cliente não encontrado.';
  end if;
  if v_email not like '%@locadora.com' then
    raise exception 'E-mail de acesso inválido.';
  end if;

  select id into v_user_id from auth.users where lower(email) = v_email;
  if v_user_id is null then
    raise exception 'Não existe usuário com o e-mail %. Crie-o antes em Authentication > Users no Supabase.', v_email;
  end if;
  if exists (select 1 from clientes where auth_user_id = v_user_id and id <> v_cliente_id) then
    raise exception 'Este usuário já está vinculado a outro cliente.';
  end if;

  update clientes set auth_user_id = v_user_id where id = v_cliente_id;
  return jsonb_build_object('cliente_id', v_cliente_id, 'email', v_email);
end $$;
