-- =====================================================================
-- 20261125120000_historico_chats.sql
-- Caixa de entrada do histórico dos chats «Locadora - Acompanhamento Financeiro» e «Contratos Locadora» (seção 24 do plano).
--
-- O Claude de cada chat extrai o histórico e o ENTREGA em lotes pequenos pelo conector. Nada disso entra no financeiro: vai para um
-- RASCUNHO que o dono confere. O banco compara cada registro com o que já existe (`ja_existe`, `nova`, `diverge`) e guarda o trecho do
-- chat que o originou. Aplicar no sistema continua sendo uma carga SQL aprovada pelo dono (sessão de sincronização, dev antes de produção).
--
--   historico_chat_lotes       um lote entregue: fonte, rótulo, período que ele cobre (para achar buracos) e quantos registros;
--   historico_chat_registros   cada registro (tipo, data, dados, trecho do chat, resumo), com a situação da comparação;
--   rpc_conector_entregar_lote_historico(payload)   usuário de serviço ou dono: valida, grava o lote e compara cada registro;
--   rpc_conector_resumo_historico(fonte)            contagens por tipo e situação e os períodos dos lotes (o app calcula os buracos);
--   rpc_conector_historico_a_conferir(...)          o que é novo ou diverge, em resumo (sem trecho nem CPF inteiro);
--   rpc_historico_descartar_lote(lote)              só dono: apaga um lote entregue por engano (não toca no que já foi aplicado).
--
-- O usuário de serviço do conector continua sem ler tabela nenhuma: só executa estas RPCs. Só o dono lê as tabelas (o backup as inclui).
-- Compatível com a versão anterior do app: só objetos novos. Depende de 20261124120000_pendencias_lancamento.sql (funções de apoio).
-- =====================================================================

create table if not exists historico_chat_lotes (
  id                   uuid primary key default gen_random_uuid(),
  fonte                text not null check (fonte in ('chat_financeiro', 'chat_contratos')),
  rotulo               text not null check (length(rotulo) between 1 and 60),
  periodo_inicio       date not null,
  periodo_fim          date not null,
  observacao           text check (length(observacao) <= 500),
  registros_recebidos  int not null default 0,
  registros_novos      int not null default 0,
  entregue_em          timestamptz not null default now(),
  entregue_por         uuid,
  check (periodo_fim >= periodo_inicio)
);
create unique index if not exists uq_historico_lote on historico_chat_lotes (fonte, rotulo, periodo_inicio, periodo_fim);

create table if not exists historico_chat_registros (
  id            uuid primary key default gen_random_uuid(),
  lote_id       uuid not null references historico_chat_lotes(id) on delete cascade,
  fonte         text not null check (fonte in ('chat_financeiro', 'chat_contratos')),
  tipo          text not null check (tipo in ('pagamento', 'despesa', 'multa', 'divida', 'movimento_socio', 'cliente', 'veiculo', 'contrato', 'outro')),
  data_ref      date,
  dados         jsonb not null check (jsonb_typeof(dados) = 'object'),
  trecho        text not null check (length(trecho) between 1 and 600),
  resumo        text not null check (length(resumo) between 1 and 200),
  chave         text not null,
  situacao      text not null default 'sem_comparacao'
                check (situacao in ('nova', 'ja_existe', 'diverge', 'sem_comparacao', 'descartada', 'aplicada')),
  detalhe       text check (length(detalhe) <= 300),
  entregue_em   timestamptz not null default now(),
  entregue_por  uuid
);
create unique index if not exists uq_historico_registro_chave on historico_chat_registros (chave);
create index if not exists ix_historico_registro_situacao on historico_chat_registros (fonte, situacao, data_ref);
create index if not exists ix_historico_registro_lote on historico_chat_registros (lote_id);

alter table historico_chat_lotes enable row level security;
alter table historico_chat_registros enable row level security;
drop policy if exists "dono_le" on historico_chat_lotes;
drop policy if exists "dono_le" on historico_chat_registros;
create policy "dono_le" on historico_chat_lotes for select to authenticated using (is_dono());
create policy "dono_le" on historico_chat_registros for select to authenticated using (is_dono());
revoke all on historico_chat_lotes, historico_chat_registros from anon, authenticated;
grant select on historico_chat_lotes, historico_chat_registros to authenticated;

