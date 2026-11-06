-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar as migrations
--   20261106120000_whatsapp_base.sql e 20261106130000_whatsapp_leitura.sql
-- Verifica: os controles novos de Configurações (envio desligado e em modo teste por padrão), a leitura
--   `rpc_whatsapp_dados` (cobranças abertas, pagamentos recentes, CNH, documentos e óleo no locatário do
--   contrato ativo, inclusive de moto vinculada), o histórico só com mensagens pendentes ou enviadas e a recusa
--   a quem não é o usuário de serviço nem administrador.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  dono     uuid;
  robo     uuid := gen_random_uuid();
  estranho uuid := gen_random_uuid();
  cli      uuid;
  cli2     uuid;
  moto1    uuid;
  moto2    uuid;
  ct       uuid;
  cobr     uuid;
  doc      uuid;
  item     uuid;
  r        jsonb;
  msg      uuid;
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'Precisa existir um administrador (dono)';

  -- padrões seguros
  assert (select whatsapp_ativo from configuracoes where id = 1) = false, 'O envio deveria nascer desligado';
  assert (select whatsapp_modo_teste from configuracoes where id = 1) = true, 'O envio deveria nascer em modo teste';
  assert (select whatsapp_max_repeticoes from configuracoes where id = 1) = 10, 'Máximo de repetições padrão: 10';
  begin
    update configuracoes set whatsapp_numero_teste = '123' where id = 1;
    raise exception 'Número de teste inválido deveria ser recusado';
  exception when check_violation then null;
  end;

  -- dados de apoio
  insert into clientes (nome, cpf, whatsapp, cnh_validade) values ('Locatario Zap', '90000000011', '(11) 98888-7777', hoje_br() - 3)
    returning id into cli;
  insert into clientes (nome, cpf) values ('Sem Contrato Zap', '90000000012') returning id into cli2;
  insert into motos (placa, marca, modelo, km_atual) values ('ZAP1A11', 'Teste', 'Principal', 1000) returning id into moto1;
  insert into motos (placa, marca, modelo, km_atual) values ('ZAP2B22', 'Teste', 'Vinculada', 1000) returning id into moto2;
  insert into contratos (moto_id, cliente_id, data_inicio, periodicidade, valor_periodo, km_inicial)
    values (moto1, cli, hoje_br() - 20, 'semanal', 450, 1000) returning id into ct;
  insert into contrato_motos (contrato_id, moto_id) values (ct, moto2);

  insert into cobrancas (contrato_id, tipo, numero, vencimento, valor) values (ct, 'locacao', 1, hoje_br() - 2, 450)
    returning id into cobr;
  insert into cobrancas (contrato_id, tipo, numero, vencimento, valor) values (ct, 'locacao', 2, hoje_br() + 30, 450);
  insert into pagamentos (cobranca_id, data_pagamento, valor) values (cobr, hoje_br(), 100);

  -- documento da moto VINCULADA vencido: deve chegar ao locatário do contrato
  insert into documentos_moto (moto_id, tipo, vencimento) values (moto2, 'ipva', hoje_br() - 4) returning id into doc;
  -- documento regularizado não entra
  insert into documentos_moto (moto_id, tipo, vencimento, regularizado) values (moto1, 'seguro', hoje_br() - 4, true);

  -- troca de óleo vencida da moto principal
  select id into item from itens_manutencao where nome ilike 'troca de óleo%' limit 1;
  if item is null then
    insert into itens_manutencao (nome, intervalo_km) values ('Troca de óleo (teste)', 1000) returning id into item;
  end if;
  insert into moto_plano_manutencao (moto_id, item_id, intervalo_km, ultima_km, ultima_data)
    values (moto1, item, 500, 100, hoje_br() - 30)
    on conflict (moto_id, item_id) do update
      set intervalo_km = 500, ultima_km = 100, ultima_data = hoje_br() - 30;

  -- usuário que não é do serviço nem administrador: recusado
  perform set_config('request.jwt.claim.sub', estranho::text, true);
  set local role authenticated;
  begin
    perform rpc_whatsapp_dados(hoje_br());
    raise exception 'Usuário qualquer não deveria ler os dados';
  exception when insufficient_privilege then null;
  end;
  reset role;

  -- o robô lê
  insert into servico_mensagens (user_id) values (robo);
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  r := rpc_whatsapp_dados(hoje_br());
  reset role;

  assert r->'config'->>'ativo' = 'false' and r->'config'->>'modo_teste' = 'true', 'Config do envio errada: ' || (r->'config')::text;
  assert r->'config'->>'multa_atraso' is not null and r->'config'->>'encargo_diario' is not null, 'Faltam os encargos';

  assert (select count(*) from jsonb_array_elements(r->'cobrancas') x where x->>'id' = cobr::text
            and x->>'saldo' = '350.00' and x->>'situacao' = 'atrasada' and x->>'placa' = 'ZAP1A11'
            and x->>'periodicidade' = 'semanal') = 1, 'Cobrança em atraso com saldo de 350 deveria vir';
  assert (select count(*) from jsonb_array_elements(r->'cobrancas') x where (x->>'vencimento')::date = hoje_br() + 30) = 0,
    'Cobrança distante não deveria vir';

  assert (select count(*) from jsonb_array_elements(r->'pagamentos') x
           where x->>'cliente_id' = cli::text and x->>'valor' = '100.00' and x->>'saldo_restante' = '350.00') = 1,
    'Pagamento de hoje deveria vir com o saldo restante';

  assert (select count(*) from jsonb_array_elements(r->'cnhs') x
           where x->>'cliente_id' = cli::text and x->>'situacao' = 'vencida') = 1, 'CNH vencida do locatário deveria vir';

  assert (select count(*) from jsonb_array_elements(r->'documentos') x
           where x->>'id' = doc::text and x->>'cliente_id' = cli::text and x->>'placa' = 'ZAP2B22'
             and x->>'tipo_documento' = 'ipva' and x->>'situacao' = 'vencido') = 1,
    'Documento da moto vinculada deveria ir ao locatário do contrato';
  assert (select count(*) from jsonb_array_elements(r->'documentos') x where x->>'tipo_documento' = 'seguro'
            and x->>'placa' = 'ZAP1A11') = 0, 'Documento regularizado não deveria vir';

  assert (select count(*) from jsonb_array_elements(r->'oleo') x
           where x->>'moto_id' = moto1::text and x->>'cliente_id' = cli::text and x->>'situacao' = 'vencida') = 1,
    'Troca de óleo vencida da moto do locatário deveria vir';

  assert (select count(*) from jsonb_array_elements(r->'clientes') x where x->>'id' = cli2::text) = 1, 'Cliente sem contrato também é listado';

  -- histórico: só pendente e enviada contam
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  perform rpc_whatsapp_enfileirar(jsonb_build_object('mensagens', jsonb_build_array(
    jsonb_build_object('cliente_id', cli, 'numero', '5511988887777', 'texto', 'Atraso',
      'itens', jsonb_build_array(jsonb_build_object('tipo','atraso','referencia_id',cobr,'data_referencia', hoje_br()))))));
  r := rpc_whatsapp_dados(hoje_br());
  assert (select count(*) from jsonb_array_elements(r->'historico') x
           where x->>'tipo' = 'atraso' and x->>'referencia_id' = cobr::text) = 1, 'Pendente deveria constar no histórico';
  reset role;

  select id into msg from mensagens_whatsapp where cliente_id = cli;
  update mensagens_whatsapp set status = 'cancelada', erro = 'teste' where id = msg;
  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  r := rpc_whatsapp_dados(hoje_br());
  reset role;
  assert (select count(*) from jsonb_array_elements(r->'historico') x where x->>'referencia_id' = cobr::text) = 0,
    'Cancelada não deveria constar no histórico';

  -- o administrador também lê
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  assert jsonb_typeof(rpc_whatsapp_dados(hoje_br())->'cobrancas') = 'array', 'O administrador deveria ler';
  reset role;

  raise notice 'Verificação da leitura do WhatsApp: OK';
end $$;
rollback;
