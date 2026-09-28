-- =====================================================================
-- 20260928120000_portal_locatario.sql : Fase 7 — portal do locatário
--
-- O locatário entra com LOGIN COMPLETO do Supabase Auth, como um segundo papel de
-- usuário. O login é por CPF + senha: o app converte o CPF (só dígitos) no e-mail
-- interno <cpf>@portal.example.com (domínio reservado, que nunca recebe e-mail).
-- A senha inicial é PROVISÓRIA e individual (gerada pelo app, mostrada uma vez ao
-- dono); o locatário é obrigado a trocá-la no primeiro acesso. Ele NÃO recebe nenhuma permissão direta nas
-- tabelas: a RLS "dono_total" (is_dono()) continua sendo a única política das
-- tabelas do sistema. Tudo que o locatário lê ou grava passa por RPCs
-- SECURITY DEFINER que identificam quem chamou por auth.uid() e só enxergam o
-- contrato/moto vinculados a ele.
--
-- Como criar um locatário (o app nunca usa a service_role):
--   1. no app, Clientes > ficha do cliente > aba "Portal": "Gerar senha provisória";
--   2. Authentication > Users > Add user no painel do Supabase, com o e-mail e a
--      senha mostrados pelo app e "Auto Confirm User" marcado (cadastro público
--      continua desativado);
--   3. no app, "Vincular acesso" (rpc_vincular_locatario).
-- =====================================================================

-- ---------- Vínculo cliente <-> usuário do Supabase Auth ----------
alter table clientes
  add column auth_user_id uuid unique references auth.users(id) on delete set null;
-- true enquanto o locatário ainda não trocou a senha provisória
alter table clientes
  add column senha_provisoria boolean not null default false;

-- ---------- Multa fixa por troca de óleo fora do intervalo ----------
-- 0 = sem multa configurada: o excesso é registrado, mas nada é cobrado.
alter table configuracoes
  add column multa_troca_oleo_valor numeric(12,2) not null default 0
  check (multa_troca_oleo_valor >= 0);

-- ---------- Novo tipo de cobrança ----------
alter table cobrancas drop constraint cobrancas_tipo_check;
alter table cobrancas add constraint cobrancas_tipo_check
  check (tipo in ('locacao','caucao','dano','multa_transito','multa_manutencao','outros'));

-- ---------- Trocas de óleo reportadas pelo locatário ----------
create table trocas_oleo (
  id                uuid primary key default gen_random_uuid(),
  cliente_id        uuid not null references clientes(id),
  contrato_id       uuid not null references contratos(id),
  moto_id           uuid not null references motos(id),
  manutencao_id     uuid not null references manutencoes(id),
  cobranca_id       uuid references cobrancas(id),          -- multa gerada, se houve
  km                int  not null check (km >= 0),
  km_excedente      int  not null default 0 check (km_excedente >= 0),
  foto_painel_path  text not null,                          -- Storage, bucket trocas_oleo
  nota_fiscal_path  text not null,
  criado_em         timestamptz not null default now(),
  unique (contrato_id, km)                                  -- evita envio duplicado
);
create index ix_trocas_oleo_contrato on trocas_oleo (contrato_id, criado_em desc);

alter table trocas_oleo enable row level security;
create policy "dono_total" on trocas_oleo
  for all to authenticated using (is_dono()) with check (is_dono());

-- ---------- Funções auxiliares ----------
create or replace function cliente_id_logado() returns uuid
language sql stable security definer set search_path = public as $$
  select id from clientes where auth_user_id = auth.uid();
$$;

-- Item do catálogo que representa a troca de óleo.
create or replace function item_troca_oleo_id() returns uuid
language sql stable security definer set search_path = public as $$
  select id from itens_manutencao
   where ativo and nome ilike 'troca de óleo%'
   order by nome limit 1;
$$;

-- Papel de quem está logado: 'dono', 'locatario' ou null (sem permissão).
create or replace function rpc_meu_papel() returns text
language sql stable security definer set search_path = public as $$
  select case
    when is_dono() then 'dono'
    when cliente_id_logado() is not null then 'locatario'
  end;
$$;

