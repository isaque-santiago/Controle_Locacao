-- =====================================================================
-- 20261124130000_escrita_direta_conector.sql
-- Escrita direta do conector do claude.ai (seção 24.7b do plano, etapa 3).
--
-- Decisão do dono em 24/11/2026: nada de fila de aprovação. O chat GRAVA DIRETO o que está limpo e, na dúvida, NÃO GRAVA e devolve o
-- motivo para o Claude perguntar ao usuário na conversa. A tabela `pendencias_lancamento` (migration 20261124120000) vira o
-- HISTÓRICO e a auditoria do que o chat gravou, com a marca `decisao_automatica`.
--
--   rpc_conector_registrar_pagamento(payload)   grava o pagamento se a cobrança foi identificada, o valor é igual ao saldo, não há
--                                               duplicidade nem data futura e o valor é de até R$ 10.000,00; senão devolve o motivo;
--   rpc_conector_registrar_despesa(payload)     idem, com teto de R$ 5.000,00 (e exige o veículo ou a descrição dele);
--   rpc_conector_cadastrar_cliente(payload)     cadastra o cliente (CPF válido, ou CPF provisório 0000000000N com a marca na observação);
--                                               recusa CPF repetido e homônimo não confirmado;
--   rpc_conector_cadastrar_veiculo(payload)     cadastra o veículo (placa válida e única);
--   rpc_pendencia_desfazer(id, motivo)          só dono: desfaz um lançamento AUTOMÁTICO dentro de 7 dias (apaga o pagamento, a despesa,
--                                               o cliente ou o veículo, se ainda não tiverem outros registros ligados);
--   rpc_conector_minhas_pendencias(limite)      passa a trazer também `decisao_automatica` e `desfeita_em`.
--
-- Cada RPC devolve um jsonb: {"gravado": true, "pendencia_id", "registro_id", "resumo", "repetida"} ou
-- {"gravado": false, "motivo": "duvida" | "acima_do_teto" | ..., "mensagem": "...", "avisos": [...]}. Dado inválido (valor, data, CPF,
-- placa...) levanta erro com mensagem em português, como as demais RPCs. Quem pode chamar: o usuário de serviço do conector ou um dono;
-- o usuário de serviço continua sem ler tabela nenhuma. Idempotência: a mesma `chave_operacao` devolve o que já foi gravado.
--
-- Compatível com a versão anterior do app: só colunas novas com padrão e funções novas.
-- =====================================================================

-- ---------- O histórico passa a registrar cadastros e desfazimentos ----------
alter table pendencias_lancamento
  add column if not exists decisao_automatica boolean not null default false,
  add column if not exists desfeita_em        timestamptz,
  add column if not exists desfeita_por       uuid,
  add column if not exists motivo_desfazer    text check (length(motivo_desfazer) <= 300);

alter table pendencias_lancamento drop constraint if exists pendencias_lancamento_tipo_check;
alter table pendencias_lancamento add constraint pendencias_lancamento_tipo_check
  check (tipo in ('pagamento', 'despesa', 'cliente', 'veiculo'));
alter table pendencias_lancamento drop constraint if exists pendencias_lancamento_status_check;
alter table pendencias_lancamento add constraint pendencias_lancamento_status_check
  check (status in ('pendente', 'aprovada', 'recusada', 'desfeita'));

alter table pendencias_lancamento drop constraint if exists ck_pendencia_estado;
alter table pendencias_lancamento add constraint ck_pendencia_estado check (
  (status = 'pendente' and decidido_por is null and decidido_em is null and registro_id is null and motivo_recusa is null
     and desfeita_em is null)
  or (status = 'aprovada' and decidido_por is not null and decidido_em is not null and registro_id is not null
     and motivo_recusa is null and desfeita_em is null)
  or (status = 'recusada' and decidido_por is not null and decidido_em is not null and registro_id is null
     and nullif(btrim(motivo_recusa), '') is not null and desfeita_em is null)
  or (status = 'desfeita' and decidido_por is not null and decidido_em is not null and registro_id is not null
     and desfeita_em is not null and desfeita_por is not null and nullif(btrim(motivo_desfazer), '') is not null)
);

-- ---------- Funções de apoio (internas) ----------
-- CPF válido pelos dígitos verificadores (mesma regra de src/domain/validadores.py).
create or replace function fn_cpf_valido(p_cpf text) returns boolean
language plpgsql immutable as $$
declare
  d  text := regexp_replace(coalesce(p_cpf, ''), '\D', '', 'g');
  s  int;
  i  int;
  d1 int;
  d2 int;
