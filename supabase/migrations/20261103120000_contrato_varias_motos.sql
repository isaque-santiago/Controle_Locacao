-- =====================================================================
-- 20261103120000_contrato_varias_motos.sql
-- Contrato com mais de uma moto (ex.: Plano Conquista, uma parcela única que vale por duas motos).
--   * contratos.moto_id continua sendo a moto PRINCIPAL: parcela, receita e relatórios por veículo
--     ficam nela (decisão de 03/11/2026). As demais motos ficam em contrato_motos (vinculadas);
--   * uma moto só pode estar em um contrato ativo, como principal ou vinculada;
--   * rpc_criar_contrato aceita "motos_vinculadas" (lista de ids) e rpc_encerrar_contrato libera todas;
--   * fn_validar_moto também impede inativar moto vinculada a contrato ativo;
--   * vw_contrato_motos lista as motos de cada contrato, principal primeiro.
-- Compatível com a versão anterior do app: sem "motos_vinculadas" tudo funciona como antes.
-- =====================================================================

create table if not exists contrato_motos (
  contrato_id  uuid not null references contratos(id) on delete cascade,
  moto_id      uuid not null references motos(id),
  criado_em    timestamptz not null default now(),
  primary key (contrato_id, moto_id)
);
create index if not exists ix_contrato_motos_moto on contrato_motos (moto_id);

-- A moto vinculada não pode ser a principal do próprio contrato, nem estar em outro contrato ativo.
create or replace function fn_valida_moto_vinculada() returns trigger
language plpgsql security invoker set search_path = public as $$
declare v_principal uuid; v_status text;
begin
  select moto_id, status into v_principal, v_status from contratos where id = new.contrato_id;
  if new.moto_id = v_principal then
    raise exception 'A moto principal do contrato não pode ser listada como vinculada.';
  end if;
  if v_status = 'ativo' and exists (
    select 1 from contratos c
     where c.status = 'ativo' and c.id <> new.contrato_id
       and (c.moto_id = new.moto_id
            or exists (select 1 from contrato_motos cm where cm.contrato_id = c.id and cm.moto_id = new.moto_id))
  ) then
    raise exception 'A moto já está em outro contrato ativo.';
  end if;
  return new;
end $$;

drop trigger if exists trg_valida_moto_vinculada on contrato_motos;
create trigger trg_valida_moto_vinculada before insert or update on contrato_motos
for each row execute function fn_valida_moto_vinculada();

-- A moto principal de um contrato ativo não pode ser vinculada a outro contrato ativo.
create or replace function fn_valida_principal_nao_vinculada() returns trigger
language plpgsql security invoker set search_path = public as $$
begin
  if new.status = 'ativo' and exists (
    select 1 from contrato_motos cm
      join contratos c on c.id = cm.contrato_id
     where cm.moto_id = new.moto_id and c.status = 'ativo' and c.id <> new.id
  ) then
    raise exception 'A moto já está vinculada a outro contrato ativo.';
  end if;
  return new;
end $$;

drop trigger if exists trg_valida_principal_nao_vinculada on contratos;
create trigger trg_valida_principal_nao_vinculada before insert or update of moto_id, status on contratos
for each row execute function fn_valida_principal_nao_vinculada();

-- Motos de cada contrato (a principal vem primeiro).
create or replace view vw_contrato_motos with (security_invoker = true) as
select c.id as contrato_id, c.moto_id, true as principal, m.placa, m.modelo
  from contratos c join motos m on m.id = c.moto_id
union all
select cm.contrato_id, cm.moto_id, false, m.placa, m.modelo
  from contrato_motos cm join motos m on m.id = cm.moto_id;

alter table contrato_motos enable row level security;
drop policy if exists "dono_total" on contrato_motos;
create policy "dono_total" on contrato_motos for all to authenticated using (is_dono()) with check (is_dono());
grant select, insert, update, delete on contrato_motos to authenticated;

-- Inativar a moto: também bloqueia se ela estiver vinculada a um contrato ativo.
create or replace function fn_validar_moto() returns trigger
language plpgsql security invoker set search_path = public as $$
begin
  if new.km_atual < old.km_atual then
    raise exception 'A quilometragem atual não pode diminuir.';
  end if;
  if new.status = 'inativa' and (exists(select 1 from contratos where moto_id = new.id and status = 'ativo')
      or exists(select 1 from contrato_motos cm join contratos c on c.id = cm.contrato_id
                 where cm.moto_id = new.id and c.status = 'ativo')
      or exists(select 1 from manutencoes where moto_id = new.id and status = 'aberta')) then
    raise exception 'Encerre os contratos e manutenções antes de inativar a moto.';
  end if;
  return new;
