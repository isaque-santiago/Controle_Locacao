-- =====================================================================
-- 20261106120000_whatsapp_base.sql : envio automático por WhatsApp, Etapa 1 (Projeto_Locação.md, seção 20)
--
-- Só a BASE do banco; nada envia mensagem ainda:
--   * `clientes` ganha o bloqueio de envio, que só o dono liga (com motivo e data);
--   * `mensagens_whatsapp` é a fila e o histórico: uma linha por mensagem a enviar a um cliente (já agrupada);
--   * `mensagens_whatsapp_itens` diz QUAIS assuntos cada mensagem leva (cobrança, CNH, documento...). A chave
--     única (tipo, referência, data) é o que impede o mesmo aviso de sair duas vezes no mesmo dia;
--   * `servico_mensagens` lista o usuário de serviço (o robô que roda o script agendado). Ele NÃO enxerga nenhuma
--     tabela: só executa as três RPCs abaixo, que conferem quem chamou. A service_role nunca é usada.
--
-- RPCs (SECURITY DEFINER; aceitam só o usuário de serviço ou um administrador):
--   rpc_whatsapp_enfileirar          grava mensagens novas (ignora duplicadas e clientes bloqueados);
--   rpc_whatsapp_reservar            entrega as pendentes devidas e as reserva por 10 min (dois scripts não pegam a mesma);
--   rpc_whatsapp_registrar_resultado grava enviada / ignorada / falha (até 3 tentativas, com espera crescente).
--
-- Compatível com a versão anterior do app: só colunas com padrão e tabelas novas.
--
-- Para criar o usuário de serviço (depois de criá-lo em Authentication > Users, com "Auto Confirm User"):
--   insert into servico_mensagens (user_id) select id from auth.users where email = 'robo@exemplo.com';
-- Para tirar o acesso:
--   delete from servico_mensagens where user_id = (select id from auth.users where email = 'robo@exemplo.com');
-- =====================================================================

-- ---------- Bloqueio de envio no cliente (só o dono altera) ----------
alter table clientes
  add column if not exists nao_enviar_whatsapp boolean not null default false,
  add column if not exists motivo_bloqueio_whatsapp text,
  add column if not exists bloqueio_whatsapp_em timestamptz;

alter table clientes drop constraint if exists clientes_bloqueio_whatsapp_check;
alter table clientes add constraint clientes_bloqueio_whatsapp_check
  check (not nao_enviar_whatsapp
         or (nullif(btrim(motivo_bloqueio_whatsapp), '') is not null and bloqueio_whatsapp_em is not null));

-- ---------- Usuário de serviço (mesmo padrão de `administradores`) ----------
create table if not exists servico_mensagens (
  user_id   uuid primary key,
  criado_em timestamptz not null default now()
);

alter table servico_mensagens enable row level security;
drop policy if exists "ver_o_proprio" on servico_mensagens;
create policy "ver_o_proprio" on servico_mensagens for select to authenticated using (user_id = auth.uid());
revoke all on servico_mensagens from anon, authenticated;
grant select on servico_mensagens to authenticated;

create or replace function is_servico_mensagens() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from servico_mensagens where user_id = auth.uid());
$$;

-- ---------- Fila e histórico ----------
create table if not exists mensagens_whatsapp (
  id             uuid primary key default gen_random_uuid(),
  cliente_id     uuid not null references clientes(id) on delete cascade,
  numero         text check (numero is null or numero ~ '^55[0-9]{10,11}$'),  -- 55 + DDD + número, só dígitos
  texto          text not null check (btrim(texto) <> ''),
  status         text not null default 'pendente'
                 check (status in ('pendente','enviada','falhou','ignorada','cancelada')),
  tentativas     int  not null default 0 check (tentativas >= 0),
  erro           text,
  enviar_apos    timestamptz not null default now(),
  reservada_ate  timestamptz,
  enviada_em     timestamptz,
  evolution_id   text,                                   -- id da mensagem devolvido pela Evolution
  criado_em      timestamptz not null default now(),
  check (status <> 'enviada' or (enviada_em is not null and numero is not null)),
  check (status <> 'pendente' or numero is not null)
);
create index if not exists ix_mensagens_whatsapp_pendentes on mensagens_whatsapp (enviar_apos) where status = 'pendente';
create index if not exists ix_mensagens_whatsapp_cliente on mensagens_whatsapp (cliente_id, criado_em desc);

