-- =====================================================================
-- 20261105130000_vistoria_por_moto.sql
-- Vistoria por moto em contrato com várias motos (seção 19 do plano):
--   * vistorias: uma entrega e uma devolução POR MOTO do contrato, em vez de uma por contrato
--     (unique (contrato_id, moto_id, tipo)); os dados existentes continuam válidos;
--   * gatilho e rpc_registrar_vistoria: a vistoria só aceita moto do contrato (principal ou vinculada);
--   * rpc_criar_contrato_com_vistoria e rpc_encerrar_contrato_com_vistoria ganham
--     p_vistorias_vinculadas jsonb default '[]' (vistoria de cada moto vinculada, na mesma transação).
--     Quem chama sem o parâmetro novo continua funcionando. O banco não exige a vistoria das vinculadas
--     (contratos antigos não quebram); a exigência é da tela.
-- Cada vistoria extra grava o km da moto no histórico (o km_atual acompanha) e não pode ser menor que o atual.
-- =====================================================================

alter table vistorias drop constraint if exists vistorias_contrato_id_tipo_key;
alter table vistorias drop constraint if exists uq_vistorias_contrato_moto_tipo;
alter table vistorias add constraint uq_vistorias_contrato_moto_tipo unique (contrato_id, moto_id, tipo);

create or replace function fn_valida_vistoria_moto() returns trigger
language plpgsql security invoker set search_path = public as $$
begin
  if not (exists (select 1 from contratos c where c.id = new.contrato_id and c.moto_id = new.moto_id)
          or exists (select 1 from contrato_motos cm where cm.contrato_id = new.contrato_id and cm.moto_id = new.moto_id)) then
    raise exception 'A moto da vistoria não pertence ao contrato.';
  end if;
  return new;
end $$;

drop trigger if exists trg_valida_vistoria_moto on vistorias;
create trigger trg_valida_vistoria_moto before insert on vistorias
for each row execute function fn_valida_vistoria_moto();

-- ---------------------------------------------------------------------
-- rpc_registrar_vistoria: a moto da vistoria pode ser a principal OU uma vinculada do contrato
-- (antes só aceitava a principal). O resto é igual: trava contrato e moto, km não menor que o atual e histórico de km.
-- ---------------------------------------------------------------------
create or replace function rpc_registrar_vistoria(payload jsonb) returns jsonb
security invoker
language plpgsql as $$
declare
  v_vistoria_id uuid;
  v_contrato_id uuid := (payload->>'contrato_id')::uuid;
  v_moto_id     uuid := (payload->>'moto_id')::uuid;
  v_km          int  := (payload->>'km')::int;
  v_data        timestamptz := coalesce(nullif(payload->>'data', '')::timestamptz, now());
begin
  perform 1 from contratos where id = v_contrato_id for update;
  if not found
     or not (exists (select 1 from contratos where id = v_contrato_id and moto_id = v_moto_id)
             or exists (select 1 from contrato_motos where contrato_id = v_contrato_id and moto_id = v_moto_id)) then
    raise exception 'Contrato e moto incompatíveis.';
  end if;
  perform 1 from motos where id = v_moto_id for update;
  if v_km < (select km_atual from motos where id = v_moto_id) then
    raise exception 'O km da vistoria não pode ser menor que o atual.';
  end if;
  insert into vistorias (
    contrato_id, moto_id, tipo, data, km, nivel_combustivel, checklist, avarias, observacoes
  ) values (
    v_contrato_id,
    v_moto_id,
    payload->>'tipo',
    v_data,
    v_km,
    payload->>'nivel_combustivel',
    coalesce(payload->'checklist', '{}'::jsonb),
    payload->>'avarias',
    payload->>'observacoes'
  ) returning id into v_vistoria_id;

  insert into historico_km (moto_id, km, data, origem)
  values (v_moto_id, v_km, (v_data at time zone 'America/Sao_Paulo')::date, 'vistoria');

  return jsonb_build_object('vistoria_id', v_vistoria_id);
end $$;

-- ---------------------------------------------------------------------
-- Cria o contrato com a vistoria de entrega da principal e, se houver, a de cada moto vinculada.
-- p_vistorias_vinculadas: [{moto_id, km, nivel_combustivel, checklist, avarias, observacoes, data}, ...]
-- ---------------------------------------------------------------------
drop function if exists rpc_criar_contrato_com_vistoria(jsonb, jsonb);

