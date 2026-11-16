-- =====================================================================
-- 20261117130000_whatsapp_grupo.sql : as mensagens automáticas vão para o GRUPO de WhatsApp de cada locatário
-- (item 6 da seção 23 do plano; decisão do dono em 17/11/2026)
--
-- Cada locatário tem um grupo com ele, o dono e as duas pessoas do financeiro. O destino da mensagem passa a ser o ID
-- do grupo (`...@g.us`), guardado em `clientes.whatsapp_grupo_id`. A coluna `mensagens_whatsapp.numero` continua sendo o
-- destino e passa a aceitar também o ID de um grupo (o histórico antigo, com números, continua válido). Cliente sem grupo:
-- a mensagem fica `ignorada`, com o motivo.
--
-- Também guarda a lista de grupos da instância (`whatsapp_grupos`), atualizada a cada rodada do script de envio, para o
-- dono escolher o grupo do cliente pelo nome, sem a Evolution ter de ser consultada pela tela.
-- Compatível com a versão anterior do app. Roteiro de conferência: supabase/verificar_whatsapp_grupo.sql (só em dev).
-- =====================================================================

-- ---------- Grupo do cliente ----------
alter table clientes add column if not exists whatsapp_grupo_id text;
alter table clientes drop constraint if exists clientes_whatsapp_grupo_id_check;
alter table clientes add constraint clientes_whatsapp_grupo_id_check
  check (whatsapp_grupo_id is null or whatsapp_grupo_id ~ '^[0-9]{10,30}(-[0-9]{5,30})?@g\.us$');
-- um grupo pertence a um cliente só (senão a cobrança de um iria para o grupo do outro)
create unique index if not exists ux_clientes_whatsapp_grupo on clientes (whatsapp_grupo_id) where whatsapp_grupo_id is not null;

-- ---------- Destino da mensagem: número ou grupo ----------
alter table mensagens_whatsapp drop constraint if exists mensagens_whatsapp_numero_check;
alter table mensagens_whatsapp add constraint mensagens_whatsapp_numero_check
  check (numero is null or numero ~ '^55[0-9]{10,11}$' or numero ~ '^[0-9]{10,30}(-[0-9]{5,30})?@g\.us$');

