-- Correções de encerramento e validação de vistoria.
-- Serializa pagamentos e impede receber cobranças canceladas ou acima do saldo.
create or replace function fn_validar_pagamento() returns trigger
language plpgsql security invoker set search_path = public as $$
declare c cobrancas%rowtype; pago numeric;
begin
  select * into c from cobrancas where id = new.cobranca_id for update;
  if not found or c.status <> 'aberta' then
    raise exception 'A cobrança não está aberta para pagamento.';
  end if;
  select coalesce(sum(valor), 0) into pago from pagamentos where cobranca_id = c.id;
  if new.valor > c.valor - pago then
    raise exception 'O pagamento supera o saldo da cobrança.';
  end if;
  return new;
end $$;
create trigger trg_validar_pagamento before insert on pagamentos
for each row execute function fn_validar_pagamento();

create or replace function rpc_criar_contrato_com_vistoria(payload jsonb, p_vistoria jsonb) returns jsonb
language plpgsql security invoker set search_path = public as $$
declare resultado jsonb;
begin
  if nullif(payload->>'data_fim_prevista', '') is null then
    raise exception 'Informe a data final do contrato.';
  end if;
  if (p_vistoria->>'km')::int <> (payload->>'km_inicial')::int then
    raise exception 'A leitura da entrega deve corresponder ao km inicial.';
  end if;
  resultado := rpc_criar_contrato(payload);
  perform rpc_registrar_vistoria(p_vistoria || jsonb_build_object(
    'contrato_id', resultado->>'contrato_id', 'moto_id', payload->>'moto_id', 'tipo', 'entrega'));
  return resultado;
end $$;

create or replace function rpc_encerrar_contrato_com_vistoria(
  p_contrato_id uuid, p_data date, p_vistoria jsonb, p_caucao_devolvida boolean default false
) returns jsonb language plpgsql security invoker set search_path = public as $$
declare c contratos%rowtype; v vistorias%rowtype;
begin
  select * into c from contratos where id = p_contrato_id for update;
  if not found then raise exception 'Contrato não encontrado.'; end if;
  select * into v from vistorias where contrato_id = c.id and tipo = 'devolucao';
  if found then
    if v.km <> (p_vistoria->>'km')::int then
      raise exception 'Use a quilometragem da vistoria de devolução já registrada.';
    end if;
  else
    perform rpc_registrar_vistoria(p_vistoria || jsonb_build_object(
      'contrato_id', c.id, 'moto_id', c.moto_id, 'tipo', 'devolucao'));
  end if;
  return rpc_encerrar_contrato(c.id, p_data, (p_vistoria->>'km')::int, p_caucao_devolvida);
end $$;

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
       and not exists(select 1 from pagamentos p where p.cobranca_id = cobrancas.id)
    returning 1
  )
  select count(*) into v_qtd_canceladas from canceladas;

  insert into historico_km (moto_id, km, data, origem)
  values (v_contrato.moto_id, p_km_final, p_data, 'contrato');

  update motos set status = case when exists(select 1 from manutencoes where moto_id = v_contrato.moto_id and status = 'aberta') then 'manutencao' else 'disponivel' end where id = v_contrato.moto_id;

  return jsonb_build_object(
    'contrato_id', p_contrato_id,
    'cobrancas_canceladas', v_qtd_canceladas
  );
end $$;


create or replace function rpc_registrar_vistoria(payload jsonb) returns jsonb
security invoker
language plpgsql as $$
declare
  v_vistoria_id uuid;
  v_moto_id     uuid := (payload->>'moto_id')::uuid;
  v_km          int  := (payload->>'km')::int;
  v_data        timestamptz := coalesce(nullif(payload->>'data', '')::timestamptz, now());
begin
  perform 1 from contratos where id = (payload->>'contrato_id')::uuid and moto_id = v_moto_id for update;
  if not found then raise exception 'Contrato e moto incompatíveis.'; end if;
  perform 1 from motos where id = v_moto_id for update;
  if v_km < (select km_atual from motos where id = v_moto_id) then
    raise exception 'O km da vistoria não pode ser menor que o atual.';
  end if;
  insert into vistorias (
    contrato_id, moto_id, tipo, data, km, nivel_combustivel, checklist, avarias, observacoes
  ) values (
    (payload->>'contrato_id')::uuid,
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