create or replace function rpc_criar_contrato_com_vistoria(
  payload                 jsonb,
  p_vistoria              jsonb,
  p_vistorias_vinculadas  jsonb default '[]'::jsonb
) returns jsonb
language plpgsql security invoker set search_path = public as $$
declare
  resultado jsonb;
  v_item    jsonb;
  v_moto_km int;
begin
  if (p_vistoria->>'km')::int <> (payload->>'km_inicial')::int then
    raise exception 'A leitura da entrega deve corresponder ao km inicial.';
  end if;
  resultado := rpc_criar_contrato(payload);
  perform rpc_registrar_vistoria(p_vistoria || jsonb_build_object(
    'contrato_id', resultado->>'contrato_id', 'moto_id', payload->>'moto_id', 'tipo', 'entrega'));

  for v_item in select * from jsonb_array_elements(coalesce(p_vistorias_vinculadas, '[]'::jsonb))
  loop
    select km_atual into v_moto_km from motos where id = (v_item->>'moto_id')::uuid;
    if v_moto_km is null then
      raise exception 'Moto da vistoria não encontrada.';
    end if;
    if (v_item->>'km')::int < v_moto_km then
      raise exception 'A quilometragem da vistoria não pode ser menor que a atual da moto.';
    end if;
    perform rpc_registrar_vistoria(v_item || jsonb_build_object(
      'contrato_id', resultado->>'contrato_id', 'tipo', 'entrega'));
  end loop;
  return resultado;
end $$;

-- ---------------------------------------------------------------------
-- Encerra o contrato com a vistoria de devolução da principal e, se houver, a de cada moto vinculada.
-- Se a vistoria de devolução de uma moto já existir, o km informado tem de ser o dela.
-- ---------------------------------------------------------------------
drop function if exists rpc_encerrar_contrato_com_vistoria(uuid, date, jsonb, numeric, text);

create or replace function rpc_encerrar_contrato_com_vistoria(
  p_contrato_id           uuid,
  p_data                  date,
  p_vistoria              jsonb,
  p_valor_danos           numeric default 0,
  p_descricao_danos       text    default null,
  p_vistorias_vinculadas  jsonb   default '[]'::jsonb
) returns jsonb language plpgsql security invoker set search_path = public as $$
declare
  c         contratos%rowtype;
  v         vistorias%rowtype;
  v_item    jsonb;
  v_moto    uuid;
  v_moto_km int;
begin
  select * into c from contratos where id = p_contrato_id for update;
  if not found then raise exception 'Contrato não encontrado.'; end if;

  select * into v from vistorias where contrato_id = c.id and moto_id = c.moto_id and tipo = 'devolucao';
  if found then
    if v.km <> (p_vistoria->>'km')::int then
      raise exception 'Use a quilometragem da vistoria de devolução já registrada.';
    end if;
  else
    perform rpc_registrar_vistoria(p_vistoria || jsonb_build_object(
      'contrato_id', c.id, 'moto_id', c.moto_id, 'tipo', 'devolucao'));
  end if;

  for v_item in select * from jsonb_array_elements(coalesce(p_vistorias_vinculadas, '[]'::jsonb))
  loop
    v_moto := (v_item->>'moto_id')::uuid;
    if not exists (select 1 from contrato_motos cm where cm.contrato_id = c.id and cm.moto_id = v_moto) then
      raise exception 'A moto da vistoria não é uma moto vinculada do contrato.';
    end if;
    select * into v from vistorias where contrato_id = c.id and moto_id = v_moto and tipo = 'devolucao';
    if found then
      if v.km <> (v_item->>'km')::int then
        raise exception 'Use a quilometragem da vistoria de devolução já registrada.';
      end if;
    else
      select km_atual into v_moto_km from motos where id = v_moto;
      if (v_item->>'km')::int < v_moto_km then
        raise exception 'A quilometragem da vistoria não pode ser menor que a atual da moto.';
      end if;
      perform rpc_registrar_vistoria(v_item || jsonb_build_object(
        'contrato_id', c.id, 'tipo', 'devolucao'));
    end if;
  end loop;

  return rpc_encerrar_contrato(c.id, p_data, (p_vistoria->>'km')::int, p_valor_danos, p_descricao_danos);
end $$;

grant execute on function rpc_criar_contrato_com_vistoria(jsonb, jsonb, jsonb) to authenticated;
grant execute on function rpc_encerrar_contrato_com_vistoria(uuid, date, jsonb, numeric, text, jsonb) to authenticated;

notify pgrst, 'reload schema';
