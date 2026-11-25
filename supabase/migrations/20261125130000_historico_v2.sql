-- =====================================================================
-- 20261125130000_historico_v2.sql
-- Histórico dos chats, versão 2 (seção 24.9 do plano): ajustes depois da primeira entrega real dos dois chats (25/11/2026).
--
--   * a lista «a conferir» passa a ter PAGINAÇÃO e o TOTAL (o Financeiro tinha 55 novos e só 50 apareciam), e filtra por tipo;
--   * multa: compara também com o valor atualizado e reconhece o valor com 20% de desconto (as 8 «divergências» de multa eram esse desconto);
--   * `data_estimada` (janela de ±7 dias no pagamento e na despesa, ±30 no contrato), `finalidade` do pagamento (semana, caução, multa...
--     casa com o tipo da cobrança, para o pagamento composto), `inferido` e `faltando` aparecem na lista;
--   * a entrega avisa quando um registro «igual» já entregue tem OUTRO trecho do chat (pode ser um segundo pagamento real: o chat reenvia
--     com `ocorrencia` = 2);
--   * `rpc_historico_conferencia` (só dono): todos os registros com trecho e lote, para a planilha de conferência gerada pelo app.
--
-- Substitui funções da migration 20261125120000_historico_chats.sql (create or replace). Compatível com a versão anterior do app.
-- =====================================================================

create or replace function fn_hist_tipo_de_cobranca(p_finalidade text) returns text
language sql immutable as $$
  select case fn_pend_sem_acento(p_finalidade)
           when 'locacao' then 'locacao' when 'semana' then 'locacao' when 'parcela' then 'locacao'
           when 'caucao' then 'caucao' when 'multa' then 'multa_transito' when 'dano' then 'dano' when 'outros' then 'outros'
         end;
$$;

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
  v_cob    text := fn_hist_tipo_de_cobranca(p_dados->>'finalidade');
  v_estim  boolean := false;
  v_janela int;
  v_n      int;
  v_outro  numeric;
  r        record;