end $$;

-- ---------------------------------------------------------------------
-- rpc_criar_contrato: igual à versão de 20261022120000 (promessa de compra), com "motos_vinculadas".
-- As motos vinculadas precisam estar disponíveis; ficam alugadas e ganham a leitura de km atual no histórico.
-- ---------------------------------------------------------------------
create or replace function rpc_criar_contrato(payload jsonb) returns jsonb
security invoker
language plpgsql as $$
declare
  v_moto               motos%rowtype;
  v_vinc               motos%rowtype;
  v_cliente            clientes%rowtype;
  v_contrato_id        uuid;
  v_km_inicial         int;
  v_data_inicio        date    := (payload->>'data_inicio')::date;
  v_data_fim_prevista  date    := nullif(payload->>'data_fim_prevista', '')::date;
  v_periodicidade      text    := payload->>'periodicidade';
  v_valor_periodo      numeric(12,2) := (payload->>'valor_periodo')::numeric;
  v_caucao_valor       numeric(12,2) := coalesce((payload->>'caucao_valor')::numeric, 0);
  v_km_informado       int     := nullif(payload->>'km_inicial', '')::int;
  v_tipo_contrato      text    := coalesce(nullif(payload->>'tipo_contrato', ''), 'locacao');
  v_numero_parcelas    int     := nullif(payload->>'numero_parcelas', '')::int;
  v_valor_entrada      numeric(12,2) := coalesce(nullif(payload->>'valor_entrada', '')::numeric, 0);
  v_pagas_inicial      int     := coalesce(nullif(payload->>'parcelas_pagas_inicial', '')::int, 0);
  v_dia_cobranca       int     := nullif(payload->>'dia_cobranca', '')::int;
  v_primeira_cobranca  date    := nullif(payload->>'primeira_cobranca', '')::date;
  v_vinculadas         uuid[]  := '{}';
  v_vinc_id            uuid;
  v_valor_total        numeric(12,2);
  v_horizonte_padrao   constant int := 30;
  v_max_motos          constant int := 5;
  v_vencimento         date;
  v_numero             int;
  v_qtd_cobrancas      int := 0;
