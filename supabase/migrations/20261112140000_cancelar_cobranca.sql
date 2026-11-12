-- =====================================================================
-- 20261112140000_cancelar_cobranca.sql : o dono cancela uma cobrança pela tela (pendência da Fase 7)
--
-- Até aqui só era possível cancelar cobrança direto no banco (o encerramento do contrato cancela as futuras, mas não há
-- como cancelar uma avulsa lançada por engano, uma multa de trânsito indevida ou um dano contestado).
-- Regra confirmada com o dono (12/11/2026):
--   * só cobrança em aberto (aberta ou atrasada) E sem nenhum pagamento registrado pode ser cancelada;
--     com pagamento, o dono precisa estornar antes (não há tela de estorno: continua sendo feito no banco);
--   * o motivo é obrigatório (3 a 200 caracteres) e fica guardado junto com a data do cancelamento;
--   * cancelada, a cobrança sai da dívida, das listas de cobrança e dos avisos de WhatsApp (a situação `cancelada` já era tratada assim
--     pelo encerramento do contrato) e não é gerada de novo (a agenda segue pelo maior número já existente).
-- `rpc_cancelar_cobranca(p_cobranca, p_motivo)`: só o dono. Trava a linha da cobrança antes de olhar os pagamentos, então um pagamento
-- que esteja sendo gravado no mesmo instante faz o cancelamento esperar (a chave estrangeira do pagamento trava a linha) e a RPC o enxerga.
-- A tela de pagamento só abre para cobrança em aberto; o gatilho de pagamentos nunca reabre cobrança cancelada.
-- Compatível com a versão anterior do app: só colunas novas (anuláveis) e uma função nova.
-- =====================================================================

alter table cobrancas add column if not exists motivo_cancelamento text;
alter table cobrancas add column if not exists cancelada_em timestamptz;

create or replace function rpc_cancelar_cobranca(p_cobranca uuid, p_motivo text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_cobranca cobrancas%rowtype;
  v_motivo   text := btrim(coalesce(p_motivo, ''));
begin
  if not is_dono() then
    raise exception 'Acesso negado.' using errcode = '42501';
  end if;
  if char_length(v_motivo) < 3 then
    raise exception 'Informe o motivo do cancelamento (mínimo 3 letras).';
  end if;
  if char_length(v_motivo) > 200 then
    raise exception 'O motivo do cancelamento deve ter no máximo 200 caracteres.';
  end if;

  select * into v_cobranca from cobrancas where id = p_cobranca for update;
  if not found then
    raise exception 'Cobrança não encontrada.';
  end if;
  if v_cobranca.status = 'cancelada' then
    raise exception 'Esta cobrança já está cancelada.';
  end if;
  if v_cobranca.status = 'paga' then
    raise exception 'Cobrança paga não pode ser cancelada.';
  end if;
  if exists (select 1 from pagamentos where cobranca_id = p_cobranca) then
    raise exception 'Esta cobrança já tem pagamento registrado e não pode ser cancelada.';
  end if;

  update cobrancas
     set status = 'cancelada', motivo_cancelamento = v_motivo, cancelada_em = now()
   where id = p_cobranca;

  return jsonb_build_object('cobranca_id', p_cobranca, 'status', 'cancelada');
end $$;

revoke all on function rpc_cancelar_cobranca(uuid, text) from public, anon;
grant execute on function rpc_cancelar_cobranca(uuid, text) to authenticated;
