-- =====================================================================
-- 20261124120000_pendencias_lancamento.sql
-- Caixa de pendências de lançamento (seção 24 do plano, etapa 2).
--
-- O conector do claude.ai NUNCA grava no financeiro: ele só PROPÕE (uma pendência). Um usuário dono (o dono ou as pessoas do
-- financeiro, todos em `administradores`) aprova, edita-e-aprova ou recusa no app. Só na aprovação o pagamento ou a despesa
-- é gravado, numa transação única e pelas mesmas regras do fluxo normal (os gatilhos de `pagamentos` continuam valendo).
--
--   * `servico_conector` lista o usuário de serviço do conector (mesmo padrão de `servico_mensagens`, do WhatsApp). Ele NÃO
--     enxerga nenhuma tabela: só executa as RPCs `rpc_pendencia_criar`, `rpc_conector_*` abaixo. A service_role nunca é usada;
--   * `pendencias_lancamento` guarda a proposta, o resumo, os avisos de divergência e quem decidiu. Só o dono lê a tabela;
--     ninguém grava direto: só as RPCs;
--   * idempotência: `chave_operacao` única. Repetir a mesma proposta devolve a pendência que já existe;
--   * trava contra enxurrada: no máximo 200 pendências em aberto;
--   * tipos desta etapa: `pagamento` e `despesa`. O serviço só usa as origens `chat_*`; `manual` é do dono.
--
-- RPCs (SECURITY DEFINER):
--   rpc_pendencia_criar(payload)             usuário de serviço ou dono: valida, resolve cobrança/cliente/veículo e grava a pendência;
--   rpc_pendencia_aprovar(id, ajustes)       só dono: confere de novo, grava o pagamento/despesa e fecha a pendência;
--   rpc_pendencia_recusar(id, motivo)        só dono;
--   rpc_conector_cobrancas_abertas(busca)    usuário de serviço ou dono: cobranças em aberto por nome, CPF parcial ou placa;
--   rpc_conector_veiculos(busca)             idem, para despesas;
--   rpc_conector_minhas_pendencias(limite)   idem: as últimas propostas do chat e o que aconteceu com elas.
--
-- Compatível com a versão anterior do app: só objetos novos.
--
-- Para criar o usuário de serviço (depois de criá-lo em Authentication > Users, com "Auto Confirm User"):
--   insert into servico_conector (user_id) select id from auth.users where email = 'conector@exemplo.com';
-- Para tirar o acesso:
--   delete from servico_conector where user_id = (select id from auth.users where email = 'conector@exemplo.com');
-- =====================================================================

-- ---------- Usuário de serviço (mesmo padrão de `servico_mensagens`) ----------
create table if not exists servico_conector (
  user_id   uuid primary key,
  criado_em timestamptz not null default now()
);

alter table servico_conector enable row level security;
drop policy if exists "ver_o_proprio" on servico_conector;
create policy "ver_o_proprio" on servico_conector for select to authenticated using (user_id = auth.uid());
revoke all on servico_conector from anon, authenticated;
grant select on servico_conector to authenticated;

create or replace function is_servico_conector() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from servico_conector where user_id = auth.uid());
$$;

