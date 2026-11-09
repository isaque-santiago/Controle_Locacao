-- =====================================================================
-- 20261109120000_portal_eventos_senha.sql : aviso de "senha do portal alterada" por WhatsApp (seção 20 do plano)
--
-- A troca de senha acontece no Supabase Auth e não deixava registro no banco, então o envio não tinha de onde saber que ela
-- aconteceu. Agora cada troca grava um evento, e `rpc_whatsapp_dados` o entrega ao script (o último de cada cliente nos
-- últimos dias):
--   * `portal_eventos (cliente_id, tipo, origem, criado_em)`: histórico de eventos do portal, visível só ao dono;
--   * `rpc_portal_registrar_troca_senha()`: chamada pelo locatário depois de trocar a própria senha (origem 'locatario').
--     Identifica quem chamou por auth.uid(); no máximo um evento a cada 10 minutos por cliente;
--   * `rpc_portal_registrar_redefinicao_senha(cliente_id)`: chamada pelo dono depois de gerar uma senha nova (origem 'dono');
--   * `rpc_whatsapp_dados` passa a incluir os eventos de senha em `portal`.
-- O registro é "o melhor possível": se falhar, a troca de senha já feita não é desfeita (o app só anota o erro no log).
-- Compatível com a versão anterior do app: tabela e funções novas; a leitura do WhatsApp continua com o mesmo formato.
-- =====================================================================

create table if not exists portal_eventos (
  id         uuid primary key default gen_random_uuid(),
  cliente_id uuid not null references clientes(id) on delete cascade,
  tipo       text not null check (tipo in ('senha_alterada')),
  origem     text not null check (origem in ('locatario', 'dono')),
  criado_em  timestamptz not null default now()
);
create index if not exists ix_portal_eventos_cliente on portal_eventos (cliente_id, criado_em desc);

alter table portal_eventos enable row level security;
drop policy if exists "dono_ve" on portal_eventos;
create policy "dono_ve" on portal_eventos for select to authenticated using (is_dono());
revoke all on portal_eventos from anon, authenticated;
grant select on portal_eventos to authenticated;

create or replace function rpc_portal_registrar_troca_senha() returns void
language plpgsql security definer set search_path = public as $$
declare
  v_cliente uuid := cliente_id_logado();
begin
  if v_cliente is null then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
  if exists (select 1 from portal_eventos
              where cliente_id = v_cliente and tipo = 'senha_alterada' and criado_em > now() - interval '10 minutes') then
    return;
  end if;
  insert into portal_eventos (cliente_id, tipo, origem) values (v_cliente, 'senha_alterada', 'locatario');
end $$;

create or replace function rpc_portal_registrar_redefinicao_senha(p_cliente_id uuid) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not is_dono() then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
  if not exists (select 1 from clientes where id = p_cliente_id) then
    raise exception 'Cliente não encontrado.';
  end if;
  insert into portal_eventos (cliente_id, tipo, origem) values (p_cliente_id, 'senha_alterada', 'dono');
end $$;

revoke all on function rpc_portal_registrar_troca_senha() from public, anon;
revoke all on function rpc_portal_registrar_redefinicao_senha(uuid) from public, anon;
grant execute on function rpc_portal_registrar_troca_senha() to authenticated;
grant execute on function rpc_portal_registrar_redefinicao_senha(uuid) to authenticated;

-- Leitura do envio de WhatsApp, agora com os eventos de senha (o resto é igual à versão anterior).
create or replace function rpc_whatsapp_dados(p_dia date) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_oleo_item uuid := item_troca_oleo_id();
  v_config    jsonb;
  v_cobrancas jsonb;
  v_pagamentos jsonb;
  v_cnhs      jsonb;
  v_documentos jsonb;
  v_oleo      jsonb;
  v_portal    jsonb;
  v_clientes  jsonb;
  v_historico jsonb;
