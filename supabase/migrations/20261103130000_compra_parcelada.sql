-- =====================================================================
-- 20261103130000_compra_parcelada.sql
-- Compra a prazo como dívida (ex.: Celta, R$ 14.000 = entrada de R$ 5.000 + 9 parcelas mensais de R$ 1.000, dia 28):
--   * dividas.tipo ganha 'compra_parcelada', com valor_entrada e primeira_parcela;
--     total = entrada + parcelas x valor da parcela (restrição ck_dividas_compra_parcelada);
--   * dividas_vencimentos.numero e pagamentos_divida.vencimento_id ligam cada pagamento a uma parcela;
--     a parcela vira "paga" sozinha quando a soma dos pagamentos cobre o valor (como em cobrancas);
--   * rpc_criar_compra_parcelada gera o calendário de parcelas (e a entrada) numa transação só;
--   * rpc_pagar_parcela_divida registra o pagamento de uma parcela;
--   * vw_parcelas_divida mostra cada parcela com valor pago, saldo e situação.
-- Compatível com a versão anterior do app: só colunas com padrão, funções e view novas.
-- =====================================================================

alter table dividas drop constraint if exists dividas_tipo_check;
alter table dividas add constraint dividas_tipo_check
  check (tipo in ('moto_fiado','financiamento','fornecedor','rastreador','emprestimo','compra_parcelada'));

alter table dividas
  add column if not exists valor_entrada   numeric(12,2) not null default 0 check (valor_entrada >= 0),
  add column if not exists primeira_parcela date;

alter table dividas drop constraint if exists ck_dividas_compra_parcelada;
alter table dividas add constraint ck_dividas_compra_parcelada check (
  tipo <> 'compra_parcelada'
  or (numero_parcelas is not null
      and valor_parcela is not null
      and primeira_parcela is not null
      and valor_original = valor_entrada + numero_parcelas * valor_parcela)
);

alter table dividas_vencimentos
  add column if not exists numero int check (numero > 0);
create unique index if not exists uq_dividas_venc_numero
  on dividas_vencimentos (divida_id, numero) where numero is not null;

alter table pagamentos_divida
  add column if not exists vencimento_id uuid references dividas_vencimentos(id) on delete set null;
create index if not exists ix_pagamentos_divida_venc on pagamentos_divida (vencimento_id) where vencimento_id is not null;

-- Um pagamento ligado a uma parcela não pode superar o saldo dela nem apontar para parcela de outra dívida.
create or replace function fn_valida_pagamento_parcela() returns trigger
language plpgsql security invoker set search_path = public as $$
declare v_parcela dividas_vencimentos%rowtype; v_pago numeric;
begin
  if new.vencimento_id is null then
    return new;
  end if;
  select * into v_parcela from dividas_vencimentos where id = new.vencimento_id for update;
  if not found then
    raise exception 'Parcela não encontrada.';
  end if;
  if v_parcela.divida_id <> new.divida_id then
    raise exception 'A parcela não pertence a essa dívida.';
  end if;
  select coalesce(sum(valor), 0) into v_pago
    from pagamentos_divida where vencimento_id = new.vencimento_id and id is distinct from new.id;
  if v_pago + new.valor > v_parcela.valor then
    raise exception 'O pagamento supera o saldo da parcela.';
  end if;
  return new;
end $$;

drop trigger if exists trg_valida_pagamento_parcela on pagamentos_divida;
create trigger trg_valida_pagamento_parcela before insert or update on pagamentos_divida
for each row execute function fn_valida_pagamento_parcela();

