-- =====================================================================
-- 20261002130000_corrige_idempotencia_manutencao.sql
-- Corrige 20261002120000: na consulta da chave de operação, `select ... into v_custo_pecas`
-- zerava a variável (NULL) quando a chave ainda não existia, e o `update manutencoes set
-- custo_pecas = ...` violava o NOT NULL. Toda manutenção nova com chave falhava.
-- A consulta agora usa variáveis próprias (v_repetida_*).
-- Detectado por supabase/verificar_fluxos.sql.
-- =====================================================================

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
  v_chave              uuid := nullif(payload->>'chave_operacao', '')::uuid;
  v_repetida_id        uuid;
  v_repetida_pecas     numeric(12,2);
begin
  select * into v_moto from motos where id = (payload->>'moto_id')::uuid for update;
  if not found then
    raise exception 'Moto não encontrada.';
  end if;

  -- Repetição do mesmo envio (duplo clique, nova tentativa após falha de rede): devolve o
  -- resultado do primeiro envio em vez de gravar outra manutenção. A moto já está bloqueada
  -- acima, então um envio concorrente espera o primeiro terminar e o enxerga aqui.
  if v_chave is not null then
    select id, custo_pecas into v_repetida_id, v_repetida_pecas from manutencoes where chave_operacao = v_chave;
    if found then
      return jsonb_build_object('manutencao_id', v_repetida_id, 'custo_pecas', v_repetida_pecas, 'repetido', true);
    end if;
  end if;

  if v_km < v_moto.km_atual then raise exception 'O km não pode ser menor que o atual.'; end if;
  if v_moto.status = 'inativa' then raise exception 'Reative a moto antes de registrar manutenção.'; end if;
  insert into manutencoes (
    moto_id, contrato_id, tipo, status, data_entrada, data_saida, km, oficina,
    descricao, custo_mao_obra, cobrar_do_cliente, observacoes, chave_operacao
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
    payload->>'observacoes',
    v_chave
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

notify pgrst, 'reload schema';