-- ---------- Pendências ----------
create table if not exists pendencias_lancamento (
  id               uuid primary key default gen_random_uuid(),
  tipo             text not null check (tipo in ('pagamento', 'despesa')),
  origem           text not null check (origem in ('chat_financeiro', 'chat_contratos', 'comprovante_grupo', 'manual')),
  chave_operacao   text not null check (length(chave_operacao) between 1 and 120),
  dados            jsonb not null,
  cliente_id       uuid references clientes(id) on delete set null,
  contrato_id      uuid references contratos(id) on delete set null,
  cobranca_id      uuid references cobrancas(id) on delete set null,
  moto_id          uuid references motos(id) on delete set null,
  resumo           text not null check (length(resumo) <= 300),
  trecho_origem    text check (length(trecho_origem) <= 600),
  avisos           jsonb not null default '[]'::jsonb,
  status           text not null default 'pendente' check (status in ('pendente', 'aprovada', 'recusada')),
  motivo_recusa    text check (length(motivo_recusa) <= 300),
  registro_id      uuid,
  criado_por       uuid,
  criado_em        timestamptz not null default now(),
  decidido_por     uuid,
  decidido_em      timestamptz,
  constraint ck_pendencia_estado check (
    (status = 'pendente' and decidido_por is null and decidido_em is null and registro_id is null and motivo_recusa is null)
    or (status = 'aprovada' and decidido_por is not null and decidido_em is not null and registro_id is not null and motivo_recusa is null)
    or (status = 'recusada' and decidido_por is not null and decidido_em is not null and registro_id is null
        and nullif(btrim(motivo_recusa), '') is not null)
  )
);
create unique index if not exists uq_pendencias_chave on pendencias_lancamento (chave_operacao);
create index if not exists ix_pendencias_status on pendencias_lancamento (status, criado_em desc);
create index if not exists ix_pendencias_cobranca on pendencias_lancamento (cobranca_id) where cobranca_id is not null;

alter table pendencias_lancamento enable row level security;
drop policy if exists "dono_le" on pendencias_lancamento;
create policy "dono_le" on pendencias_lancamento for select to authenticated using (is_dono());
revoke all on pendencias_lancamento from anon, authenticated;
grant select on pendencias_lancamento to authenticated;

-- ---------- Funções de apoio (internas: ninguém as chama de fora) ----------
create or replace function fn_pend_moeda(p_valor numeric) returns text
language sql immutable as $$
  select 'R$ ' || translate(to_char(p_valor, 'FM999,999,990.00'), ',.', '.,');
$$;

create or replace function fn_pend_sem_acento(p_texto text) returns text
language sql immutable as $$
  select translate(lower(coalesce(p_texto, '')), 'áàâãäéèêëíìîïóòôõöúùûüç', 'aaaaaeeeeiiiiooooouuuuc');
$$;

-- Normaliza e valida a proposta (mesmas regras de src/domain/pendencias.py). Levanta mensagens em português.
create or replace function fn_pend_normalizar(p_tipo text, p_dados jsonb) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_valor    numeric;
  v_multa    numeric := 0;
  v_data     date;
  v_forma    text;
  v_cat      text;
  v_obs      text;
  v_desc     text;
  v_id       uuid;
  v_moto     uuid;
