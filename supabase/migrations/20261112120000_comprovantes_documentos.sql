-- =====================================================================
-- 20261112120000_comprovantes_documentos.sql : o locatário envia o comprovante de documento da moto pelo portal
-- (Etapa 6 da seção 20 do plano)
--
-- Quando um documento da moto (IPVA, licenciamento, seguro, vistoria do Detran...) vence ou está para vencer, o locatário pode
-- mandar a foto ou o PDF do comprovante pelo portal. O envio NÃO regulariza o documento: fica aguardando o dono, que confere e
-- aceita (o documento passa a regularizado e o arquivo vira o comprovante dele) ou recusa com um motivo (o locatário pode enviar outro).
--   * `documento_comprovantes`: cada envio, com situação `enviado`, `aceito` ou `recusado`. No máximo UM envio aguardando por documento.
--     Só o dono lê (RLS); o locatário nunca acessa a tabela: tudo passa por RPCs SECURITY DEFINER que o identificam por auth.uid();
--   * Storage: o arquivo vai para o bucket privado `documentos` (o mesmo dos comprovantes do dono), na pasta `portal/<cliente_id>/`.
--     O locatário só ENVIA (insert) para a própria pasta: não lista, não lê e não altera arquivos;
--   * `rpc_portal_documentos()`: os documentos ainda não regularizados das motos dos contratos ATIVOS do locatário (moto principal ou
--     vinculada), com a situação do último envio;
--   * `rpc_portal_enviar_comprovante(payload)`: registra o envio depois de conferir que o documento é de uma moto dele, que não está
--     regularizado, que não há outro envio aguardando e que o arquivo está na pasta dele no Storage;
--   * `rpc_aceitar_comprovante_documento(p_envio, p_data)`: só o dono. Regulariza o documento e marca o envio como aceito, numa transação.
--     A recusa é uma atualização de uma tabela só (o dono já tem a política `dono_total`).
-- Compatível com a versão anterior do app: só tabela, políticas e funções novas.
-- =====================================================================

create table if not exists documento_comprovantes (
  id            uuid primary key default gen_random_uuid(),
  documento_id  uuid not null references documentos_moto(id) on delete cascade,
  cliente_id    uuid not null references clientes(id) on delete cascade,
  arquivo_path  text not null,
  observacao    text check (observacao is null or char_length(observacao) <= 200),
  status        text not null default 'enviado' check (status in ('enviado', 'aceito', 'recusado')),
  motivo_recusa text,
  enviado_em    timestamptz not null default now(),
  conferido_em  timestamptz,
  check (status <> 'recusado' or nullif(btrim(motivo_recusa), '') is not null),
  check (status = 'enviado' or conferido_em is not null)
);
create unique index if not exists uq_comprovante_aguardando_por_documento
  on documento_comprovantes (documento_id) where status = 'enviado';
create index if not exists ix_documento_comprovantes_documento on documento_comprovantes (documento_id, enviado_em desc);

alter table documento_comprovantes enable row level security;
drop policy if exists "dono_total" on documento_comprovantes;
create policy "dono_total" on documento_comprovantes for all to authenticated using (is_dono()) with check (is_dono());

-- ---------- Storage: o locatário só envia, e só para a própria pasta ----------
drop policy if exists "locatario_envia_comprovantes_documentos" on storage.objects;
create policy "locatario_envia_comprovantes_documentos" on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'documentos'
    and cliente_id_logado() is not null
    and (storage.foldername(name))[1] = 'portal'
    and (storage.foldername(name))[2] = cliente_id_logado()::text
  );

-- ---------- Documentos do locatário ----------
create or replace function rpc_portal_documentos() returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_cliente uuid := cliente_id_logado();
  v_cfg     configuracoes%rowtype;
begin
  if v_cliente is null then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
  select * into v_cfg from configuracoes where id = 1;

  return coalesce((
    select jsonb_agg(jsonb_build_object(
             'documento_id', d.id, 'placa', m.placa, 'modelo', m.modelo, 'tipo', d.tipo, 'descricao', d.descricao,
             'ano_referencia', d.ano_referencia, 'vencimento', d.vencimento,
             'situacao', case when d.vencimento < hoje_br() then 'vencido'
                              when d.vencimento - hoje_br() <= v_cfg.alerta_documento_dias then 'a_vencer'
                              else 'em_dia' end,
             'envio_status', e.status, 'envio_em', e.enviado_em, 'envio_motivo', e.motivo_recusa
           ) order by d.vencimento, m.placa)
      from documentos_moto d
      join motos m on m.id = d.moto_id
      left join lateral (
        select x.status, x.enviado_em, x.motivo_recusa from documento_comprovantes x
         where x.documento_id = d.id order by x.enviado_em desc limit 1
      ) e on true
     where not d.regularizado
       and exists (
         select 1 from contratos ct
          where ct.cliente_id = v_cliente and ct.status = 'ativo'
            and (ct.moto_id = d.moto_id
                 or exists (select 1 from contrato_motos cm where cm.contrato_id = ct.id and cm.moto_id = d.moto_id)))
  ), '[]'::jsonb);
