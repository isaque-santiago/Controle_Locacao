-- =====================================================================
-- 20261022120000_importacao_veiculos_contratos.sql
-- Migration 1 da importação dos dados reais (Arquivos/Importacao_Dados_Reais.md, seção 16 do plano):
--   * motos: tipo (moto/carro), dono no documento, link do CRLV, rastreador e seguro;
--   * contratos: promessa de compra (parcelas, valor total, entrada, parcelas já pagas, âncora da agenda);
--   * contas de recebimento e novos campos em pagamentos (conta, data estimada, forma "abatimento");
--   * rpc_criar_contrato e rpc_gerar_cobrancas_pendentes passam a respeitar a promessa de compra.
-- Compatível com a versão anterior do app: todas as colunas novas têm padrão ou aceitam nulo.
-- =====================================================================

-- ---------- Motos / veículos ----------
alter table motos
  add column if not exists tipo                   text not null default 'moto'
    check (tipo in ('moto','carro')),
  add column if not exists proprietario_documento text,            -- nome que consta no CRLV
  add column if not exists link_documento         text,            -- link do documento (Drive)
  add column if not exists possui_rastreador      boolean not null default false,
  add column if not exists seguro_valor_mensal    numeric(12,2) check (seguro_valor_mensal >= 0),
  add column if not exists seguro_dia_vencimento  int check (seguro_dia_vencimento between 1 and 31);

-- ---------- Contas de recebimento ----------
create table if not exists contas (
  id         uuid primary key default gen_random_uuid(),
  nome       text not null unique,
  tipo       text not null default 'pessoa' check (tipo in ('pessoa','especie')),
  ativa      boolean not null default true,
  criado_em  timestamptz not null default now()
);

-- ---------- Contratos: promessa de compra ----------
alter table contratos
  add column if not exists tipo_contrato          text not null default 'locacao'
    check (tipo_contrato in ('locacao','promessa_compra')),
  add column if not exists numero_parcelas        int check (numero_parcelas > 0),
  add column if not exists valor_total            numeric(12,2) check (valor_total > 0),
  add column if not exists valor_entrada          numeric(12,2) not null default 0 check (valor_entrada >= 0),
  add column if not exists parcelas_pagas_inicial int not null default 0 check (parcelas_pagas_inicial >= 0),
  add column if not exists dia_cobranca           int check (dia_cobranca between 1 and 31),  -- semanal: 1=domingo..7=sábado; mensal: dia do mês
  add column if not exists primeira_cobranca      date;                                        -- âncora da agenda (nulo = data_inicio)

alter table contratos drop constraint if exists ck_contratos_promessa;
alter table contratos add constraint ck_contratos_promessa check (
  tipo_contrato = 'locacao'
  or (numero_parcelas is not null
      and valor_total is not null
      and valor_total = valor_entrada + numero_parcelas * valor_periodo
      and parcelas_pagas_inicial <= numero_parcelas)
);

-- ---------- Pagamentos ----------
alter table pagamentos
  add column if not exists conta_id       uuid references contas(id),
  add column if not exists data_estimada  boolean not null default false;  -- data não informada: valor aproximado

-- "abatimento" = desconto sem dinheiro recebido (não entra no caixa).
alter table pagamentos drop constraint if exists pagamentos_forma_check;
alter table pagamentos add constraint pagamentos_forma_check
  check (forma in ('pix','dinheiro','cartao','transferencia','outro','abatimento'));

create index if not exists ix_pagamentos_conta on pagamentos (conta_id);

-- ---------- RLS e permissões das tabelas novas ----------
alter table contas enable row level security;
drop policy if exists "dono_total" on contas;
create policy "dono_total" on contas for all to authenticated using (is_dono()) with check (is_dono());
grant select, insert, update, delete on contas to authenticated;

-- ---------------------------------------------------------------------
-- rpc_criar_contrato: igual à versão anterior (20260921120300), com promessa de compra.
-- Promessa: exige número de parcelas; a agenda começa em primeira_cobranca (ou data_inicio),
-- numera a partir de parcelas_pagas_inicial + 1 e para na última parcela. A entrada vira
-- uma cobrança "outros" vencendo na data de início.
-- ---------------------------------------------------------------------
create or replace function rpc_criar_contrato(payload jsonb) returns jsonb
security invoker
language plpgsql as $$
declare
  v_moto               motos%rowtype;
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
  v_valor_total        numeric(12,2);
  v_horizonte_padrao   constant int := 30;
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
    'cobrancas_geradas', v_qtd_cobrancas
  );
end $$;

-- ---------------------------------------------------------------------
-- rpc_gerar_cobrancas_pendentes: idempotente, janela móvel. Para contratos importados,
-- a 1ª cobrança nasce em primeira_cobranca (não em data_inicio, que pode ser antiga),
-- a numeração parte de parcelas_pagas_inicial + 1 e a promessa para na última parcela.
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
      v_vencimento := coalesce(v_contrato.primeira_cobranca, v_contrato.data_inicio);
      v_numero := v_contrato.parcelas_pagas_inicial + 1;
    else
      v_vencimento := fn_somar_periodo(v_ultimo.ultimo_vencimento, v_contrato.periodicidade);
      v_numero := v_ultimo.ultimo_numero + 1;
    end if;

    while v_vencimento <= v_limite
          and (v_contrato.numero_parcelas is null or v_numero <= v_contrato.numero_parcelas) loop
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

notify pgrst, 'reload schema';