begin
  if p_dados is null or jsonb_typeof(p_dados) <> 'object' then
    raise exception 'A proposta precisa ser um objeto.';
  end if;

  begin
    v_valor := (p_dados->>'valor')::numeric;
  exception when others then
    raise exception 'O valor precisa ser um número positivo com até duas casas decimais.';
  end;
  if v_valor is null or v_valor <= 0 or v_valor <> round(v_valor, 2) then
    raise exception 'O valor precisa ser um número positivo com até duas casas decimais.';
  end if;

  if p_tipo = 'pagamento' then
    if v_valor > 20000 then raise exception 'O valor passa do limite de R$ 20.000,00 para uma proposta do chat.'; end if;
    begin
      v_data := coalesce(nullif(p_dados->>'data_pagamento', '')::date, hoje_br());
    exception when others then
      raise exception 'A data do pagamento precisa estar no formato aaaa-mm-dd.';
    end;
    if v_data > hoje_br() + 1 then raise exception 'A data do pagamento não pode estar no futuro.'; end if;
    v_forma := fn_pend_sem_acento(btrim(coalesce(nullif(p_dados->>'forma', ''), 'pix')));
    if v_forma not in ('pix', 'dinheiro', 'cartao', 'transferencia', 'outro') then
      raise exception 'A forma de pagamento precisa ser: pix, dinheiro, cartao, transferencia ou outro.';
    end if;
    begin
      v_multa := coalesce(nullif(p_dados->>'multa_juros', '')::numeric, 0);
    exception when others then
      raise exception 'O valor dos encargos precisa ser um número positivo com até duas casas decimais.';
    end;
    if v_multa < 0 or v_multa > 20000 or v_multa <> round(v_multa, 2) then
      raise exception 'O valor dos encargos precisa ser um número positivo com até duas casas decimais.';
    end if;
    v_obs := nullif(btrim(regexp_replace(coalesce(p_dados->>'observacoes', ''), '\s+', ' ', 'g')), '');
    if length(coalesce(v_obs, '')) > 500 then raise exception 'O campo observações passa de 500 caracteres.'; end if;
    begin
      v_id := nullif(p_dados->>'cobranca_id', '')::uuid;
    exception when others then
      raise exception 'O identificador de cobrança é inválido.';
    end;
    return jsonb_build_object(
      'cobranca_id', v_id, 'valor', to_char(v_valor, 'FM999999990.00'), 'multa_juros', to_char(v_multa, 'FM999999990.00'),
      'data_pagamento', v_data, 'forma', v_forma, 'observacoes', v_obs);

  elsif p_tipo = 'despesa' then
    if v_valor > 50000 then raise exception 'O valor passa do limite de R$ 50.000,00 para uma proposta do chat.'; end if;
    begin
      v_data := coalesce(nullif(p_dados->>'data', '')::date, hoje_br());
    exception when others then
      raise exception 'A data da despesa precisa estar no formato aaaa-mm-dd.';
    end;
    if v_data > hoje_br() + 1 then raise exception 'A data da despesa não pode estar no futuro.'; end if;
    v_cat := replace(fn_pend_sem_acento(btrim(coalesce(nullif(p_dados->>'categoria', ''), 'outros'))), ' ', '_');
    if v_cat not in ('manutencao', 'documentacao', 'seguro_rastreador', 'multas', 'combustivel', 'outros') then
      raise exception 'A categoria precisa ser: manutencao, documentacao, seguro_rastreador, multas, combustivel ou outros.';
    end if;
    v_obs := nullif(btrim(regexp_replace(coalesce(p_dados->>'observacoes', ''), '\s+', ' ', 'g')), '');
    if v_obs is null then raise exception 'Descreva a despesa.'; end if;
    if length(v_obs) > 500 then raise exception 'O campo descrição passa de 500 caracteres.'; end if;
    v_desc := nullif(btrim(regexp_replace(coalesce(p_dados->>'descricao_veiculo', ''), '\s+', ' ', 'g')), '');
    if length(coalesce(v_desc, '')) > 120 then raise exception 'O campo veículo passa de 120 caracteres.'; end if;
    begin
      v_moto := nullif(p_dados->>'moto_id', '')::uuid;
    exception when others then
      raise exception 'O identificador de veículo é inválido.';
    end;
    return jsonb_build_object(
      'moto_id', v_moto, 'descricao_veiculo', v_desc, 'valor', to_char(v_valor, 'FM999999990.00'), 'data', v_data,
      'categoria', v_cat, 'repassar_locatario', coalesce((p_dados->>'repassar_locatario')::boolean, false), 'observacoes', v_obs);
  end if;

  raise exception 'Tipo de pendência desconhecido.';
end $$;

-- Avisos de divergência (mesmos códigos e textos de src/domain/pendencias.py). Os cinco primeiros códigos abaixo (cobrança não identificada, paga, cancelada, valor acima do saldo e veículo não encontrado) bloqueiam a aprovação.
create or replace function fn_pend_avisos(p_tipo text, p_dados jsonb) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_avisos jsonb := '[]'::jsonb;
  v_cob    cobrancas%rowtype;
  v_saldo  numeric;
  v_valor  numeric := (p_dados->>'valor')::numeric;
  v_moto   uuid;