end $$;

-- ---------- Enviar o comprovante ----------
-- payload: {"documento_id", "arquivo_path", "observacao" (opcional)}. O arquivo já foi enviado ao Storage pelo app.
create or replace function rpc_portal_enviar_comprovante(payload jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_cliente   uuid := cliente_id_logado();
  v_documento uuid := (payload->>'documento_id')::uuid;
  v_arquivo   text := payload->>'arquivo_path';
  v_obs       text := nullif(btrim(coalesce(payload->>'observacao', '')), '');
  v_doc       documentos_moto%rowtype;
  v_id        uuid;
begin
  if v_cliente is null then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
  if v_obs is not null and char_length(v_obs) > 200 then
    raise exception 'A observação pode ter no máximo 200 caracteres.';
  end if;

  select * into v_doc from documentos_moto where id = v_documento;
  if not found
     or not exists (
       select 1 from contratos ct
        where ct.cliente_id = v_cliente and ct.status = 'ativo'
          and (ct.moto_id = v_doc.moto_id
               or exists (select 1 from contrato_motos cm where cm.contrato_id = ct.id and cm.moto_id = v_doc.moto_id)))
  then
    raise exception 'Documento não encontrado.';
  end if;
  if v_doc.regularizado then
    raise exception 'Este documento já está regularizado.';
  end if;
  if exists (select 1 from documento_comprovantes where documento_id = v_documento and status = 'enviado') then
    raise exception 'Já existe um comprovante aguardando conferência para este documento.';
  end if;
  if v_arquivo is null or v_arquivo not like 'portal/' || v_cliente::text || '/%' then
    raise exception 'Arquivo do comprovante inválido.';
  end if;
  if not exists (select 1 from storage.objects where bucket_id = 'documentos' and name = v_arquivo) then
    raise exception 'O arquivo do comprovante não foi encontrado. Envie de novo.';
  end if;

  insert into documento_comprovantes (documento_id, cliente_id, arquivo_path, observacao)
  values (v_documento, v_cliente, v_arquivo, v_obs)
  returning id into v_id;

  return jsonb_build_object('id', v_id, 'status', 'enviado');
end $$;

-- ---------- O dono aceita: regulariza o documento e fecha o envio ----------
create or replace function rpc_aceitar_comprovante_documento(p_envio uuid, p_data date) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_envio documento_comprovantes%rowtype;
begin
  if not is_dono() then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
  if p_data is null or p_data > hoje_br() then
    raise exception 'A data de regularização não pode ser vazia nem futura.';
  end if;

  select * into v_envio from documento_comprovantes where id = p_envio for update;
  if not found then
    raise exception 'Comprovante não encontrado.';
  end if;
  if v_envio.status <> 'enviado' then
    raise exception 'Este comprovante já foi conferido.';
  end if;
  if exists (select 1 from documentos_moto where id = v_envio.documento_id and regularizado) then
    raise exception 'Este documento já está regularizado.';
  end if;

  update documentos_moto
     set regularizado = true, data_regularizacao = p_data, arquivo_path = v_envio.arquivo_path
   where id = v_envio.documento_id;
  update documento_comprovantes set status = 'aceito', conferido_em = now() where id = p_envio;

  return jsonb_build_object('documento_id', v_envio.documento_id, 'status', 'aceito');
end $$;

revoke all on function rpc_portal_documentos() from public, anon;
revoke all on function rpc_portal_enviar_comprovante(jsonb) from public, anon;
revoke all on function rpc_aceitar_comprovante_documento(uuid, date) from public, anon;
grant execute on function rpc_portal_documentos() to authenticated;
grant execute on function rpc_portal_enviar_comprovante(jsonb) to authenticated;
grant execute on function rpc_aceitar_comprovante_documento(uuid, date) to authenticated;

notify pgrst, 'reload schema';
