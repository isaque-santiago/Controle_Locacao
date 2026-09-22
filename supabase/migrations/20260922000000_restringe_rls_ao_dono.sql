-- =====================================================================
-- 20260922000000_restringe_rls_ao_dono.sql
-- Fecha o gap de segurança das políticas "dono_total"/"dono_storage_*":
-- antes usavam using(true)/with check(true), ou seja, QUALQUER usuário
-- autenticado tinha acesso total — não só o dono. Como o cadastro público
-- do Supabase é desativado manualmente (Authentication > Providers >
-- Email), essa política era a única trava real contra uma conta nova
-- conseguir se autenticar e ter acesso irrestrito.
--
-- Esta migration não muda nenhum comportamento para o dono (mesmo UUID
-- que já usa o app hoje); só fecha o acesso para qualquer outra conta.
-- =====================================================================

create or replace function is_dono() returns boolean
language sql stable security invoker set search_path = public as $$
  select auth.uid() = '9ca7a878-9625-4be7-a325-016d375028f3'::uuid;
$$;

do $$
declare t text;
begin
  foreach t in array array[
    'configuracoes','motos','clientes','contratos','cobrancas','pagamentos',
    'historico_km','itens_manutencao','moto_plano_manutencao','manutencoes',
    'manutencao_itens','documentos_moto','vistorias','vistoria_fotos'
  ] loop
    execute format('drop policy if exists "dono_total" on %I', t);
    execute format(
      'create policy "dono_total" on %I for all to authenticated using (is_dono()) with check (is_dono())', t);
  end loop;
end $$;

drop policy if exists "dono_storage_vistorias" on storage.objects;
create policy "dono_storage_vistorias" on storage.objects
  for all to authenticated
  using (bucket_id in ('vistorias','documentos') and is_dono())
  with check (bucket_id in ('vistorias','documentos') and is_dono());
