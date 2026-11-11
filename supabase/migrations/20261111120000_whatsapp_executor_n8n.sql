-- =====================================================================
-- 20261111120000_whatsapp_executor_n8n.sql : o envio pode ser feito por outro executor (n8n); seção 20 do plano
--
-- A decisão de QUEM recebe O QUÊ e QUANDO continua no app (Python, testado). Quem só envia (o script ou o n8n) fica "burro":
-- reserva as pendentes, manda e registra. Para isso o banco passa a guardar o que antes só o script sabia:
--   * `whatsapp_envio_liberado_ate`: o "portão da janela". O preparo (Python) grava aqui, a cada rodada, até quando o
--     envio está liberado: no máximo 25 minutos à frente e nunca depois do fechamento da janela (8h às 19h, segunda a
--     sábado, sem feriados nacionais). Fora da janela fica nulo. Sem portão aberto, `rpc_whatsapp_reservar` não entrega nada,
--     então nenhum executor envia à noite, no domingo, no feriado, nem quando o preparo está parado (padrão seguro);
--   * `whatsapp_ultimo_enfileiramento_em` e `whatsapp_ultimo_preparo`: batimento do preparo, para o Dashboard avisar se
--     ele parar (o batimento do envio continua em `whatsapp_ultima_rodada_em`);
--   * `rpc_whatsapp_registrar_preparo(p_liberado_ate, p_resumo)`: só usuário de serviço e administradores;
--   * `rpc_whatsapp_reservar` só entrega com o envio ligado e o portão aberto, e devolve já resolvidos `numero_envio`,
--     `texto_envio` e `modo_teste`: no modo teste vão o número de teste e o aviso «[TESTE] …» (sem número de teste, nada é
--     reservado). Os campos antigos (`id, cliente_id, numero, texto, tentativas`) continuam iguais;
--   * `rpc_whatsapp_registrar_resultado` grava `teste:<id>` como id da mensagem enviada em modo teste.
-- Compatível com a versão anterior do app, com um cuidado: depois desta migration o envio só sai se o preparo novo gravar o
-- portão; aplique a migration e publique o app (que o grava) juntos.
-- =====================================================================

alter table configuracoes
  add column if not exists whatsapp_envio_liberado_ate timestamptz,
  add column if not exists whatsapp_ultimo_enfileiramento_em timestamptz,
  add column if not exists whatsapp_ultimo_preparo jsonb;

-- ---------- Registrar o preparo (portão + batimento) ----------
create or replace function rpc_whatsapp_registrar_preparo(p_liberado_ate timestamptz default null, p_resumo jsonb default null)
returns void
language plpgsql security definer set search_path = public as $$
begin
  perform fn_exige_gestao_whatsapp();
  if p_liberado_ate is not null and p_liberado_ate > now() + interval '30 minutes' then
    raise exception 'O portão do envio não pode passar de 30 minutos à frente.';
  end if;
  update configuracoes
     set whatsapp_envio_liberado_ate = p_liberado_ate,
         whatsapp_ultimo_enfileiramento_em = now(),
         whatsapp_ultimo_preparo = p_resumo
   where id = 1;
end $$;

-- ---------- Reservar pendentes para envio ----------
-- Só entrega com o envio ligado e o portão da janela aberto. Devolve até `p_limite` mensagens devidas e as reserva por
-- 10 minutos: se o executor morrer no meio, a reserva expira e elas voltam a ser entregues. Mensagem de cliente bloqueado
-- depois de enfileirada é cancelada. `numero_envio` e `texto_envio` já vêm resolvidos para o modo teste.
create or replace function rpc_whatsapp_reservar(p_limite int default 20) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  r        record;
  v_cfg    configuracoes%rowtype;
  v_lista  jsonb := '[]'::jsonb;
begin
  perform fn_exige_gestao_whatsapp();
  if p_limite is null or p_limite < 1 or p_limite > 200 then
    raise exception 'p_limite deve estar entre 1 e 200.';
  end if;

  select * into v_cfg from configuracoes where id = 1;
  if not coalesce(v_cfg.whatsapp_ativo, false) then
    return v_lista;
  end if;
  if v_cfg.whatsapp_envio_liberado_ate is null or v_cfg.whatsapp_envio_liberado_ate <= now() then
    return v_lista;
  end if;
  if coalesce(v_cfg.whatsapp_modo_teste, true) and v_cfg.whatsapp_numero_teste is null then
    return v_lista;
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
        'texto', r.texto, 'tentativas', r.tentativas,
        'modo_teste', coalesce(v_cfg.whatsapp_modo_teste, true),
        'numero_envio', case when coalesce(v_cfg.whatsapp_modo_teste, true) then v_cfg.whatsapp_numero_teste else r.numero end,
        'texto_envio', case when coalesce(v_cfg.whatsapp_modo_teste, true)
                            then '[TESTE] Esta mensagem iria para '
                                 || left(r.numero, length(r.numero) - 8) || '****' || right(r.numero, 4)
                                 || E'.\n\n' || r.texto
                            else r.texto end);
    end if;
  end loop;

  return v_lista;
end $$;

-- ---------- Registrar o resultado de um envio ----------
-- p_resultado: 'enviada' (guarda o id da Evolution; em modo teste, `teste:<id da mensagem>`), 'ignorada' (ex.: número sem
-- WhatsApp; não tenta de novo) ou 'falhou' (falha temporária: volta para a fila em 30 min x tentativas; na 3ª falha fica 'falhou').
create or replace function rpc_whatsapp_registrar_resultado(
  p_id uuid, p_resultado text, p_erro text default null, p_evolution_id text default null
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  c_max_tentativas constant int := 3;
  v_msg   mensagens_whatsapp%rowtype;
  v_tent  int;
  v_status text;
  v_evolution_id text := p_evolution_id;
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
    if (select coalesce(whatsapp_modo_teste, true) from configuracoes where id = 1)
       and coalesce(v_evolution_id, '') not like 'teste:%' then
      v_evolution_id := 'teste:' || p_id::text;
    end if;
    update mensagens_whatsapp
       set status = 'enviada', tentativas = v_tent, enviada_em = now(), erro = null,
           evolution_id = v_evolution_id, reservada_ate = null
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

revoke all on function rpc_whatsapp_registrar_preparo(timestamptz, jsonb) from public, anon;
grant execute on function rpc_whatsapp_registrar_preparo(timestamptz, jsonb) to authenticated;

notify pgrst, 'reload schema';
