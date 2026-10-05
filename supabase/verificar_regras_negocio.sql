-- Executar no SQL Editor de HOMOLOGAÇÃO após aplicar as migrations
--   20261005120000_encargos_fixos.sql
--   20261005130000_contrato_indeterminado.sql
--   20261005140000_caucao_danos.sql
-- Verifica as decisões de negócio da seção 14 do plano que dependem do banco:
--   14.1 parâmetros fixos de encargo em `configuracoes` (o cálculo em si é testado em pytest);
--   14.2 caução + primeira semana vencendo na data de início;
--   14.3 danos descontados da caução, com cobrança do excedente;
--   14.4 contrato por prazo indeterminado e janela móvel de cobranças.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  cliente uuid; moto1 uuid; moto2 uuid; moto3 uuid;
  c1 jsonb; c2 jsonb; c3 jsonb;
  caucao uuid; r jsonb; n int;
begin
  -- 14.1: parâmetros de encargo existem e os percentuais/carência foram removidos
  assert (select multa_atraso_valor from configuracoes where id = 1) is not null, 'multa_atraso_valor ausente';
  assert (select encargo_diario_valor from configuracoes where id = 1) is not null, 'encargo_diario_valor ausente';
  assert not exists (
    select 1 from information_schema.columns
     where table_name = 'configuracoes'
       and column_name in ('multa_atraso_percentual', 'juros_mensal_percentual', 'carencia_dias')
  ), 'Colunas antigas de encargo ainda existem';

  insert into clientes(nome, cpf) values ('Teste regras de negocio', '00000000001') returning id into cliente;
  insert into motos(placa, marca, modelo, km_atual) values ('TST8Z88', 'Teste', 'Teste', 100) returning id into moto1;
  insert into motos(placa, marca, modelo, km_atual) values ('TST7Z77', 'Teste', 'Teste', 100) returning id into moto2;
  insert into motos(placa, marca, modelo, km_atual) values ('TST6Z66', 'Teste', 'Teste', 100) returning id into moto3;

  -- 14.4 + 14.2: contrato indeterminado (sem data final), semanal, caução + 1ª semana na data de início
  c1 := rpc_criar_contrato_com_vistoria(jsonb_build_object('moto_id', moto1, 'cliente_id', cliente,
    'data_inicio', hoje_br(), 'data_fim_prevista', null::text, 'periodicidade', 'semanal',
    'valor_periodo', 350, 'caucao_valor', 1000, 'km_inicial', 100), '{"km":100,"checklist":{"farol":"ok"}}');
  assert (select data_fim_prevista from contratos where id = (c1->>'contrato_id')::uuid) is null,
    'Contrato indeterminado ficou com data final';
  assert (select count(*) from cobrancas where contrato_id = (c1->>'contrato_id')::uuid and tipo = 'locacao') = 5,
    'Janela inicial de 30 dias deveria ter 5 cobranças semanais';
  assert (select vencimento from cobrancas where contrato_id = (c1->>'contrato_id')::uuid and tipo = 'locacao' and numero = 1) = hoje_br(),
    '1ª semana não vence na data de início';
  select id into caucao from cobrancas where contrato_id = (c1->>'contrato_id')::uuid and tipo = 'caucao';
  assert caucao is not null, 'Cobrança da caução não gerada';
  assert (select vencimento from cobrancas where id = caucao) = hoje_br(), 'Caução não vence na data de início';

  -- 14.4: janela móvel é idempotente
  perform rpc_gerar_cobrancas_pendentes(60);
  select count(*) into n from cobrancas where contrato_id = (c1->>'contrato_id')::uuid and tipo = 'locacao';
  assert n = 9, 'Janela de 60 dias deveria ter 9 cobranças semanais, veio ' || n;
  perform rpc_gerar_cobrancas_pendentes(60);
  assert (select count(*) from cobrancas where contrato_id = (c1->>'contrato_id')::uuid and tipo = 'locacao') = n,
    'rpc_gerar_cobrancas_pendentes duplicou cobranças';

  -- 14.3: validações do encerramento (o contrato continua ativo após cada recusa)
  insert into pagamentos(cobranca_id, data_pagamento, valor) values (caucao, hoje_br(), 1000);
  begin
    perform rpc_encerrar_contrato_com_vistoria((c1->>'contrato_id')::uuid, hoje_br(),
      '{"km":150,"checklist":{"farol":"avaria"}}', 50, null);
    raise exception using errcode = 'ZX101', message = 'Dano sem descrição foi aceito';
  exception when raise_exception then null;
  end;
  begin
    perform rpc_encerrar_contrato_com_vistoria((c1->>'contrato_id')::uuid, hoje_br(),
      '{"km":150,"checklist":{"farol":"avaria"}}', -1, 'x');
    raise exception using errcode = 'ZX102', message = 'Dano negativo foi aceito';
  exception when raise_exception then null;
  end;
  assert (select status from contratos where id = (c1->>'contrato_id')::uuid) = 'ativo', 'Encerramento recusado alterou o contrato';

  -- 14.3: dano menor que a caução (caução 1.000, dano 300 -> devolve 700)
  r := rpc_encerrar_contrato_com_vistoria((c1->>'contrato_id')::uuid, hoje_br(),
    '{"km":150,"checklist":{"farol":"avaria"}}', 300, 'Retrovisor quebrado');
  assert (r->>'caucao_paga')::numeric = 1000, 'Caução paga incorreta';
  assert (r->>'caucao_desconto_danos')::numeric = 300, 'Desconto incorreto';
  assert (r->>'caucao_valor_devolvido')::numeric = 700, 'Devolução incorreta';
  assert (r->>'dano_excedente')::numeric = 0, 'Não deveria haver excedente';
  assert (select caucao_devolvida from contratos where id = (c1->>'contrato_id')::uuid), 'caucao_devolvida deveria ser true';
  assert (select caucao_valor_devolvido from contratos where id = (c1->>'contrato_id')::uuid) = 700, 'Devolução não gravada';
  assert (select descricao_danos from contratos where id = (c1->>'contrato_id')::uuid) = 'Retrovisor quebrado', 'Descrição não gravada';
  assert not exists (select 1 from cobrancas where contrato_id = (c1->>'contrato_id')::uuid and tipo = 'dano'),
    'Dano menor que a caução não deveria gerar cobrança';

  -- 14.3: dano maior que a caução (caução 1.000, dano 1.300 -> devolve 0 e cobra 300)
  c2 := rpc_criar_contrato_com_vistoria(jsonb_build_object('moto_id', moto2, 'cliente_id', cliente,
    'data_inicio', hoje_br(), 'periodicidade', 'semanal', 'valor_periodo', 350, 'caucao_valor', 1000,
    'km_inicial', 100), '{"km":100,"checklist":{"farol":"ok"}}');
  select id into caucao from cobrancas where contrato_id = (c2->>'contrato_id')::uuid and tipo = 'caucao';
  insert into pagamentos(cobranca_id, data_pagamento, valor) values (caucao, hoje_br(), 1000);
  r := rpc_encerrar_contrato_com_vistoria((c2->>'contrato_id')::uuid, hoje_br(),
    '{"km":150,"checklist":{"farol":"avaria"}}', 1300, 'Moto tombada');
  assert (r->>'caucao_valor_devolvido')::numeric = 0, 'Nada deveria ser devolvido';
  assert (r->>'caucao_desconto_danos')::numeric = 1000, 'A caução toda deveria ser retida';
  assert (r->>'dano_excedente')::numeric = 300, 'Excedente incorreto';
  assert not (select caucao_devolvida from contratos where id = (c2->>'contrato_id')::uuid), 'caucao_devolvida deveria ser false';
  assert (select valor from cobrancas where contrato_id = (c2->>'contrato_id')::uuid and tipo = 'dano' and status = 'aberta') = 300,
    'Cobrança do excedente não foi criada';

  -- 14.3: caução não recebida não se devolve (dano de 200 vira cobrança integral)
  c3 := rpc_criar_contrato_com_vistoria(jsonb_build_object('moto_id', moto3, 'cliente_id', cliente,
    'data_inicio', hoje_br(), 'periodicidade', 'semanal', 'valor_periodo', 350, 'caucao_valor', 1000,
    'km_inicial', 100), '{"km":100,"checklist":{"farol":"ok"}}');
  r := rpc_encerrar_contrato_com_vistoria((c3->>'contrato_id')::uuid, hoje_br(),
    '{"km":150,"checklist":{"farol":"ok"}}', 200, 'Risco no tanque');
  assert (r->>'caucao_paga')::numeric = 0, 'Caução não paga foi considerada';
  assert (r->>'caucao_valor_devolvido')::numeric = 0, 'Devolveu caução que não foi recebida';
  assert (r->>'dano_excedente')::numeric = 200, 'Excedente deveria ser o dano inteiro';

  -- Encerramento sem informar danos continua funcionando (caução toda devolvida)
  -- (coberto por verificar_fluxos.sql, que chama a RPC com 3 argumentos)

  raise notice 'Encargos fixos, contrato indeterminado, caução e danos verificados.';
end $$;
rollback;