-- Marca a parcela como paga (paga_em = data do último pagamento) quando a soma cobre o valor.
create or replace function fn_atualiza_parcela_divida() returns trigger
language plpgsql security invoker set search_path = public as $$
declare v_ids uuid[] := '{}'; v_id uuid; v_pago numeric; v_valor numeric; v_data date;
begin
  if tg_op in ('INSERT', 'UPDATE') and new.vencimento_id is not null then
    v_ids := v_ids || new.vencimento_id;
  end if;
  if tg_op in ('UPDATE', 'DELETE') and old.vencimento_id is not null and not (old.vencimento_id = any(v_ids)) then
    v_ids := v_ids || old.vencimento_id;
  end if;
  foreach v_id in array v_ids loop
    select coalesce(sum(valor), 0), max(data) into v_pago, v_data from pagamentos_divida where vencimento_id = v_id;
    select valor into v_valor from dividas_vencimentos where id = v_id;
    if v_valor is not null then
      update dividas_vencimentos
         set paga_em = case when v_pago >= v_valor then v_data else null end
       where id = v_id;
    end if;
  end loop;
  return null;
end $$;

drop trigger if exists trg_atualiza_parcela_divida on pagamentos_divida;
create trigger trg_atualiza_parcela_divida after insert or update or delete on pagamentos_divida
for each row execute function fn_atualiza_parcela_divida();

-- Parcelas com valor pago, saldo e situação (paga, atrasada, a vencer ou sem data).
create or replace view vw_parcelas_divida with (security_invoker = true) as
select
  v.id as vencimento_id,
  v.divida_id,
  d.credor,
  d.tipo,
  d.moto_id,
  v.numero,
  v.vencimento,
  v.valor,
  coalesce(p.pago, 0)                          as valor_pago,
  greatest(v.valor - coalesce(p.pago, 0), 0)   as saldo,
  v.paga_em,
  case
    when coalesce(p.pago, 0) >= v.valor then 'paga'
    when v.vencimento is null            then 'sem_data'
    when v.vencimento < hoje_br()        then 'atrasada'
    else 'a_vencer'
  end                                          as situacao,
  case
    when coalesce(p.pago, 0) < v.valor and v.vencimento < hoje_br() then hoje_br() - v.vencimento
    else 0
  end                                          as dias_atraso
from dividas_vencimentos v
join dividas d on d.id = v.divida_id
left join lateral (
  select sum(valor) as pago from pagamentos_divida where vencimento_id = v.id
) p on true;

-- ---------------------------------------------------------------------
-- rpc_criar_compra_parcelada: cria a dívida, a entrada paga (se houver), o calendário de parcelas
-- e marca como pagas as primeiras "parcelas_pagas" (data = vencimento, marcada como estimada).
-- payload: credor*, valor_total*, numero_parcelas*, valor_parcela*, primeira_parcela*,
--          valor_entrada, data_entrada, parcelas_pagas, conta_id, fornecedor_id, moto_id, descricao, observacoes.
-- Vencimentos: primeira_parcela + (n-1) meses, mantendo o dia (em mês curto vale o último dia do mês).
-- ---------------------------------------------------------------------
create or replace function rpc_criar_compra_parcelada(payload jsonb) returns jsonb
security invoker
language plpgsql as $$
declare
  v_credor         text := nullif(btrim(coalesce(payload->>'credor', '')), '');
  v_total          numeric(12,2) := (payload->>'valor_total')::numeric;
  v_entrada        numeric(12,2) := coalesce(nullif(payload->>'valor_entrada', '')::numeric, 0);
  v_n              int           := (payload->>'numero_parcelas')::int;
  v_parcela        numeric(12,2) := (payload->>'valor_parcela')::numeric;
  v_primeira       date          := (payload->>'primeira_parcela')::date;
  v_pagas          int           := coalesce(nullif(payload->>'parcelas_pagas', '')::int, 0);
  v_data_entrada   date          := nullif(payload->>'data_entrada', '')::date;
  v_conta          uuid          := nullif(payload->>'conta_id', '')::uuid;
  v_divida_id      uuid;
  v_venc_id        uuid;
  v_venc           date;
  i                int;