-- ---------- Vincular / desvincular locatário (só o dono) ----------
-- O usuário no Auth deve ter o e-mail <cpf>@portal.example.com (o app mostra o
-- valor exato). Vincular marca a senha como provisória: o locatário terá de trocá-la.
create or replace function rpc_vincular_locatario(payload jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_cliente_id uuid := (payload->>'cliente_id')::uuid;
  v_cpf        text;
  v_email      text;
  v_user_id    uuid;
begin
  if not is_dono() then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;

  select cpf into v_cpf from clientes where id = v_cliente_id;
  if not found then
    raise exception 'Cliente não encontrado.';
  end if;
  v_email := v_cpf || '@portal.example.com';

  select id into v_user_id from auth.users where lower(email) = v_email;
  if v_user_id is null then
    raise exception 'Não existe usuário com o e-mail %. Crie-o antes em Authentication > Users no Supabase.', v_email;
  end if;
  if exists (select 1 from clientes where auth_user_id = v_user_id and id <> v_cliente_id) then
    raise exception 'Este usuário já está vinculado a outro cliente.';
  end if;

  update clientes set auth_user_id = v_user_id, senha_provisoria = true where id = v_cliente_id;
  return jsonb_build_object('cliente_id', v_cliente_id, 'email', v_email);
end $$;

create or replace function rpc_desvincular_locatario(payload jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
begin
  if not is_dono() then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
  update clientes set auth_user_id = null, senha_provisoria = false
   where id = (payload->>'cliente_id')::uuid;
  if not found then
    raise exception 'Cliente não encontrado.';
  end if;
  return jsonb_build_object('cliente_id', payload->>'cliente_id');
end $$;

-- Dono redefiniu a senha do locatário no painel do Supabase: volta a exigir a troca.
create or replace function rpc_definir_senha_provisoria(payload jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
begin
  if not is_dono() then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
  update clientes set senha_provisoria = true
   where id = (payload->>'cliente_id')::uuid and auth_user_id is not null;
  if not found then
    raise exception 'Este cliente não tem acesso ao portal.';
  end if;
  return jsonb_build_object('cliente_id', payload->>'cliente_id');
end $$;

-- O locatário chama depois de trocar a senha (auth.update_user). Não dá para o
-- banco confirmar que a senha mudou de fato; a senha provisória é aleatória e de
-- uso individual, então o flag serve para forçar o fluxo de troca, não como prova.
create or replace function rpc_confirmar_troca_senha() returns void
language plpgsql security definer set search_path = public as $$
begin
  update clientes set senha_provisoria = false where auth_user_id = auth.uid();
  if not found then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
end $$;

-- ---------- Dados mínimos do portal ----------
-- Devolve só o necessário para a tela do locatário: contratos ATIVOS dele, a
-- moto (placa, modelo, km), o plano de troca de óleo e as últimas trocas.
create or replace function rpc_portal_locatario() returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_cliente   clientes%rowtype;
  v_config    configuracoes%rowtype;
  v_contratos jsonb;
begin
  select * into v_cliente from clientes where auth_user_id = auth.uid();
  if not found then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
  select * into v_config from configuracoes where id = 1;

  select coalesce(jsonb_agg(jsonb_build_object(
      'contrato_id',    c.id,
      'placa',          m.placa,
      'modelo',         m.modelo,
      'km_atual',       m.km_atual,
      'ultima_km',      o.ultima_km,
      'ultima_data',    o.ultima_data,
      'intervalo_km',   o.intervalo_km,
      'intervalo_dias', o.intervalo_dias,
      'trocas', coalesce((
        select jsonb_agg(jsonb_build_object(
                 'km', t.km, 'criado_em', t.criado_em,
                 'km_excedente', t.km_excedente, 'multada', t.cobranca_id is not null)
               order by t.criado_em desc)
          from (select * from trocas_oleo where contrato_id = c.id
                 order by criado_em desc limit 5) t
      ), '[]'::jsonb)
    ) order by m.placa), '[]'::jsonb)
    into v_contratos
    from contratos c
    join motos m on m.id = c.moto_id
    left join lateral (
      select pl.ultima_km, pl.ultima_data,
             coalesce(pl.intervalo_km,   i.intervalo_km)   as intervalo_km,
             coalesce(pl.intervalo_dias, i.intervalo_dias) as intervalo_dias
        from itens_manutencao i
        join moto_plano_manutencao pl on pl.item_id = i.id and pl.moto_id = m.id
       where i.id = item_troca_oleo_id()
    ) o on true
   where c.cliente_id = v_cliente.id and c.status = 'ativo';

  return jsonb_build_object(
    'cliente_id',     v_cliente.id,
    'trocar_senha',   v_cliente.senha_provisoria,
    'nome',           v_cliente.nome,
    'multa_valor',    v_config.multa_troca_oleo_valor,
    'alerta_km',      v_config.alerta_manutencao_km,
    'alerta_dias',    v_config.alerta_manutencao_dias,
    'contratos',      v_contratos
  );
end $$;

-- ---------------------------------------------------------------------
-- rpc_registrar_troca_oleo_locatario: transação única.
--   - só o locatário dono do contrato ATIVO pode registrar;
--   - hodômetro >= km atual da moto (o km nunca regride);
--   - exige foto do painel e nota fiscal já enviadas ao bucket trocas_oleo,
--     dentro da pasta do próprio cliente (cláusula 4.13 do contrato);
--   - grava a manutenção (preventiva, concluída, custo zero) + item do plano,
--     zera o contador do plano de óleo e registra o km no histórico;
--   - se km > última km + intervalo do plano, gera a cobrança fixa
--     'multa_manutencao' (valor em configuracoes.multa_troca_oleo_valor; 0 = não cobra).
--
-- payload: {"contrato_id": uuid, "km": int,
--           "foto_painel_path": text, "nota_fiscal_path": text}
-- ---------------------------------------------------------------------
create or replace function rpc_registrar_troca_oleo_locatario(payload jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_cliente_id   uuid := cliente_id_logado();
  v_contrato     contratos%rowtype;
  v_moto         motos%rowtype;
  v_km           int  := (payload->>'km')::int;
  v_foto         text := payload->>'foto_painel_path';
  v_nota         text := payload->>'nota_fiscal_path';
  v_item_id      uuid := item_troca_oleo_id();
  v_plano        moto_plano_manutencao%rowtype;
  v_intervalo_km int;
  v_proxima_km   int;
  v_excedente    int  := 0;
  v_multa        numeric(12,2);
  v_hoje         date := hoje_br();
  v_manutencao   uuid;
  v_cobranca     uuid;
  v_troca        uuid;
begin
  if v_cliente_id is null then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;

  if exists (select 1 from clientes where id = v_cliente_id and senha_provisoria) then
    raise exception 'Troque a senha provisória antes de registrar a troca de óleo.';
  end if;

  select * into v_contrato from contratos
   where id = (payload->>'contrato_id')::uuid
     and cliente_id = v_cliente_id and status = 'ativo';
  if not found then
    raise exception 'Contrato ativo não encontrado para este acesso.';
  end if;

  select * into v_moto from motos where id = v_contrato.moto_id for update;

  if v_km is null or v_km < v_moto.km_atual then
    raise exception 'O hodômetro não pode ser menor que o último registrado (% km).', v_moto.km_atual;
  end if;
  if exists (select 1 from trocas_oleo where contrato_id = v_contrato.id and km = v_km) then
    raise exception 'Uma troca de óleo com este hodômetro já foi registrada.';
  end if;

  -- Fotos: precisam existir no Storage, na pasta do próprio cliente.
  if coalesce(v_foto, '') = '' or coalesce(v_nota, '') = '' or v_foto = v_nota then
    raise exception 'Envie a foto do painel e a nota fiscal do óleo.';
  end if;
  if left(v_foto, length(v_cliente_id::text) + 1) <> v_cliente_id::text || '/'
     or left(v_nota, length(v_cliente_id::text) + 1) <> v_cliente_id::text || '/' then
    raise exception 'Arquivo enviado em local inválido.';
  end if;
  if (select count(*) from storage.objects
       where bucket_id = 'trocas_oleo' and name in (v_foto, v_nota)) <> 2 then
    raise exception 'Não encontramos os arquivos enviados. Envie a foto e a nota fiscal novamente.';
  end if;

  -- Plano de troca de óleo da moto.
  select * into v_plano from moto_plano_manutencao
   where moto_id = v_moto.id and item_id = v_item_id for update;
  if v_item_id is null or not found then
    raise exception 'O plano de troca de óleo desta moto não está configurado. Avise o proprietário.';
  end if;
  select coalesce(v_plano.intervalo_km, i.intervalo_km) into v_intervalo_km
    from itens_manutencao i where i.id = v_item_id;
  if v_intervalo_km is not null then
    v_proxima_km := coalesce(v_plano.ultima_km, 0) + v_intervalo_km;
    if v_km > v_proxima_km then
      v_excedente := v_km - v_proxima_km;
    end if;
  end if;

  -- Manutenção concluída (custo zero: o óleo é pago pelo locatário).
  insert into manutencoes (moto_id, contrato_id, tipo, status, data_entrada, data_saida,
                           km, descricao, observacoes)
  values (v_moto.id, v_contrato.id, 'preventiva', 'concluida', v_hoje, v_hoje, v_km,
          'Troca de óleo do motor (reportada pelo locatário)',
          'Foto do painel e nota fiscal anexadas pelo locatário no portal.')
  returning id into v_manutencao;

  insert into manutencao_itens (manutencao_id, item_id, descricao, quantidade, valor_unitario)
  values (v_manutencao, v_item_id, 'Troca de óleo do motor', 1, 0);

  update moto_plano_manutencao set ultima_km = v_km, ultima_data = v_hoje where id = v_plano.id;
  insert into historico_km (moto_id, km, data, origem) values (v_moto.id, v_km, v_hoje, 'manutencao');

  -- Multa fixa quando passou do intervalo do plano.
  select multa_troca_oleo_valor into v_multa from configuracoes where id = 1;
  if v_excedente > 0 and coalesce(v_multa, 0) > 0 then
    insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao)
    values (v_contrato.id, 'multa_manutencao', v_hoje, v_multa,
            'Multa: troca de óleo fora do intervalo (' || v_excedente || ' km acima do previsto)')
    returning id into v_cobranca;
  end if;

  insert into trocas_oleo (cliente_id, contrato_id, moto_id, manutencao_id, cobranca_id,
                           km, km_excedente, foto_painel_path, nota_fiscal_path)
  values (v_cliente_id, v_contrato.id, v_moto.id, v_manutencao, v_cobranca,
          v_km, v_excedente, v_foto, v_nota)
  returning id into v_troca;

  return jsonb_build_object(
    'troca_id', v_troca, 'manutencao_id', v_manutencao,
    'excedeu', v_excedente > 0, 'km_excedente', v_excedente,
    'multa_valor', case when v_cobranca is not null then v_multa end,
    'proxima_km', v_km + coalesce(v_intervalo_km, 0)
  );
end $$;

-- ---------- Permissões das RPCs ----------
-- Funções nascem executáveis por PUBLIC (inclui anon): fecha para anon. Quem
-- não é dono nem locatário recebe "Acesso negado" dentro das próprias RPCs.
revoke execute on function
  cliente_id_logado(), item_troca_oleo_id(), rpc_meu_papel(),
  rpc_vincular_locatario(jsonb), rpc_desvincular_locatario(jsonb),
  rpc_definir_senha_provisoria(jsonb), rpc_confirmar_troca_senha(),
  rpc_portal_locatario(), rpc_registrar_troca_oleo_locatario(jsonb)
from public, anon;
grant execute on function
  cliente_id_logado(), item_troca_oleo_id(), rpc_meu_papel(),
  rpc_vincular_locatario(jsonb), rpc_desvincular_locatario(jsonb),
  rpc_definir_senha_provisoria(jsonb), rpc_confirmar_troca_senha(),
  rpc_portal_locatario(), rpc_registrar_troca_oleo_locatario(jsonb)
to authenticated;

-- ---------- Storage: bucket privado das fotos de troca de óleo ----------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('trocas_oleo', 'trocas_oleo', false, 10485760, array['image/jpeg', 'image/png'])
on conflict (id) do nothing;

-- Dono: acesso total (inclui o novo bucket, para ver as fotos por URL assinada).
drop policy if exists "dono_storage_vistorias" on storage.objects;
create policy "dono_storage_vistorias" on storage.objects
  for all to authenticated
  using (bucket_id in ('vistorias','documentos','trocas_oleo') and is_dono())
  with check (bucket_id in ('vistorias','documentos','trocas_oleo') and is_dono());

-- Locatário: só ENVIA (insert) para a própria pasta <cliente_id>/... Não lista,
-- não lê e não altera arquivos (nem os seus): a RPC valida o que foi enviado.
create policy "locatario_envia_trocas_oleo" on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'trocas_oleo'
    and cliente_id_logado() is not null
    and (storage.foldername(name))[1] = cliente_id_logado()::text
  );
