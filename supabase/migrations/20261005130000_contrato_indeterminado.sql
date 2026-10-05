-- =====================================================================
-- 20261005130000_contrato_indeterminado.sql
-- Decisão de negócio (seção 14.4 do plano): o contrato é por PRAZO INDETERMINADO —
-- segue aberto enquanto o cliente estiver com a moto e pagando, até o encerramento.
-- `data_fim_prevista` nula é o caso normal. A coluna já aceitava null; faltava a RPC
-- do assistente deixar de exigir a data final. As cobranças da janela móvel (30 dias à
-- frente) continuam sendo geradas por rpc_gerar_cobrancas_pendentes.
-- =====================================================================

create or replace function rpc_criar_contrato_com_vistoria(payload jsonb, p_vistoria jsonb) returns jsonb
language plpgsql security invoker set search_path = public as $$
declare resultado jsonb;
begin
  if (p_vistoria->>'km')::int <> (payload->>'km_inicial')::int then
    raise exception 'A leitura da entrega deve corresponder ao km inicial.';
  end if;
  resultado := rpc_criar_contrato(payload);
  perform rpc_registrar_vistoria(p_vistoria || jsonb_build_object(
    'contrato_id', resultado->>'contrato_id', 'moto_id', payload->>'moto_id', 'tipo', 'entrega'));
  return resultado;
end $$;

notify pgrst, 'reload schema';