begin
  if p_tipo = 'pagamento' then
    select * into v_cob from cobrancas where id = nullif(p_dados->>'cobranca_id', '')::uuid;
    if not found then
      return jsonb_build_array(jsonb_build_object('codigo', 'cobranca_nao_identificada',
        'texto', 'A cobrança não foi identificada: escolha qual cobrança este pagamento quita.'));
    end if;
    select v_cob.valor - coalesce(sum(valor), 0) into v_saldo from pagamentos where cobranca_id = v_cob.id;
    if v_cob.status = 'paga' then
      v_avisos := v_avisos || jsonb_build_object('codigo', 'cobranca_paga', 'texto', 'Esta cobrança já está paga.');
    elsif v_cob.status = 'cancelada' then
      v_avisos := v_avisos || jsonb_build_object('codigo', 'cobranca_cancelada', 'texto', 'Esta cobrança foi cancelada.');
    elsif v_valor > v_saldo then
      v_avisos := v_avisos || jsonb_build_object('codigo', 'valor_acima_do_saldo',
        'texto', 'O valor passa do saldo da cobrança (' || fn_pend_moeda(v_saldo) || ').');
    elsif v_valor < v_saldo then
      v_avisos := v_avisos || jsonb_build_object('codigo', 'valor_abaixo_do_saldo',
        'texto', 'Pagamento parcial: o saldo da cobrança é ' || fn_pend_moeda(v_saldo) || '.');
    end if;
    if exists (select 1 from pagamentos where cobranca_id = v_cob.id and valor = v_valor
                  and data_pagamento = (p_dados->>'data_pagamento')::date) then
      v_avisos := v_avisos || jsonb_build_object('codigo', 'possivel_duplicada',
        'texto', 'Já existe um pagamento igual (mesma cobrança, valor e data).');
    end if;
    if (p_dados->>'data_pagamento')::date > hoje_br() then
      v_avisos := v_avisos || jsonb_build_object('codigo', 'data_no_futuro', 'texto', 'A data do pagamento é amanhã ou depois.');
    end if;
    return v_avisos;

  elsif p_tipo = 'despesa' then
    v_moto := nullif(p_dados->>'moto_id', '')::uuid;
    if v_moto is not null and not exists (select 1 from motos where id = v_moto) then
      v_avisos := v_avisos || jsonb_build_object('codigo', 'veiculo_nao_identificado', 'texto', 'O veículo informado não foi encontrado.');
    elsif v_moto is null and nullif(p_dados->>'descricao_veiculo', '') is null then
      v_avisos := v_avisos || jsonb_build_object('codigo', 'sem_veiculo', 'texto', 'A despesa não está ligada a nenhum veículo.');
    end if;
    if exists (select 1 from despesas where moto_id is not distinct from v_moto and valor = v_valor
                  and data = (p_dados->>'data')::date and categoria = p_dados->>'categoria') then
      v_avisos := v_avisos || jsonb_build_object('codigo', 'possivel_duplicada',
        'texto', 'Já existe uma despesa igual (mesmo veículo, valor e data).');
    end if;
    return v_avisos;
  end if;
  return v_avisos;
end $$;

-- Resolve cliente, contrato e veículo a partir da cobrança (pagamento) ou do veículo (despesa) e monta o resumo da lista.
create or replace function fn_pend_vinculos(p_tipo text, p_dados jsonb, out o_cliente uuid, out o_contrato uuid, out o_cobranca uuid,
                                            out o_moto uuid, out o_resumo text)
language plpgsql stable security definer set search_path = public as $$
declare
  v_nome  text;
  v_placa text;
  v_valor numeric := (p_dados->>'valor')::numeric;