create table if not exists mensagens_whatsapp_itens (
  id              uuid primary key default gen_random_uuid(),
  mensagem_id     uuid not null references mensagens_whatsapp(id) on delete cascade,
  tipo            text not null check (tipo in (
                    'lembrete_vespera','lembrete_vencimento','atraso','inadimplencia','recibo_pagamento',
                    'cnh_proxima','cnh_vencida','oleo_proxima','oleo_vencida',
                    'documento_proximo','documento_vencido','portal_acesso','portal_senha_alterada')),
  referencia_id   uuid not null,                         -- cobrança, pagamento, cliente, moto ou documento, conforme o tipo
  data_referencia date not null,                         -- o dia a que o aviso se refere (hoje, para as repetições)
  unique (tipo, referencia_id, data_referencia)
);
create index if not exists ix_mensagens_whatsapp_itens_mensagem on mensagens_whatsapp_itens (mensagem_id);

-- O dono vê e administra pelo app (telas da Etapa 4); o usuário de serviço só passa pelas RPCs.
alter table mensagens_whatsapp enable row level security;
alter table mensagens_whatsapp_itens enable row level security;
drop policy if exists "dono_total" on mensagens_whatsapp;
create policy "dono_total" on mensagens_whatsapp for all to authenticated using (is_dono()) with check (is_dono());
drop policy if exists "dono_total" on mensagens_whatsapp_itens;
create policy "dono_total" on mensagens_whatsapp_itens for all to authenticated using (is_dono()) with check (is_dono());

-- ---------- Quem pode chamar as RPCs ----------
create or replace function fn_exige_gestao_whatsapp() returns void
language plpgsql stable security definer set search_path = public as $$
begin
  if not (is_servico_mensagens() or is_dono()) then
    raise exception 'Sem permissão para gerir mensagens de WhatsApp.' using errcode = '42501';
  end if;
end $$;

-- ---------- Enfileirar ----------
-- payload: {"mensagens": [{"cliente_id", "numero" (ou null), "texto", "enviar_apos" (opcional),
--            "itens": [{"tipo", "referencia_id", "data_referencia"}]}]}
-- Pula a mensagem inteira se algum dos assuntos já foi enfileirado (duplicada) ou se o cliente está bloqueado.
-- Sem número válido, a mensagem é gravada como 'ignorada' com o motivo (o dono vê no sistema).
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
      v_erro := 'Cliente sem WhatsApp cadastrado.';
    elsif v_numero !~ '^55[0-9]{10,11}$' then
      v_status := 'ignorada';
      v_erro := 'Número de WhatsApp inválido.';
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

-- ---------- Reservar pendentes para envio ----------
-- Devolve até `p_limite` mensagens devidas e as reserva por 10 minutos: se o script morrer no meio, a reserva
-- expira e elas voltam a ser entregues. Mensagem de cliente que foi bloqueado depois de enfileirada é cancelada.
create or replace function rpc_whatsapp_reservar(p_limite int default 20) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  r        record;
  v_lista  jsonb := '[]'::jsonb;
