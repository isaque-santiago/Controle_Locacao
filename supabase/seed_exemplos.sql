-- =====================================================================
-- seed_exemplos.sql : massa de dados de exemplo para explorar o sistema
-- =====================================================================
-- Não faz parte da aplicação: é um script para rodar manualmente no SQL
-- Editor do Supabase (ou via psql) depois das migrations e do seed.sql,
-- como se os cadastros abaixo tivessem sido feitos à mão pelo dono do
-- negócio. Cobre motos em cada status, clientes em cada situação,
-- contratos ativos e um encerrado, cobranças pagas/em aberto/vencidas,
-- manutenção preventiva e corretiva, documentos vencidos e regularizados
-- e vistorias de entrega/devolução.
--
-- Idempotente: se a placa EXA1A11 já existir, o script não faz nada.
-- Execute em um projeto vazio (ou já com o seed_demo.sql) para não
-- colidir com placas/CPFs reais.
begin;
do $$
declare
  v_moto_biz       uuid; v_moto_factor     uuid; v_moto_cg_disp   uuid;
  v_moto_pop_manut uuid; v_moto_fazer_inat uuid; v_moto_titan_enc uuid;
  v_cliente_joao   uuid; v_cliente_maria   uuid; v_cliente_carlos uuid;
  v_cliente_ana    uuid; v_cliente_pedro   uuid;
  v_contrato_joao  jsonb; v_contrato_maria jsonb; v_contrato_carlos jsonb;
  v_contrato_carlos_id uuid;
  v_cobranca       uuid;
  v_item_oleo      uuid;