begin
  select * into v_moto from motos where id = (payload->>'moto_id')::uuid for update;
  if not found then
    raise exception 'Moto não encontrada.';
  end if;
  if v_moto.status <> 'disponivel' then
    raise exception 'Moto % não está disponível (status atual: %).', v_moto.placa, v_moto.status;
  end if;

  -- Motos vinculadas (opcional): sem repetição, sem a principal e no máximo 5 motos por contrato.
  if jsonb_typeof(payload->'motos_vinculadas') = 'array' then
    select coalesce(array_agg(x::uuid order by x::uuid), '{}') into v_vinculadas
      from jsonb_array_elements_text(payload->'motos_vinculadas') x;
  end if;
  if cardinality(v_vinculadas) > 0 then
    if (select count(distinct m) from unnest(v_vinculadas) m) <> cardinality(v_vinculadas) then
      raise exception 'A mesma moto foi informada mais de uma vez.';
    end if;
    if v_moto.id = any(v_vinculadas) then
      raise exception 'A moto principal não pode estar na lista de motos vinculadas.';
    end if;
    if cardinality(v_vinculadas) + 1 > v_max_motos then
      raise exception 'Um contrato aceita até % motos.', v_max_motos;
    end if;
  end if;

  select * into v_cliente from clientes where id = (payload->>'cliente_id')::uuid for update;
  if not found then
    raise exception 'Cliente não encontrado.';
  end if;
  if v_cliente.status <> 'ativo' then
    raise exception 'Cliente % não está ativo (status atual: %).', v_cliente.nome, v_cliente.status;
  end if;

  if v_tipo_contrato not in ('locacao', 'promessa_compra') then
    raise exception 'Tipo de contrato inválido: %.', v_tipo_contrato;
  end if;
  if v_tipo_contrato = 'promessa_compra' then
    if v_numero_parcelas is null or v_numero_parcelas <= 0 then
      raise exception 'Informe o número de parcelas da promessa de compra.';
    end if;
    if v_pagas_inicial > v_numero_parcelas then
      raise exception 'As parcelas já pagas não podem superar o número de parcelas.';
    end if;
    v_valor_total := v_valor_entrada + v_numero_parcelas * v_valor_periodo;
  else
    v_numero_parcelas := null;
    v_valor_entrada := 0;
    v_pagas_inicial := 0;
  end if;

  v_km_inicial := greatest(coalesce(v_km_informado, v_moto.km_atual), v_moto.km_atual);

  insert into contratos (
    moto_id, cliente_id, data_inicio, data_fim_prevista, periodicidade,
    valor_periodo, caucao_valor, km_inicial,
    tipo_contrato, numero_parcelas, valor_total, valor_entrada,
    parcelas_pagas_inicial, dia_cobranca, primeira_cobranca
  ) values (
    v_moto.id, v_cliente.id, v_data_inicio, v_data_fim_prevista, v_periodicidade,
    v_valor_periodo, v_caucao_valor, v_km_inicial,
    v_tipo_contrato, v_numero_parcelas, v_valor_total, v_valor_entrada,
    v_pagas_inicial, v_dia_cobranca, v_primeira_cobranca
  ) returning id into v_contrato_id;

  insert into historico_km (moto_id, km, data, origem)
  values (v_moto.id, v_km_inicial, v_data_inicio, 'contrato');

  update motos set status = 'alugada' where id = v_moto.id;

  -- Motos vinculadas: travadas em ordem de id (evita deadlock entre contratos simultâneos).
  foreach v_vinc_id in array v_vinculadas loop
    select * into v_vinc from motos where id = v_vinc_id for update;
    if not found then
      raise exception 'Moto vinculada não encontrada.';
    end if;
    if v_vinc.status <> 'disponivel' then
      raise exception 'Moto % não está disponível (status atual: %).', v_vinc.placa, v_vinc.status;
    end if;
    insert into contrato_motos (contrato_id, moto_id) values (v_contrato_id, v_vinc.id);
    insert into historico_km (moto_id, km, data, origem)
    values (v_vinc.id, v_vinc.km_atual, v_data_inicio, 'contrato');
    update motos set status = 'alugada' where id = v_vinc.id;
  end loop;

  if v_caucao_valor > 0 then
    insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao)
    values (v_contrato_id, 'caucao', v_data_inicio, v_caucao_valor, 'Caução do contrato');
  end if;

  if v_valor_entrada > 0 then
    insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao)
    values (v_contrato_id, 'outros', v_data_inicio, v_valor_entrada, 'Entrada da promessa de compra');
  end if;

  v_vencimento := coalesce(v_primeira_cobranca, v_data_inicio);
  v_numero := v_pagas_inicial + 1;
  loop
    exit when v_data_fim_prevista is not null and v_vencimento > v_data_fim_prevista;
    exit when v_data_fim_prevista is null and v_vencimento > v_data_inicio + v_horizonte_padrao;
    exit when v_numero_parcelas is not null and v_numero > v_numero_parcelas;

    insert into cobrancas (contrato_id, tipo, numero, vencimento, valor)
    values (v_contrato_id, 'locacao', v_numero, v_vencimento, v_valor_periodo);

    v_qtd_cobrancas := v_qtd_cobrancas + 1;
    v_numero := v_numero + 1;
    v_vencimento := fn_somar_periodo(v_vencimento, v_periodicidade);
  end loop;

  return jsonb_build_object(
    'contrato_id', v_contrato_id,
    'km_inicial', v_km_inicial,
    'cobrancas_geradas', v_qtd_cobrancas,
    'motos_vinculadas', cardinality(v_vinculadas)
  );
end $$;