begin
  perform fn_exige_gestao_whatsapp();
  if p_limite is null or p_limite < 1 or p_limite > 200 then
    raise exception 'p_limite deve estar entre 1 e 200.';
  end if;

  for r in
    select m.id, m.cliente_id, m.numero, m.texto, m.tentativas, c.nao_enviar_whatsapp as bloqueado
      from mensagens_whatsapp m
      join clientes c on c.id = m.cliente_id
     where m.status = 'pendente'
       and m.enviar_apos <= now()
       and (m.reservada_ate is null or m.reservada_ate < now())
     order by m.enviar_apos, m.id
     limit p_limite
       for update of m skip locked
  loop
    if r.bloqueado then
      update mensagens_whatsapp
         set status = 'cancelada', erro = 'Cliente bloqueado para envio de WhatsApp.', reservada_ate = null
       where id = r.id;
    else
      update mensagens_whatsapp set reservada_ate = now() + interval '10 minutes' where id = r.id;
      v_lista := v_lista || jsonb_build_object(
        'id', r.id, 'cliente_id', r.cliente_id, 'numero', r.numero,
        'texto', r.texto, 'tentativas', r.tentativas);
    end if;
  end loop;

  return v_lista;
end $$;

-- ---------- Registrar o resultado de um envio ----------
-- p_resultado: 'enviada' (guarda o id da Evolution), 'ignorada' (ex.: número sem WhatsApp; não tenta de novo)
-- ou 'falhou' (falha temporária: volta para a fila em 30 min x tentativas; na 3ª falha fica 'falhou').
create or replace function rpc_whatsapp_registrar_resultado(
  p_id uuid, p_resultado text, p_erro text default null, p_evolution_id text default null
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  c_max_tentativas constant int := 3;
  v_msg   mensagens_whatsapp%rowtype;
  v_tent  int;
  v_status text;
begin
  perform fn_exige_gestao_whatsapp();
  if p_resultado not in ('enviada', 'ignorada', 'falhou') then
    raise exception 'Resultado inválido: %.', p_resultado;
  end if;

  select * into v_msg from mensagens_whatsapp where id = p_id for update;
  if not found then
    raise exception 'Mensagem % não encontrada.', p_id;
  end if;
  if v_msg.status <> 'pendente' then
    raise exception 'A mensagem % não está pendente (situação: %).', p_id, v_msg.status;
  end if;

  v_tent := v_msg.tentativas + 1;

  if p_resultado = 'enviada' then
    v_status := 'enviada';
    update mensagens_whatsapp
       set status = 'enviada', tentativas = v_tent, enviada_em = now(), erro = null,
           evolution_id = p_evolution_id, reservada_ate = null
     where id = p_id;
  elsif p_resultado = 'ignorada' then
    v_status := 'ignorada';
    update mensagens_whatsapp
       set status = 'ignorada', tentativas = v_tent, erro = coalesce(p_erro, 'Ignorada pelo envio.'), reservada_ate = null
     where id = p_id;
  elsif v_tent >= c_max_tentativas then
    v_status := 'falhou';
    update mensagens_whatsapp
       set status = 'falhou', tentativas = v_tent, erro = coalesce(p_erro, 'Falha no envio.'), reservada_ate = null
     where id = p_id;
  else
    v_status := 'pendente';
    update mensagens_whatsapp
       set tentativas = v_tent, erro = coalesce(p_erro, 'Falha no envio.'), reservada_ate = null,
           enviar_apos = now() + (v_tent * interval '30 minutes')
     where id = p_id;
  end if;

  return jsonb_build_object('status', v_status, 'tentativas', v_tent);
end $$;

-- Só quem está autenticado chama as RPCs (a conferência de quem é fica dentro delas).
revoke all on function fn_exige_gestao_whatsapp() from public, anon;
revoke all on function is_servico_mensagens() from public, anon;
revoke all on function rpc_whatsapp_enfileirar(jsonb) from public, anon;
revoke all on function rpc_whatsapp_reservar(int) from public, anon;
revoke all on function rpc_whatsapp_registrar_resultado(uuid, text, text, text) from public, anon;
grant execute on function is_servico_mensagens() to authenticated;
grant execute on function rpc_whatsapp_enfileirar(jsonb) to authenticated;
grant execute on function rpc_whatsapp_reservar(int) to authenticated;
grant execute on function rpc_whatsapp_registrar_resultado(uuid, text, text, text) to authenticated;
-- fn_exige_gestao_whatsapp só é chamada por dentro das RPCs (que são SECURITY DEFINER do mesmo dono).

notify pgrst, 'reload schema';
