-- =====================================================================
-- 20260922010000_finalizar_manutencao_payload_jsonb.sql
-- rpc_finalizar_manutencao usava parâmetros posicionais (p_id, p_status,
-- p_data, p_km), inconsistente com o padrão de payload jsonb único usado
-- por todas as outras RPCs do projeto (rpc_registrar_manutencao,
-- rpc_registrar_vistoria, rpc_criar_contrato, etc.). Padroniza para o
-- mesmo estilo, sem mudar nenhuma regra de negócio — só a forma de
-- receber os parâmetros.
-- =====================================================================

drop function if exists rpc_finalizar_manutencao(uuid, text, date, int);

create or replace function rpc_finalizar_manutencao(payload jsonb) returns jsonb
language plpgsql security invoker set search_path = public as $$
declare
  m manutencoes%rowtype;
  moto motos%rowtype;
  contrato uuid;
  p_id     uuid := (payload->>'id')::uuid;
  p_status text := payload->>'status';
  p_data   date := (payload->>'data')::date;
  p_km     int  := (payload->>'km')::int;
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
