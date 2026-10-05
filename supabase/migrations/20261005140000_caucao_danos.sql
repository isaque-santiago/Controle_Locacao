-- =====================================================================
-- 20261005140000_caucao_danos.sql
-- Decisão de negócio (seção 14.3 do plano): os danos causados pelo cliente são
-- DESCONTADOS DA CAUÇÃO no encerramento.
--   devolução = caução recebida − danos
--   se os danos passarem da caução: devolução = 0 e o excedente vira uma cobrança
--   `tipo = 'dano'` contra o cliente.
-- A base é a caução efetivamente RECEBIDA (soma dos pagamentos das cobranças de
-- caução do contrato): caução não paga não se devolve.
--
-- As RPCs de encerramento trocam o parâmetro booleano `p_caucao_devolvida` por
-- `p_valor_danos` e `p_descricao_danos`. As funções antigas são removidas (em vez de
-- ficarem como sobrecarga) para o PostgREST não resolver a chamada de forma ambígua.
-- A regra é espelhada em src/domain/caucao.py.
-- =====================================================================

alter table contratos
  add column if not exists caucao_desconto_danos numeric(12,2) not null default 0
    check (caucao_desconto_danos >= 0),   -- parte da caução retida para cobrir danos
  add column if not exists caucao_valor_devolvido numeric(12,2)
    check (caucao_valor_devolvido >= 0),  -- caução − desconto, calculado no encerramento
  add column if not exists descricao_danos text;

drop function if exists rpc_encerrar_contrato_com_vistoria(uuid, date, jsonb, boolean);
drop function if exists rpc_encerrar_contrato(uuid, date, int, boolean);

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

  return jsonb_build_object(
    'contrato_id', p_contrato_id,
    'cobrancas_canceladas', v_qtd_canceladas,
    'caucao_paga', v_caucao_paga,
    'caucao_desconto_danos', v_desconto,
    'caucao_valor_devolvido', v_devolucao,
    'dano_excedente', v_excedente
  );
end $$;

create or replace function rpc_encerrar_contrato_com_vistoria(
  p_contrato_id       uuid,
  p_data              date,
  p_vistoria          jsonb,
  p_valor_danos       numeric default 0,
  p_descricao_danos   text    default null
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
  return rpc_encerrar_contrato(c.id, p_data, (p_vistoria->>'km')::int, p_valor_danos, p_descricao_danos);
end $$;

grant execute on function rpc_encerrar_contrato(uuid, date, int, numeric, text) to authenticated;
grant execute on function rpc_encerrar_contrato_com_vistoria(uuid, date, jsonb, numeric, text) to authenticated;

notify pgrst, 'reload schema';