-- ---------- Enfileirar: aceita grupo (o resto é igual à versão da migration 20261106120000) ----------
create or replace function rpc_whatsapp_enfileirar(payload jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  m            jsonb;
  i            jsonb;
  v_cliente    uuid;
  v_numero     text;
  v_status     text;
  v_erro       text;
  v_id         uuid;
  v_enfileiradas int := 0;
  v_sem_numero   int := 0;
  v_duplicadas   int := 0;
  v_bloqueadas   int := 0;
begin
  perform fn_exige_gestao_whatsapp();
  if jsonb_typeof(payload->'mensagens') is distinct from 'array' then
    raise exception 'payload.mensagens deve ser uma lista.';
  end if;

  -- um enfileiramento por vez: a checagem de duplicadas e a gravação não se atropelam
  perform pg_advisory_xact_lock(hashtext('rpc_whatsapp_enfileirar'));

  for m in select * from jsonb_array_elements(payload->'mensagens') loop
    v_cliente := (m->>'cliente_id')::uuid;
    if jsonb_typeof(m->'itens') is distinct from 'array' or jsonb_array_length(m->'itens') = 0 then
      raise exception 'Toda mensagem precisa de ao menos um item.';
    end if;
    if not exists (select 1 from clientes where id = v_cliente) then
      raise exception 'Cliente % não encontrado.', v_cliente;
    end if;

    if exists (select 1 from clientes where id = v_cliente and nao_enviar_whatsapp) then
      v_bloqueadas := v_bloqueadas + 1;
      continue;
    end if;

    if exists (
      select 1
        from jsonb_array_elements(m->'itens') it
        join mensagens_whatsapp_itens x
          on x.tipo = it->>'tipo'
         and x.referencia_id = (it->>'referencia_id')::uuid
         and x.data_referencia = (it->>'data_referencia')::date
    ) then
      v_duplicadas := v_duplicadas + 1;
      continue;
    end if;

    v_numero := nullif(btrim(coalesce(m->>'numero', '')), '');
    if v_numero is null then
      v_status := 'ignorada';
      v_erro := 'Cliente sem grupo de WhatsApp cadastrado.';
    elsif v_numero !~ '^55[0-9]{10,11}$' and v_numero !~ '^[0-9]{10,30}(-[0-9]{5,30})?@g\.us$' then
      v_status := 'ignorada';
      v_erro := 'Destino de WhatsApp inválido (grupo ou número).';
      v_numero := null;
    else
      v_status := 'pendente';
      v_erro := null;
    end if;

    insert into mensagens_whatsapp (cliente_id, numero, texto, status, erro, enviar_apos)
    values (v_cliente, v_numero, m->>'texto', v_status, v_erro,
            coalesce((m->>'enviar_apos')::timestamptz, now()))
    returning id into v_id;

    for i in select * from jsonb_array_elements(m->'itens') loop
      insert into mensagens_whatsapp_itens (mensagem_id, tipo, referencia_id, data_referencia)
      values (v_id, i->>'tipo', (i->>'referencia_id')::uuid, (i->>'data_referencia')::date);
    end loop;

    if v_status = 'pendente' then
      v_enfileiradas := v_enfileiradas + 1;
    else
      v_sem_numero := v_sem_numero + 1;
    end if;
  end loop;

  return jsonb_build_object(
    'enfileiradas', v_enfileiradas, 'sem_numero', v_sem_numero,
    'duplicadas', v_duplicadas, 'bloqueadas', v_bloqueadas);
end $$;

-- ---------- Grupos de cada cliente (para o script juntar à leitura) ----------
-- Devolve {"<cliente_id>": "<id do grupo>"} só dos clientes que têm grupo.
create or replace function rpc_whatsapp_grupos_clientes() returns jsonb
language plpgsql stable security definer set search_path = public as $$
begin
  perform fn_exige_gestao_whatsapp();
  return coalesce(
    (select jsonb_object_agg(id::text, whatsapp_grupo_id) from clientes where whatsapp_grupo_id is not null),
    '{}'::jsonb);
end $$;

-- ---------- Lista de grupos da instância ----------
create table if not exists whatsapp_grupos (
  id            text primary key check (id ~ '^[0-9]{10,30}(-[0-9]{5,30})?@g\.us$'),
  nome          text not null check (btrim(nome) <> ''),
  participantes int check (participantes is null or participantes >= 0),
  atualizado_em timestamptz not null default now()
);
alter table whatsapp_grupos enable row level security;
drop policy if exists "dono_leitura" on whatsapp_grupos;
create policy "dono_leitura" on whatsapp_grupos for select to authenticated using (is_dono());

-- payload: {"grupos": [{"id", "nome", "participantes"}]}. A lista guardada passa a ser exatamente esta (quem saiu do WhatsApp
-- some). Devolve quantos grupos ficaram. Só o usuário de serviço do envio ou o dono.
create or replace function rpc_whatsapp_gravar_grupos(payload jsonb) returns int
language plpgsql security definer set search_path = public as $$
declare
  g jsonb;
  v_ids text[] := '{}';
begin
  perform fn_exige_gestao_whatsapp();
  if jsonb_typeof(payload->'grupos') is distinct from 'array' then
    raise exception 'payload.grupos deve ser uma lista.';
  end if;

  for g in select * from jsonb_array_elements(payload->'grupos') loop
    if coalesce(g->>'id', '') !~ '^[0-9]{10,30}(-[0-9]{5,30})?@g\.us$' then
      continue;  -- ignora o que não é grupo
    end if;
    insert into whatsapp_grupos (id, nome, participantes, atualizado_em)
    values (g->>'id', coalesce(nullif(btrim(g->>'nome'), ''), '(sem nome)'), nullif(g->>'participantes', '')::int, now())
    on conflict (id) do update
       set nome = excluded.nome, participantes = excluded.participantes, atualizado_em = excluded.atualizado_em;
    v_ids := v_ids || (g->>'id');
  end loop;

  delete from whatsapp_grupos where not (id = any(v_ids));
  return coalesce(array_length(v_ids, 1), 0);
end $$;

revoke all on function rpc_whatsapp_grupos_clientes() from public, anon;
revoke all on function rpc_whatsapp_gravar_grupos(jsonb) from public, anon;
grant execute on function rpc_whatsapp_grupos_clientes() to authenticated;
grant execute on function rpc_whatsapp_gravar_grupos(jsonb) to authenticated;