begin
  if v_credor is null then
    raise exception 'Informe o credor da compra parcelada.';
  end if;
  if v_n is null or v_n <= 0 or v_parcela is null or v_parcela <= 0 or v_primeira is null then
    raise exception 'Informe o número de parcelas, o valor da parcela e a data da primeira parcela.';
  end if;
  if v_total is null or v_total <> v_entrada + v_n * v_parcela then
    raise exception 'O total (%) deve ser igual à entrada mais as parcelas (%).', v_total, v_entrada + v_n * v_parcela;
  end if;
  if v_pagas < 0 or v_pagas > v_n then
    raise exception 'As parcelas pagas devem estar entre 0 e o número de parcelas.';
  end if;

  insert into dividas (
    tipo, credor, fornecedor_id, moto_id, descricao, valor_original, numero_parcelas, valor_parcela,
    dia_vencimento, valor_entrada, primeira_parcela, observacoes
  ) values (
    'compra_parcelada', v_credor, nullif(payload->>'fornecedor_id', '')::uuid, nullif(payload->>'moto_id', '')::uuid,
    nullif(payload->>'descricao', ''), v_total, v_n, v_parcela,
    extract(day from v_primeira)::int, v_entrada, v_primeira, nullif(payload->>'observacoes', '')
  ) returning id into v_divida_id;

  if v_entrada > 0 then
    insert into pagamentos_divida (divida_id, data, data_estimada, valor, conta_id, observacoes)
    values (v_divida_id, coalesce(v_data_entrada, v_primeira), v_data_entrada is null, v_entrada, v_conta, 'Entrada da compra');
  end if;

  for i in 1..v_n loop
    v_venc := (v_primeira + make_interval(months => i - 1))::date;
    insert into dividas_vencimentos (divida_id, numero, vencimento, valor)
    values (v_divida_id, i, v_venc, v_parcela) returning id into v_venc_id;
    if i <= v_pagas then
      insert into pagamentos_divida (divida_id, vencimento_id, data, data_estimada, valor, conta_id, observacoes)
      values (v_divida_id, v_venc_id, v_venc, true, v_parcela, v_conta, 'Parcela paga antes do cadastro (data = vencimento, estimada)');
    end if;
  end loop;

  return jsonb_build_object(
    'divida_id', v_divida_id,
    'parcelas', v_n,
    'saldo', v_total - v_entrada - v_pagas * v_parcela
  );
end $$;

-- ---------------------------------------------------------------------
-- rpc_pagar_parcela_divida: registra o pagamento de uma parcela (padrão: o saldo todo).
-- ---------------------------------------------------------------------
create or replace function rpc_pagar_parcela_divida(
  p_vencimento_id  uuid,
  p_data           date,
  p_valor          numeric default null,
  p_conta_id       uuid    default null,
  p_observacoes    text    default null
) returns jsonb
security invoker
language plpgsql as $$
declare
  v_parcela   dividas_vencimentos%rowtype;
  v_pago      numeric(12,2);
  v_saldo     numeric(12,2);
  v_valor     numeric(12,2);
  v_pag_id    uuid;
begin
  select * into v_parcela from dividas_vencimentos where id = p_vencimento_id for update;
  if not found then
    raise exception 'Parcela não encontrada.';
  end if;
  select coalesce(sum(valor), 0) into v_pago from pagamentos_divida where vencimento_id = p_vencimento_id;
  v_saldo := v_parcela.valor - v_pago;
  if v_saldo <= 0 then
    raise exception 'A parcela já está paga.';
  end if;
  v_valor := coalesce(round(p_valor, 2), v_saldo);
  if v_valor <= 0 then
    raise exception 'O valor do pagamento deve ser positivo.';
  end if;
  if v_valor > v_saldo then
    raise exception 'O pagamento (%) supera o saldo da parcela (%).', v_valor, v_saldo;
  end if;

  insert into pagamentos_divida (divida_id, vencimento_id, data, valor, conta_id, observacoes)
  values (v_parcela.divida_id, p_vencimento_id, p_data, v_valor, p_conta_id, nullif(p_observacoes, ''))
  returning id into v_pag_id;

  return jsonb_build_object(
    'pagamento_id', v_pag_id,
    'parcela_paga', v_valor = v_saldo,
    'saldo_da_parcela', v_saldo - v_valor
  );
end $$;

grant execute on function rpc_criar_compra_parcelada(jsonb) to authenticated;
grant execute on function rpc_pagar_parcela_divida(uuid, date, numeric, uuid, text) to authenticated;

notify pgrst, 'reload schema';
