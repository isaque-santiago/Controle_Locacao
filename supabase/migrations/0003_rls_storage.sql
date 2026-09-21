-- =====================================================================
-- 0003_rls_storage.sql : RLS em todas as tabelas + buckets privados
-- Sistema de usuário único: qualquer usuário autenticado é o dono.
-- (Desative o cadastro público em Authentication > Providers > Email)
-- =====================================================================
do $$
declare t text;
begin
  foreach t in array array[
    'configuracoes','motos','clientes','contratos','cobrancas','pagamentos',
    'historico_km','itens_manutencao','moto_plano_manutencao','manutencoes',
    'manutencao_itens','documentos_moto','vistorias','vistoria_fotos'
  ] loop
    execute format('alter table %I enable row level security', t);
    execute format(
      'create policy "dono_total" on %I for all to authenticated using (true) with check (true)', t);
  end loop;
end $$;

insert into storage.buckets (id, name, public)
values ('vistorias', 'vistorias', false), ('documentos', 'documentos', false)
on conflict (id) do nothing;

create policy "dono_storage_vistorias" on storage.objects
  for all to authenticated
  using (bucket_id in ('vistorias','documentos'))
  with check (bucket_id in ('vistorias','documentos'));