begin
  if length(d) <> 11 or d ~ '^(\d)\1{10}$' then return false; end if;
  s := 0;
  for i in 1..9 loop s := s + substr(d, i, 1)::int * (11 - i); end loop;
  d1 := case when s % 11 < 2 then 0 else 11 - s % 11 end;
  s := 0;
  for i in 1..10 loop s := s + substr(d, i, 1)::int * (12 - i); end loop;
  d2 := case when s % 11 < 2 then 0 else 11 - s % 11 end;
  return d1 = substr(d, 10, 1)::int and d2 = substr(d, 11, 1)::int;
end $$;

-- Telefone brasileiro (DDD + 8 ou 9 dígitos) no formato guardado pelo app; nulo se vazio; erro se inválido.
create or replace function fn_pend_telefone(p_texto text, p_rotulo text) returns text
language plpgsql immutable as $$
declare d text := regexp_replace(coalesce(p_texto, ''), '\D', '', 'g');
begin
  if d = '' then return null; end if;
  if length(d) not in (10, 11) or substr(d, 1, 2)::int < 11 or (length(d) = 11 and substr(d, 3, 1) <> '9') then
    raise exception 'Informe o % com DDD e número válidos.', p_rotulo;
  end if;
  return case when length(d) = 11 then '(' || substr(d, 1, 2) || ') ' || substr(d, 3, 5) || '-' || substr(d, 8)
              else '(' || substr(d, 1, 2) || ') ' || substr(d, 3, 4) || '-' || substr(d, 7) end;
end $$;

create or replace function fn_pend_texto(p_texto text, p_limite int, p_rotulo text) returns text
language plpgsql immutable as $$
declare t text := nullif(btrim(regexp_replace(coalesce(p_texto, ''), '\s+', ' ', 'g')), '');
begin
  if length(coalesce(t, '')) > p_limite then
    raise exception 'O campo % passa de % caracteres.', p_rotulo, p_limite;
  end if;
  return t;
end $$;

-- Origem e chave de operação de uma gravação direta (só as origens do chat).
create or replace function fn_pend_confere_chamada(p_payload jsonb, out o_origem text, out o_chave text, out o_trecho text)
language plpgsql security definer set search_path = public as $$
begin
  perform fn_pend_exige_servico_ou_dono();
  o_origem := p_payload->>'origem';
  if o_origem is null or o_origem not in ('chat_financeiro', 'chat_contratos') then
    raise exception 'A origem precisa ser chat_financeiro ou chat_contratos.';
  end if;
  o_chave := btrim(coalesce(p_payload->>'chave_operacao', ''));
  if o_chave = '' or length(o_chave) > 120 then
    raise exception 'A chave de operação é obrigatória e tem até 120 caracteres.';
  end if;
  o_trecho := left(nullif(btrim(coalesce(p_payload->>'trecho_origem', '')), ''), 600);
  perform pg_advisory_xact_lock(hashtext('conector:' || o_chave));  -- dois envios iguais ao mesmo tempo viram um só
end $$;

-- Resposta quando a chave já foi gravada antes.
create or replace function fn_pend_ja_gravada(p_chave text) returns jsonb
language sql stable security definer set search_path = public as $$
  select jsonb_build_object('gravado', status = 'aprovada', 'repetida', true, 'pendencia_id', id, 'status', status,
                            'registro_id', registro_id, 'resumo', resumo,
                            'mensagem', case status
                              when 'desfeita' then 'Este lançamento foi desfeito pelo dono. Use outra chave de operação se quiser registrar de novo.'
                              when 'aprovada' then 'Este lançamento já tinha sido gravado.'
                              else 'Esta chave já foi usada por uma proposta que ainda não virou lançamento.' end)
    from pendencias_lancamento where chave_operacao = p_chave;
$$;

create or replace function fn_pend_recusa(p_motivo text, p_mensagem text, p_avisos jsonb default '[]'::jsonb) returns jsonb
language sql immutable as $$
  select jsonb_build_object('gravado', false, 'motivo', p_motivo, 'mensagem', p_mensagem, 'avisos', p_avisos);
$$;

create or replace function fn_pend_textos_dos_avisos(p_avisos jsonb) returns text
language sql immutable as $$
  select string_agg(a->>'texto', ' ') from jsonb_array_elements(p_avisos) a;
$$;

