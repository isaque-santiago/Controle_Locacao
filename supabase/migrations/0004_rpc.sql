-- =====================================================================
-- 0004_rpc.sql : RPCs de contrato e cobrança (transação única)
-- =====================================================================

-- Soma um período a uma data, com a mesma regra usada em domain/agenda_cobrancas.py
-- (dateutil.relativedelta): em "mensal", meses curtos usam o último dia do mês e o
-- dia fica "grudado" nesse valor nos meses seguintes (não volta a subir).
create or replace function fn_somar_periodo(p_data date, p_periodicidade text) returns date
language plpgsql immutable as $$
declare
  v_primeiro_dia_mes_seguinte date;
  v_ultimo_dia_mes_seguinte   date;
  v_dia_alvo                  int;
begin
  case p_periodicidade
    when 'diario'    then return p_data + 1;
    when 'semanal'   then return p_data + 7;
    when 'quinzenal' then return p_data + 15;
    when 'mensal' then
      v_primeiro_dia_mes_seguinte := (date_trunc('month', p_data) + interval '1 month')::date;
      v_ultimo_dia_mes_seguinte   := (v_primeiro_dia_mes_seguinte + interval '1 month' - interval '1 day')::date;
      v_dia_alvo := least(extract(day from p_data)::int, extract(day from v_ultimo_dia_mes_seguinte)::int);
      return v_primeiro_dia_mes_seguinte + (v_dia_alvo - 1);
    else
      raise exception 'Periodicidade inválida: %', p_periodicidade;
  end case;
end $$;

-- Evita duplicar cobrança de locação do mesmo contrato (usado por rpc_gerar_cobrancas_pendentes)
create unique index if not exists uq_cobrancas_contrato_numero
  on cobrancas (contrato_id, numero) where tipo = 'locacao';

-- ---------------------------------------------------------------------
-- rpc_criar_contrato: valida moto/cliente, cria o contrato, grava o km
-- inicial, muda a moto para "alugada", gera a cobrança da caução (se
-- houver) e a agenda de cobranças de locação até data_fim_prevista.
-- Nesta operação todo contrato tem prazo definido (data_fim_prevista);
-- se vier nulo, gera um horizonte padrão de 30 dias como salvaguarda.
-- ---------------------------------------------------------------------
create or replace function rpc_criar_contrato(payload jsonb) returns jsonb
security invoker
language plpgsql as $$
declare
  v_moto               motos%rowtype;
  v_cliente             clientes%rowtype;
  v_contrato_id         uuid;
  v_km_inicial          int;
  v_data_inicio         date    := (payload->>'data_inicio')::date;
  v_data_fim_prevista   date    := nullif(payload->>'data_fim_prevista', '')::date;
  v_periodicidade       text    := payload->>'periodicidade';
  v_valor_periodo       numeric(12,2) := (payload->>'valor_periodo')::numeric;
  v_caucao_valor        numeric(12,2) := coalesce((payload->>'caucao_valor')::numeric, 0);
  v_km_informado        int     := nullif(payload->>'km_inicial', '')::int;
  v_horizonte_padrao    constant int := 30;
  v_vencimento          date;
  v_numero              int := 1;
  v_qtd_cobrancas       int := 0;
begin
  select * into v_moto from motos where id = (payload->>'moto_id')::uuid for update;
  if not found then
    raise exception 'Moto não encontrada.';
  end if;
  if v_moto.status <> 'disponivel' then
    raise exception 'Moto % não está disponível (status atual: %).', v_moto.placa, v_moto.status;
  end if;

  select * into v_cliente from clientes where id = (payload->>'cliente_id')::uuid for update;
  if not found then
    raise exception 'Cliente não encontrado.';
  end if;
  if v_cliente.status <> 'ativo' then
    raise exception 'Cliente % não está ativo (status atual: %).', v_cliente.nome, v_cliente.status;
  end if;

  v_km_inicial := greatest(coalesce(v_km_informado, v_moto.km_atual), v_moto.km_atual);

  insert into contratos (
    moto_id, cliente_id, data_inicio, data_fim_prevista, periodicidade,
    valor_periodo, caucao_valor, km_inicial
  ) values (
    v_moto.id, v_cliente.id, v_data_inicio, v_data_fim_prevista, v_periodicidade,
    v_valor_periodo, v_caucao_valor, v_km_inicial
  ) returning id into v_contrato_id;

  insert into historico_km (moto_id, km, data, origem)
  values (v_moto.id, v_km_inicial, v_data_inicio, 'contrato');

  update motos set status = 'alugada' where id = v_moto.id;

  if v_caucao_valor > 0 then
    insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao)
    values (v_contrato_id, 'caucao', v_data_inicio, v_caucao_valor, 'Caução do contrato');
  end if;

  v_vencimento := v_data_inicio;
  loop
    exit when v_data_fim_prevista is not null and v_vencimento > v_data_fim_prevista;
    exit when v_data_fim_prevista is null and v_vencimento > v_data_inicio + v_horizonte_padrao;

    insert into cobrancas (contrato_id, tipo, numero, vencimento, valor)
    values (v_contrato_id, 'locacao', v_numero, v_vencimento, v_valor_periodo);

    v_qtd_cobrancas := v_qtd_cobrancas + 1;
    v_numero := v_numero + 1;
    v_vencimento := fn_somar_periodo(v_vencimento, v_periodicidade);
  end loop;

  return jsonb_build_object(
    'contrato_id', v_contrato_id,
    'km_inicial', v_km_inicial,
    'cobrancas_geradas', v_qtd_cobrancas
  );
