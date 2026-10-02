-- =====================================================================
-- 20261002120000_idempotencia_operacoes.sql
-- Etapa 7 do plano de UI/UX: cliques repetidos e novas tentativas não podem gerar
-- registros duplicados. O app gera um uuid por envio (`chave_operacao`) e o banco
-- recusa a segunda gravação com a mesma chave:
--   - pagamentos, documentos_moto e historico_km: coluna + índice único parcial; o
--     repositório consulta a chave antes de gravar e trata 23505 como "já gravado";
--   - manutencoes: a RPC rpc_registrar_manutencao devolve o resultado do primeiro
--     envio quando a chave já existe.
-- Registros antigos ficam com chave nula (o índice só vale para chaves informadas).
-- Motos (placa), clientes (CPF), contratos (um ativo por moto) e vistorias (uma por
-- tipo e contrato) já têm chave natural e não precisam disto.
-- =====================================================================

alter table pagamentos     add column if not exists chave_operacao uuid;
alter table documentos_moto add column if not exists chave_operacao uuid;
alter table historico_km   add column if not exists chave_operacao uuid;
alter table manutencoes    add column if not exists chave_operacao uuid;

create unique index if not exists uq_pagamentos_chave_operacao
  on pagamentos (chave_operacao) where chave_operacao is not null;
create unique index if not exists uq_documentos_moto_chave_operacao
  on documentos_moto (chave_operacao) where chave_operacao is not null;
create unique index if not exists uq_historico_km_chave_operacao
  on historico_km (chave_operacao) where chave_operacao is not null;
create unique index if not exists uq_manutencoes_chave_operacao
  on manutencoes (chave_operacao) where chave_operacao is not null;

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
begin
  select * into v_moto from motos where id = (payload->>'moto_id')::uuid for update;
  if not found then
    raise exception 'Moto não encontrada.';
  end if;

  -- Repetição do mesmo envio (duplo clique, nova tentativa após falha de rede): devolve o
  -- resultado do primeiro envio em vez de gravar outra manutenção. A moto já está bloqueada
  -- acima, então um envio concorrente espera o primeiro terminar e o enxerga aqui.
  if v_chave is not null then
    select id, custo_pecas into v_manutencao_id, v_custo_pecas from manutencoes where chave_operacao = v_chave;
    if found then
      return jsonb_build_object('manutencao_id', v_manutencao_id, 'custo_pecas', v_custo_pecas, 'repetido', true);
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
