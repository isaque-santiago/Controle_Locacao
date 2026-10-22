-- Executar no SQL Editor de DESENVOLVIMENTO (nunca em produção) após aplicar as migrations
--   20261022120000_importacao_veiculos_contratos.sql
--   20261022130000_importacao_despesas_socio_dividas.sql
--   20261022140000_importacao_multas.sql
--   20261022150000_importacao_rastreio_lotes.sql
--   20261022160000_importacao_capital_veiculos.sql
-- Verifica o modelo da importação dos dados reais (Arquivos/Importacao_Dados_Reais.md):
--   * promessa de compra: restrição do total, agenda ancorada em primeira_cobranca, numeração e parada;
--   * abatimento (desconto sem dinheiro) aceito como forma de pagamento;
--   * saldo de dívida de fornecedor (dívida anterior + pedidos novos - pagamentos);
--   * locatário na data da multa;
--   * capital em veículos sem operação (Etios e Celta): placa provisória, aquisição, empréstimo, parcelas futuras e aporte.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  cliente uuid; moto uuid; moto2 uuid; c jsonb; contrato uuid; n int; primeira uuid;
  forn uuid; div uuid; saldo numeric; locatario text;
  etios uuid; celta uuid; forn_motor uuid; div_emp uuid; div_motor uuid; cap record;