-- ---------- Comparação com o sistema (interna) ----------
-- Cada palavra de `p_busca` (2 letras ou mais) começa uma palavra do nome do cliente.
create or replace function fn_hist_nome_confere(p_nome text, p_busca text) returns boolean
language sql immutable as $$
  with t as (
    select x from unnest(string_to_array(btrim(regexp_replace(fn_pend_sem_acento(p_busca), '[^a-z0-9 ]', ' ', 'g')), ' ')) x where length(x) >= 2
  )
  select exists (select 1 from t)
     and not exists (select 1 from t where not exists (
           select 1 from unnest(string_to_array(fn_pend_sem_acento(p_nome), ' ')) w where w like t.x || '%'));
$$;

create or replace function fn_hist_resultado(p_situacao text, p_detalhe text default null) returns jsonb
language sql immutable as $$
  select jsonb_build_object('situacao', p_situacao, 'detalhe', p_detalhe);
$$;

-- Compara um registro com o sistema. Chaves esperadas em `dados`:
--   pagamento: cliente|nome, cpf, placa, valor (e a data);  despesa: placa, valor (e a data);  multa: placa, ait, valor (e a data);
--   cliente: nome, cpf;  veiculo: placa, marca;  contrato: cliente|nome, cpf, placa, valor_periodo (e a data de início).
create or replace function fn_hist_comparar(p_tipo text, p_data date, p_dados jsonb) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_valor  numeric;
  v_vper   numeric;
  v_placa  text := nullif(p_dados->>'placa', '');
  v_cpf    text := nullif(p_dados->>'cpf', '');
  v_nome   text := coalesce(nullif(p_dados->>'cliente', ''), nullif(p_dados->>'nome', ''));
  v_ait    text := nullif(p_dados->>'ait', '');
  v_marca  text := nullif(p_dados->>'marca', '');
  v_n      int;
  v_outro  numeric;
  r        record;