end $$;

-- ---------------------------------------------------------------------
-- rpc_encerrar_contrato: fecha o contrato, cancela cobranças de locação
-- em aberto com vencimento futuro, grava o km final e libera a moto.
-- ---------------------------------------------------------------------
create or replace function rpc_encerrar_contrato(
  p_contrato_id       uuid,
  p_data              date,
  p_km_final          int,
  p_caucao_devolvida  boolean default false
) returns jsonb
security invoker
language plpgsql as $$
declare
  v_contrato          contratos%rowtype;
  v_qtd_canceladas    int;
begin
  select * into v_contrato from contratos where id = p_contrato_id and status = 'ativo' for update;
  if not found then
    raise exception 'Contrato não encontrado ou já encerrado.';
  end if;

  if p_km_final < v_contrato.km_inicial then
    raise exception 'km_final (%) não pode ser menor que km_inicial (%).', p_km_final, v_contrato.km_inicial;
  end if;

  update contratos
     set status = 'encerrado',
         data_encerramento = p_data,
         km_final = p_km_final,
         caucao_devolvida = p_caucao_devolvida
   where id = p_contrato_id;

  with canceladas as (
    update cobrancas
       set status = 'cancelada'
     where contrato_id = p_contrato_id
       and status = 'aberta'
       and vencimento > p_data
    returning 1
  )
  select count(*) into v_qtd_canceladas from canceladas;

  insert into historico_km (moto_id, km, data, origem)
  values (v_contrato.moto_id, p_km_final, p_data, 'contrato');

  update motos set status = 'disponivel' where id = v_contrato.moto_id;

  return jsonb_build_object(
    'contrato_id', p_contrato_id,
    'cobrancas_canceladas', v_qtd_canceladas
  );
end $$;

-- ---------------------------------------------------------------------
-- rpc_gerar_cobrancas_pendentes: idempotente. Só se aplica a contratos
-- ativos indeterminados (data_fim_prevista nula) — nesta operação isso
-- é exceção, pois os contratos sempre têm prazo definido e a agenda
-- completa já é gerada por rpc_criar_contrato.
-- ---------------------------------------------------------------------
create or replace function rpc_gerar_cobrancas_pendentes(p_horizonte_dias int default 30) returns jsonb
security invoker
language plpgsql as $$
declare
  v_contrato        contratos%rowtype;
  v_ultimo          record;
  v_vencimento      date;
  v_numero          int;
  v_limite          date := hoje_br() + p_horizonte_dias;
  v_total_geradas   int := 0;
begin
  for v_contrato in
    select * from contratos where status = 'ativo' and data_fim_prevista is null
  loop
    select max(numero) as ultimo_numero, max(vencimento) as ultimo_vencimento
      into v_ultimo
      from cobrancas
     where contrato_id = v_contrato.id and tipo = 'locacao';

    if v_ultimo.ultimo_vencimento is null then
      v_vencimento := v_contrato.data_inicio;
      v_numero := 1;
    else
      v_vencimento := fn_somar_periodo(v_ultimo.ultimo_vencimento, v_contrato.periodicidade);
      v_numero := v_ultimo.ultimo_numero + 1;
    end if;

    while v_vencimento <= v_limite loop
      insert into cobrancas (contrato_id, tipo, numero, vencimento, valor)
      values (v_contrato.id, 'locacao', v_numero, v_vencimento, v_contrato.valor_periodo)
      on conflict do nothing;

      v_total_geradas := v_total_geradas + 1;
      v_numero := v_numero + 1;
      v_vencimento := fn_somar_periodo(v_vencimento, v_contrato.periodicidade);
    end loop;
  end loop;

  return jsonb_build_object('cobrancas_geradas', v_total_geradas);
end $$;