begin
  if p_tipo = 'pagamento' then
    select c.id, ct.id, cl.id, ct.moto_id, cl.nome
      into o_cobranca, o_contrato, o_cliente, o_moto, v_nome
      from cobrancas c
      join contratos ct on ct.id = c.contrato_id
      join clientes cl on cl.id = ct.cliente_id
     where c.id = nullif(p_dados->>'cobranca_id', '')::uuid;
    select placa into v_placa from motos where id = o_moto;
    o_resumo := 'Pagamento' || coalesce(' de ' || v_nome, '') || coalesce(' (' || v_placa || ')', '') || ': ' || fn_pend_moeda(v_valor)
      || ' em ' || to_char((p_dados->>'data_pagamento')::date, 'DD/MM/YYYY') || ' por '
      || case p_dados->>'forma' when 'pix' then 'Pix' when 'dinheiro' then 'dinheiro' when 'cartao' then 'cartão'
                                when 'transferencia' then 'transferência' else 'outro meio' end;
  else
    o_moto := nullif(p_dados->>'moto_id', '')::uuid;
    select placa into v_placa from motos where id = o_moto;
    v_placa := coalesce(v_placa, p_dados->>'descricao_veiculo');
    o_resumo := 'Despesa' || coalesce(' (' || v_placa || ')', '') || ': ' || fn_pend_moeda(v_valor)
      || ' em ' || to_char((p_dados->>'data')::date, 'DD/MM/YYYY') || ', ' || replace(p_dados->>'categoria', '_', ' ');
    if o_moto is not null and not exists (select 1 from motos where id = o_moto) then o_moto := null; end if;
  end if;
end $$;

create or replace function fn_pend_exige_servico_ou_dono() returns void
language plpgsql stable security definer set search_path = public as $$
begin
  if not (is_servico_conector() or is_dono()) then
    raise exception 'Sem permissão para usar o conector.' using errcode = '42501';
  end if;
end $$;

create or replace function fn_pend_exige_dono() returns void
language plpgsql stable security definer set search_path = public as $$
begin
  if not is_dono() then
    raise exception 'Somente os usuários donos podem decidir pendências.' using errcode = '42501';
  end if;
end $$;

