-- =====================================================================
-- 20260921140000_rpc_vistoria.sql : RPC de vistoria (Fase 5)
-- =====================================================================

-- ---------------------------------------------------------------------
-- rpc_registrar_vistoria: insere a vistoria (entrega ou devolução) e grava
-- o km no histórico, numa transação só. O índice único (contrato_id, tipo)
-- já existente em vistorias garante uma vistoria de cada tipo por contrato
-- (violação vira erro 23505, tratado no service Python).
--
-- payload esperado:
-- {
--   "contrato_id": uuid, "moto_id": uuid, "tipo": "entrega|devolucao",
--   "data": timestamptz|null, "km": int, "nivel_combustivel": text|null,
--   "checklist": {"farol_dianteiro": "ok", ...}, "avarias": text|null,
--   "observacoes": text|null
-- }
--
-- ATENÇÃO — SUPERADA: redefinida em 20260921151000_fluxos_contratos.sql
-- (adiciona checagem de contrato/moto compatíveis e km não decrescente).
-- O comportamento em produção é o do arquivo mais recente.
-- ---------------------------------------------------------------------
create or replace function rpc_registrar_vistoria(payload jsonb) returns jsonb
security invoker
language plpgsql as $$
declare
  v_vistoria_id uuid;
  v_moto_id     uuid := (payload->>'moto_id')::uuid;
  v_km          int  := (payload->>'km')::int;
  v_data        timestamptz := coalesce(nullif(payload->>'data', '')::timestamptz, now());
begin
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
  values (v_moto_id, v_km, v_data::date, 'vistoria');

  return jsonb_build_object('vistoria_id', v_vistoria_id);
end $$;
