-- =====================================================================
-- 20260921130000_rpc_manutencao.sql : RPCs de manutenção (Fase 3)
-- =====================================================================

-- ---------------------------------------------------------------------
-- rpc_aplicar_plano_padrao: cria as linhas de moto_plano_manutencao para
-- todos os itens ativos do catálogo, com baseline (ultima_km = km_atual,
-- ultima_data = hoje) para a moto não nascer com tudo "vencido". Idempotente
-- (on conflict do nothing na unique (moto_id, item_id)).
-- ---------------------------------------------------------------------
create or replace function rpc_aplicar_plano_padrao(p_moto_id uuid) returns jsonb
security invoker
language plpgsql as $$
declare
  v_moto        motos%rowtype;
  v_qtd_criadas int;
begin
  select * into v_moto from motos where id = p_moto_id;
  if not found then
    raise exception 'Moto não encontrada.';
  end if;

  with inseridos as (
    insert into moto_plano_manutencao (moto_id, item_id, ultima_km, ultima_data)
    select p_moto_id, i.id, v_moto.km_atual, hoje_br()
      from itens_manutencao i
     where i.ativo
    on conflict (moto_id, item_id) do nothing
    returning 1
  )
  select count(*) into v_qtd_criadas from inseridos;

  return jsonb_build_object('itens_aplicados', v_qtd_criadas);
end $$;

-- ---------------------------------------------------------------------
-- rpc_registrar_manutencao: insere a manutenção e seus itens; soma
-- custo_pecas; se concluída, atualiza ultima_km/ultima_data do plano para
-- cada item com item_id e grava historico_km; ajusta o status da moto; se
-- cobrar_do_cliente, cria cobrança tipo 'dano' no contrato vigente da moto.
--
-- payload esperado:
-- {
--   "moto_id": uuid, "contrato_id": uuid|null, "tipo": "preventiva|corretiva",
--   "status": "aberta|concluida|cancelada", "data_entrada": date,
--   "data_saida": date|null, "km": int, "oficina": text|null,
--   "descricao": text, "custo_mao_obra": numeric, "cobrar_do_cliente": bool,
--   "observacoes": text|null,
--   "itens": [{"item_id": uuid|null, "descricao": text, "quantidade": numeric,
--              "valor_unitario": numeric}, ...]
-- }
--
-- ATENÇÃO — SUPERADA: redefinida em 20260921152000_finalizar_manutencao.sql
-- (adiciona checagem de km/status da moto e move a validação de
-- cobrar_do_cliente para dentro do bloco "concluida"). O comportamento em
-- produção é o do arquivo mais recente.
-- ---------------------------------------------------------------------
create or replace function rpc_registrar_manutencao(payload jsonb) returns jsonb
security invoker
language plpgsql as $$
declare
  v_moto              motos%rowtype;
  v_manutencao_id      uuid;
  v_status             text    := coalesce(payload->>'status', 'concluida');
  v_km                 int     := (payload->>'km')::int;
  v_custo_pecas        numeric(12,2) := 0;
  v_item               jsonb;
  v_contrato_vigente_id uuid;
  v_custo_total        numeric(12,2);
begin
  select * into v_moto from motos where id = (payload->>'moto_id')::uuid for update;
  if not found then
    raise exception 'Moto não encontrada.';
  end if;

  insert into manutencoes (
    moto_id, contrato_id, tipo, status, data_entrada, data_saida, km, oficina,
    descricao, custo_mao_obra, cobrar_do_cliente, observacoes
  ) values (
    v_moto.id,
    nullif(payload->>'contrato_id', '')::uuid,
    payload->>'tipo',
    v_status,
    (payload->>'data_entrada')::date,
    nullif(payload->>'data_saida', '')::date,
    v_km,
    payload->>'oficina',
    payload->>'descricao',
    coalesce((payload->>'custo_mao_obra')::numeric, 0),
    coalesce((payload->>'cobrar_do_cliente')::boolean, false),
    payload->>'observacoes'
  ) returning id into v_manutencao_id;

  for v_item in select * from jsonb_array_elements(coalesce(payload->'itens', '[]'::jsonb))
  loop
    insert into manutencao_itens (manutencao_id, item_id, descricao, quantidade, valor_unitario)
    values (
      v_manutencao_id,
      nullif(v_item->>'item_id', '')::uuid,
      v_item->>'descricao',
      coalesce((v_item->>'quantidade')::numeric, 1),
      coalesce((v_item->>'valor_unitario')::numeric, 0)
    );

    v_custo_pecas := v_custo_pecas
      + coalesce((v_item->>'quantidade')::numeric, 1) * coalesce((v_item->>'valor_unitario')::numeric, 0);

    if v_status = 'concluida' and (v_item->>'item_id') is not null and (v_item->>'item_id') <> '' then
      update moto_plano_manutencao
         set ultima_km = v_km, ultima_data = (payload->>'data_entrada')::date
       where moto_id = v_moto.id and item_id = (v_item->>'item_id')::uuid;
    end if;
  end loop;

  update manutencoes set custo_pecas = v_custo_pecas where id = v_manutencao_id;

  if v_status = 'concluida' and v_km >= v_moto.km_atual then
    insert into historico_km (moto_id, km, data, origem)
    values (v_moto.id, v_km, (payload->>'data_entrada')::date, 'manutencao');
  end if;

  if v_status = 'aberta' then
    update motos set status = 'manutencao' where id = v_moto.id;
  elsif v_status = 'concluida' then
    select id into v_contrato_vigente_id
      from contratos where moto_id = v_moto.id and status = 'ativo';
    update motos
       set status = case when v_contrato_vigente_id is not null then 'alugada' else 'disponivel' end
     where id = v_moto.id;
  end if;

  if coalesce((payload->>'cobrar_do_cliente')::boolean, false) then
    select id into v_contrato_vigente_id
      from contratos where moto_id = v_moto.id and status = 'ativo';
    if v_contrato_vigente_id is null then
      raise exception 'Não é possível cobrar do cliente: a moto não tem contrato ativo.';
    end if;

    select custo_total into v_custo_total from manutencoes where id = v_manutencao_id;
    insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao)
    values (
      v_contrato_vigente_id, 'dano', coalesce((payload->>'data_saida')::date, hoje_br()),
      v_custo_total, 'Manutenção: ' || (payload->>'descricao')
    );
  end if;

  return jsonb_build_object('manutencao_id', v_manutencao_id, 'custo_pecas', v_custo_pecas);
end $$;