begin
  begin v_valor := nullif(p_dados->>'valor', '')::numeric; exception when others then v_valor := null; end;
  begin v_vper := nullif(p_dados->>'valor_periodo', '')::numeric; exception when others then v_vper := null; end;
  begin v_estim := coalesce((p_dados->>'data_estimada')::boolean, false); exception when others then v_estim := false; end;
  v_janela := case when v_estim then (case when p_tipo = 'contrato' then 30 else 7 end) else 0 end;

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
     where p.data_pagamento between p_data - v_janela and p_data + v_janela
       and (v_cob is null or c.tipo = v_cob)
       and ((v_placa is not null and m.placa = v_placa) or (v_cpf is not null and cl.cpf = v_cpf)
            or (v_nome is not null and fn_hist_nome_confere(cl.nome, v_nome)));
    if v_n > 0 then return fn_hist_resultado('ja_existe'); end if;
    if v_outro is not null then
      return fn_hist_resultado('diverge', 'No sistema, ' || case when v_estim then 'por volta desse dia' else 'nesse dia' end
                                          || case when v_cob is not null then ' (' || v_cob || ')' else '' end
                                          || ', há pagamento de ' || fn_pend_moeda(v_outro) || '.');
    end if;
    return fn_hist_resultado('nova');

  elsif p_tipo = 'despesa' then
    if p_data is null or v_valor is null then
      return fn_hist_resultado('sem_comparacao', 'Faltam a data ou o valor.');
    end if;
    select count(*) filter (where d.valor = v_valor), max(d.valor) filter (where d.valor <> v_valor) into v_n, v_outro
      from despesas d left join motos m on m.id = d.moto_id
     where d.data between p_data - v_janela and p_data + v_janela and (v_placa is null or m.placa = v_placa);
    if v_n > 0 then return fn_hist_resultado('ja_existe'); end if;
    if v_placa is not null and v_outro is not null then
      return fn_hist_resultado('diverge', 'No sistema, nesse dia e nesse veículo, há despesa de ' || fn_pend_moeda(v_outro) || '.');
    end if;
    return fn_hist_resultado('nova');

  elsif p_tipo = 'multa' then
    if v_placa is null or (v_ait is null and (p_data is null or v_valor is null)) then
      return fn_hist_resultado('sem_comparacao', 'Faltam a placa e o AIT (ou a data e o valor).');
    end if;
    select mt.valor, mt.valor_atual into r from multas_transito mt join motos m on m.id = mt.moto_id
     where m.placa = v_placa and ((v_ait is not null and mt.ait = v_ait)
            or (v_ait is null and mt.data_infracao = p_data and (mt.valor = v_valor or mt.valor_atual = v_valor))) limit 1;
    if not found then return fn_hist_resultado('nova'); end if;
    if v_valor is null or v_valor = r.valor or v_valor = r.valor_atual then return fn_hist_resultado('ja_existe'); end if;
    if abs(v_valor - round(r.valor * 0.8, 2)) <= 0.01 then
      return fn_hist_resultado('ja_existe', 'O valor do chat é o da multa com 20% de desconto (valor cheio no sistema: ' || fn_pend_moeda(r.valor) || ').');
    end if;
    return fn_hist_resultado('diverge', 'No sistema a multa tem valor ' || fn_pend_moeda(r.valor) || '.');

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
    if (p_data is null or abs(r.data_inicio - p_data) <= v_janela) and (v_vper is null or r.valor_periodo = v_vper) then
      return fn_hist_resultado('ja_existe');
    end if;
    return fn_hist_resultado('diverge', 'No sistema: início em ' || to_char(r.data_inicio, 'DD/MM/YYYY') || ', ' || fn_pend_moeda(r.valor_periodo) || ' por período.');
  end if;

  return fn_hist_resultado('sem_comparacao', 'Sem comparação automática para este tipo.');
end $$;

-- ---------- Entrega: avisa quando um registro «igual» já entregue tem outro trecho do chat ----------
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
  v_antigo   text;
  v_inseridos int := 0;
  v_repetidos int := 0;
  v_sit      jsonb := '{}'::jsonb;
  v_parecidos jsonb := '[]'::jsonb;
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

    select trecho into v_antigo from historico_chat_registros where chave = v_chave;
    if found then
      v_repetidos := v_repetidos + 1;
      if v_antigo <> v_trecho and jsonb_array_length(v_parecidos) < 10 then v_parecidos := v_parecidos || to_jsonb(v_resumo); end if;
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
  return jsonb_build_object('lote_id', v_lote, 'recebidos', v_i, 'inseridos', v_inseridos, 'repetidos', v_repetidos, 'situacoes', v_sit,
                            'parecidos_com_trecho_diferente', v_parecidos);
end $$;

-- ---------- A conferir: paginação, total e filtro por tipo ----------
drop function if exists rpc_conector_historico_a_conferir(text, text, int);
create or replace function rpc_conector_historico_a_conferir(p_fonte text default null, p_situacao text default null, p_limite int default 30,
                                                             p_pagina int default 1, p_tipo text default null) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_limite int := least(greatest(coalesce(p_limite, 30), 1), 50);
  v_pagina int := greatest(coalesce(p_pagina, 1), 1);
  v_total  int;
