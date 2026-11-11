-- =====================================================================
-- 20261112130000_whatsapp_comprovante_enviado.sql : o aviso de documento pausa enquanto há comprovante aguardando o dono
-- (Etapa 6 da seção 20 do plano)
--
-- Quando o locatário já mandou o comprovante pelo portal, ele fez a parte dele: continuar avisando que o documento venceu seria
-- insistir à toa até o dono conferir. `rpc_whatsapp_dados` passa a dizer, em cada documento, se há comprovante aguardando
-- conferência (`comprovante_enviado`); as regras de `src/domain/avisos_whatsapp.py` pulam o aviso desse documento. Recusado o
-- comprovante, o documento volta a ser avisado. O resto da leitura é igual à versão anterior.
-- Compatível com a versão anterior do app: só um campo a mais na resposta.
-- =====================================================================

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
           'descricao', d.descricao, 'vencimento', d.vencimento, 'situacao', d.situacao,
           'comprovante_enviado', exists (select 1 from documento_comprovantes c where c.documento_id = d.id and c.status = 'enviado'))
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