begin
  perform fn_exige_gestao_whatsapp();
  if p_dia is null then
    raise exception 'Informe o dia de envio.';
  end if;

  select jsonb_build_object(
           'ativo', whatsapp_ativo, 'modo_teste', whatsapp_modo_teste,
           'numero_teste', whatsapp_numero_teste, 'max_repeticoes', whatsapp_max_repeticoes,
           'dias_inadimplencia', dias_inadimplencia,
           'multa_atraso', multa_atraso_valor::text, 'encargo_diario', encargo_diario_valor::text)
    into v_config
    from configuracoes where id = 1;

  select coalesce(jsonb_agg(jsonb_build_object(
           'id', v.id, 'cliente_id', v.cliente_id, 'tipo', v.tipo, 'vencimento', v.vencimento,
           'saldo', v.saldo::text, 'periodicidade', ct.periodicidade, 'situacao', v.situacao,
           'placa', m.placa) order by v.vencimento), '[]'::jsonb)
    into v_cobrancas
    from vw_cobrancas v
    join contratos ct on ct.id = v.contrato_id
    join motos m on m.id = v.moto_id
   where v.situacao in ('aberta', 'atrasada') and v.saldo > 0 and v.vencimento <= p_dia + 10;

  select coalesce(jsonb_agg(jsonb_build_object(
           'id', p.id, 'cliente_id', v.cliente_id, 'data_pagamento', p.data_pagamento,
           'valor', (p.valor + p.multa_juros)::text, 'placa', m.placa, 'vencimento', v.vencimento,
           'saldo_restante', v.saldo::text) order by p.data_pagamento), '[]'::jsonb)
    into v_pagamentos
    from pagamentos p
    join vw_cobrancas v on v.id = p.cobranca_id
    join motos m on m.id = v.moto_id
   where p.data_pagamento >= p_dia - 5;

  select coalesce(jsonb_agg(jsonb_build_object(
           'cliente_id', a.cliente_id, 'cnh_validade', a.cnh_validade, 'situacao', a.situacao)
           order by a.cliente_id), '[]'::jsonb)
    into v_cnhs
    from vw_alertas_cnh a
   where a.situacao in ('a_vencer', 'vencida');

  -- Documentos e óleo são da moto; quem recebe é o locatário do contrato ativo (moto principal ou vinculada).
  select coalesce(jsonb_agg(jsonb_build_object(
           'id', d.id, 'cliente_id', loc.cliente_id, 'placa', d.placa, 'tipo_documento', d.tipo,
           'descricao', d.descricao, 'vencimento', d.vencimento, 'situacao', d.situacao)
           order by d.vencimento), '[]'::jsonb)
    into v_documentos
    from vw_alertas_documentos d
    join lateral (
      select ct.cliente_id from contratos ct
       where ct.status = 'ativo'
         and (ct.moto_id = d.moto_id
              or exists (select 1 from contrato_motos cm where cm.contrato_id = ct.id and cm.moto_id = d.moto_id))
       limit 1
    ) loc on true
   where d.situacao in ('a_vencer', 'vencido');

  select coalesce(jsonb_agg(jsonb_build_object(
           'moto_id', a.moto_id, 'cliente_id', loc.cliente_id, 'placa', a.placa, 'situacao', a.situacao,
           'km_restantes', a.km_restantes, 'dias_restantes', a.dias_restantes, 'ultima_data', a.ultima_data)
           order by a.placa), '[]'::jsonb)
    into v_oleo
    from vw_alertas_manutencao a
    join lateral (
      select ct.cliente_id from contratos ct
       where ct.status = 'ativo'
         and (ct.moto_id = a.moto_id
              or exists (select 1 from contrato_motos cm where cm.contrato_id = ct.id and cm.moto_id = a.moto_id))
       limit 1
    ) loc on true
   where a.item_id = v_oleo_item and a.situacao in ('proxima', 'vencida');

  -- Acesso novo (a data de criação do login) e senha trocada (o último evento de cada cliente, para não repetir o aviso).
  select coalesce(jsonb_agg(jsonb_build_object(
           'tipo', 'portal_acesso', 'cliente_id', c.id, 'referencia_id', u.id,
           'ocorrido_em', (u.created_at at time zone 'America/Sao_Paulo')::date)), '[]'::jsonb)
    into v_portal
    from clientes c
    join auth.users u on u.id = c.auth_user_id
   where (u.created_at at time zone 'America/Sao_Paulo')::date >= p_dia - 5;

  select v_portal || coalesce(jsonb_agg(jsonb_build_object(
           'tipo', 'portal_senha_alterada', 'cliente_id', e.cliente_id, 'referencia_id', e.id,
           'ocorrido_em', (e.criado_em at time zone 'America/Sao_Paulo')::date)), '[]'::jsonb)
    into v_portal
    from (select distinct on (cliente_id) id, cliente_id, criado_em
            from portal_eventos
           where tipo = 'senha_alterada'
             and (criado_em at time zone 'America/Sao_Paulo')::date >= p_dia - 5
           order by cliente_id, criado_em desc) e;

  select coalesce(jsonb_agg(jsonb_build_object('id', c.id, 'nome', c.nome, 'whatsapp', c.whatsapp)), '[]'::jsonb)
    into v_clientes
    from clientes c;

  -- O que já foi enfileirado e não deu errado (falha definitiva, ignorada e cancelada não contam como aviso feito).
  select coalesce(jsonb_agg(jsonb_build_object(
           'tipo', i.tipo, 'referencia_id', i.referencia_id, 'data_referencia', i.data_referencia)), '[]'::jsonb)
    into v_historico
    from mensagens_whatsapp_itens i
    join mensagens_whatsapp m on m.id = i.mensagem_id
   where m.status in ('pendente', 'enviada') and i.data_referencia >= p_dia - 400;

  return jsonb_build_object(
    'config', v_config, 'cobrancas', v_cobrancas, 'pagamentos', v_pagamentos, 'cnhs', v_cnhs,
    'documentos', v_documentos, 'oleo', v_oleo, 'portal', v_portal, 'clientes', v_clientes,
    'historico', v_historico);
end $$;

revoke all on function rpc_whatsapp_dados(date) from public, anon;
grant execute on function rpc_whatsapp_dados(date) to authenticated;

notify pgrst, 'reload schema';