begin
  begin v_valor := nullif(p_dados->>'valor', '')::numeric; exception when others then v_valor := null; end;
  begin v_vper := nullif(p_dados->>'valor_periodo', '')::numeric; exception when others then v_vper := null; end;

  if p_tipo = 'pagamento' then
    if p_data is null or v_valor is null or (v_placa is null and v_cpf is null and v_nome is null) then
      return fn_hist_resultado('sem_comparacao', 'Faltam a data, o valor ou quem pagou (placa, CPF ou nome).');
    end if;
    select count(*) filter (where p.valor = v_valor), max(p.valor) filter (where p.valor <> v_valor) into v_n, v_outro
      from pagamentos p
      join cobrancas c on c.id = p.cobranca_id
      join contratos ct on ct.id = c.contrato_id
      join clientes cl on cl.id = ct.cliente_id
      join motos m on m.id = ct.moto_id
     where p.data_pagamento = p_data
       and ((v_placa is not null and m.placa = v_placa) or (v_cpf is not null and cl.cpf = v_cpf)
            or (v_nome is not null and fn_hist_nome_confere(cl.nome, v_nome)));
    if v_n > 0 then return fn_hist_resultado('ja_existe'); end if;
    if v_outro is not null then
      return fn_hist_resultado('diverge', 'No sistema, nesse dia, há pagamento de ' || fn_pend_moeda(v_outro) || '.');
    end if;
    return fn_hist_resultado('nova');

  elsif p_tipo = 'despesa' then
    if p_data is null or v_valor is null then
      return fn_hist_resultado('sem_comparacao', 'Faltam a data ou o valor.');
    end if;
    select count(*) filter (where d.valor = v_valor), max(d.valor) filter (where d.valor <> v_valor) into v_n, v_outro
      from despesas d left join motos m on m.id = d.moto_id
     where d.data = p_data and (v_placa is null or m.placa = v_placa);
    if v_n > 0 then return fn_hist_resultado('ja_existe'); end if;
    if v_placa is not null and v_outro is not null then
      return fn_hist_resultado('diverge', 'No sistema, nesse dia e nesse veículo, há despesa de ' || fn_pend_moeda(v_outro) || '.');
    end if;
    return fn_hist_resultado('nova');

  elsif p_tipo = 'multa' then
    if v_placa is null or (v_ait is null and (p_data is null or v_valor is null)) then
      return fn_hist_resultado('sem_comparacao', 'Faltam a placa e o AIT (ou a data e o valor).');
    end if;
    select mt.valor into r from multas_transito mt join motos m on m.id = mt.moto_id
     where m.placa = v_placa and ((v_ait is not null and mt.ait = v_ait)
            or (v_ait is null and mt.data_infracao = p_data and mt.valor = v_valor)) limit 1;
    if not found then return fn_hist_resultado('nova'); end if;
    if v_valor is not null and r.valor <> v_valor then
      return fn_hist_resultado('diverge', 'No sistema a multa tem valor ' || fn_pend_moeda(r.valor) || '.');
    end if;
    return fn_hist_resultado('ja_existe');

  elsif p_tipo = 'cliente' then
    if v_cpf is not null then
      select nome into r from clientes where cpf = v_cpf;
      if found then
        if v_nome is not null and not fn_hist_nome_confere(r.nome, v_nome) then
          return fn_hist_resultado('diverge', 'No sistema este CPF está no nome de ' || r.nome || '.');
        end if;
        return fn_hist_resultado('ja_existe');
      end if;
      if v_nome is not null then
        select cpf into r from clientes where fn_pend_sem_acento(nome) = fn_pend_sem_acento(v_nome) limit 1;
        if found then return fn_hist_resultado('diverge', 'Já existe cliente com este nome e CPF final ' || right(r.cpf, 4) || '.'); end if;
      end if;
      return fn_hist_resultado('nova');
    end if;
    if v_nome is null then return fn_hist_resultado('sem_comparacao', 'Faltam o nome ou o CPF.'); end if;
    if exists (select 1 from clientes where fn_pend_sem_acento(nome) = fn_pend_sem_acento(v_nome)) then
      return fn_hist_resultado('ja_existe');
    end if;
    return fn_hist_resultado('nova');

  elsif p_tipo = 'veiculo' then
    if v_placa is null then return fn_hist_resultado('sem_comparacao', 'Falta a placa.'); end if;
    select marca, modelo into r from motos where placa = v_placa;
    if not found then return fn_hist_resultado('nova'); end if;
    if v_marca is not null and fn_pend_sem_acento(r.marca) <> fn_pend_sem_acento(v_marca) then
      return fn_hist_resultado('diverge', 'No sistema é ' || r.marca || ' ' || r.modelo || '.');
    end if;
    return fn_hist_resultado('ja_existe');

  elsif p_tipo = 'contrato' then
    if v_placa is null or (v_cpf is null and v_nome is null) then
      return fn_hist_resultado('sem_comparacao', 'Faltam a placa ou o cliente (CPF ou nome).');
    end if;
    select ct.data_inicio, ct.valor_periodo into r
      from contratos ct join motos m on m.id = ct.moto_id join clientes cl on cl.id = ct.cliente_id
     where m.placa = v_placa and ((v_cpf is not null and cl.cpf = v_cpf) or (v_nome is not null and fn_hist_nome_confere(cl.nome, v_nome)))
     order by ct.data_inicio desc limit 1;
    if not found then return fn_hist_resultado('nova'); end if;
    if (p_data is null or r.data_inicio = p_data) and (v_vper is null or r.valor_periodo = v_vper) then
      return fn_hist_resultado('ja_existe');
    end if;
    return fn_hist_resultado('diverge', 'No sistema: início em ' || to_char(r.data_inicio, 'DD/MM/YYYY') || ', ' || fn_pend_moeda(r.valor_periodo) || ' por período.');
  end if;

  return fn_hist_resultado('sem_comparacao', 'Sem comparação automática para este tipo.');
end $$;