begin
  if exists (select 1 from motos where placa = 'EXA1A11') then
    raise notice 'Exemplos já cadastrados (placa EXA1A11 encontrada) — nada a fazer.';
    return;
  end if;

  -- -------------------------------------------------------------
  -- Motos: uma em cada status possível
  -- -------------------------------------------------------------
  insert into motos (placa, renavam, chassi, marca, modelo, ano_fabricacao, ano_modelo, cor, km_atual, status, valor_aquisicao, data_aquisicao, valor_locacao_sugerido)
  values ('EXA1A11', '01234567890', '9BD11111111111111', 'Honda', 'CG 160 Start', 2022, 2023, 'Vermelha', 14200, 'disponivel', 14500.00, hoje_br() - 400, 260.00)
  returning id into v_moto_cg_disp;

  insert into motos (placa, renavam, chassi, marca, modelo, ano_fabricacao, ano_modelo, cor, km_atual, status, valor_aquisicao, data_aquisicao, valor_locacao_sugerido)
  values ('EXA2B22', '01234567891', '9BD22222222222222', 'Honda', 'Biz 125', 2021, 2021, 'Prata', 15320, 'disponivel', 11800.00, hoje_br() - 600, 280.00)
  returning id into v_moto_biz;

  insert into motos (placa, renavam, chassi, marca, modelo, ano_fabricacao, ano_modelo, cor, km_atual, status, valor_aquisicao, data_aquisicao, valor_locacao_sugerido)
  values ('EXA3C33', '01234567892', '9BD33333333333333', 'Yamaha', 'Factor 150', 2023, 2023, 'Azul', 8000, 'disponivel', 15900.00, hoje_br() - 200, 900.00)
  returning id into v_moto_factor;

  insert into motos (placa, renavam, chassi, marca, modelo, ano_fabricacao, ano_modelo, cor, km_atual, status, valor_aquisicao, data_aquisicao, valor_locacao_sugerido, observacoes)
  values ('EXA4D44', '01234567893', '9BD44444444444444', 'Honda', 'Pop 110i', 2020, 2020, 'Preta', 22140, 'disponivel', 9200.00, hoje_br() - 900, 220.00, 'Amortecedor traseiro batendo desde a última entrega.')
  returning id into v_moto_pop_manut;

  insert into motos (placa, renavam, chassi, marca, modelo, ano_fabricacao, ano_modelo, cor, km_atual, status, valor_aquisicao, data_aquisicao, valor_locacao_sugerido, observacoes)
  values ('EXA5E55', '01234567894', '9BD55555555555555', 'Yamaha', 'Fazer 250', 2019, 2019, 'Cinza', 31500, 'inativa', 18500.00, hoje_br() - 1200, 0, 'Sinistro em 15/06/2026 (colisão). Aguardando decisão da seguradora, fora de operação.')
  returning id into v_moto_fazer_inat;

  insert into motos (placa, renavam, chassi, marca, modelo, ano_fabricacao, ano_modelo, cor, km_atual, status, valor_aquisicao, data_aquisicao, valor_locacao_sugerido)
  values ('EXA6F66', '01234567895', '9BD66666666666666', 'Honda', 'CG 160 Titan', 2022, 2022, 'Branca', 8000, 'disponivel', 14900.00, hoje_br() - 500, 260.00)
  returning id into v_moto_titan_enc;

  -- -------------------------------------------------------------
  -- Clientes: um em cada situação
  -- -------------------------------------------------------------
  insert into clientes (nome, cpf, telefone, whatsapp, email, endereco, cnh_numero, cnh_categoria, cnh_validade, status, observacoes)
  values ('João da Silva Ferreira', '12345678909', '11987654321', '11987654321', 'joao.ferreira@example.com',
          'Rua das Palmeiras, 120 - São Paulo/SP', '87654321098', 'A', hoje_br() + 800, 'ativo', null)
  returning id into v_cliente_joao;

  insert into clientes (nome, cpf, telefone, whatsapp, email, endereco, cnh_numero, cnh_categoria, cnh_validade, status, observacoes)
  values ('Maria Aparecida Souza', '98765432100', '11976543210', '11976543210', 'maria.souza@example.com',
          'Av. Brasil, 980 - São Paulo/SP', '76543210987', 'AB', hoje_br() + 15, 'ativo', 'CNH próxima do vencimento, avisar na próxima renovação de contrato.')
  returning id into v_cliente_maria;

  insert into clientes (nome, cpf, telefone, whatsapp, email, endereco, cnh_numero, cnh_categoria, cnh_validade, status, observacoes)
  values ('Carlos Eduardo Lima', '33344455508', '11965432109', null, 'carlos.lima@example.com',
          'Rua Sete de Setembro, 45 - Guarulhos/SP', '65432109876', 'A', hoje_br() + 500, 'ativo', 'Cliente antigo, sempre pagou em dia. Sem contrato ativo no momento.')
  returning id into v_cliente_carlos;

  insert into clientes (nome, cpf, telefone, whatsapp, email, endereco, cnh_numero, cnh_categoria, cnh_validade, status, observacoes)
  values ('Ana Paula Rodrigues', '71428593691', '11954321098', '11954321098', 'ana.rodrigues@example.com',
          'Rua das Acácias, 210 - Osasco/SP', '54321098765', 'A', hoje_br() - 40, 'bloqueado', 'Bloqueada em ' || to_char(hoje_br() - 10, 'DD/MM/YYYY') || ' por atraso superior a 30 dias e CNH vencida.')
  returning id into v_cliente_ana;

  insert into clientes (nome, cpf, telefone, whatsapp, email, endereco, cnh_numero, cnh_categoria, cnh_validade, status, observacoes)
  values ('Pedro Henrique Santos', '24681357928', '11943210987', '11943210987', 'pedro.santos@example.com',
          'Rua Amazonas, 33 - São Paulo/SP', '43210987654', 'A', hoje_br() + 900, 'ativo', 'Cadastro novo, ainda sem contrato — em negociação.')
  returning id into v_cliente_pedro;

  -- -------------------------------------------------------------
  -- Contrato 1 (ativo, semanal): João + Biz 125
  -- Histórico de pagamento normal com UMA parcela em atraso.
  -- -------------------------------------------------------------
  v_contrato_joao := rpc_criar_contrato_com_vistoria(
    jsonb_build_object(
      'moto_id', v_moto_biz, 'cliente_id', v_cliente_joao,
      'data_inicio', hoje_br() - 35, 'data_fim_prevista', hoje_br() + 55,
      'periodicidade', 'semanal', 'valor_periodo', 280, 'caucao_valor', 400,
      'km_inicial', 15320
    ),
    jsonb_build_object('km', 15320, 'nivel_combustivel', 'cheio',
      'checklist', '{"farol_dianteiro":"ok","farol_traseiro":"ok","pneus":"ok","freios":"ok","retrovisores":"ok"}'::jsonb)
  );

  select id into v_cobranca from cobrancas
   where contrato_id = (v_contrato_joao->>'contrato_id')::uuid and tipo = 'caucao';
  insert into pagamentos (cobranca_id, data_pagamento, valor, forma)
  values (v_cobranca, hoje_br() - 35, 400, 'pix');

  -- parcelas 1 e 2 pagas em dia
  select id into v_cobranca from cobrancas
   where contrato_id = (v_contrato_joao->>'contrato_id')::uuid and tipo = 'locacao' and numero = 1;
  insert into pagamentos (cobranca_id, data_pagamento, valor, forma) values (v_cobranca, hoje_br() - 35, 280, 'pix');

  select id into v_cobranca from cobrancas
   where contrato_id = (v_contrato_joao->>'contrato_id')::uuid and tipo = 'locacao' and numero = 2;
  insert into pagamentos (cobranca_id, data_pagamento, valor, forma) values (v_cobranca, hoje_br() - 28, 280, 'pix');

  -- parcela 3 (venceu há 21 dias) ficou em aberto: exemplo de cobrança vencida com multa/juros
  -- parcela 4 (venceu há 14 dias) paga com atraso (pagou 3 dias depois do vencimento)
  select id into v_cobranca from cobrancas
   where contrato_id = (v_contrato_joao->>'contrato_id')::uuid and tipo = 'locacao' and numero = 4;
  insert into pagamentos (cobranca_id, data_pagamento, valor, multa_juros, forma, observacoes)
  values (v_cobranca, hoje_br() - 11, 280, 8.40, 'dinheiro', 'Pago com 3 dias de atraso, multa cobrada à parte.');

  -- multa de trânsito repassada ao cliente
  insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao)
  values ((v_contrato_joao->>'contrato_id')::uuid, 'multa_transito', hoje_br() + 10, 195.23,
          'Multa por excesso de velocidade (Radar Marginal Tietê, ' || to_char(hoje_br() - 6, 'DD/MM/YYYY') || ')');

  insert into historico_km (moto_id, km, data, origem) values (v_moto_biz, 15450, hoje_br() - 3, 'manual');

  -- -------------------------------------------------------------
  -- Contrato 2 (ativo, mensal): Maria + Factor 150
  -- Contrato recém-iniciado, só a primeira parcela paga.
  -- -------------------------------------------------------------
  v_contrato_maria := rpc_criar_contrato_com_vistoria(
    jsonb_build_object(
      'moto_id', v_moto_factor, 'cliente_id', v_cliente_maria,
      'data_inicio', hoje_br() - 20, 'data_fim_prevista', hoje_br() + 160,
      'periodicidade', 'mensal', 'valor_periodo', 900, 'caucao_valor', 600,
      'km_inicial', 8000
    ),
    jsonb_build_object('km', 8000, 'nivel_combustivel', '3/4',
      'checklist', '{"farol_dianteiro":"ok","pneus":"ok","freios":"ok","carenagem":"risco leve no para-lama"}'::jsonb,
      'avarias', 'Risco leve no para-lama dianteiro, já existente na entrega.')
  );

  select id into v_cobranca from cobrancas
   where contrato_id = (v_contrato_maria->>'contrato_id')::uuid and tipo = 'caucao';
  insert into pagamentos (cobranca_id, data_pagamento, valor, forma) values (v_cobranca, hoje_br() - 20, 600, 'transferencia');

  select id into v_cobranca from cobrancas
   where contrato_id = (v_contrato_maria->>'contrato_id')::uuid and tipo = 'locacao' and numero = 1;
  insert into pagamentos (cobranca_id, data_pagamento, valor, forma) values (v_cobranca, hoje_br() - 20, 900, 'pix');

  -- -------------------------------------------------------------
  -- Contrato 3 (encerrado): Carlos + CG 160 Titan
  -- Contrato quinzenal já finalizado, todas as parcelas pagas,
  -- caução devolvida. Fica como histórico do cliente e da moto.
  -- -------------------------------------------------------------
  v_contrato_carlos := rpc_criar_contrato_com_vistoria(
    jsonb_build_object(
      'moto_id', v_moto_titan_enc, 'cliente_id', v_cliente_carlos,
      'data_inicio', hoje_br() - 120, 'data_fim_prevista', hoje_br() - 30,
      'periodicidade', 'quinzenal', 'valor_periodo', 260, 'caucao_valor', 350,
      'km_inicial', 8000
    ),
    jsonb_build_object('km', 8000, 'nivel_combustivel', 'cheio',
      'checklist', '{"farol_dianteiro":"ok","farol_traseiro":"ok","pneus":"ok","freios":"ok"}'::jsonb)
  );
  v_contrato_carlos_id := (v_contrato_carlos->>'contrato_id')::uuid;

  select id into v_cobranca from cobrancas where contrato_id = v_contrato_carlos_id and tipo = 'caucao';
  insert into pagamentos (cobranca_id, data_pagamento, valor, forma) values (v_cobranca, hoje_br() - 120, 350, 'dinheiro');

  -- paga todas as parcelas quinzenais geradas para o período do contrato
  for v_cobranca in
    select id from cobrancas where contrato_id = v_contrato_carlos_id and tipo = 'locacao' order by numero
  loop
    insert into pagamentos (cobranca_id, data_pagamento, valor, forma)
    select v_cobranca, c.vencimento, c.valor, 'pix' from cobrancas c where c.id = v_cobranca;
  end loop;

  perform rpc_encerrar_contrato_com_vistoria(
    v_contrato_carlos_id, hoje_br() - 30,
    jsonb_build_object('km', 8300, 'nivel_combustivel', '1/2',
      'checklist', '{"farol_dianteiro":"ok","farol_traseiro":"ok","pneus":"ok","freios":"ok"}'::jsonb),
    true
  );

  -- -------------------------------------------------------------
  -- Manutenção preventiva concluída: CG 160 Start (disponível)
  -- -------------------------------------------------------------
  perform rpc_aplicar_plano_padrao(v_moto_cg_disp);
  select id into v_item_oleo from itens_manutencao where nome = 'Troca de óleo do motor';

  perform rpc_registrar_manutencao(jsonb_build_object(
    'moto_id', v_moto_cg_disp, 'contrato_id', null, 'tipo', 'preventiva', 'status', 'concluida',
    'data_entrada', hoje_br() - 5, 'data_saida', hoje_br() - 5, 'km', 14200,
    'oficina', 'Oficina do Zé Motos', 'descricao', 'Troca de óleo e filtro programada',
    'custo_mao_obra', 30.00, 'cobrar_do_cliente', false,
    'itens', jsonb_build_array(
      jsonb_build_object('item_id', v_item_oleo, 'descricao', 'Óleo 10W30 semissintético (1L)', 'quantidade', 1, 'valor_unitario', 45.90),
      jsonb_build_object('item_id', null, 'descricao', 'Filtro de óleo', 'quantidade', 1, 'valor_unitario', 22.00)
    )
  ));

  -- -------------------------------------------------------------
  -- Manutenção corretiva em aberto: Pop 110i (fica "em manutenção")
  -- -------------------------------------------------------------
  perform rpc_registrar_manutencao(jsonb_build_object(
    'moto_id', v_moto_pop_manut, 'contrato_id', null, 'tipo', 'corretiva', 'status', 'aberta',
    'data_entrada', hoje_br() - 2, 'km', 22140,
    'oficina', 'Moto Peças Central', 'descricao', 'Troca do amortecedor traseiro e regulagem da corrente',
    'custo_mao_obra', 80.00, 'cobrar_do_cliente', false,
    'itens', jsonb_build_array(
      jsonb_build_object('item_id', null, 'descricao', 'Amortecedor traseiro', 'quantidade', 1, 'valor_unitario', 210.00)
    )
  ));

  -- -------------------------------------------------------------
  -- Documentos das motos: um vencido, um a vencer, um regularizado
  -- -------------------------------------------------------------
  insert into documentos_moto (moto_id, tipo, ano_referencia, vencimento, valor, regularizado)
  values (v_moto_cg_disp, 'ipva', extract(year from hoje_br())::int, hoje_br() - 10, 210.50, false);

  insert into documentos_moto (moto_id, tipo, descricao, vencimento, valor, regularizado)
  values (v_moto_biz, 'licenciamento', 'Licenciamento anual CRLV-e', hoje_br() + 20, 130.00, false);

  insert into documentos_moto (moto_id, tipo, descricao, vencimento, valor, regularizado, data_regularizacao)
  values (v_moto_factor, 'seguro', 'Seguro contra roubo/colisão - Apólice 998877', hoje_br() + 200, 890.00, true, hoje_br() - 15);

  insert into documentos_moto (moto_id, tipo, descricao, vencimento, valor, regularizado)
  values (v_moto_fazer_inat, 'vistoria_detran', 'Vistoria para transferência (pendente por sinistro)', hoje_br() + 5, 95.00, false);

  raise notice 'Exemplos cadastrados: 6 motos, 5 clientes, 3 contratos (2 ativos, 1 encerrado).';
end $$;
commit;
