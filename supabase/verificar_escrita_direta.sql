-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar as migrations
--   20261124120000_pendencias_lancamento.sql  e  20261124130000_escrita_direta_conector.sql
-- Verifica: só o usuário de serviço e o dono chamam as RPCs de gravação direta, e só o dono desfaz; pagamento limpo grava uma vez
--   (a cobrança fica paga, o histórico marca a decisão automática) e repetir a chave devolve o mesmo; na dúvida (sem cobrança, cobrança
--   paga, valor parcial ou acima do saldo) NÃO grava e devolve o motivo; acima do teto (R$ 10.000 / R$ 5.000) não grava, e o valor
--   igual ao teto grava; despesa sem veículo é dúvida; cliente (CPF válido, CPF repetido, homônimo, CPF provisório 0000000000N, telefone
--   formatado) e veículo (placa válida e única); desfazer apaga o registro e reabre a cobrança, só dentro de 7 dias, só os automáticos
--   e só se o registro não tiver outros dados ligados.
-- Precisa existir pelo menos um administrador (dono). Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
-- Usa nomes de teste próprios (Zeferino/Zuleica/Zacarias Testeescrita, ESC1A11, ESC2B22...) para dados reais não interferirem.
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
  cob_b    uuid;
  cob_c    uuid;
  cob_d    uuid;
  r        jsonb;
  r2       jsonb;
  pa       uuid;
  p_cli    uuid;
  p_cli2   uuid;
  p_cli3   uuid;
  p_des    uuid;
  n        int;
  st       text;
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'Precisa existir um administrador (dono)';
  assert not exists (select 1 from clientes where cpf in ('11144477735', '39053344705')), 'CPF de teste já existe neste banco: troque no roteiro';
  assert not exists (select 1 from motos where placa in ('ESC1A11', 'ESC2B22', 'ESC3C33')), 'Placa de teste já existe neste banco';

  insert into clientes (nome, cpf) values ('Zeferino Testeescrita Silva', '90000000071') returning id into cli1;
  insert into motos (placa, marca, modelo, km_atual) values ('ESC1A11', 'Honda', 'Testeescrita 160', 100) returning id into moto1;
  insert into contratos (moto_id, cliente_id, data_inicio, periodicidade, valor_periodo, km_inicial)
    values (moto1, cli1, hoje_br() - 10, 'semanal', 275, 100) returning id into ct1;
  insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao) values (ct1, 'outros', hoje_br(), 275, 'A') returning id into cob_a;
  insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao) values (ct1, 'outros', hoje_br() + 2, 300, 'B') returning id into cob_b;
  insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao) values (ct1, 'outros', hoje_br() + 3, 12000, 'C acima do teto') returning id into cob_c;
  insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao) values (ct1, 'outros', hoje_br() + 4, 10000, 'D no teto') returning id into cob_d;
  insert into servico_conector (user_id) values (robo);

  -- ---------- quem não é dono nem robô não chama nada; o robô não desfaz ----------
  perform set_config('request.jwt.claim.sub', estranho::text, true);
  set local role authenticated;
  begin perform rpc_conector_registrar_pagamento('{}'::jsonb); raise exception 'Estranho não deveria registrar pagamento';
  exception when insufficient_privilege then null; end;
  begin perform rpc_conector_registrar_despesa('{}'::jsonb); raise exception 'Estranho não deveria registrar despesa';
  exception when insufficient_privilege then null; end;
  begin perform rpc_conector_cadastrar_cliente('{}'::jsonb); raise exception 'Estranho não deveria cadastrar cliente';
  exception when insufficient_privilege then null; end;
  begin perform rpc_conector_cadastrar_veiculo('{}'::jsonb); raise exception 'Estranho não deveria cadastrar veículo';
  exception when insufficient_privilege then null; end;
  begin perform rpc_pendencia_desfazer(gen_random_uuid(), 'x'); raise exception 'Estranho não deveria desfazer';
  exception when insufficient_privilege then null; end;
  reset role;

  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  begin perform rpc_pendencia_desfazer(gen_random_uuid(), 'x'); raise exception 'O robô não deveria desfazer';
  exception when insufficient_privilege then null; end;
  assert (select count(*) from clientes) = 0 and (select count(*) from pagamentos) = 0 and (select count(*) from despesas) = 0,
    'O robô não deveria ler tabelas';

  -- ---------- pagamento limpo grava uma vez ----------
  r := rpc_conector_registrar_pagamento(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-pag-1',
         'trecho_origem', 'Zeferino pagou 275', 'dados', jsonb_build_object('cobranca_id', cob_a, 'valor', '275', 'forma', 'pix')));
  assert (r->>'gravado')::boolean and not (r->>'repetida')::boolean, 'Pagamento limpo grava: ' || r::text;
  assert r->>'resumo' like 'Pagamento de Zeferino Testeescrita Silva (ESC1A11): R$ 275,00 em %', 'Resumo: ' || (r->>'resumo');
  pa := (r->>'pendencia_id')::uuid;
  r2 := rpc_conector_registrar_pagamento(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-pag-1',
          'dados', jsonb_build_object('cobranca_id', cob_a, 'valor', '275')));
  assert (r2->>'gravado')::boolean and (r2->>'repetida')::boolean and (r2->>'pendencia_id')::uuid = pa, 'Repetir a chave devolve o mesmo: ' || r2::text;
  reset role;
  assert (select count(*) from pagamentos where cobranca_id = cob_a) = 1, 'Um pagamento só';
  assert (select chave_operacao from pagamentos where cobranca_id = cob_a) = pa, 'A chave do pagamento é a pendência';
  assert (select status from cobrancas where id = cob_a) = 'paga', 'A cobrança A ficou paga';
  assert (select decisao_automatica and status = 'aprovada' and decidido_por = robo and tipo = 'pagamento' and trecho_origem = 'Zeferino pagou 275'
            from pendencias_lancamento where id = pa), 'Histórico: decisão automática, quem pediu e o trecho';

  -- ---------- dúvida: NÃO grava e devolve o motivo ----------
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  r := rpc_conector_registrar_pagamento(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-parcial',
         'dados', jsonb_build_object('cobranca_id', cob_b, 'valor', '100')));
  assert not (r->>'gravado')::boolean and r->>'motivo' = 'duvida' and r->>'mensagem' like '%Pagamento parcial%R$ 300,00%', 'Parcial é dúvida: ' || r::text;
  r := rpc_conector_registrar_pagamento(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-semcob',
         'dados', jsonb_build_object('valor', '50')));
  assert r->>'motivo' = 'duvida' and r->>'mensagem' like '%cobrança não foi identificada%', 'Sem cobrança: ' || r::text;
  r := rpc_conector_registrar_pagamento(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-paga',
         'dados', jsonb_build_object('cobranca_id', cob_a, 'valor', '275')));
  assert r->>'motivo' = 'duvida' and r->>'mensagem' like '%já está paga%', 'Cobrança paga: ' || r::text;
  r := rpc_conector_registrar_pagamento(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-acima',
         'dados', jsonb_build_object('cobranca_id', cob_b, 'valor', '350')));
  assert r->>'motivo' = 'duvida' and r->>'mensagem' like '%passa do saldo%', 'Acima do saldo: ' || r::text;
  r := rpc_conector_registrar_pagamento(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-fut',
         'dados', jsonb_build_object('cobranca_id', cob_b, 'valor', '300', 'data_pagamento', (hoje_br() + 1)::text)));
  assert r->>'motivo' = 'duvida' and jsonb_array_length(r->'avisos') = 1 and r->'avisos'->0->>'codigo' = 'data_no_futuro', 'Amanhã é dúvida: ' || r::text;
  reset role;
  assert (select count(*) from pagamentos where cobranca_id = cob_b) = 0, 'Nada foi gravado na dúvida';
  assert (select count(*) from pendencias_lancamento where chave_operacao like 'esc-%' and chave_operacao <> 'esc-pag-1') = 0, 'A dúvida não deixa pendência';

  -- ---------- teto: acima não grava, igual grava ----------
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  r := rpc_conector_registrar_pagamento(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-teto-1',
         'dados', jsonb_build_object('cobranca_id', cob_c, 'valor', '12000')));
  assert not (r->>'gravado')::boolean and r->>'motivo' = 'acima_do_teto' and r->>'mensagem' like '%R$ 10.000,00%', 'Acima do teto: ' || r::text;
  r := rpc_conector_registrar_pagamento(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-teto-2',
         'dados', jsonb_build_object('cobranca_id', cob_d, 'valor', '10000')));
  assert (r->>'gravado')::boolean, 'Valor igual ao teto grava: ' || r::text;

  -- ---------- validações que levantam erro ----------
  begin perform rpc_conector_registrar_pagamento(jsonb_build_object('origem', 'manual', 'chave_operacao', 'e1', 'dados', jsonb_build_object('valor', '1')));
    raise exception 'Origem manual deveria ser recusada';
  exception when others then if sqlerrm like 'Origem manual deveria%' then raise; end if; assert sqlerrm like 'A origem precisa ser%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_conector_registrar_pagamento(jsonb_build_object('origem', 'chat_financeiro', 'dados', jsonb_build_object('valor', '1')));
    raise exception 'Sem chave deveria ser recusado';
  exception when others then if sqlerrm like 'Sem chave deveria%' then raise; end if; assert sqlerrm like 'A chave de operação%', 'Mensagem: ' || sqlerrm; end;
  foreach st in array array['0', '-5', 'abc', '10.999', '20000.01'] loop
    begin
      perform rpc_conector_registrar_pagamento(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'val-' || st,
                'dados', jsonb_build_object('cobranca_id', cob_b, 'valor', st)));
      raise exception 'Valor % deveria ser recusado', st;
    exception when others then if sqlerrm like 'Valor % deveria%' then raise; end if; assert sqlerrm like 'O valor %', 'Mensagem: ' || sqlerrm; end;
  end loop;

  -- ---------- despesa ----------
  r := rpc_conector_registrar_despesa(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-des-1',
         'dados', jsonb_build_object('valor', '95', 'categoria', 'Manutenção', 'observacoes', 'Pastilha de freio', 'moto_id', moto1)));
  assert (r->>'gravado')::boolean and r->>'resumo' like 'Despesa (ESC1A11): R$ 95,00 em %, manutencao', 'Despesa limpa: ' || r::text;
  p_des := (r->>'pendencia_id')::uuid;
  r := rpc_conector_registrar_despesa(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-des-2',
         'dados', jsonb_build_object('valor', '40', 'observacoes', 'Sem veículo')));
  assert not (r->>'gravado')::boolean and r->>'motivo' = 'duvida' and r->>'mensagem' like '%não está ligada a nenhum veículo%', 'Sem veículo é dúvida: ' || r::text;
  r := rpc_conector_registrar_despesa(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-des-3',
         'dados', jsonb_build_object('valor', '5000.01', 'observacoes', 'Grande', 'descricao_veiculo', 'Biz')));
  assert r->>'motivo' = 'acima_do_teto' and r->>'mensagem' like '%R$ 5.000,00%', 'Acima do teto da despesa: ' || r::text;
  r := rpc_conector_registrar_despesa(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-des-4',
         'dados', jsonb_build_object('valor', '5000', 'observacoes', 'No teto', 'descricao_veiculo', 'Biz')));
  assert (r->>'gravado')::boolean, 'Despesa no teto grava: ' || r::text;
  r := rpc_conector_registrar_despesa(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-des-5',
         'dados', jsonb_build_object('valor', '95', 'categoria', 'manutencao', 'observacoes', 'Igual', 'moto_id', moto1,
                                     'data', hoje_br()::text)));
  assert r->>'motivo' = 'duvida' and r->>'mensagem' like '%despesa igual%', 'Duplicada é dúvida: ' || r::text;

  -- ---------- cliente ----------
  r := rpc_conector_cadastrar_cliente(jsonb_build_object('origem', 'chat_contratos', 'chave_operacao', 'esc-cli-1', 'trecho_origem', 'novo locatário',
         'dados', jsonb_build_object('nome', '  Zacarias   Testeescrita  Lima ', 'cpf', '111.444.777-35', 'telefone', '11912345678',
                                      'whatsapp', '(11) 3456-7890', 'email', 'z@exemplo.com')));
  assert (r->>'gravado')::boolean and r->>'resumo' = 'Cliente cadastrado: Zacarias Testeescrita Lima (CPF final 7735)', 'Cliente: ' || r::text;
  p_cli := (r->>'pendencia_id')::uuid;
  reset role;
  assert (select cpf = '11144477735' and telefone = '(11) 91234-5678' and whatsapp = '(11) 3456-7890' and email = 'z@exemplo.com'
            from clientes where id = (select registro_id from pendencias_lancamento where id = p_cli)), 'Cliente gravado com telefone formatado';
  assert (select dados->>'cpf_final' = '7735' and position('11144477735' in dados::text) = 0 from pendencias_lancamento where id = p_cli),
    'O histórico guarda só o final do CPF';
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  r := rpc_conector_cadastrar_cliente(jsonb_build_object('origem', 'chat_contratos', 'chave_operacao', 'esc-cli-2',
         'dados', jsonb_build_object('nome', 'Outra Pessoa Testeescrita', 'cpf', '11144477735')));
  assert not (r->>'gravado')::boolean and r->>'motivo' = 'cpf_ja_cadastrado' and r->>'mensagem' like '%Zacarias Testeescrita Lima%', 'CPF repetido: ' || r::text;
  r := rpc_conector_cadastrar_cliente(jsonb_build_object('origem', 'chat_contratos', 'chave_operacao', 'esc-cli-3',
         'dados', jsonb_build_object('nome', 'zacarias testeescrita lima', 'cpf', '39053344705')));
  assert r->>'motivo' = 'homonimo' and r->>'mensagem' like '%CPF final 7735%', 'Homônimo pede confirmação: ' || r::text;
  r := rpc_conector_cadastrar_cliente(jsonb_build_object('origem', 'chat_contratos', 'chave_operacao', 'esc-cli-3',
         'dados', jsonb_build_object('nome', 'zacarias testeescrita lima', 'cpf', '39053344705', 'confirmar_homonimo', true)));
  assert (r->>'gravado')::boolean, 'Homônimo confirmado grava: ' || r::text;
  p_cli2 := (r->>'pendencia_id')::uuid;
  r := rpc_conector_cadastrar_cliente(jsonb_build_object('origem', 'chat_contratos', 'chave_operacao', 'esc-cli-4',
         'dados', jsonb_build_object('nome', 'Zuleica Testeescrita Prado', 'cpf_provisorio', true, 'observacoes', 'sem CPF ainda')));
  assert (r->>'gravado')::boolean and r->>'resumo' like 'Cliente cadastrado: Zuleica Testeescrita Prado (CPF provisório 0000000000%)', 'Provisório: ' || r::text;
  p_cli3 := (r->>'pendencia_id')::uuid;
  r := rpc_conector_cadastrar_cliente(jsonb_build_object('origem', 'chat_contratos', 'chave_operacao', 'esc-cli-5',
         'dados', jsonb_build_object('nome', 'Zenaide Testeescrita Souza', 'cpf_provisorio', true)));
  assert (r->>'gravado')::boolean, 'Segundo provisório: ' || r::text;
  reset role;
  assert (select count(*) from clientes where observacoes like '[CPF PROVISÓRIO]%' and nome ilike '%Testeescrita%') = 2, 'Dois provisórios marcados';
  assert (select observacoes from clientes where nome = 'Zuleica Testeescrita Prado') = '[CPF PROVISÓRIO] sem CPF ainda', 'Marca e observação';
  assert (select count(distinct cpf) from clientes where nome ilike '%Testeescrita%' and cpf <> '90000000071') = 4, 'CPFs distintos: ' || (select string_agg(nome || '=' || cpf, ', ') from clientes where nome ilike '%Testeescrita%');
  assert not exists (select 1 from clientes where nome ilike '%Testeescrita%' and observacoes like '[CPF PROVISÓRIO]%' and fn_cpf_valido(cpf)), 'Provisório nunca é CPF válido';
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  foreach st in array array['Maria', '', 'Maria Silva'] loop
    begin
      perform rpc_conector_cadastrar_cliente(jsonb_build_object('origem', 'chat_contratos', 'chave_operacao', 'cli-' || st,
                'dados', jsonb_build_object('nome', st, 'cpf', '52998224726')));
      raise exception 'Cliente % deveria ser recusado', st;
    exception when others then if sqlerrm like 'Cliente % deveria%' then raise; end if;
      assert sqlerrm like 'Informe o nome completo%' or sqlerrm like 'Informe um CPF válido%', 'Mensagem: ' || sqlerrm; end;
  end loop;
  begin perform rpc_conector_cadastrar_cliente(jsonb_build_object('origem', 'chat_contratos', 'chave_operacao', 'cli-tel',
          'dados', jsonb_build_object('nome', 'Telefone Errado Silva', 'cpf', '52998224725', 'telefone', '123')));
    raise exception 'Telefone inválido deveria ser recusado';
  exception when others then if sqlerrm like 'Telefone inválido deveria%' then raise; end if; assert sqlerrm like 'Informe o telefone com DDD%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_conector_cadastrar_cliente(jsonb_build_object('origem', 'chat_contratos', 'chave_operacao', 'cli-prov-cpf',
          'dados', jsonb_build_object('nome', 'Provisorio Com Cpf', 'cpf_provisorio', true, 'cpf', '52998224725')));
    raise exception 'Provisório com CPF deveria ser recusado';
  exception when others then if sqlerrm like 'Provisório com CPF deveria%' then raise; end if; assert sqlerrm like 'Com cpf_provisorio não se informa CPF%', 'Mensagem: ' || sqlerrm; end;

  -- ---------- veículo ----------
  r := rpc_conector_cadastrar_veiculo(jsonb_build_object('origem', 'chat_contratos', 'chave_operacao', 'esc-vei-1',
         'dados', jsonb_build_object('placa', 'esc-2b22', 'marca', ' Fiat ', 'modelo', 'Uno Testeescrita', 'tipo', 'Carro', 'km_atual', '12.500', 'ano_modelo', 2020)));
  assert (r->>'gravado')::boolean and r->>'resumo' = 'Veículo cadastrado: ESC2B22, Fiat Uno Testeescrita', 'Veículo: ' || r::text;
  r2 := rpc_conector_cadastrar_veiculo(jsonb_build_object('origem', 'chat_contratos', 'chave_operacao', 'esc-vei-2',
          'dados', jsonb_build_object('placa', 'ESC2B22', 'marca', 'Fiat', 'modelo', 'Outro')));
  assert not (r2->>'gravado')::boolean and r2->>'motivo' = 'placa_ja_cadastrada', 'Placa repetida: ' || r2::text;
  reset role;
  assert (select tipo = 'carro' and km_atual = 12500 and ano_modelo = 2020 and marca = 'Fiat' from motos where placa = 'ESC2B22'), 'Veículo gravado';
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  foreach st in array array['123', 'ABCD123', ''] loop
    begin
      perform rpc_conector_cadastrar_veiculo(jsonb_build_object('origem', 'chat_contratos', 'chave_operacao', 'vei-' || st,
                'dados', jsonb_build_object('placa', st, 'marca', 'Honda', 'modelo', 'CG')));
      raise exception 'Placa % deveria ser recusada', st;
    exception when others then if sqlerrm like 'Placa % deveria%' then raise; end if; assert sqlerrm like 'Placa: use%', 'Mensagem: ' || sqlerrm; end;
  end loop;
  begin perform rpc_conector_cadastrar_veiculo(jsonb_build_object('origem', 'chat_contratos', 'chave_operacao', 'vei-tipo',
          'dados', jsonb_build_object('placa', 'ESC3C33', 'marca', 'Honda', 'modelo', 'CG', 'tipo', 'barco')));
    raise exception 'Tipo barco deveria ser recusado';
  exception when others then if sqlerrm like 'Tipo barco deveria%' then raise; end if; assert sqlerrm like 'O tipo precisa ser%', 'Mensagem: ' || sqlerrm; end;

  -- ---------- últimos lançamentos do chat ----------
  assert (rpc_conector_minhas_pendencias(5)->0 ? 'decisao_automatica') and jsonb_array_length(rpc_conector_minhas_pendencias(5)) = 5, 'Últimos lançamentos';
  reset role;

  -- ---------- desfazer (só dono) ----------
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  begin perform rpc_pendencia_desfazer(pa, '   '); raise exception 'Sem motivo deveria ser recusado';
  exception when others then if sqlerrm like 'Sem motivo deveria%' then raise; end if; assert sqlerrm like 'Informe o motivo%', 'Mensagem: ' || sqlerrm; end;
  r := rpc_pendencia_desfazer(pa, 'Pagamento lançado na cobrança errada');
  assert r->>'status' = 'desfeita', 'Desfeito: ' || r::text;
  reset role;
  assert (select count(*) from pagamentos where cobranca_id = cob_a) = 0, 'O pagamento foi apagado';
  assert (select status from cobrancas where id = cob_a) = 'aberta', 'A cobrança A voltou a ficar aberta';
  assert (select status = 'desfeita' and desfeita_por = dono and motivo_desfazer like 'Pagamento lançado%' from pendencias_lancamento where id = pa), 'Histórico do desfazer';
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  begin perform rpc_pendencia_desfazer(pa, 'de novo'); raise exception 'Desfazer de novo deveria ser recusado';
  exception when others then if sqlerrm like 'Desfazer de novo%' then raise; end if; assert sqlerrm like 'Este lançamento já foi desfeito%', 'Mensagem: ' || sqlerrm; end;
  reset role;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  r := rpc_conector_registrar_pagamento(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-pag-1',
         'dados', jsonb_build_object('cobranca_id', cob_a, 'valor', '275')));
  assert not (r->>'gravado')::boolean and r->>'mensagem' like '%desfeito pelo dono%', 'A chave de um lançamento desfeito não regrava: ' || r::text;
  r := rpc_conector_registrar_pagamento(jsonb_build_object('origem', 'chat_financeiro', 'chave_operacao', 'esc-pag-1b',
         'dados', jsonb_build_object('cobranca_id', cob_a, 'valor', '275')));
  assert (r->>'gravado')::boolean, 'Com chave nova regrava: ' || r::text;
  reset role;

  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  assert (rpc_pendencia_desfazer(p_des, 'Despesa errada')->>'status') = 'desfeita', 'Desfaz a despesa';
  assert (rpc_pendencia_desfazer(p_cli3, 'Cadastro duplicado')->>'status') = 'desfeita', 'Desfaz o cliente sem vínculos';
  reset role;
  assert not exists (select 1 from despesas where observacoes = 'Pastilha de freio') and not exists (select 1 from clientes where nome = 'Zuleica Testeescrita Prado'),
    'Despesa e cliente apagados';
  -- cliente que já tem contrato não se desfaz
  insert into contratos (moto_id, cliente_id, data_inicio, periodicidade, valor_periodo, km_inicial)
    select (select id from motos where placa = 'ESC2B22'), (select registro_id from pendencias_lancamento where id = p_cli2), hoje_br(), 'semanal', 100, 0;
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  begin perform rpc_pendencia_desfazer(p_cli2, 'quero apagar'); raise exception 'Cliente com contrato deveria ser recusado';
  exception when others then if sqlerrm like 'Cliente com contrato deveria%' then raise; end if; assert sqlerrm like 'Este registro já tem outros dados ligados%', 'Mensagem: ' || sqlerrm; end;
  -- depois de 7 dias não desfaz; proposta manual do dono não é automática
  reset role;
  update pendencias_lancamento set decidido_em = now() - interval '8 days' where id = p_cli;
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  begin perform rpc_pendencia_desfazer(p_cli, 'tarde'); raise exception 'Depois de 7 dias deveria ser recusado';
  exception when others then if sqlerrm like 'Depois de 7 dias%' then raise; end if; assert sqlerrm like 'Passaram mais de 7 dias%', 'Mensagem: ' || sqlerrm; end;
  r := rpc_pendencia_criar(jsonb_build_object('tipo', 'despesa', 'origem', 'manual', 'chave_operacao', 'esc-manual',
         'dados', jsonb_build_object('valor', '10', 'observacoes', 'Proposta manual', 'descricao_veiculo', 'Biz')));
  begin perform rpc_pendencia_desfazer((r->>'id')::uuid, 'x'); raise exception 'Proposta manual deveria ser recusada';
  exception when others then if sqlerrm like 'Proposta manual deveria%' then raise; end if; assert sqlerrm like 'Só dá para desfazer lançamentos gravados direto%', 'Mensagem: ' || sqlerrm; end;
  reset role;

  raise notice 'verificar_escrita_direta: tudo certo';
end $$;
rollback;