-- ---------- Entregar um lote ----------
-- payload: {"fonte": "chat_financeiro"|"chat_contratos", "rotulo": text, "periodo_inicio": "aaaa-mm-dd", "periodo_fim": "aaaa-mm-dd",
--           "observacao": text, "registros": [{"tipo", "data", "dados": {...}, "trecho", "resumo"}]}   (até 50 registros)
create or replace function rpc_conector_entregar_lote_historico(payload jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_fonte    text := payload->>'fonte';
  v_rotulo   text := nullif(btrim(coalesce(payload->>'rotulo', '')), '');
  v_inicio   date;
  v_fim      date;
  v_obs      text := nullif(btrim(coalesce(payload->>'observacao', '')), '');
  v_regs     jsonb := payload->'registros';
  v_lote     uuid;
  v_item     jsonb;
  v_i        int := 0;
  v_tipo     text;
  v_data     date;
  v_dados    jsonb;
  v_trecho   text;
  v_resumo   text;
  v_chave    text;
  v_cmp      jsonb;
  v_id       uuid;
  v_inseridos int := 0;
  v_repetidos int := 0;
  v_sit      jsonb := '{}'::jsonb;
begin
  perform fn_pend_exige_servico_ou_dono();
  if v_fonte is null or v_fonte not in ('chat_financeiro', 'chat_contratos') then
    raise exception 'A fonte precisa ser chat_financeiro ou chat_contratos.';
  end if;
  if v_rotulo is null or length(v_rotulo) > 60 then raise exception 'O rótulo do lote é obrigatório e tem até 60 caracteres.'; end if;
  if length(coalesce(v_obs, '')) > 500 then raise exception 'A observação passa de 500 caracteres.'; end if;
  begin
    v_inicio := (payload->>'periodo_inicio')::date;
    v_fim := (payload->>'periodo_fim')::date;
  exception when others then
    raise exception 'O período precisa estar no formato aaaa-mm-dd.';
  end;
  if v_inicio is null or v_fim is null or v_fim < v_inicio then raise exception 'Informe o período do lote (início e fim, com o fim depois do início).'; end if;
  if v_fim - v_inicio > 1100 then raise exception 'O período passa de 1100 dias: divida o chat em lotes menores.'; end if;
  if v_regs is null or jsonb_typeof(v_regs) <> 'array' or jsonb_array_length(v_regs) = 0 then raise exception 'Envie ao menos um registro.'; end if;
  if jsonb_array_length(v_regs) > 50 then raise exception 'Envie no máximo 50 registros por vez.'; end if;

  perform pg_advisory_xact_lock(hashtext('historico:' || v_fonte || ':' || v_rotulo));
  insert into historico_chat_lotes (fonte, rotulo, periodo_inicio, periodo_fim, observacao, entregue_por)
  values (v_fonte, v_rotulo, v_inicio, v_fim, v_obs, auth.uid())
  on conflict (fonte, rotulo, periodo_inicio, periodo_fim) do update set observacao = coalesce(excluded.observacao, historico_chat_lotes.observacao)
  returning id into v_lote;

  for v_item in select * from jsonb_array_elements(v_regs) loop
    v_i := v_i + 1;
    v_tipo := v_item->>'tipo';
    if v_tipo is null or v_tipo not in ('pagamento', 'despesa', 'multa', 'divida', 'movimento_socio', 'cliente', 'veiculo', 'contrato', 'outro') then
      raise exception 'Registro %: tipo desconhecido.', v_i;
    end if;
    begin v_data := nullif(v_item->>'data', '')::date; exception when others then raise exception 'Registro %: data inválida.', v_i; end;
    if v_data is not null and (v_data < v_inicio or v_data > v_fim) then raise exception 'Registro %: a data está fora do período do lote.', v_i; end if;
    v_dados := v_item->'dados';
    if v_dados is null or jsonb_typeof(v_dados) <> 'object' or v_dados = '{}'::jsonb or length(v_dados::text) > 3000 then
      raise exception 'Registro %: os dados precisam ser um objeto não vazio de até 3000 caracteres.', v_i;
    end if;
    v_trecho := left(nullif(btrim(coalesce(v_item->>'trecho', '')), ''), 600);
    if v_trecho is null then raise exception 'Registro %: falta o trecho do chat que originou o registro.', v_i; end if;
    v_resumo := left(nullif(btrim(coalesce(v_item->>'resumo', '')), ''), 200);
    if v_resumo is null then raise exception 'Registro %: falta o resumo.', v_i; end if;
    v_chave := md5(v_fonte || '|' || v_tipo || '|' || coalesce(v_data::text, '') || '|' || v_dados::text);

    if exists (select 1 from historico_chat_registros where chave = v_chave) then
      v_repetidos := v_repetidos + 1;
      continue;
    end if;
    v_cmp := fn_hist_comparar(v_tipo, v_data, v_dados);
    insert into historico_chat_registros (lote_id, fonte, tipo, data_ref, dados, trecho, resumo, chave, situacao, detalhe, entregue_por)
    values (v_lote, v_fonte, v_tipo, v_data, v_dados, v_trecho, v_resumo, v_chave, v_cmp->>'situacao', left(v_cmp->>'detalhe', 300), auth.uid())
    on conflict (chave) do nothing returning id into v_id;
    if v_id is null then
      v_repetidos := v_repetidos + 1;
    else
      v_inseridos := v_inseridos + 1;
      v_sit := jsonb_set(v_sit, array[v_cmp->>'situacao'], to_jsonb(coalesce((v_sit->>(v_cmp->>'situacao'))::int, 0) + 1));
    end if;
  end loop;

  update historico_chat_lotes
     set registros_recebidos = registros_recebidos + v_i, registros_novos = registros_novos + v_inseridos
   where id = v_lote;
  return jsonb_build_object('lote_id', v_lote, 'recebidos', v_i, 'inseridos', v_inseridos, 'repetidos', v_repetidos, 'situacoes', v_sit);
end $$;

-- ---------- Resumo: contagens e períodos dos lotes ----------
create or replace function rpc_conector_resumo_historico(p_fonte text default null) returns jsonb
language plpgsql stable security definer set search_path = public as $$
begin
  perform fn_pend_exige_servico_ou_dono();
  if p_fonte is not null and p_fonte not in ('chat_financeiro', 'chat_contratos') then
    raise exception 'A fonte precisa ser chat_financeiro ou chat_contratos.';
  end if;
  return jsonb_build_object(
    'lotes', coalesce((
      select jsonb_agg(jsonb_build_object('fonte', fonte, 'rotulo', rotulo, 'periodo_inicio', periodo_inicio, 'periodo_fim', periodo_fim,
                                          'registros', registros_recebidos, 'entregue_em', entregue_em) order by fonte, periodo_inicio)
        from (select * from historico_chat_lotes where p_fonte is null or fonte = p_fonte order by periodo_inicio limit 500) l), '[]'::jsonb),
    'contagens', coalesce((
      select jsonb_agg(jsonb_build_object('fonte', fonte, 'tipo', tipo, 'situacao', situacao, 'qtd', n) order by fonte, tipo, situacao)
        from (select fonte, tipo, situacao, count(*) n from historico_chat_registros where p_fonte is null or fonte = p_fonte
               group by fonte, tipo, situacao) c), '[]'::jsonb));
end $$;

-- ---------- O que é novo ou diverge (sem trecho e sem CPF inteiro) ----------
create or replace function rpc_conector_historico_a_conferir(p_fonte text default null, p_situacao text default null, p_limite int default 30)
returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_limite int := least(greatest(coalesce(p_limite, 30), 1), 50);
begin
  perform fn_pend_exige_servico_ou_dono();
  if p_fonte is not null and p_fonte not in ('chat_financeiro', 'chat_contratos') then
    raise exception 'A fonte precisa ser chat_financeiro ou chat_contratos.';
  end if;
  if p_situacao is not null and p_situacao not in ('nova', 'ja_existe', 'diverge', 'sem_comparacao') then
    raise exception 'A situação precisa ser nova, ja_existe, diverge ou sem_comparacao.';
  end if;
  return coalesce((
    select jsonb_agg(jsonb_build_object('id', id, 'fonte', fonte, 'tipo', tipo, 'data', data_ref, 'resumo', resumo, 'situacao', situacao,
                                         'detalhe', detalhe) order by data_ref nulls last, entregue_em)
      from (select * from historico_chat_registros
             where (p_fonte is null or fonte = p_fonte)
               and ((p_situacao is null and situacao in ('nova', 'diverge')) or situacao = p_situacao)
             order by data_ref nulls last, entregue_em limit v_limite) r), '[]'::jsonb);
end $$;

-- ---------- Descartar um lote entregue por engano (só dono) ----------
create or replace function rpc_historico_descartar_lote(p_lote uuid) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_n int;
begin
  perform fn_pend_exige_dono();
  if not exists (select 1 from historico_chat_lotes where id = p_lote) then raise exception 'Lote não encontrado.'; end if;
  if exists (select 1 from historico_chat_registros where lote_id = p_lote and situacao = 'aplicada') then
    raise exception 'Este lote já tem registros aplicados no sistema: não dá para descartar.';
  end if;
  select count(*) into v_n from historico_chat_registros where lote_id = p_lote;
  delete from historico_chat_lotes where id = p_lote;  -- os registros saem junto (on delete cascade)
  return jsonb_build_object('lote_id', p_lote, 'registros_apagados', v_n);
end $$;

-- ---------- Permissões ----------
revoke all on function fn_hist_nome_confere(text, text), fn_hist_resultado(text, text), fn_hist_comparar(text, date, jsonb) from public, anon, authenticated;
revoke all on function rpc_conector_entregar_lote_historico(jsonb) from public, anon;
revoke all on function rpc_conector_resumo_historico(text) from public, anon;
revoke all on function rpc_conector_historico_a_conferir(text, text, int) from public, anon;
revoke all on function rpc_historico_descartar_lote(uuid) from public, anon;
grant execute on function rpc_conector_entregar_lote_historico(jsonb) to authenticated;
grant execute on function rpc_conector_resumo_historico(text) to authenticated;
grant execute on function rpc_conector_historico_a_conferir(text, text, int) to authenticated;
grant execute on function rpc_historico_descartar_lote(uuid) to authenticated;

notify pgrst, 'reload schema';