-- ---------- rpc_pendencia_criar ----------
-- payload: {"tipo": "pagamento"|"despesa", "origem": "chat_financeiro"|..., "chave_operacao": text,
--           "dados": {...}, "trecho_origem": text}
create or replace function rpc_pendencia_criar(payload jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_tipo    text := payload->>'tipo';
  v_origem  text := payload->>'origem';
  v_chave   text := btrim(coalesce(payload->>'chave_operacao', ''));
  v_trecho  text := nullif(btrim(coalesce(payload->>'trecho_origem', '')), '');
  v_dados   jsonb;
  v_existe  pendencias_lancamento%rowtype;
  v_vinc    record;
  v_avisos  jsonb;
  v_id      uuid;
begin
  perform fn_pend_exige_servico_ou_dono();
  if v_tipo not in ('pagamento', 'despesa') then
    raise exception 'Tipo de pendência desconhecido.';
  end if;
  if v_origem is null or v_origem not in ('chat_financeiro', 'chat_contratos', 'comprovante_grupo', 'manual') then
    raise exception 'Origem desconhecida.';
  end if;
  if not is_dono() and v_origem not in ('chat_financeiro', 'chat_contratos') then
    raise exception 'O conector só usa as origens do chat.' using errcode = '42501';
  end if;
  if v_chave = '' or length(v_chave) > 120 then
    raise exception 'A chave de operação é obrigatória e tem até 120 caracteres.';
  end if;
  if length(coalesce(v_trecho, '')) > 600 then v_trecho := left(v_trecho, 600); end if;

  -- repetir a mesma proposta devolve a que já existe
  select * into v_existe from pendencias_lancamento where chave_operacao = v_chave;
  if found then
    return jsonb_build_object('id', v_existe.id, 'status', v_existe.status, 'repetida', true, 'resumo', v_existe.resumo,
                              'avisos', v_existe.avisos);
  end if;

  if (select count(*) from pendencias_lancamento where status = 'pendente') >= 200 then
    raise exception 'Há pendências demais em aberto. Peça ao dono para decidir as que já estão na fila.';
  end if;

  v_dados := fn_pend_normalizar(v_tipo, payload->'dados');
  select * into v_vinc from fn_pend_vinculos(v_tipo, v_dados);
  v_avisos := fn_pend_avisos(v_tipo, v_dados);

  insert into pendencias_lancamento (tipo, origem, chave_operacao, dados, cliente_id, contrato_id, cobranca_id, moto_id,
                                     resumo, trecho_origem, avisos, criado_por)
  values (v_tipo, v_origem, v_chave, v_dados, v_vinc.o_cliente, v_vinc.o_contrato, v_vinc.o_cobranca, v_vinc.o_moto,
          v_vinc.o_resumo, v_trecho, v_avisos, auth.uid())
  on conflict (chave_operacao) do nothing
  returning id into v_id;

  if v_id is null then  -- outro envio igual chegou ao mesmo tempo
    select * into v_existe from pendencias_lancamento where chave_operacao = v_chave;
    return jsonb_build_object('id', v_existe.id, 'status', v_existe.status, 'repetida', true, 'resumo', v_existe.resumo,
                              'avisos', v_existe.avisos);
  end if;
  return jsonb_build_object('id', v_id, 'status', 'pendente', 'repetida', false, 'resumo', v_vinc.o_resumo, 'avisos', v_avisos);
end $$;

-- ---------- rpc_pendencia_aprovar ----------
-- p_ajustes: campos que o dono corrigiu na tela (mesmas chaves de `dados`); valem só para esta pendência.
create or replace function rpc_pendencia_aprovar(p_id uuid, p_ajustes jsonb default null) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_p        pendencias_lancamento%rowtype;
  v_dados    jsonb;
  v_vinc     record;
  v_avisos   jsonb;
  v_bloqueio text;
  v_registro uuid;
begin
  perform fn_pend_exige_dono();
  select * into v_p from pendencias_lancamento where id = p_id for update;
  if not found then
    raise exception 'Pendência não encontrada.';
  end if;
  if v_p.status <> 'pendente' then
    raise exception 'Esta pendência já foi decidida.';
  end if;

  v_dados := fn_pend_normalizar(v_p.tipo, v_p.dados || coalesce(p_ajustes, '{}'::jsonb));
  select * into v_vinc from fn_pend_vinculos(v_p.tipo, v_dados);
  v_avisos := fn_pend_avisos(v_p.tipo, v_dados);

  select a->>'texto' into v_bloqueio
    from jsonb_array_elements(v_avisos) a
   where a->>'codigo' in ('cobranca_nao_identificada', 'cobranca_paga', 'cobranca_cancelada', 'valor_acima_do_saldo', 'veiculo_nao_identificado')
   limit 1;
  if v_bloqueio is not null then
    raise exception 'Não dá para aprovar: %', v_bloqueio;
  end if;

  if v_p.tipo = 'pagamento' then
    -- os gatilhos de `pagamentos` (cobrança aberta, saldo) continuam valendo; a chave de operação é o id da pendência
    insert into pagamentos (cobranca_id, data_pagamento, valor, multa_juros, forma, observacoes, chave_operacao)
    values ((v_dados->>'cobranca_id')::uuid, (v_dados->>'data_pagamento')::date, (v_dados->>'valor')::numeric,
            (v_dados->>'multa_juros')::numeric, v_dados->>'forma', v_dados->>'observacoes', v_p.id)
    returning id into v_registro;
  else
    insert into despesas (data, moto_id, descricao_veiculo, categoria, valor, repassar_locatario, observacoes)
    values ((v_dados->>'data')::date, nullif(v_dados->>'moto_id', '')::uuid, v_dados->>'descricao_veiculo', v_dados->>'categoria',
            (v_dados->>'valor')::numeric, (v_dados->>'repassar_locatario')::boolean, v_dados->>'observacoes')
    returning id into v_registro;
  end if;

  update pendencias_lancamento
     set dados = v_dados, cliente_id = v_vinc.o_cliente, contrato_id = v_vinc.o_contrato, cobranca_id = v_vinc.o_cobranca,
         moto_id = v_vinc.o_moto, resumo = v_vinc.o_resumo, avisos = v_avisos,
         status = 'aprovada', registro_id = v_registro, decidido_por = auth.uid(), decidido_em = now()
   where id = v_p.id;
  return jsonb_build_object('id', v_p.id, 'status', 'aprovada', 'registro_id', v_registro);
end $$;

-- ---------- rpc_pendencia_recusar ----------
create or replace function rpc_pendencia_recusar(p_id uuid, p_motivo text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_p pendencias_lancamento%rowtype;
  v_motivo text := nullif(btrim(coalesce(p_motivo, '')), '');
begin
  perform fn_pend_exige_dono();
  if v_motivo is null then raise exception 'Informe o motivo da recusa.'; end if;
  if length(v_motivo) > 300 then raise exception 'O motivo passa de 300 caracteres.'; end if;
  select * into v_p from pendencias_lancamento where id = p_id for update;
  if not found then raise exception 'Pendência não encontrada.'; end if;
  if v_p.status <> 'pendente' then raise exception 'Esta pendência já foi decidida.'; end if;
  update pendencias_lancamento
     set status = 'recusada', motivo_recusa = v_motivo, decidido_por = auth.uid(), decidido_em = now()
   where id = p_id;
  return jsonb_build_object('id', p_id, 'status', 'recusada');
end $$;

-- ---------- Consultas mínimas para o chat (não expõem tabelas) ----------
-- Cobranças em aberto por nome (cada palavra começa uma palavra do nome), CPF parcial (4 dígitos ou mais) ou placa.
-- Devolve só o necessário para o chat escolher a cobrança certa: o CPF sai só com os 4 últimos dígitos.
create or replace function rpc_conector_cobrancas_abertas(p_busca text, p_limite int default 20) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_busca  text := coalesce(btrim(p_busca), '');
  v_digitos text := regexp_replace(v_busca, '\D', '', 'g');
  v_placas text[];
  v_nome   text[];
  v_limite int := least(greatest(coalesce(p_limite, 20), 1), 50);
  v_res    jsonb;
begin
  perform fn_pend_exige_servico_ou_dono();
  if length(v_busca) < 3 then
    raise exception 'Informe ao menos 3 caracteres para buscar.';
  end if;
  select coalesce(array_agg(upper(m[1] || m[2])), '{}') into v_placas
    from regexp_matches(v_busca, '\y([A-Za-z]{3})-?(\d[A-Za-z0-9]\d{2})\y', 'g') as m;
  select coalesce(array_agg(t), '{}') into v_nome
    from unnest(string_to_array(btrim(regexp_replace(fn_pend_sem_acento(
           regexp_replace(regexp_replace(v_busca, '\y[A-Za-z]{3}-?\d[A-Za-z0-9]\d{2}\y', ' ', 'g'), '[0-9*.\-]+', ' ', 'g')), '\s+', ' ', 'g')), ' ')) as t
   where length(t) >= 2;

  select coalesce(jsonb_agg(linha order by (linha->>'vencimento'), (linha->>'cliente_nome')), '[]'::jsonb) into v_res
  from (
    select jsonb_build_object(
             'cobranca_id', c.id, 'contrato_id', ct.id, 'numero', c.numero, 'vencimento', c.vencimento, 'valor', c.valor,
             'saldo', c.valor - coalesce((select sum(p.valor) from pagamentos p where p.cobranca_id = c.id), 0),
             'cliente_nome', cl.nome, 'cpf_final', right(cl.cpf, 4), 'placa', m.placa) as linha
      from cobrancas c
      join contratos ct on ct.id = c.contrato_id
      join clientes cl on cl.id = ct.cliente_id
      join motos m on m.id = ct.moto_id
     where c.status = 'aberta'
       and (
            (length(v_digitos) >= 4 and cl.cpf like '%' || v_digitos || '%')
         or (cardinality(v_placas) > 0 and m.placa = any(v_placas))
         or (cardinality(v_nome) > 0 and not exists (
               select 1 from unnest(v_nome) t
                where not exists (select 1 from unnest(string_to_array(fn_pend_sem_acento(cl.nome), ' ')) w where w like t || '%')))
       )
     order by c.vencimento, cl.nome
     limit v_limite
  ) s;
  return v_res;
end $$;

create or replace function rpc_conector_veiculos(p_busca text, p_limite int default 10) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_busca text := fn_pend_sem_acento(btrim(coalesce(p_busca, '')));
  v_limite int := least(greatest(coalesce(p_limite, 10), 1), 30);
begin
  perform fn_pend_exige_servico_ou_dono();
  if length(v_busca) < 2 then
    raise exception 'Informe ao menos 2 caracteres para buscar.';
  end if;
  return coalesce((
    select jsonb_agg(jsonb_build_object('moto_id', id, 'placa', placa, 'descricao', marca || ' ' || modelo, 'status', status) order by placa)
      from (select * from motos
             where arquivada_em is null
               and (replace(lower(placa), '-', '') like '%' || replace(v_busca, '-', '') || '%'
                    or fn_pend_sem_acento(marca || ' ' || modelo) like '%' || v_busca || '%')
             order by placa limit v_limite) m
  ), '[]'::jsonb);
end $$;

create or replace function rpc_conector_minhas_pendencias(p_limite int default 10) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_limite int := least(greatest(coalesce(p_limite, 10), 1), 50);
begin
  perform fn_pend_exige_servico_ou_dono();
  return coalesce((
    select jsonb_agg(jsonb_build_object('id', id, 'tipo', tipo, 'resumo', resumo, 'status', status, 'motivo_recusa', motivo_recusa,
                                         'criado_em', criado_em) order by criado_em desc)
      from (select * from pendencias_lancamento where origem in ('chat_financeiro', 'chat_contratos')
             order by criado_em desc limit v_limite) p
  ), '[]'::jsonb);
end $$;

-- ---------- Permissões ----------
revoke all on function fn_pend_moeda(numeric), fn_pend_sem_acento(text), fn_pend_normalizar(text, jsonb), fn_pend_avisos(text, jsonb),
  fn_pend_vinculos(text, jsonb), fn_pend_exige_servico_ou_dono(), fn_pend_exige_dono() from public, anon, authenticated;
revoke all on function is_servico_conector() from public, anon;
revoke all on function rpc_pendencia_criar(jsonb) from public, anon;
revoke all on function rpc_pendencia_aprovar(uuid, jsonb) from public, anon;
revoke all on function rpc_pendencia_recusar(uuid, text) from public, anon;
revoke all on function rpc_conector_cobrancas_abertas(text, int) from public, anon;
revoke all on function rpc_conector_veiculos(text, int) from public, anon;
revoke all on function rpc_conector_minhas_pendencias(int) from public, anon;
grant execute on function is_servico_conector() to authenticated;
grant execute on function rpc_pendencia_criar(jsonb) to authenticated;
grant execute on function rpc_pendencia_aprovar(uuid, jsonb) to authenticated;
grant execute on function rpc_pendencia_recusar(uuid, text) to authenticated;
grant execute on function rpc_conector_cobrancas_abertas(text, int) to authenticated;
grant execute on function rpc_conector_veiculos(text, int) to authenticated;
grant execute on function rpc_conector_minhas_pendencias(int) to authenticated;

notify pgrst, 'reload schema';
