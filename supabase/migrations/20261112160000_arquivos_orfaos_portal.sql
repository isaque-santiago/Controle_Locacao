-- =====================================================================
-- 20261112160000_arquivos_orfaos_portal.sql : lista os arquivos órfãos enviados pelo portal (pendência da Fase 7)
--
-- O locatário envia as fotos (troca de óleo) e o comprovante (documento) ao Storage ANTES de registrar a operação pela RPC. Se o registro
-- falha (km regredido, troca duplicada, documento já regularizado...), o arquivo fica no Storage sem nenhuma linha que o referencie: um
-- arquivo órfão. Decisão do dono (12/11/2026): a limpeza é um botão em Configurações, que lista e pede confirmação antes de apagar.
--   * `rpc_listar_arquivos_orfaos(p_horas)`: só o dono. Devolve os arquivos (no máximo 1000, os mais antigos primeiro) que
--       - estão no bucket `trocas_oleo` e não são a foto do painel nem a nota fiscal de nenhuma troca; ou
--       - estão na pasta `portal/` do bucket `documentos` (a dos envios do locatário) e não são o comprovante de nenhum envio
--         (inclusive recusado) nem o arquivo de nenhum documento da moto;
--     e foram criados há mais de `p_horas` horas (padrão 24), para nunca pegar um envio que ainda está sendo registrado.
--     Os buckets `vistorias` e o resto de `documentos` (arquivos do próprio dono) NÃO entram: a lista só traz o que se sabe que é do portal.
--   * Quem apaga é o app, pela API do Storage (que remove também o arquivo, não só a linha), com a sessão do dono: a lista é calculada de
--     novo na hora de apagar, nunca vem do navegador.
-- Compatível com a versão anterior do app: só uma função nova.
-- =====================================================================

create or replace function rpc_listar_arquivos_orfaos(p_horas int default 24) returns jsonb
language plpgsql stable security definer set search_path = public as $$
begin
  if not is_dono() then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
  if p_horas is null or p_horas < 1 then
    raise exception 'Informe pelo menos 1 hora de idade para os arquivos.';
  end if;

  return coalesce((
    select jsonb_agg(jsonb_build_object(
             'bucket', x.bucket_id, 'caminho', x.name, 'tamanho', x.tamanho, 'criado_em', x.created_at
           ) order by x.created_at, x.name)
      from (
        select o.bucket_id, o.name, o.created_at, coalesce((o.metadata->>'size')::bigint, 0) as tamanho
          from storage.objects o
         where o.created_at < now() - make_interval(hours => p_horas)
           and o.name not like '%.emptyFolderPlaceholder'
           and (
             (o.bucket_id = 'trocas_oleo'
              and not exists (select 1 from trocas_oleo t where o.name in (t.foto_painel_path, t.nota_fiscal_path)))
             or
             (o.bucket_id = 'documentos' and o.name like 'portal/%'
              and not exists (select 1 from documento_comprovantes c where c.arquivo_path = o.name)
              and not exists (select 1 from documentos_moto d where d.arquivo_path = o.name))
           )
         order by o.created_at, o.name
         limit 1000
      ) x
  ), '[]'::jsonb);
end $$;

revoke all on function rpc_listar_arquivos_orfaos(int) from public, anon;
grant execute on function rpc_listar_arquivos_orfaos(int) to authenticated;
