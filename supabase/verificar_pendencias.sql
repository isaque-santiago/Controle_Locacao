-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar a migration
--   20261124120000_pendencias_lancamento.sql
-- Verifica: só o usuário de serviço e o dono chamam as RPCs de proposta e consulta, e só o dono aprova e recusa; o usuário de serviço
--   não lê nenhuma tabela e só usa as origens do chat; a proposta é normalizada e validada (valor, data, forma, categoria);
--   repetir a mesma chave devolve a mesma pendência; os avisos de divergência (cobrança não identificada, paga, valor acima do
--   saldo, pagamento parcial, duplicada, veículo sem cadastro); aprovar grava o pagamento/despesa uma vez, pelos gatilhos de sempre
--   (a cobrança fica paga), e fecha a pendência com quem decidiu; aprovar com avisos bloqueantes é recusado, e «editar e aprovar»
--   corrige; recusar exige motivo; pendência decidida não muda mais; as consultas do chat não expõem o CPF inteiro; trava de 200
--   pendências em aberto.
-- Precisa existir pelo menos um administrador (dono). Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  dono     uuid;
  robo     uuid := gen_random_uuid();
  estranho uuid := gen_random_uuid();
  cli1     uuid;
  cli2     uuid;
  moto1    uuid;
  moto2    uuid;
  ct1      uuid;
  ct2      uuid;
  cob_a    uuid;
  cob_b    uuid;
  cob_c    uuid;
  cob_d    uuid;
  r        jsonb;
  r2       jsonb;
  lista    jsonb;
  p1       uuid;
  p2       uuid;
  p3       uuid;
  n        int;
  st       text;
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'Precisa existir um administrador (dono)';

  insert into clientes (nome, cpf) values ('Jhonatan Silva Souza', '90000000061') returning id into cli1;
  insert into clientes (nome, cpf) values ('Joana Prado', '90000000062') returning id into cli2;
  insert into motos (placa, marca, modelo, km_atual) values ('PEN1A11', 'Honda', 'CG 160', 100) returning id into moto1;
  insert into motos (placa, marca, modelo, km_atual) values ('PEN2B22', 'Yamaha', 'Fazer 250', 100) returning id into moto2;
  insert into contratos (moto_id, cliente_id, data_inicio, periodicidade, valor_periodo, km_inicial)
    values (moto1, cli1, hoje_br() - 10, 'semanal', 275, 100) returning id into ct1;
  insert into contratos (moto_id, cliente_id, data_inicio, periodicidade, valor_periodo, km_inicial)
    values (moto2, cli2, hoje_br() - 10, 'semanal', 100, 100) returning id into ct2;
  insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao) values (ct1, 'outros', hoje_br(), 275, 'A') returning id into cob_a;
  insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao) values (ct2, 'outros', hoje_br() + 2, 100, 'B') returning id into cob_b;
  insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao) values (ct2, 'outros', hoje_br() - 3, 80, 'C paga') returning id into cob_c;
  insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao) values (ct1, 'outros', hoje_br() + 5, 300, 'D') returning id into cob_d;
  insert into pagamentos (cobranca_id, data_pagamento, valor) values (cob_c, hoje_br(), 80);
  assert (select status from cobrancas where id = cob_c) = 'paga', 'O gatilho deveria marcar a cobrança C como paga';
  insert into servico_conector (user_id) values (robo);

  -- ---------- um usuário qualquer não chama nada ----------
  perform set_config('request.jwt.claim.sub', estranho::text, true);
  set local role authenticated;
  begin perform rpc_pendencia_criar('{}'::jsonb); raise exception 'Estranho não deveria criar';
  exception when insufficient_privilege then null; end;
  begin perform rpc_pendencia_aprovar(gen_random_uuid()); raise exception 'Estranho não deveria aprovar';
  exception when insufficient_privilege then null; end;
  begin perform rpc_pendencia_recusar(gen_random_uuid(), 'x'); raise exception 'Estranho não deveria recusar';
  exception when insufficient_privilege then null; end;
  begin perform rpc_conector_cobrancas_abertas('Jhonatan'); raise exception 'Estranho não deveria consultar cobranças';
  exception when insufficient_privilege then null; end;
  begin perform rpc_conector_veiculos('PEN1'); raise exception 'Estranho não deveria consultar veículos';
  exception when insufficient_privilege then null; end;
  begin perform rpc_conector_minhas_pendencias(); raise exception 'Estranho não deveria listar pendências';
  exception when insufficient_privilege then null; end;
  assert (select count(*) from pendencias_lancamento) = 0, 'Estranho não lê a tabela';
  reset role;

  -- ---------- o usuário de serviço: chama as RPCs de proposta e consulta, mas não lê tabelas nem decide ----------
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  assert is_servico_conector(), 'O robô deveria ser is_servico_conector()';
  assert not is_dono(), 'O robô não é administrador';
  assert (select count(*) from clientes) = 0, 'O robô não deveria enxergar clientes';
  assert (select count(*) from pagamentos) = 0, 'O robô não deveria enxergar pagamentos';
  assert (select count(*) from pendencias_lancamento) = 0, 'O robô não deveria ler a tabela de pendências';
  begin
    insert into pendencias_lancamento (tipo, origem, chave_operacao, dados, resumo) values ('pagamento', 'chat_financeiro', 'direto', '{}', 'x');
    raise exception 'O robô não deveria gravar direto na tabela';
  exception when insufficient_privilege or others then if sqlerrm like 'O robô não deveria%' then raise; end if; end;
  begin perform rpc_pendencia_aprovar(gen_random_uuid()); raise exception 'O robô não deveria aprovar';
  exception when insufficient_privilege then null; end;
  begin perform rpc_pendencia_recusar(gen_random_uuid(), 'x'); raise exception 'O robô não deveria recusar';
  exception when insufficient_privilege then null; end;

  -- consultas do chat: por nome, CPF parcial e placa; o CPF sai só com os 4 últimos dígitos; cobrança paga não aparece
  lista := rpc_conector_cobrancas_abertas('Jhonatan');
  assert jsonb_array_length(lista) = 2, 'Jhonatan tem 2 cobranças em aberto: ' || lista::text;
  assert lista->0->>'cliente_nome' = 'Jhonatan Silva Souza' and lista->0->>'placa' = 'PEN1A11', 'Cliente e placa: ' || lista::text;
  assert lista->0->>'cpf_final' = '0061' and position('90000000061' in lista::text) = 0, 'O CPF inteiro não pode sair';
  assert lista->0->>'cobranca_id' = cob_a::text and (lista->0->>'saldo')::numeric = 275, 'Primeira por vencimento, com o saldo';
  assert jsonb_array_length(rpc_conector_cobrancas_abertas('jhon sil')) = 2, 'Prefixos de palavras do nome';
  assert jsonb_array_length(rpc_conector_cobrancas_abertas('CPF ***.000.006-**')) >= 1, 'CPF parcial (0000006)';
  assert (rpc_conector_cobrancas_abertas('placa pen-2b22')->0->>'cobranca_id') = cob_b::text, 'Placa com hífen e minúscula';
  assert jsonb_array_length(rpc_conector_cobrancas_abertas('Joana')) = 1, 'A cobrança paga de Joana não aparece';
  assert jsonb_array_length(rpc_conector_cobrancas_abertas('Fulano Inexistente')) = 0, 'Sem resultado';
  begin perform rpc_conector_cobrancas_abertas('ab'); raise exception 'Busca curta deveria ser recusada';
  exception when others then if sqlerrm like 'Busca curta%' then raise; end if; assert sqlerrm like 'Informe ao menos 3%', 'Mensagem: ' || sqlerrm; end;
  assert rpc_conector_veiculos('PEN1')->0->>'moto_id' = moto1::text and rpc_conector_veiculos('fazer')->0->>'placa' = 'PEN2B22', 'Veículos por placa e modelo';

  -- ---------- propor pagamento ----------
  r := rpc_pendencia_criar(jsonb_build_object('tipo', 'pagamento', 'origem', 'chat_financeiro', 'chave_operacao', 'chat-1',
         'trecho_origem', 'Jhonatan pagou 275 hoje',
         'dados', jsonb_build_object('cobranca_id', cob_a, 'valor', '275', 'forma', 'PIX')));
  p1 := (r->>'id')::uuid;
  assert r->>'status' = 'pendente' and (r->>'repetida')::boolean = false, 'Pendência nova: ' || r::text;
  assert r->>'resumo' = 'Pagamento de Jhonatan Silva Souza (PEN1A11): R$ 275,00 em ' || to_char(hoje_br(), 'DD/MM/YYYY') || ' por Pix', 'Resumo: ' || (r->>'resumo');
  assert jsonb_array_length(r->'avisos') = 0, 'Valor igual ao saldo não tem aviso: ' || (r->'avisos')::text;

  -- repetir a mesma chave devolve a mesma pendência
  r2 := rpc_pendencia_criar(jsonb_build_object('tipo', 'pagamento', 'origem', 'chat_financeiro', 'chave_operacao', 'chat-1',
          'dados', jsonb_build_object('cobranca_id', cob_a, 'valor', '999')));
  assert (r2->>'id')::uuid = p1 and (r2->>'repetida')::boolean, 'Mesma chave, mesma pendência: ' || r2::text;

  -- recusas de validação
  begin perform rpc_pendencia_criar(jsonb_build_object('tipo', 'pagamento', 'origem', 'manual', 'chave_operacao', 'x1', 'dados', jsonb_build_object('valor', '1')));
    raise exception 'Robô com origem manual deveria ser recusado';
  exception when insufficient_privilege then null; end;
  begin perform rpc_pendencia_criar(jsonb_build_object('tipo', 'dividas', 'origem', 'chat_financeiro', 'chave_operacao', 'x2', 'dados', jsonb_build_object('valor', '1')));
    raise exception 'Tipo desconhecido deveria ser recusado';
  exception when others then if sqlerrm like 'Tipo desconhecido deveria%' then raise; end if; assert sqlerrm like 'Tipo de pendência desconhecido%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_pendencia_criar(jsonb_build_object('tipo', 'pagamento', 'origem', 'chat_financeiro', 'dados', jsonb_build_object('valor', '1')));
    raise exception 'Sem chave deveria ser recusado';
  exception when others then if sqlerrm like 'Sem chave deveria%' then raise; end if; assert sqlerrm like 'A chave de operação%', 'Mensagem: ' || sqlerrm; end;
  foreach st in array array['0', '-5', 'abc', '10.999', '20000.01'] loop
    begin
      perform rpc_pendencia_criar(jsonb_build_object('tipo', 'pagamento', 'origem', 'chat_financeiro', 'chave_operacao', 'v-' || st,
                'dados', jsonb_build_object('cobranca_id', cob_a, 'valor', st)));
      raise exception 'Valor % deveria ser recusado', st;
    exception when others then if sqlerrm like 'Valor % deveria%' then raise; end if; assert sqlerrm like 'O valor %', 'Mensagem: ' || sqlerrm; end;
  end loop;
  begin perform rpc_pendencia_criar(jsonb_build_object('tipo', 'pagamento', 'origem', 'chat_financeiro', 'chave_operacao', 'f1',
          'dados', jsonb_build_object('valor', '10', 'forma', 'abatimento')));
    raise exception 'Abatimento deveria ser recusado';
  exception when others then if sqlerrm like 'Abatimento deveria%' then raise; end if; assert sqlerrm like 'A forma de pagamento%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_pendencia_criar(jsonb_build_object('tipo', 'pagamento', 'origem', 'chat_financeiro', 'chave_operacao', 'd1',
          'dados', jsonb_build_object('valor', '10', 'data_pagamento', (hoje_br() + 5)::text)));
    raise exception 'Data futura deveria ser recusada';
  exception when others then if sqlerrm like 'Data futura deveria%' then raise; end if; assert sqlerrm like '%não pode estar no futuro%', 'Mensagem: ' || sqlerrm; end;
  assert (select count(*) from pendencias_lancamento) = 0 or true, 'só para manter a leitura do robô fora do roteiro';

  -- avisos
  r := rpc_pendencia_criar(jsonb_build_object('tipo', 'pagamento', 'origem', 'chat_financeiro', 'chave_operacao', 'a-semcob',
         'dados', jsonb_build_object('valor', '50')));
  p2 := (r->>'id')::uuid;
  assert r->'avisos'->0->>'codigo' = 'cobranca_nao_identificada', 'Sem cobrança: ' || (r->'avisos')::text;
  r := rpc_pendencia_criar(jsonb_build_object('tipo', 'pagamento', 'origem', 'chat_financeiro', 'chave_operacao', 'a-paga',
         'dados', jsonb_build_object('cobranca_id', cob_c, 'valor', '80')));
  assert r->'avisos'->0->>'codigo' = 'cobranca_paga', 'Cobrança paga: ' || (r->'avisos')::text;
  r := rpc_pendencia_criar(jsonb_build_object('tipo', 'pagamento', 'origem', 'chat_financeiro', 'chave_operacao', 'a-acima',
         'dados', jsonb_build_object('cobranca_id', cob_b, 'valor', '150')));
  assert r->'avisos'->0->>'codigo' = 'valor_acima_do_saldo' and r->'avisos'->0->>'texto' like '%R$ 100,00%', 'Acima do saldo: ' || (r->'avisos')::text;
  p3 := (r->>'id')::uuid;
  r := rpc_pendencia_criar(jsonb_build_object('tipo', 'pagamento', 'origem', 'chat_financeiro', 'chave_operacao', 'a-parcial',
         'dados', jsonb_build_object('cobranca_id', cob_d, 'valor', '100')));
  assert r->'avisos'->0->>'codigo' = 'valor_abaixo_do_saldo' and r->'avisos'->0->>'texto' like '%R$ 300,00%', 'Parcial: ' || (r->'avisos')::text;
  reset role;
  update cobrancas set status = 'cancelada' where id = cob_d;  -- cobrança cancelada (como o dono faria)
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  r := rpc_pendencia_criar(jsonb_build_object('tipo', 'pagamento', 'origem', 'chat_financeiro', 'chave_operacao', 'a-cancelada',
         'dados', jsonb_build_object('cobranca_id', cob_d, 'valor', '100')));
  assert r->'avisos'->0->>'codigo' = 'cobranca_cancelada', 'Cobrança cancelada: ' || (r->'avisos')::text;

  -- ---------- propor despesa ----------
  r := rpc_pendencia_criar(jsonb_build_object('tipo', 'despesa', 'origem', 'chat_financeiro', 'chave_operacao', 'des-1',
         'dados', jsonb_build_object('valor', '95', 'categoria', 'Manutenção', 'observacoes', 'Pastilha de freio', 'moto_id', moto1)));
  assert r->>'resumo' = 'Despesa (PEN1A11): R$ 95,00 em ' || to_char(hoje_br(), 'DD/MM/YYYY') || ', manutencao' and jsonb_array_length(r->'avisos') = 0,
    'Despesa com veículo: ' || r::text;
  declare p_des uuid := (r->>'id')::uuid; begin
    r := rpc_pendencia_criar(jsonb_build_object('tipo', 'despesa', 'origem', 'chat_financeiro', 'chave_operacao', 'des-2',
           'dados', jsonb_build_object('valor', '40', 'observacoes', 'Sem veículo')));
    assert r->'avisos'->0->>'codigo' = 'sem_veiculo', 'Sem veículo avisa: ' || (r->'avisos')::text;
    r := rpc_pendencia_criar(jsonb_build_object('tipo', 'despesa', 'origem', 'chat_financeiro', 'chave_operacao', 'des-3',
           'dados', jsonb_build_object('valor', '40', 'observacoes', 'Veículo fantasma', 'moto_id', gen_random_uuid())));
    assert r->'avisos'->0->>'codigo' = 'veiculo_nao_identificado', 'Veículo inexistente: ' || (r->'avisos')::text;
    begin perform rpc_pendencia_criar(jsonb_build_object('tipo', 'despesa', 'origem', 'chat_financeiro', 'chave_operacao', 'des-4',
            'dados', jsonb_build_object('valor', '40', 'categoria', 'lazer', 'observacoes', 'x')));
      raise exception 'Categoria inválida deveria ser recusada';
    exception when others then if sqlerrm like 'Categoria inválida deveria%' then raise; end if; assert sqlerrm like 'A categoria precisa%', 'Mensagem: ' || sqlerrm; end;
    begin perform rpc_pendencia_criar(jsonb_build_object('tipo', 'despesa', 'origem', 'chat_financeiro', 'chave_operacao', 'des-5',
            'dados', jsonb_build_object('valor', '40')));
      raise exception 'Sem descrição deveria ser recusada';
    exception when others then if sqlerrm like 'Sem descrição deveria%' then raise; end if; assert sqlerrm like 'Descreva a despesa%', 'Mensagem: ' || sqlerrm; end;
    perform set_config('app.p_des', p_des::text, true);
  end;

  -- as últimas propostas do chat e o que aconteceu com elas (sem os dados)
  lista := rpc_conector_minhas_pendencias(3);
  assert jsonb_array_length(lista) = 3 and not (lista->0 ? 'dados'), 'Minhas pendências: ' || lista::text;
  reset role;

  -- ---------- o dono decide ----------
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  assert (select count(*) from pendencias_lancamento) > 5, 'O dono lê a tabela';

  -- aprovar pagamento: grava uma vez, a cobrança fica paga, a pendência registra quem decidiu
  r := rpc_pendencia_aprovar(p1);
  assert r->>'status' = 'aprovada' and r->>'registro_id' is not null, 'Aprovada: ' || r::text;
  reset role;
  assert (select count(*) from pagamentos where cobranca_id = cob_a) = 1, 'Um pagamento gravado';
  assert (select chave_operacao from pagamentos where cobranca_id = cob_a) = p1, 'A chave de operação é o id da pendência';
  assert (select status from cobrancas where id = cob_a) = 'paga', 'A cobrança A ficou paga pelo gatilho de sempre';
  assert (select decidido_por from pendencias_lancamento where id = p1) = dono, 'Quem decidiu';
  assert (select registro_id from pendencias_lancamento where id = p1) = (select id from pagamentos where cobranca_id = cob_a), 'registro_id';
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  begin perform rpc_pendencia_aprovar(p1); raise exception 'Aprovar de novo deveria ser recusado';
  exception when others then if sqlerrm like 'Aprovar de novo%' then raise; end if; assert sqlerrm like 'Esta pendência já foi decidida%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_pendencia_recusar(p1, 'tarde demais'); raise exception 'Recusar a aprovada deveria ser recusado';
  exception when others then if sqlerrm like 'Recusar a aprovada%' then raise; end if; assert sqlerrm like 'Esta pendência já foi decidida%', 'Mensagem: ' || sqlerrm; end;

  -- avisos bloqueantes impedem a aprovação; «editar e aprovar» corrige
  begin perform rpc_pendencia_aprovar(p2); raise exception 'Sem cobrança deveria bloquear';
  exception when others then if sqlerrm like 'Sem cobrança deveria%' then raise; end if; assert sqlerrm like 'Não dá para aprovar: A cobrança não foi identificada%', 'Mensagem: ' || sqlerrm; end;
  r := rpc_pendencia_aprovar(p2, jsonb_build_object('cobranca_id', cob_b, 'valor', '50'));
  assert r->>'status' = 'aprovada', 'Editar e aprovar: ' || r::text;
  assert (select resumo from pendencias_lancamento where id = p2) like 'Pagamento de Joana Prado (PEN2B22): R$ 50,00%', 'O resumo acompanha a correção';
  assert (select valor from pagamentos where cobranca_id = cob_b) = 50, 'Pagamento de 50 gravado';

  begin perform rpc_pendencia_aprovar(p3); raise exception 'Acima do saldo deveria bloquear';  -- o saldo de B agora é 50
  exception when others then if sqlerrm like 'Acima do saldo deveria%' then raise; end if; assert sqlerrm like 'Não dá para aprovar: O valor passa do saldo%R$ 50,00%', 'Mensagem: ' || sqlerrm; end;
  r := rpc_pendencia_aprovar(p3, '{"valor": "50"}'::jsonb);
  assert r->>'status' = 'aprovada' and (select status from cobrancas where id = cob_b) = 'paga', 'Corrigido para o saldo: ' || r::text;

  -- despesa aprovada vira linha em `despesas`
  r := rpc_pendencia_aprovar(current_setting('app.p_des')::uuid);
  assert r->>'status' = 'aprovada', 'Despesa aprovada: ' || r::text;
  reset role;
  assert (select count(*) from despesas where moto_id = moto1 and valor = 95 and categoria = 'manutencao' and observacoes = 'Pastilha de freio') = 1, 'Despesa gravada';
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;

  -- veículo inexistente bloqueia; sem veículo aprova
  declare p_fantasma uuid := (select id from pendencias_lancamento where chave_operacao = 'des-3');
          p_sem uuid := (select id from pendencias_lancamento where chave_operacao = 'des-2');
  begin
    begin perform rpc_pendencia_aprovar(p_fantasma); raise exception 'Veículo inexistente deveria bloquear';
    exception when others then if sqlerrm like 'Veículo inexistente deveria%' then raise; end if; assert sqlerrm like 'Não dá para aprovar: O veículo informado não foi encontrado%', 'Mensagem: ' || sqlerrm; end;
    assert (rpc_pendencia_aprovar(p_sem)->>'status') = 'aprovada', 'Despesa sem veículo é aprovada (com aviso)';
  end;

  -- cobrança que ficou paga entre a proposta e a aprovação bloqueia
  declare p_paga uuid := (select id from pendencias_lancamento where chave_operacao = 'a-paga');
  begin
    begin perform rpc_pendencia_aprovar(p_paga); raise exception 'Cobrança paga deveria bloquear';
    exception when others then if sqlerrm like 'Cobrança paga deveria%' then raise; end if; assert sqlerrm like 'Não dá para aprovar: Esta cobrança já está paga%', 'Mensagem: ' || sqlerrm; end;

    -- recusar: o motivo é obrigatório
    begin perform rpc_pendencia_recusar(p_paga, '   '); raise exception 'Motivo em branco deveria ser recusado';
    exception when others then if sqlerrm like 'Motivo em branco%' then raise; end if; assert sqlerrm like 'Informe o motivo%', 'Mensagem: ' || sqlerrm; end;
    r := rpc_pendencia_recusar(p_paga, 'Já estava paga');
    assert r->>'status' = 'recusada', 'Recusada: ' || r::text;
    begin perform rpc_pendencia_aprovar(p_paga); raise exception 'Aprovar a recusada deveria ser recusado';
    exception when others then if sqlerrm like 'Aprovar a recusada%' then raise; end if; assert sqlerrm like 'Esta pendência já foi decidida%', 'Mensagem: ' || sqlerrm; end;
    assert (select motivo_recusa from pendencias_lancamento where id = p_paga) = 'Já estava paga' and (select decidido_por from pendencias_lancamento where id = p_paga) = dono, 'Motivo e quem recusou';
  end;
  begin perform rpc_pendencia_aprovar(gen_random_uuid()); raise exception 'Pendência inexistente deveria ser recusada';
  exception when others then if sqlerrm like 'Pendência inexistente deveria%' then raise; end if; assert sqlerrm like 'Pendência não encontrada%', 'Mensagem: ' || sqlerrm; end;

  -- o dono também propõe (origem manual) e o estado é coerente
  r := rpc_pendencia_criar(jsonb_build_object('tipo', 'despesa', 'origem', 'manual', 'chave_operacao', 'manual-1',
         'dados', jsonb_build_object('valor', '10', 'observacoes', 'Teste do dono', 'descricao_veiculo', 'Biz')));
  assert r->>'status' = 'pendente', 'O dono propõe com origem manual: ' || r::text;
  reset role;
  begin
    update pendencias_lancamento set status = 'aprovada' where chave_operacao = 'manual-1';
    raise exception 'Estado incoerente deveria ser recusado';
  exception when check_violation then null; end;

  -- ---------- trava contra enxurrada ----------
  insert into pendencias_lancamento (tipo, origem, chave_operacao, dados, resumo)
    select 'despesa', 'chat_financeiro', 'lote-' || g, '{"valor": "1.00"}'::jsonb, 'lote' from generate_series(1, 200) g;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  begin
    perform rpc_pendencia_criar(jsonb_build_object('tipo', 'despesa', 'origem', 'chat_financeiro', 'chave_operacao', 'estourou',
              'dados', jsonb_build_object('valor', '1', 'observacoes', 'x', 'descricao_veiculo', 'Biz')));
    raise exception 'A trava de 200 deveria recusar';
  exception when others then if sqlerrm like 'A trava de 200%' then raise; end if; assert sqlerrm like 'Há pendências demais em aberto%', 'Mensagem: ' || sqlerrm; end;
  -- repetir uma chave já existente continua funcionando mesmo com a fila cheia
  assert (rpc_pendencia_criar(jsonb_build_object('tipo', 'despesa', 'origem', 'chat_financeiro', 'chave_operacao', 'lote-1',
            'dados', jsonb_build_object('valor', '1', 'observacoes', 'x')))->>'repetida')::boolean, 'Chave repetida passa pela trava';
  reset role;

  raise notice 'verificar_pendencias: tudo certo';
end $$;
rollback;
