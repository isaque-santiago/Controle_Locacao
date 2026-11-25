-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar as migrations
--   20261124120000_pendencias_lancamento.sql, 20261125120000_historico_chats.sql  e  20261125130000_historico_v2.sql
-- Verifica: só o usuário de serviço e o dono entregam e consultam o histórico, e só o dono descarta; o usuário de serviço não lê
--   as tabelas nem grava direto; o lote é validado (fonte, período, tipo, data dentro do período, dados, trecho, até 50 registros);
--   cada registro é comparado com o sistema (pagamento, despesa, multa, cliente, veículo e contrato: já existe, nova ou diverge;
--   dívida e registro sem data: sem comparação); multa com valor atualizado ou com 20% de desconto não diverge; `data_estimada` abre uma janela
--   de datas; `finalidade` casa com o tipo da cobrança; a lista «a conferir» tem total, páginas e filtro por tipo; um registro «igual» com outro
--   trecho é avisado; a conferência completa é só do dono; reenviar o mesmo lote não duplica; o resumo traz contagens e períodos; a lista
--   «a conferir» traz só novas e divergentes, sem trecho nem CPF inteiro; descartar apaga o lote e os registros, menos os já aplicados.
-- Precisa existir pelo menos um administrador (dono). Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
-- Usa nomes de teste próprios (Zeferino/Zacarias Testehist, HIS1A11, HIS9Z99) para dados reais não interferirem nas comparações.
-- Rode só no DESENVOLVIMENTO: ele cria dados de teste e, se algum assert falhar, a transação é abortada.
begin;
do $$
declare
  dono     uuid;
  robo     uuid := gen_random_uuid();
  estranho uuid := gen_random_uuid();
  cli1     uuid;
  moto1    uuid;
  ct1      uuid;
  cob_a    uuid;
  p1       date := hoje_br() - 10;
  d0       date := hoje_br() - 30;
  r        jsonb;
  r2       jsonb;
  lista    jsonb;
  lote_f   uuid;
  lote_c   uuid;
  lote     jsonb;
  n        int;
  regs     jsonb;
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'Precisa existir um administrador (dono)';
  assert not exists (select 1 from clientes where cpf in ('90000000091', '11144477735', '22233344405')), 'CPF de teste já existe neste banco';
  assert not exists (select 1 from motos where placa in ('HIS1A11', 'HIS9Z99')), 'Placa de teste já existe neste banco';

  insert into clientes (nome, cpf) values ('Zeferino Testehist Silva', '90000000091') returning id into cli1;
  insert into motos (placa, marca, modelo, km_atual) values ('HIS1A11', 'Honda', 'Testehist 160', 100) returning id into moto1;
  insert into contratos (moto_id, cliente_id, data_inicio, periodicidade, valor_periodo, km_inicial)
    values (moto1, cli1, d0, 'semanal', 275, 100) returning id into ct1;
  insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao) values (ct1, 'outros', p1, 275, 'A') returning id into cob_a;
  insert into pagamentos (cobranca_id, data_pagamento, valor) values (cob_a, p1, 275);
  insert into despesas (data, moto_id, categoria, valor, observacoes) values (hoje_br() - 12, moto1, 'manutencao', 95, 'Pastilha');
  insert into multas_transito (moto_id, data_infracao, ait, valor) values (moto1, hoje_br() - 20, 'HIS-001', 130.16);
  insert into servico_conector (user_id) values (robo);

  -- ---------- quem não é dono nem robô não chama nada ----------
  perform set_config('request.jwt.claim.sub', estranho::text, true);
  set local role authenticated;
  begin perform rpc_conector_entregar_lote_historico('{}'::jsonb); raise exception 'Estranho não deveria entregar';
  exception when insufficient_privilege then null; end;
  begin perform rpc_conector_resumo_historico(); raise exception 'Estranho não deveria ver o resumo';
  exception when insufficient_privilege then null; end;
  begin perform rpc_conector_historico_a_conferir(); raise exception 'Estranho não deveria listar';
  exception when insufficient_privilege then null; end;
  begin perform rpc_historico_descartar_lote(gen_random_uuid()); raise exception 'Estranho não deveria descartar';
  exception when insufficient_privilege then null; end;
  reset role;

  -- ---------- o robô: entrega e consulta, mas não lê tabelas, não grava direto e não descarta ----------
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  assert (select count(*) from historico_chat_lotes) = 0 and (select count(*) from historico_chat_registros) = 0, 'O robô não lê as tabelas';
  begin
    insert into historico_chat_lotes (fonte, rotulo, periodo_inicio, periodo_fim) values ('chat_financeiro', 'direto', hoje_br(), hoje_br());
    raise exception 'O robô não deveria gravar direto';
  exception when insufficient_privilege or others then if sqlerrm like 'O robô não deveria%' then raise; end if; end;
  begin perform rpc_historico_descartar_lote(gen_random_uuid()); raise exception 'O robô não deveria descartar';
  exception when insufficient_privilege then null; end;

  -- ---------- lote do chat financeiro: cada registro é comparado ----------
  r := rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_financeiro', 'rotulo', 'fin-teste-1',
    'periodo_inicio', (hoje_br() - 40)::text, 'periodo_fim', (hoje_br() - 1)::text, 'observacao', 'primeiro lote',
    'registros', jsonb_build_array(
      jsonb_build_object('tipo', 'pagamento', 'data', p1::text, 'trecho', 't1', 'resumo', 'Pagamento igual',
        'dados', jsonb_build_object('cliente', 'Zeferino Testehist', 'placa', 'HIS1A11', 'valor', '275.00')),
      jsonb_build_object('tipo', 'pagamento', 'data', p1::text, 'trecho', 't2', 'resumo', 'Pagamento de valor diferente',
        'dados', jsonb_build_object('cliente', 'Zeferino Testehist', 'valor', '300.00')),
      jsonb_build_object('tipo', 'pagamento', 'data', (hoje_br() - 3)::text, 'trecho', 't3', 'resumo', 'Pagamento novo',
        'dados', jsonb_build_object('placa', 'HIS1A11', 'valor', '275.00')),
      jsonb_build_object('tipo', 'despesa', 'data', (hoje_br() - 12)::text, 'trecho', 't4', 'resumo', 'Despesa igual',
        'dados', jsonb_build_object('placa', 'HIS1A11', 'valor', '95.00')),
      jsonb_build_object('tipo', 'despesa', 'data', (hoje_br() - 12)::text, 'trecho', 't5', 'resumo', 'Despesa de valor diferente',
        'dados', jsonb_build_object('placa', 'HIS1A11', 'valor', '100.00')),
      jsonb_build_object('tipo', 'despesa', 'data', (hoje_br() - 5)::text, 'trecho', 't6', 'resumo', 'Despesa nova',
        'dados', jsonb_build_object('placa', 'HIS1A11', 'valor', '50.00')),
      jsonb_build_object('tipo', 'multa', 'data', (hoje_br() - 20)::text, 'trecho', 't7', 'resumo', 'Multa igual',
        'dados', jsonb_build_object('placa', 'HIS1A11', 'ait', 'HIS-001', 'valor', '130.16')),
      jsonb_build_object('tipo', 'multa', 'data', (hoje_br() - 20)::text, 'trecho', 't8', 'resumo', 'Multa de valor diferente',
        'dados', jsonb_build_object('placa', 'HIS1A11', 'ait', 'HIS-001', 'valor', '140.00')),
      jsonb_build_object('tipo', 'divida', 'data', (hoje_br() - 7)::text, 'trecho', 't9', 'resumo', 'Dívida sem comparação',
        'dados', jsonb_build_object('credor', 'Lima', 'saldo', '1000.00')),
      jsonb_build_object('tipo', 'pagamento', 'trecho', 't10', 'resumo', 'Pagamento sem data',
        'dados', jsonb_build_object('cliente', 'Zeferino Testehist', 'valor', '275.00')))));
  lote_f := (r->>'lote_id')::uuid;
  assert (r->>'recebidos')::int = 10 and (r->>'inseridos')::int = 10 and (r->>'repetidos')::int = 0, 'Contagens: ' || r::text;
  assert r->'situacoes' = '{"nova": 2, "diverge": 3, "ja_existe": 3, "sem_comparacao": 2}'::jsonb, 'Situações: ' || (r->'situacoes')::text;

  -- reenviar o mesmo lote não duplica
  r2 := rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_financeiro', 'rotulo', 'fin-teste-1',
    'periodo_inicio', (hoje_br() - 40)::text, 'periodo_fim', (hoje_br() - 1)::text,
    'registros', jsonb_build_array(jsonb_build_object('tipo', 'pagamento', 'data', p1::text, 'trecho', 'outro trecho', 'resumo', 'Pagamento igual',
      'dados', jsonb_build_object('cliente', 'Zeferino Testehist', 'placa', 'HIS1A11', 'valor', '275.00')))));
  assert (r2->>'lote_id')::uuid = lote_f and (r2->>'inseridos')::int = 0 and (r2->>'repetidos')::int = 1, 'Repetido: ' || r2::text;
  -- o mesmo registro em outro lote também é repetido
  r2 := rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_financeiro', 'rotulo', 'fin-teste-2',
    'periodo_inicio', (hoje_br() - 40)::text, 'periodo_fim', (hoje_br() - 1)::text,
    'registros', jsonb_build_array(jsonb_build_object('tipo', 'despesa', 'data', (hoje_br() - 5)::text, 'trecho', 'x', 'resumo', 'Despesa nova',
      'dados', jsonb_build_object('placa', 'HIS1A11', 'valor', '50.00')))));
  assert (r2->>'inseridos')::int = 0 and (r2->>'repetidos')::int = 1 and (r2->>'lote_id')::uuid <> lote_f, 'Repetido em outro lote: ' || r2::text;

  -- ---------- lote do chat de contratos ----------
  r := rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_contratos', 'rotulo', 'con-teste-1',
    'periodo_inicio', (hoje_br() - 60)::text, 'periodo_fim', hoje_br()::text,
    'registros', jsonb_build_array(
      jsonb_build_object('tipo', 'cliente', 'trecho', 'c1', 'resumo', 'Cliente igual', 'dados', jsonb_build_object('nome', 'Zeferino Testehist Silva', 'cpf', '90000000091')),
      jsonb_build_object('tipo', 'cliente', 'trecho', 'c2', 'resumo', 'CPF em outro nome', 'dados', jsonb_build_object('nome', 'Outro Nome Totalmente', 'cpf', '90000000091')),
      jsonb_build_object('tipo', 'cliente', 'trecho', 'c3', 'resumo', 'Nome igual, outro CPF', 'dados', jsonb_build_object('nome', 'Zeferino Testehist Silva', 'cpf', '22233344405')),
      jsonb_build_object('tipo', 'cliente', 'trecho', 'c4', 'resumo', 'Cliente novo', 'dados', jsonb_build_object('nome', 'Zacarias Testehist Lima', 'cpf', '11144477735')),
      jsonb_build_object('tipo', 'veiculo', 'trecho', 'v1', 'resumo', 'Veículo igual', 'dados', jsonb_build_object('placa', 'HIS1A11', 'marca', 'Honda')),
      jsonb_build_object('tipo', 'veiculo', 'trecho', 'v2', 'resumo', 'Veículo de outra marca', 'dados', jsonb_build_object('placa', 'HIS1A11', 'marca', 'Yamaha')),
      jsonb_build_object('tipo', 'veiculo', 'trecho', 'v3', 'resumo', 'Veículo novo', 'dados', jsonb_build_object('placa', 'HIS9Z99', 'marca', 'Fiat')),
      jsonb_build_object('tipo', 'contrato', 'data', d0::text, 'trecho', 'k1', 'resumo', 'Contrato igual',
        'dados', jsonb_build_object('placa', 'HIS1A11', 'cliente', 'Zeferino Testehist', 'valor_periodo', '275.00')),
      jsonb_build_object('tipo', 'contrato', 'data', d0::text, 'trecho', 'k2', 'resumo', 'Contrato de outro valor',
        'dados', jsonb_build_object('placa', 'HIS1A11', 'cpf', '90000000091', 'valor_periodo', '300.00')),
      jsonb_build_object('tipo', 'contrato', 'data', d0::text, 'trecho', 'k3', 'resumo', 'Contrato novo',
        'dados', jsonb_build_object('placa', 'HIS9Z99', 'cliente', 'Zacarias Testehist', 'valor_periodo', '275.00')))));
  lote_c := (r->>'lote_id')::uuid;
  assert r->'situacoes' = '{"nova": 3, "diverge": 4, "ja_existe": 3}'::jsonb, 'Situações do chat de contratos: ' || (r->'situacoes')::text;

  -- ---------- validações do lote ----------
  begin perform rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'outra', 'rotulo', 'x', 'periodo_inicio', '2026-01-01', 'periodo_fim', '2026-01-31',
          'registros', jsonb_build_array(jsonb_build_object('tipo', 'outro', 'trecho', 't', 'resumo', 'r', 'dados', jsonb_build_object('a', 1)))));
    raise exception 'Fonte inválida deveria ser recusada';
  exception when others then if sqlerrm like 'Fonte inválida deveria%' then raise; end if; assert sqlerrm like 'A fonte precisa ser%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_financeiro', 'rotulo', 'v1', 'periodo_inicio', '2026-02-01', 'periodo_fim', '2026-01-01',
          'registros', jsonb_build_array(jsonb_build_object('tipo', 'outro', 'trecho', 't', 'resumo', 'r', 'dados', jsonb_build_object('a', 1)))));
    raise exception 'Período invertido deveria ser recusado';
  exception when others then if sqlerrm like 'Período invertido deveria%' then raise; end if; assert sqlerrm like 'Informe o período do lote%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_financeiro', 'rotulo', 'v2', 'periodo_inicio', '2020-01-01', 'periodo_fim', '2026-01-01',
          'registros', jsonb_build_array(jsonb_build_object('tipo', 'outro', 'trecho', 't', 'resumo', 'r', 'dados', jsonb_build_object('a', 1)))));
    raise exception 'Período longo deveria ser recusado';
  exception when others then if sqlerrm like 'Período longo deveria%' then raise; end if; assert sqlerrm like 'O período passa de 1100 dias%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_financeiro', 'rotulo', 'v3', 'periodo_inicio', '2026-01-01', 'periodo_fim', '2026-01-31', 'registros', '[]'::jsonb));
    raise exception 'Sem registros deveria ser recusado';
  exception when others then if sqlerrm like 'Sem registros deveria%' then raise; end if; assert sqlerrm like 'Envie ao menos um registro%', 'Mensagem: ' || sqlerrm; end;
  select jsonb_agg(jsonb_build_object('tipo', 'outro', 'trecho', 't' || g, 'resumo', 'r', 'dados', jsonb_build_object('a', g))) into regs from generate_series(1, 51) g;
  begin perform rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_financeiro', 'rotulo', 'v4', 'periodo_inicio', '2026-01-01', 'periodo_fim', '2026-01-31', 'registros', regs));
    raise exception '51 registros deveriam ser recusados';
  exception when others then if sqlerrm like '51 registros%' then raise; end if; assert sqlerrm like 'Envie no máximo 50%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_financeiro', 'rotulo', 'v5', 'periodo_inicio', '2026-01-01', 'periodo_fim', '2026-01-31',
          'registros', jsonb_build_array(jsonb_build_object('tipo', 'lazer', 'trecho', 't', 'resumo', 'r', 'dados', jsonb_build_object('a', 1)))));
    raise exception 'Tipo desconhecido deveria ser recusado';
  exception when others then if sqlerrm like 'Tipo desconhecido deveria%' then raise; end if; assert sqlerrm like 'Registro 1: tipo desconhecido%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_financeiro', 'rotulo', 'v6', 'periodo_inicio', '2026-01-01', 'periodo_fim', '2026-01-31',
          'registros', jsonb_build_array(jsonb_build_object('tipo', 'outro', 'data', '2026-03-01', 'trecho', 't', 'resumo', 'r', 'dados', jsonb_build_object('a', 1)))));
    raise exception 'Data fora do período deveria ser recusada';
  exception when others then if sqlerrm like 'Data fora%' then raise; end if; assert sqlerrm like 'Registro 1: a data está fora do período%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_financeiro', 'rotulo', 'v7', 'periodo_inicio', '2026-01-01', 'periodo_fim', '2026-01-31',
          'registros', jsonb_build_array(jsonb_build_object('tipo', 'outro', 'trecho', '', 'resumo', 'r', 'dados', jsonb_build_object('a', 1)))));
    raise exception 'Sem trecho deveria ser recusado';
  exception when others then if sqlerrm like 'Sem trecho deveria%' then raise; end if; assert sqlerrm like 'Registro 1: falta o trecho%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_financeiro', 'rotulo', 'v8', 'periodo_inicio', '2026-01-01', 'periodo_fim', '2026-01-31',
          'registros', jsonb_build_array(jsonb_build_object('tipo', 'outro', 'trecho', 't', 'resumo', 'r', 'dados', '{}'::jsonb))));
    raise exception 'Dados vazios deveriam ser recusados';
  exception when others then if sqlerrm like 'Dados vazios deveriam%' then raise; end if; assert sqlerrm like 'Registro 1: os dados precisam%', 'Mensagem: ' || sqlerrm; end;
  reset role;
  assert not exists (select 1 from historico_chat_lotes where rotulo in ('x', 'v1', 'v2', 'v3', 'v4', 'v5', 'v6', 'v7', 'v8')), 'Lote recusado não deixa rastro';

  -- ---------- o que ficou gravado ----------
  assert (select registros_recebidos = 11 and registros_novos = 10 from historico_chat_lotes where id = lote_f), 'Contagens do lote financeiro';
  assert (select count(*) from historico_chat_registros where lote_id = lote_f) = 10, 'Dez registros no lote financeiro';
  assert (select situacao = 'diverge' and detalhe like 'No sistema, nesse dia, há pagamento de R$ 275,00.%' from historico_chat_registros where lote_id = lote_f and trecho = 't2'), 'Detalhe do pagamento divergente';
  assert (select detalhe like 'No sistema a multa tem valor R$ 130,16.%' from historico_chat_registros where lote_id = lote_f and trecho = 't8'), 'Detalhe da multa divergente';
  assert (select detalhe like 'No sistema este CPF está no nome de Zeferino Testehist Silva.%' from historico_chat_registros where lote_id = lote_c and trecho = 'c2'), 'CPF em outro nome';
  assert (select detalhe = 'Já existe cliente com este nome e CPF final 0091.' from historico_chat_registros where lote_id = lote_c and trecho = 'c3'), 'Nome igual com outro CPF';
  assert (select detalhe like 'No sistema é Honda Testehist 160.%' from historico_chat_registros where lote_id = lote_c and trecho = 'v2'), 'Veículo de outra marca';
  assert (select detalhe like 'No sistema: início em %, R$ 275,00 por período.%' from historico_chat_registros where lote_id = lote_c and trecho = 'k2'), 'Contrato de outro valor';
  assert (select situacao = 'sem_comparacao' from historico_chat_registros where trecho = 't10'), 'Pagamento sem data não é comparado';

  -- ---------- resumo e a conferir (pelo robô) ----------
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  r := rpc_conector_resumo_historico();
  assert jsonb_array_length(r->'lotes') = 3, 'Três lotes: ' || (r->'lotes')::text;  -- fin-teste-1, fin-teste-2 (vazio) e con-teste-1
  assert (select count(*) from jsonb_array_elements(r->'contagens') c where c->>'fonte' = 'chat_financeiro' and c->>'tipo' = 'pagamento' and c->>'situacao' = 'ja_existe'
            and (c->>'qtd')::int = 1) = 1, 'Contagem por tipo e situação: ' || (r->'contagens')::text;
  assert jsonb_array_length(rpc_conector_resumo_historico('chat_contratos')->'lotes') = 1, 'Filtro por fonte';
  begin perform rpc_conector_resumo_historico('outra'); raise exception 'Fonte inválida no resumo deveria ser recusada';
  exception when others then if sqlerrm like 'Fonte inválida no resumo%' then raise; end if; assert sqlerrm like 'A fonte precisa ser%', 'Mensagem: ' || sqlerrm; end;

  r := rpc_conector_historico_a_conferir('chat_contratos');
  lista := r->'linhas';
  assert (r->>'total')::int = 7 and (r->>'pagina')::int = 1 and jsonb_array_length(lista) = 7 and not exists (select 1 from jsonb_array_elements(lista) e where e->>'situacao' not in ('nova', 'diverge')), 'A conferir: só novas e divergentes: ' || lista::text;
  assert not (lista->0 ? 'trecho') and not (lista->0 ? 'dados') and position('90000000091' in lista::text) = 0 and position('11144477735' in lista::text) = 0,
    'A lista não traz trecho, dados nem CPF inteiro';
  assert jsonb_array_length(rpc_conector_historico_a_conferir('chat_financeiro', 'ja_existe')->'linhas') = 3, 'Filtro por situação';
  assert jsonb_array_length(rpc_conector_historico_a_conferir(null, null, 2)->'linhas') = 2, 'Limite';
  -- paginação: 7 registros do chat de contratos, de 3 em 3
  r := rpc_conector_historico_a_conferir('chat_contratos', null, 3, 3);
  assert (r->>'total')::int = 7 and (r->>'pagina')::int = 3 and jsonb_array_length(r->'linhas') = 1, 'Terceira página: ' || r::text;
  assert (rpc_conector_historico_a_conferir('chat_contratos', null, 3, 2)->'linhas'->0->>'id') <> (rpc_conector_historico_a_conferir('chat_contratos', null, 3, 1)->'linhas'->0->>'id'), 'Páginas diferentes';
  assert jsonb_array_length(rpc_conector_historico_a_conferir('chat_contratos', null, 30, 4)->'linhas') = 0, 'Página além do fim vem vazia';
  -- filtro por tipo
  r := rpc_conector_historico_a_conferir('chat_contratos', null, 30, 1, 'contrato');
  assert (r->>'total')::int = 2 and not exists (select 1 from jsonb_array_elements(r->'linhas') e where e->>'tipo' <> 'contrato'), 'Filtro por tipo: ' || r::text;
  begin perform rpc_conector_historico_a_conferir(null, null, 30, 1, 'lazer'); raise exception 'Tipo inválido deveria ser recusado';
  exception when others then if sqlerrm like 'Tipo inválido deveria%' then raise; end if; assert sqlerrm like 'Tipo desconhecido%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_conector_historico_a_conferir(null, 'aplicada'); raise exception 'Situação inválida deveria ser recusada';
  exception when others then if sqlerrm like 'Situação inválida deveria%' then raise; end if; assert sqlerrm like 'A situação precisa ser%', 'Mensagem: ' || sqlerrm; end;

  -- ---------- versão 2: multa com desconto, data estimada, finalidade, inferido/faltando e trecho diferente ----------
  reset role;
  update multas_transito set valor_atual = 120.00 where ait = 'HIS-001';
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  r := rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_financeiro', 'rotulo', 'v2-teste',
    'periodo_inicio', (hoje_br() - 40)::text, 'periodo_fim', hoje_br()::text,
    'registros', jsonb_build_array(
      jsonb_build_object('tipo', 'multa', 'data', (hoje_br() - 20)::text, 'trecho', 'm1', 'resumo', 'Multa com 20% de desconto',
        'dados', jsonb_build_object('placa', 'HIS1A11', 'ait', 'HIS-001', 'valor', '104.13')),
      jsonb_build_object('tipo', 'multa', 'data', (hoje_br() - 20)::text, 'trecho', 'm2', 'resumo', 'Multa com o valor atualizado',
        'dados', jsonb_build_object('placa', 'HIS1A11', 'ait', 'HIS-001', 'valor', '120.00')),
      jsonb_build_object('tipo', 'pagamento', 'data', (p1 + 3)::text, 'trecho', 'e1', 'resumo', 'Pagamento com data estimada',
        'dados', jsonb_build_object('cliente', 'Zeferino Testehist', 'valor', '275.00', 'data_estimada', true)),
      jsonb_build_object('tipo', 'pagamento', 'data', (p1 + 3)::text, 'trecho', 'e2', 'resumo', 'Pagamento com data certa',
        'dados', jsonb_build_object('cliente', 'Zeferino Testehist', 'valor', '275.00')),
      jsonb_build_object('tipo', 'pagamento', 'data', p1::text, 'trecho', 'f1', 'resumo', 'Pagamento de caução',
        'dados', jsonb_build_object('cliente', 'Zeferino Testehist', 'valor', '275.00', 'finalidade', 'caução')),
      jsonb_build_object('tipo', 'pagamento', 'data', p1::text, 'trecho', 'f2', 'resumo', 'Pagamento de outros',
        'dados', jsonb_build_object('cliente', 'Zeferino Testehist', 'valor', '275.00', 'finalidade', 'outros')),
      jsonb_build_object('tipo', 'contrato', 'data', (d0 + 10)::text, 'trecho', 'k4', 'resumo', 'Contrato com data estimada',
        'dados', jsonb_build_object('placa', 'HIS1A11', 'cliente', 'Zeferino Testehist', 'valor_periodo', '275.00', 'data_estimada', true)),
      jsonb_build_object('tipo', 'contrato', 'data', (d0 + 10)::text, 'trecho', 'k5', 'resumo', 'Contrato com data certa',
        'dados', jsonb_build_object('placa', 'HIS1A11', 'cliente', 'Zeferino Testehist', 'valor_periodo', '275.00')),
      jsonb_build_object('tipo', 'pagamento', 'data', (hoje_br() - 2)::text, 'trecho', 'i1', 'resumo', 'Pagamento sem valor, inferido',
        'dados', jsonb_build_object('cliente', 'Zeferino Testehist', 'inferido', true, 'faltando', 'valor')))));
  assert (r->'situacoes'->>'ja_existe')::int = 5 and (r->'situacoes'->>'nova')::int = 2 and (r->'situacoes'->>'diverge')::int = 1
         and (r->'situacoes'->>'sem_comparacao')::int = 1, 'Situações da v2: ' || (r->'situacoes')::text;
  assert (select count(*) from historico_chat_registros) = 0, 'continua sem ler a tabela';
  lista := rpc_conector_historico_a_conferir('chat_financeiro', 'ja_existe', 50)->'linhas';
  assert (select e->>'detalhe' from jsonb_array_elements(lista) e where e->>'resumo' = 'Multa com 20% de desconto') like '%20% de desconto%R$ 130,16%', 'Multa com desconto: ' || lista::text;
  assert (select e->>'detalhe' is null from jsonb_array_elements(lista) e where e->>'resumo' = 'Multa com o valor atualizado'), 'Multa com valor atualizado não diverge';
  assert (select e->>'data_estimada' from jsonb_array_elements(lista) e where e->>'resumo' = 'Pagamento com data estimada') = 'true', 'data_estimada aparece na lista';
  lista := rpc_conector_historico_a_conferir('chat_financeiro', 'nova', 50)->'linhas';
  assert exists (select 1 from jsonb_array_elements(lista) e where e->>'resumo' = 'Pagamento com data certa'), 'Sem data_estimada a data tem de bater';
  assert exists (select 1 from jsonb_array_elements(lista) e where e->>'resumo' = 'Pagamento de caução'), 'finalidade caução não casa com cobrança de outros';
  lista := rpc_conector_historico_a_conferir('chat_financeiro', 'sem_comparacao', 50)->'linhas';
  assert (select e->>'inferido' = 'true' and e->>'faltando' = 'valor' from jsonb_array_elements(lista) e where e->>'resumo' = 'Pagamento sem valor, inferido'), 'inferido e faltando na lista';
  -- o mesmo registro com outro trecho do chat é avisado (pode ser um segundo pagamento real)
  r := rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_financeiro', 'rotulo', 'v2-teste',
    'periodo_inicio', (hoje_br() - 40)::text, 'periodo_fim', hoje_br()::text,
    'registros', jsonb_build_array(jsonb_build_object('tipo', 'pagamento', 'data', p1::text, 'trecho', 'OUTRO trecho', 'resumo', 'Pagamento igual',
      'dados', jsonb_build_object('cliente', 'Zeferino Testehist', 'placa', 'HIS1A11', 'valor', '275.00')))));
  assert (r->>'repetidos')::int = 1 and r->'parecidos_com_trecho_diferente' = '["Pagamento igual"]'::jsonb, 'Aviso de trecho diferente: ' || r::text;
  r := rpc_conector_entregar_lote_historico(jsonb_build_object('fonte', 'chat_financeiro', 'rotulo', 'v2-teste',
    'periodo_inicio', (hoje_br() - 40)::text, 'periodo_fim', hoje_br()::text,
    'registros', jsonb_build_array(jsonb_build_object('tipo', 'pagamento', 'data', p1::text, 'trecho', 't1', 'resumo', 'Pagamento igual',
      'dados', jsonb_build_object('cliente', 'Zeferino Testehist', 'placa', 'HIS1A11', 'valor', '275.00')))));
  assert (r->>'repetidos')::int = 1 and r->'parecidos_com_trecho_diferente' = '[]'::jsonb, 'Reenvio idêntico não avisa: ' || r::text;
  begin perform rpc_historico_conferencia(); raise exception 'O robô não deveria ver a conferência';
  exception when insufficient_privilege then null; end;
  reset role;

  -- ---------- o dono lê e descarta ----------
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  assert (select count(*) from historico_chat_registros) >= 20, 'O dono lê os registros';
  r := rpc_historico_conferencia();
  assert (r->>'total')::int = (select count(*) from historico_chat_registros) and jsonb_array_length(r->'linhas') = (r->>'total')::int, 'Conferência completa: ' || (r->>'total');
  assert (r->'linhas'->0 ? 'trecho') and (r->'linhas'->0 ? 'lote') and (r->'linhas'->0 ? 'entregue_em'), 'A conferência traz trecho, lote e data';
  assert (rpc_historico_conferencia('chat_contratos', 'nova')->>'total')::int = 3 and (rpc_historico_conferencia('chat_contratos')->'linhas'->0->>'situacao') = 'diverge', 'Filtros e ordem (divergentes primeiro)';
  begin perform rpc_historico_conferencia('outra'); raise exception 'Fonte inválida deveria ser recusada';
  exception when others then if sqlerrm like 'Fonte inválida deveria%' then raise; end if; assert sqlerrm like 'A fonte precisa ser%', 'Mensagem: ' || sqlerrm; end;
  begin update historico_chat_registros set situacao = 'aplicada' where false; raise exception 'Nem o dono deveria alterar a tabela direto';
  exception when insufficient_privilege then null; end;  -- só as RPCs (e a carga aprovada, rodada pelo SQL Editor) escrevem
  begin
    perform rpc_historico_descartar_lote(gen_random_uuid());
    raise exception 'Lote inexistente deveria ser recusado';
  exception when others then if sqlerrm like 'Lote inexistente deveria%' then raise; end if; assert sqlerrm like 'Lote não encontrado%', 'Mensagem: ' || sqlerrm; end;
  reset role;
  update historico_chat_registros set situacao = 'aplicada' where lote_id = lote_f and trecho = 't3';
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  begin perform rpc_historico_descartar_lote(lote_f); raise exception 'Lote com aplicado deveria ser recusado';
  exception when others then if sqlerrm like 'Lote com aplicado%' then raise; end if; assert sqlerrm like 'Este lote já tem registros aplicados%', 'Mensagem: ' || sqlerrm; end;
  r := rpc_historico_descartar_lote(lote_c);
  assert (r->>'registros_apagados')::int = 10, 'Descartar o lote de contratos: ' || r::text;
  reset role;
  assert not exists (select 1 from historico_chat_registros where lote_id = lote_c) and not exists (select 1 from historico_chat_lotes where id = lote_c), 'Lote e registros apagados';
  assert exists (select 1 from historico_chat_lotes where id = lote_f), 'O outro lote continua';

  raise notice 'verificar_historico_chats: tudo certo';
end $$;
rollback;