begin
  insert into clientes(nome, cpf) values ('Teste importacao', '00000000002') returning id into cliente;
  insert into motos(placa, marca, modelo, km_atual, tipo) values ('TST5Z55', 'Teste', 'Teste', 100, 'carro') returning id into moto;

  -- Promessa: 10 parcelas semanais de 550, 6 já pagas, agenda ancorada em hoje (contrato começou há 70 dias)
  c := rpc_criar_contrato(jsonb_build_object('moto_id', moto, 'cliente_id', cliente,
    'data_inicio', hoje_br() - 70, 'periodicidade', 'semanal', 'valor_periodo', 550, 'km_inicial', 100,
    'tipo_contrato', 'promessa_compra', 'numero_parcelas', 10, 'parcelas_pagas_inicial', 6,
    'primeira_cobranca', hoje_br()));
  contrato := (c->>'contrato_id')::uuid;
  assert (select valor_total from contratos where id = contrato) = 5500, 'valor_total da promessa incorreto';
  assert (select count(*) from cobrancas where contrato_id = contrato and tipo = 'locacao') = 0,
    'Criação não deveria gerar cobranças antigas (primeira_cobranca é hoje, fora da janela de data_inicio + 30)';

  -- Janela móvel: nasce em primeira_cobranca, numera de 7 a 10 e para na última parcela
  perform rpc_gerar_cobrancas_pendentes(30);
  select count(*) into n from cobrancas where contrato_id = contrato and tipo = 'locacao';
  assert n = 4, 'Deveriam existir 4 parcelas (7 a 10), vieram ' || n;
  assert (select min(numero) from cobrancas where contrato_id = contrato and tipo = 'locacao') = 7, 'Numeração deveria partir de 7';
  assert (select min(vencimento) from cobrancas where contrato_id = contrato and tipo = 'locacao') = hoje_br(),
    'A 1ª parcela deveria vencer em primeira_cobranca';
  perform rpc_gerar_cobrancas_pendentes(365);
  assert (select count(*) from cobrancas where contrato_id = contrato and tipo = 'locacao') = 4,
    'A promessa não pode gerar parcelas além do número de parcelas';

  -- Restrição do total (entrada + parcelas x valor)
  begin
    update contratos set valor_total = 1 where id = contrato;
    raise exception using errcode = 'ZX201', message = 'valor_total inconsistente foi aceito';
  exception when check_violation then null;
  end;

  -- Abatimento: desconto sem dinheiro é aceito
  select id into primeira from cobrancas where contrato_id = contrato and tipo = 'locacao' and numero = 7;
  insert into pagamentos(cobranca_id, data_pagamento, valor, forma, data_estimada, observacoes)
  values (primeira, hoje_br(), 24, 'abatimento', false, 'Pastilha de freio trocada pelo locatário');
  assert (select count(*) from pagamentos where cobranca_id = primeira and forma = 'abatimento') = 1, 'Abatimento não gravado';

  -- Dívida de fornecedor: 2.395 anterior + 2.044 em pedidos - 960 pagos = 3.479
  insert into fornecedores(nome) values ('Fornecedor teste') returning id into forn;
  insert into despesas(data, categoria, valor, fornecedor_id) values (hoje_br(), 'manutencao', 2044, forn);
  insert into dividas(tipo, credor, fornecedor_id, valor_original) values ('fornecedor', 'Fornecedor teste', forn, 2395) returning id into div;
  insert into pagamentos_divida(divida_id, data, valor) values (div, hoje_br(), 960);
  select saldo_calculado into saldo from vw_saldo_dividas where divida_id = div;
  assert saldo = 3479, 'Saldo da dívida do fornecedor incorreto: ' || saldo;
  update dividas set saldo_confirmado = 3500 where id = div;
  assert (select diferenca from vw_saldo_dividas where divida_id = div) = 21, 'Diferença do saldo confirmado incorreta';

  -- Despesa por moto entra em custo_despesas, sem alterar "resultado"
  insert into despesas(data, categoria, valor, moto_id) values (hoje_br(), 'seguro_rastreador', 100, moto);
  assert (select custo_despesas from vw_resultado_moto where moto_id = moto) = 100, 'custo_despesas incorreto';
  assert (select resultado_com_despesas from vw_resultado_moto where moto_id = moto)
       = (select resultado from vw_resultado_moto where moto_id = moto) - 100, 'resultado_com_despesas incorreto';

  -- Multa: locatário na data da infração (dentro do contrato) e dono anterior (antes do contrato)
  insert into multas_transito(moto_id, data_infracao, ait, valor) values (moto, hoje_br() - 30, 'AIT-T1', 130.16);
  insert into multas_transito(moto_id, data_infracao, ait, valor) values (moto, hoje_br() - 100, 'AIT-T2', 130.16);
  select locatario_na_data into locatario from vw_multas_locatario v
    join multas_transito mu on mu.id = v.multa_id where mu.ait = 'AIT-T1';
  assert locatario = 'Teste importacao', 'Locatário na data da multa incorreto';
  assert (select locatario_na_data from vw_multas_locatario v join multas_transito mu on mu.id = v.multa_id where mu.ait = 'AIT-T2') is null,
    'Multa anterior ao contrato não deveria ter locatário';
  assert (select count(*) from multas_transito where moto_id = moto) = 2, 'Multas não gravadas';

  -- Idempotência por linha de origem
  insert into importacoes_lote(lote, tabela, registro_id, aba_origem, linha_origem)
  values ('teste', 'despesas', gen_random_uuid(), 'Despesas', 2);
  begin
    insert into importacoes_lote(lote, tabela, registro_id, aba_origem, linha_origem)
    values ('teste', 'despesas', gen_random_uuid(), 'Despesas', 2);
    raise exception using errcode = 'ZX202', message = 'Linha de origem duplicada foi aceita';
  exception when unique_violation then null;
  end;

  -- Capital em veículos sem operação: Etios (compra com empréstimo) e Celta (reforma do motor parcelada)
  insert into motos(placa, marca, modelo, tipo, placa_provisoria) values ('PROV-ETIOS', 'Toyota', 'Etios 2015', 'carro', true) returning id into etios;
  insert into motos(placa, marca, modelo, tipo, placa_provisoria) values ('PROV-CELTA', 'A INFORMAR', 'Celta', 'carro', true) returning id into celta;
  assert (select placa_provisoria from motos where id = etios), 'placa_provisoria não gravada';

  insert into despesas(data, data_estimada, moto_id, categoria, valor, a_confirmar, observacoes) values
    (hoje_br(), true, etios, 'aquisicao', 15500, true, 'Arremate (de memória)'),
    (hoje_br(), true, etios, 'aquisicao', 775, false, 'Comissão de 5%'),
    (hoje_br(), true, etios, 'aquisicao', 500, false, 'Busca do carro'),
    (hoje_br(), true, etios, 'aquisicao', 50, false, 'Almoço na viagem'),
    (hoje_br(), true, etios, 'aquisicao', 140, false, '2 pneus');
  insert into dividas(tipo, credor, moto_id, valor_original) values ('emprestimo', 'Empréstimo do Etios', etios, 14000) returning id into div_emp;
  insert into pagamentos_divida(divida_id, data, data_estimada, valor) values (div_emp, hoje_br(), true, 3000);
  insert into dividas_vencimentos(divida_id, vencimento, valor, observacoes) values
    (div_emp, null, 1000, 'Sem data informada'), (div_emp, hoje_br() + 15, 10000, 'Parcela principal');
  insert into movimentos_socio(tipo, data, data_estimada, valor, moto_id, origem_destino)
  values ('aporte', hoje_br(), true, 2965, etios, 'Dinheiro próprio no Etios');

  select * into cap from vw_capital_veiculo where moto_id = etios;
  assert cap.custo_total = 16965, 'Custo total do Etios incorreto: ' || cap.custo_total;
  assert cap.a_pagar = 11000, 'A pagar do Etios incorreto: ' || cap.a_pagar;
  assert cap.saiu_do_bolso = 5965, 'Saiu do bolso do Etios incorreto: ' || cap.saiu_do_bolso;
  assert cap.saldo = -16965, 'Saldo do Etios incorreto';
  assert cap.tem_valor_a_confirmar, 'Valor a confirmar do Etios não sinalizado';
  assert (select count(*) from dividas_vencimentos where divida_id = div_emp and vencimento is null) = 1, 'Parcela sem data não gravada';
  assert (select sum(valor) from dividas_vencimentos where divida_id = div_emp) = 11000, 'Parcelas futuras do Etios não fecham com o saldo';
  assert (select sum(valor) from movimentos_socio where moto_id = etios) = 2965, 'Aporte ligado ao veículo incorreto';

  insert into fornecedores(nome) values ('Motor do Celta (teste)') returning id into forn_motor;
  insert into despesas(data, data_estimada, moto_id, categoria, valor, fornecedor_id, observacoes)
  values (hoje_br(), true, celta, 'aquisicao', 8000, forn_motor, 'Motor (reforma)');
  insert into despesas(data, data_estimada, moto_id, categoria, valor, observacoes) values
    (hoje_br(), false, celta, 'aquisicao', 100, 'Peças enviadas ao Gabriel');
  insert into despesas(data, data_estimada, moto_id, categoria, valor, pago_por, observacoes)
  values (hoje_br(), true, celta, 'aquisicao', 450, 'locatario', 'Compressor do ar-condicionado');
  insert into despesas(data, data_estimada, moto_id, categoria, valor, a_confirmar, observacoes)
  values (hoje_br(), true, celta, 'aquisicao', 1000, true, 'Diferença: parcelas x valor do motor (a confirmar)');
  insert into dividas(tipo, credor, fornecedor_id, moto_id, valor_original, saldo_confirmado)
  values ('fornecedor', 'Motor do Celta (teste)', forn_motor, celta, 0, 4000) returning id into div_motor;
  insert into pagamentos_divida(divida_id, data, data_estimada, valor) values (div_motor, hoje_br(), true, 5000);

  select * into cap from vw_capital_veiculo where moto_id = celta;
  assert cap.custo_total = 9550, 'Custo total do Celta incorreto: ' || cap.custo_total;
  assert cap.pago_pelo_locatario = 450, 'Pago pelo locatário do Celta incorreto';
  assert cap.a_pagar = 4000, 'A pagar do Celta incorreto: ' || cap.a_pagar;
  assert cap.saiu_do_bolso = 5100, 'Saiu do bolso do Celta incorreto: ' || cap.saiu_do_bolso;
  -- o saldo calculado (8.000 - 5.000) difere do confirmado (4.000): a diferença fica visível
  assert (select diferenca from vw_saldo_dividas where divida_id = div_motor) = 1000, 'Diferença do motor do Celta incorreta';

  -- Capital e despesas pagas por terceiros não entram no resultado das motos
  assert (select custo_despesas from vw_resultado_moto where moto_id = etios) = 0, 'Aquisição não deveria entrar em custo_despesas';
  insert into despesas(data, categoria, valor, moto_id, pago_por) values (hoje_br(), 'manutencao', 10, celta, 'locatario');
  insert into despesas(data, categoria, valor, moto_id) values (hoje_br(), 'manutencao', 20, celta);
  assert (select custo_despesas from vw_resultado_moto where moto_id = celta) = 20, 'Só o que a locadora pagou deveria entrar em custo_despesas';
  -- Veículo sem despesas de aquisição não aparece em vw_capital_veiculo
  assert not exists (select 1 from vw_capital_veiculo where moto_id = moto), 'Veículo sem aquisição apareceu em vw_capital_veiculo';

  raise notice 'Verificação do modelo de importação: OK';
end $$;
rollback;