-- ---------------------------------------------------------------------
-- rpc_encerrar_contrato: igual à versão de 20261005140000 (caução e danos), liberando também as
-- motos vinculadas. O km final vale só para a moto principal; as vinculadas voltam disponíveis
-- (ou em manutenção, se houver manutenção aberta) sem nova leitura de km.
-- ---------------------------------------------------------------------
create or replace function rpc_encerrar_contrato(
  p_contrato_id       uuid,
  p_data              date,
  p_km_final          int,
  p_valor_danos       numeric default 0,
  p_descricao_danos   text    default null
) returns jsonb
security invoker
language plpgsql as $$
declare
  v_contrato          contratos%rowtype;
  v_vinc_id           uuid;
  v_qtd_canceladas    int;
  v_danos             numeric(12,2) := round(coalesce(p_valor_danos, 0), 2);
  v_descricao         text := nullif(btrim(coalesce(p_descricao_danos, '')), '');
  v_caucao_paga       numeric(12,2);
  v_desconto          numeric(12,2);
  v_devolucao         numeric(12,2);
  v_excedente         numeric(12,2);
begin
  select * into v_contrato from contratos where id = p_contrato_id and status = 'ativo' for update;
  if not found then
    raise exception 'Contrato não encontrado ou já encerrado.';
  end if;

  if p_data < v_contrato.data_inicio then
    raise exception 'O encerramento não pode anteceder o início.';
  end if;
  perform 1 from motos where id = v_contrato.moto_id for update;
  if p_km_final < (select km_atual from motos where id = v_contrato.moto_id) then
    raise exception 'O km final não pode ser menor que o atual.';
  end if;
  if p_km_final < v_contrato.km_inicial then
    raise exception 'km_final (%) não pode ser menor que km_inicial (%).', p_km_final, v_contrato.km_inicial;
  end if;

  if v_danos < 0 then
    raise exception 'O valor dos danos não pode ser negativo.';
  end if;
  if v_danos > 0 and v_descricao is null then
    raise exception 'Descreva os danos que serão descontados da caução.';
  end if;

  -- Caução efetivamente recebida neste contrato (base da devolução).
  select coalesce(sum(p.valor), 0) into v_caucao_paga
    from pagamentos p
    join cobrancas c on c.id = p.cobranca_id
   where c.contrato_id = p_contrato_id and c.tipo = 'caucao';

  v_desconto  := least(v_danos, v_caucao_paga);
  v_devolucao := v_caucao_paga - v_desconto;
  v_excedente := v_danos - v_desconto;

  update contratos
     set status = 'encerrado',
         data_encerramento = p_data,
         km_final = p_km_final,
         caucao_devolvida = v_devolucao > 0,
         caucao_desconto_danos = v_desconto,
         caucao_valor_devolvido = v_devolucao,
         descricao_danos = v_descricao
   where id = p_contrato_id;

  with canceladas as (
    update cobrancas
       set status = 'cancelada'
     where contrato_id = p_contrato_id
       and status = 'aberta'
       and vencimento > p_data
       and not exists(select 1 from pagamentos p where p.cobranca_id = cobrancas.id)
    returning 1
  )
  select count(*) into v_qtd_canceladas from canceladas;

  -- Danos acima da caução: o excedente é cobrado do cliente.
  if v_excedente > 0 then
    insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao)
    values (p_contrato_id, 'dano', p_data, v_excedente, 'Danos acima da caução: ' || v_descricao);
  end if;

  insert into historico_km (moto_id, km, data, origem)
  values (v_contrato.moto_id, p_km_final, p_data, 'contrato');

  update motos set status = case when exists(select 1 from manutencoes where moto_id = v_contrato.moto_id and status = 'aberta') then 'manutencao' else 'disponivel' end where id = v_contrato.moto_id;

  -- Motos vinculadas voltam a ficar disponíveis (travadas em ordem de id).
  for v_vinc_id in
    select m.id from contrato_motos cm join motos m on m.id = cm.moto_id
     where cm.contrato_id = p_contrato_id order by m.id for update of m
  loop
    update motos
       set status = case when exists(select 1 from manutencoes where moto_id = v_vinc_id and status = 'aberta') then 'manutencao' else 'disponivel' end
     where id = v_vinc_id;
  end loop;

  return jsonb_build_object(
    'contrato_id', p_contrato_id,
    'cobrancas_canceladas', v_qtd_canceladas,
    'caucao_paga', v_caucao_paga,
    'caucao_desconto_danos', v_desconto,
    'caucao_valor_devolvido', v_devolucao,
    'dano_excedente', v_excedente
  );
end $$;

grant execute on function rpc_criar_contrato(jsonb) to authenticated;
grant execute on function rpc_encerrar_contrato(uuid, date, int, numeric, text) to authenticated;

notify pgrst, 'reload schema';