-- Registra no histórico uma gravação feita direto (decisão automática, em nome do usuário que chamou).
create or replace function fn_pend_registrar_automatica(
  p_id uuid, p_tipo text, p_origem text, p_chave text, p_dados jsonb, p_resumo text, p_trecho text, p_registro uuid,
  p_cliente uuid default null, p_contrato uuid default null, p_cobranca uuid default null, p_moto uuid default null) returns void
language sql security definer set search_path = public as $$
  insert into pendencias_lancamento (id, tipo, origem, chave_operacao, dados, cliente_id, contrato_id, cobranca_id, moto_id, resumo,
                                     trecho_origem, avisos, status, registro_id, criado_por, decidido_por, decidido_em, decisao_automatica)
  values (p_id, p_tipo, p_origem, p_chave, p_dados, p_cliente, p_contrato, p_cobranca, p_moto, p_resumo, p_trecho, '[]'::jsonb,
          'aprovada', p_registro, auth.uid(), auth.uid(), now(), true);
$$;

-- ---------- Pagamento ----------
-- payload: {"origem": "chat_financeiro", "chave_operacao": text, "trecho_origem": text,
--           "dados": {"cobranca_id", "valor", "data_pagamento", "forma", "multa_juros", "observacoes"}}
create or replace function rpc_conector_registrar_pagamento(payload jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  c        record;
  v_dados  jsonb;
  v_vinc   record;
  v_avisos jsonb;
  v_id     uuid := gen_random_uuid();
  v_reg    uuid;
  v_ja     jsonb;
begin
  select * into c from fn_pend_confere_chamada(payload);
  v_ja := fn_pend_ja_gravada(c.o_chave);
  if v_ja is not null then return v_ja; end if;

  v_dados := fn_pend_normalizar('pagamento', payload->'dados');
  if (v_dados->>'valor')::numeric > 10000 then
    return fn_pend_recusa('acima_do_teto', 'O valor passa de R$ 10.000,00, o máximo que o chat grava sozinho. Registre pelo app.');
  end if;
  select * into v_vinc from fn_pend_vinculos('pagamento', v_dados);
  v_avisos := fn_pend_avisos('pagamento', v_dados);
  if jsonb_array_length(v_avisos) > 0 then
    return fn_pend_recusa('duvida', fn_pend_textos_dos_avisos(v_avisos), v_avisos);
  end if;

  insert into pagamentos (cobranca_id, data_pagamento, valor, multa_juros, forma, observacoes, chave_operacao)
  values ((v_dados->>'cobranca_id')::uuid, (v_dados->>'data_pagamento')::date, (v_dados->>'valor')::numeric,
          (v_dados->>'multa_juros')::numeric, v_dados->>'forma', v_dados->>'observacoes', v_id)
  returning id into v_reg;
  perform fn_pend_registrar_automatica(v_id, 'pagamento', c.o_origem, c.o_chave, v_dados, v_vinc.o_resumo, c.o_trecho, v_reg,
                                       v_vinc.o_cliente, v_vinc.o_contrato, v_vinc.o_cobranca, v_vinc.o_moto);
  return jsonb_build_object('gravado', true, 'repetida', false, 'pendencia_id', v_id, 'registro_id', v_reg, 'resumo', v_vinc.o_resumo);
end $$;

-- ---------- Despesa ----------
create or replace function rpc_conector_registrar_despesa(payload jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  c        record;
  v_dados  jsonb;
  v_vinc   record;
  v_avisos jsonb;
  v_id     uuid := gen_random_uuid();
  v_reg    uuid;
  v_ja     jsonb;
begin
  select * into c from fn_pend_confere_chamada(payload);
  v_ja := fn_pend_ja_gravada(c.o_chave);
  if v_ja is not null then return v_ja; end if;

  v_dados := fn_pend_normalizar('despesa', payload->'dados');
  if (v_dados->>'valor')::numeric > 5000 then
    return fn_pend_recusa('acima_do_teto', 'O valor passa de R$ 5.000,00, o máximo que o chat grava sozinho. Registre pelo app.');
  end if;
  select * into v_vinc from fn_pend_vinculos('despesa', v_dados);
  v_avisos := fn_pend_avisos('despesa', v_dados);
  if jsonb_array_length(v_avisos) > 0 then
    return fn_pend_recusa('duvida', fn_pend_textos_dos_avisos(v_avisos), v_avisos);
  end if;

  insert into despesas (data, moto_id, descricao_veiculo, categoria, valor, repassar_locatario, observacoes)
  values ((v_dados->>'data')::date, nullif(v_dados->>'moto_id', '')::uuid, v_dados->>'descricao_veiculo', v_dados->>'categoria',
          (v_dados->>'valor')::numeric, (v_dados->>'repassar_locatario')::boolean, v_dados->>'observacoes')
  returning id into v_reg;
  perform fn_pend_registrar_automatica(v_id, 'despesa', c.o_origem, c.o_chave, v_dados, v_vinc.o_resumo, c.o_trecho, v_reg,
                                       null, null, null, v_vinc.o_moto);
  return jsonb_build_object('gravado', true, 'repetida', false, 'pendencia_id', v_id, 'registro_id', v_reg, 'resumo', v_vinc.o_resumo);
end $$;

-- ---------- Cliente ----------
-- dados: {"nome", "cpf" | "cpf_provisorio": true, "telefone", "whatsapp", "email", "endereco", "observacoes", "confirmar_homonimo"}
create or replace function rpc_conector_cadastrar_cliente(payload jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  c         record;
  d         jsonb := payload->'dados';
  v_nome    text;
  v_cpf     text;
  v_prov    boolean;
  v_tel     text;
  v_zap     text;
  v_email   text;
  v_end     text;
  v_obs     text;
  v_outro   record;
  v_n       int := 1;
  v_id      uuid := gen_random_uuid();
  v_cli     uuid;
  v_ja      jsonb;
  v_resumo  text;
begin
  select * into c from fn_pend_confere_chamada(payload);
  v_ja := fn_pend_ja_gravada(c.o_chave);
  if v_ja is not null then return v_ja; end if;
  if d is null or jsonb_typeof(d) <> 'object' then raise exception 'Os dados do cliente precisam ser um objeto.'; end if;

  v_nome := fn_pend_texto(d->>'nome', 160, 'nome');
  if v_nome is null or length(v_nome) < 3 or position(' ' in v_nome) = 0 then
    raise exception 'Informe o nome completo do cliente (nome e sobrenome).';
  end if;
  v_prov := coalesce((d->>'cpf_provisorio')::boolean, false);
  v_cpf := regexp_replace(coalesce(d->>'cpf', ''), '\D', '', 'g');
  if v_prov and v_cpf <> '' then raise exception 'Com cpf_provisorio não se informa CPF.'; end if;
  if not v_prov and not fn_cpf_valido(v_cpf) then
    raise exception 'Informe um CPF válido; sem CPF, marque cpf_provisorio e complete depois.';
  end if;
  v_tel := fn_pend_telefone(d->>'telefone', 'telefone');
  v_zap := fn_pend_telefone(d->>'whatsapp', 'WhatsApp');
  v_email := fn_pend_texto(d->>'email', 160, 'e-mail');
  if v_email is not null and v_email !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then raise exception 'Informe um e-mail válido.'; end if;
  v_end := fn_pend_texto(d->>'endereco', 300, 'endereco');
  v_obs := fn_pend_texto(d->>'observacoes', 500, 'observacoes');

  if not v_prov then
    select nome into v_outro from clientes where cpf = v_cpf;
    if found then
      return fn_pend_recusa('cpf_ja_cadastrado', 'Já existe o cliente ' || v_outro.nome || ' com este CPF.');
    end if;
  end if;
  select nome, cpf into v_outro from clientes
   where fn_pend_sem_acento(nome) = fn_pend_sem_acento(v_nome) limit 1;
  if found and not coalesce((d->>'confirmar_homonimo')::boolean, false) then
    return fn_pend_recusa('homonimo', 'Já existe um cliente com este nome (CPF final ' || right(v_outro.cpf, 4)
      || '). Se é outra pessoa, confirme com confirmar_homonimo.');
  end if;

  if v_prov then  -- CPF provisório: 0000000000N com dígito verificador inválido e ainda não usado
    loop
      v_cpf := lpad(v_n::text, 11, '0');
      exit when not fn_cpf_valido(v_cpf) and not exists (select 1 from clientes where cpf = v_cpf);
      v_n := v_n + 1;
      if v_n > 100000 then raise exception 'Não foi possível gerar um CPF provisório livre.'; end if;  -- nunca fica em laço
    end loop;
    v_obs := '[CPF PROVISÓRIO]' || coalesce(' ' || v_obs, '');
  end if;

  insert into clientes (nome, cpf, telefone, whatsapp, email, endereco, observacoes)
  values (v_nome, v_cpf, v_tel, v_zap, v_email, v_end, v_obs) returning id into v_cli;
  v_resumo := 'Cliente cadastrado: ' || v_nome || case when v_prov then ' (CPF provisório ' || v_cpf || ')' else ' (CPF final ' || right(v_cpf, 4) || ')' end;
  perform fn_pend_registrar_automatica(v_id, 'cliente', c.o_origem, c.o_chave,
            jsonb_build_object('nome', v_nome, 'cpf_final', right(v_cpf, 4), 'cpf_provisorio', v_prov), v_resumo, c.o_trecho, v_cli, v_cli);
  return jsonb_build_object('gravado', true, 'repetida', false, 'pendencia_id', v_id, 'registro_id', v_cli, 'resumo', v_resumo);
end $$;

-- ---------- Veículo ----------
-- dados: {"placa", "marca", "modelo", "tipo", "km_atual", "ano_fabricacao", "ano_modelo", "cor", "observacoes"}
create or replace function rpc_conector_cadastrar_veiculo(payload jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  c        record;
  d        jsonb := payload->'dados';
  v_placa  text;
  v_marca  text;
  v_modelo text;
  v_tipo   text;
  v_km     int;
  v_af     int;
  v_am     int;
  v_cor    text;
  v_obs    text;
  v_id     uuid := gen_random_uuid();
  v_moto   uuid;
  v_ja     jsonb;
  v_resumo text;
begin
  select * into c from fn_pend_confere_chamada(payload);
  v_ja := fn_pend_ja_gravada(c.o_chave);
  if v_ja is not null then return v_ja; end if;
  if d is null or jsonb_typeof(d) <> 'object' then raise exception 'Os dados do veículo precisam ser um objeto.'; end if;

  v_placa := upper(regexp_replace(coalesce(d->>'placa', ''), '[\s-]', '', 'g'));
  if v_placa !~ '^[A-Z]{3}([0-9]{4}|[0-9][A-Z][0-9]{2})$' then raise exception 'Placa: use ABC1234 ou ABC1D23.'; end if;
  v_marca := fn_pend_texto(d->>'marca', 60, 'marca');
  v_modelo := fn_pend_texto(d->>'modelo', 80, 'modelo');
  if v_marca is null or v_modelo is null then raise exception 'Informe a marca e o modelo do veículo.'; end if;
  v_tipo := fn_pend_sem_acento(coalesce(nullif(btrim(d->>'tipo'), ''), 'moto'));
  if v_tipo not in ('moto', 'carro') then raise exception 'O tipo precisa ser moto ou carro.'; end if;
  begin
    v_km := coalesce(nullif(replace(coalesce(d->>'km_atual', ''), '.', ''), '')::int, 0);
    v_af := nullif(d->>'ano_fabricacao', '')::int;
    v_am := nullif(d->>'ano_modelo', '')::int;
  exception when others then
    raise exception 'Quilometragem e anos precisam ser números inteiros.';
  end;
  if v_km < 0 or v_km > 2000000 then raise exception 'A quilometragem precisa estar entre 0 e 2.000.000.'; end if;
  if v_af is not null and v_af not between 1950 and extract(year from hoje_br())::int + 1
     or v_am is not null and v_am not between 1950 and extract(year from hoje_br())::int + 1 then
    raise exception 'Informe anos entre 1950 e o ano que vem.';
  end if;
  v_cor := left(fn_pend_texto(d->>'cor', 80, 'cor'), 40);
  v_obs := fn_pend_texto(d->>'observacoes', 500, 'observacoes');

  if exists (select 1 from motos where placa = v_placa) then
    return fn_pend_recusa('placa_ja_cadastrada', 'Já existe um veículo com a placa ' || v_placa || '.');
  end if;
  insert into motos (placa, marca, modelo, tipo, km_atual, ano_fabricacao, ano_modelo, cor, observacoes)
  values (v_placa, v_marca, v_modelo, v_tipo, v_km, v_af, v_am, v_cor, v_obs) returning id into v_moto;
  v_resumo := 'Veículo cadastrado: ' || v_placa || ', ' || v_marca || ' ' || v_modelo;
  perform fn_pend_registrar_automatica(v_id, 'veiculo', c.o_origem, c.o_chave,
            jsonb_build_object('placa', v_placa, 'marca', v_marca, 'modelo', v_modelo, 'tipo', v_tipo), v_resumo, c.o_trecho, v_moto,
            null, null, null, v_moto);
  return jsonb_build_object('gravado', true, 'repetida', false, 'pendencia_id', v_id, 'registro_id', v_moto, 'resumo', v_resumo);
end $$;

-- ---------- Desfazer um lançamento automático (só dono, até 7 dias) ----------
create or replace function rpc_pendencia_desfazer(p_id uuid, p_motivo text) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_p      pendencias_lancamento%rowtype;
  v_motivo text := nullif(btrim(coalesce(p_motivo, '')), '');
  v_apagou int;
begin
  perform fn_pend_exige_dono();
  if v_motivo is null then raise exception 'Informe o motivo para desfazer.'; end if;
  if length(v_motivo) > 300 then raise exception 'O motivo passa de 300 caracteres.'; end if;
  select * into v_p from pendencias_lancamento where id = p_id for update;
  if not found then raise exception 'Lançamento não encontrado.'; end if;
  if v_p.status = 'desfeita' then raise exception 'Este lançamento já foi desfeito.'; end if;
  if v_p.status <> 'aprovada' or not v_p.decisao_automatica then
    raise exception 'Só dá para desfazer lançamentos gravados direto pelo chat.';
  end if;
  if v_p.decidido_em < now() - interval '7 days' then
    raise exception 'Passaram mais de 7 dias: corrija pelo app.';
  end if;

  begin
    if v_p.tipo = 'pagamento' then delete from pagamentos where id = v_p.registro_id;
    elsif v_p.tipo = 'despesa' then delete from despesas where id = v_p.registro_id;
    elsif v_p.tipo = 'cliente' then delete from clientes where id = v_p.registro_id;
    else delete from motos where id = v_p.registro_id;
    end if;
    get diagnostics v_apagou = row_count;
  exception when foreign_key_violation then
    raise exception 'Este registro já tem outros dados ligados (contrato, cobrança, manutenção...): corrija pelo app.';
  end;
  if v_apagou = 0 then raise exception 'O registro já não existe: ele foi apagado ou alterado pelo app.'; end if;

  update pendencias_lancamento
     set status = 'desfeita', desfeita_em = now(), desfeita_por = auth.uid(), motivo_desfazer = v_motivo
   where id = p_id;
  return jsonb_build_object('id', p_id, 'status', 'desfeita');
end $$;

-- ---------- Últimos lançamentos do chat (com a decisão automática e o desfazimento) ----------
create or replace function rpc_conector_minhas_pendencias(p_limite int default 10) returns jsonb
language plpgsql stable security definer set search_path = public as $$
declare
  v_limite int := least(greatest(coalesce(p_limite, 10), 1), 50);
begin
  perform fn_pend_exige_servico_ou_dono();
  return coalesce((
    select jsonb_agg(jsonb_build_object('id', id, 'tipo', tipo, 'resumo', resumo, 'status', status, 'motivo_recusa', motivo_recusa,
                                         'decisao_automatica', decisao_automatica, 'desfeita_em', desfeita_em, 'criado_em', criado_em)
                     order by criado_em desc)
      from (select * from pendencias_lancamento where origem in ('chat_financeiro', 'chat_contratos')
             order by criado_em desc limit v_limite) p
  ), '[]'::jsonb);
end $$;

-- ---------- Permissões ----------
revoke all on function fn_cpf_valido(text), fn_pend_telefone(text, text), fn_pend_texto(text, int, text),
  fn_pend_confere_chamada(jsonb), fn_pend_ja_gravada(text), fn_pend_recusa(text, text, jsonb), fn_pend_textos_dos_avisos(jsonb),
  fn_pend_registrar_automatica(uuid, text, text, text, jsonb, text, text, uuid, uuid, uuid, uuid, uuid) from public, anon, authenticated;
revoke all on function rpc_conector_registrar_pagamento(jsonb) from public, anon;
revoke all on function rpc_conector_registrar_despesa(jsonb) from public, anon;
revoke all on function rpc_conector_cadastrar_cliente(jsonb) from public, anon;
revoke all on function rpc_conector_cadastrar_veiculo(jsonb) from public, anon;
revoke all on function rpc_pendencia_desfazer(uuid, text) from public, anon;
revoke all on function rpc_conector_minhas_pendencias(int) from public, anon;
grant execute on function rpc_conector_registrar_pagamento(jsonb) to authenticated;
grant execute on function rpc_conector_registrar_despesa(jsonb) to authenticated;
grant execute on function rpc_conector_cadastrar_cliente(jsonb) to authenticated;
grant execute on function rpc_conector_cadastrar_veiculo(jsonb) to authenticated;
grant execute on function rpc_pendencia_desfazer(uuid, text) to authenticated;
grant execute on function rpc_conector_minhas_pendencias(int) to authenticated;

notify pgrst, 'reload schema';