begin
  perform fn_pend_exige_servico_ou_dono();
  if p_fonte is not null and p_fonte not in ('chat_financeiro', 'chat_contratos') then
    raise exception 'A fonte precisa ser chat_financeiro ou chat_contratos.';
  end if;
  if p_situacao is not null and p_situacao not in ('nova', 'ja_existe', 'diverge', 'sem_comparacao') then
    raise exception 'A situação precisa ser nova, ja_existe, diverge ou sem_comparacao.';
  end if;
  if p_tipo is not null and p_tipo not in ('pagamento', 'despesa', 'multa', 'divida', 'movimento_socio', 'cliente', 'veiculo', 'contrato', 'outro') then
    raise exception 'Tipo desconhecido.';
  end if;
  select count(*) into v_total from historico_chat_registros
   where (p_fonte is null or fonte = p_fonte) and (p_tipo is null or tipo = p_tipo)
     and ((p_situacao is null and situacao in ('nova', 'diverge')) or situacao = p_situacao);
  return jsonb_build_object('total', v_total, 'pagina', v_pagina, 'por_pagina', v_limite, 'linhas', coalesce((
    select jsonb_agg(jsonb_build_object('id', id, 'fonte', fonte, 'tipo', tipo, 'data', data_ref, 'resumo', resumo, 'situacao', situacao,
                                         'detalhe', detalhe, 'inferido', dados->>'inferido', 'faltando', dados->>'faltando',
                                         'data_estimada', coalesce((dados->>'data_estimada') = 'true', false))
                     order by data_ref nulls last, entregue_em, id)
      from (select * from historico_chat_registros
             where (p_fonte is null or fonte = p_fonte) and (p_tipo is null or tipo = p_tipo)
               and ((p_situacao is null and situacao in ('nova', 'diverge')) or situacao = p_situacao)
             order by data_ref nulls last, entregue_em, id limit v_limite offset (v_pagina - 1) * v_limite) r), '[]'::jsonb));
end $$;

-- ---------- Conferência completa para a planilha do app (só dono) ----------
create or replace function rpc_historico_conferencia(p_fonte text default null, p_situacao text default null) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_total int;
begin
  perform fn_pend_exige_dono();
  if p_fonte is not null and p_fonte not in ('chat_financeiro', 'chat_contratos') then
    raise exception 'A fonte precisa ser chat_financeiro ou chat_contratos.';
  end if;
  if p_situacao is not null and p_situacao not in ('nova', 'ja_existe', 'diverge', 'sem_comparacao', 'descartada', 'aplicada') then
    raise exception 'Situação desconhecida.';
  end if;
  select count(*) into v_total from historico_chat_registros where (p_fonte is null or fonte = p_fonte) and (p_situacao is null or situacao = p_situacao);
  return jsonb_build_object('total', v_total, 'linhas', coalesce((
    select jsonb_agg(jsonb_build_object('id', r.id, 'fonte', r.fonte, 'tipo', r.tipo, 'data', r.data_ref, 'resumo', r.resumo, 'situacao', r.situacao,
                                         'detalhe', r.detalhe, 'trecho', r.trecho, 'lote', l.rotulo, 'entregue_em', r.entregue_em,
                                         'inferido', r.dados->>'inferido', 'faltando', r.dados->>'faltando',
                                         'data_estimada', coalesce((r.dados->>'data_estimada') = 'true', false))
                     order by r.fonte, case r.situacao when 'diverge' then 1 when 'nova' then 2 when 'sem_comparacao' then 3 when 'ja_existe' then 4 else 5 end,
                              r.data_ref nulls last, r.entregue_em, r.id)
      from (select * from historico_chat_registros where (p_fonte is null or fonte = p_fonte) and (p_situacao is null or situacao = p_situacao)
             order by fonte, data_ref nulls last, entregue_em, id limit 10000) r
      join historico_chat_lotes l on l.id = r.lote_id), '[]'::jsonb));
end $$;

-- ---------- Permissões ----------
revoke all on function fn_hist_tipo_de_cobranca(text) from public, anon, authenticated;
revoke all on function rpc_conector_historico_a_conferir(text, text, int, int, text) from public, anon;
revoke all on function rpc_historico_conferencia(text, text) from public, anon;
grant execute on function rpc_conector_historico_a_conferir(text, text, int, int, text) to authenticated;
grant execute on function rpc_historico_conferencia(text, text) to authenticated;

notify pgrst, 'reload schema';
