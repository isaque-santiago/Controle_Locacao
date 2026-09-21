create or replace function rpc_finalizar_manutencao(p_id uuid, p_status text, p_data date, p_km int)
returns jsonb language plpgsql security invoker set search_path = public as $$
declare m manutencoes%rowtype; moto motos%rowtype; contrato uuid;
begin
  -- Mesma ordem de bloqueio do registro: moto, depois manutenção.
  select * into m from manutencoes where id = p_id;
  if not found then raise exception 'Manutenção não encontrada.'; end if;
  select * into moto from motos where id = m.moto_id for update;
  select * into m from manutencoes where id = p_id for update;
  if m.status <> 'aberta' then raise exception 'A manutenção já foi finalizada.'; end if;
  if p_status not in ('concluida', 'cancelada') or p_data < m.data_entrada or p_km < moto.km_atual then
    raise exception 'Confira status, data e quilometragem.';
  end if;
  update manutencoes set status = p_status, data_saida = p_data, km = p_km where id = p_id;
  select id into contrato from contratos where moto_id = m.moto_id and status = 'ativo';
  if p_status = 'concluida' then
    update moto_plano_manutencao set ultima_km = p_km, ultima_data = p_data
    where moto_id = m.moto_id and item_id in (select item_id from manutencao_itens where manutencao_id = m.id);
    insert into historico_km(moto_id, km, data, origem) values (m.moto_id, p_km, p_data, 'manutencao');
    if m.cobrar_do_cliente then
      if contrato is null then raise exception 'Não há contrato ativo para cobrar o serviço.'; end if;
      insert into cobrancas(contrato_id, tipo, vencimento, valor, descricao)
      values (contrato, 'dano', p_data, m.custo_total, 'Manutenção: ' || m.descricao);
    end if;
  end if;
  update motos set status = case
    when exists(select 1 from manutencoes where moto_id = m.moto_id and status = 'aberta') then 'manutencao'
    when contrato is not null then 'alugada' else 'disponivel' end where id = m.moto_id;
  return jsonb_build_object('manutencao_id', m.id);
end $$;

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

  if v_km < v_moto.km_atual then raise exception 'O km não pode ser menor que o atual.'; end if;
  if v_moto.status = 'inativa' then raise exception 'Reative a moto antes de registrar manutenção.'; end if;
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
       set status = case when exists(select 1 from manutencoes where moto_id = v_moto.id and status = 'aberta') then 'manutencao' when v_contrato_vigente_id is not null then 'alugada' else 'disponivel' end
     where id = v_moto.id;
  end if;

  if v_status = 'concluida' and coalesce((payload->>'cobrar_do_cliente')::boolean, false) then
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
