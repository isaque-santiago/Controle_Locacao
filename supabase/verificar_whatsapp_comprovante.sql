-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar a migration
--   20261112130000_whatsapp_comprovante_enviado.sql
-- Verifica: `rpc_whatsapp_dados` marca `comprovante_enviado` nos documentos com comprovante aguardando conferência, e só nesses
--   (sem envio, aceito ou recusado o campo é falso); o resto da leitura continua vindo.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  robo  uuid := gen_random_uuid();
  cli   uuid;
  moto  uuid;
  doc_a uuid; doc_b uuid; doc_c uuid; doc_d uuid;
  r     jsonb;
begin
  insert into servico_mensagens (user_id) values (robo);
  insert into clientes (nome, cpf, whatsapp) values ('Locatario Comprovante', '90000000051', '(11) 98888-7777') returning id into cli;
  insert into motos (placa, marca, modelo, km_atual) values ('WZC1A11', 'T', 'Moto', 100) returning id into moto;
  insert into contratos (moto_id, cliente_id, data_inicio, periodicidade, valor_periodo, km_inicial)
    values (moto, cli, hoje_br() - 10, 'semanal', 450, 100);
  insert into documentos_moto (moto_id, tipo, vencimento) values (moto, 'ipva', hoje_br() - 3) returning id into doc_a;
  insert into documentos_moto (moto_id, tipo, vencimento) values (moto, 'seguro', hoje_br() - 2) returning id into doc_b;
  insert into documentos_moto (moto_id, tipo, vencimento) values (moto, 'licenciamento', hoje_br() - 1) returning id into doc_c;
  insert into documentos_moto (moto_id, tipo, vencimento) values (moto, 'outro', hoje_br() + 3) returning id into doc_d;

  insert into documento_comprovantes (documento_id, cliente_id, arquivo_path, status)
    values (doc_a, cli, 'portal/' || cli || '/a.pdf', 'enviado');
  insert into documento_comprovantes (documento_id, cliente_id, arquivo_path, status, motivo_recusa, conferido_em)
    values (doc_b, cli, 'portal/' || cli || '/b.pdf', 'recusado', 'Foto cortada', now());
  insert into documento_comprovantes (documento_id, cliente_id, arquivo_path, status, conferido_em)
    values (doc_c, cli, 'portal/' || cli || '/c.pdf', 'aceito', now());

  perform set_config('request.jwt.claim.sub', robo::text, true);
  set local role authenticated;
  r := rpc_whatsapp_dados(hoje_br());
  reset role;

  assert (select (x->>'comprovante_enviado')::boolean from jsonb_array_elements(r->'documentos') x where x->>'id' = doc_a::text) = true,
    'Documento com comprovante aguardando deveria vir marcado';
  assert (select (x->>'comprovante_enviado')::boolean from jsonb_array_elements(r->'documentos') x where x->>'id' = doc_b::text) = false,
    'Comprovante recusado não pausa o aviso';
  assert (select (x->>'comprovante_enviado')::boolean from jsonb_array_elements(r->'documentos') x where x->>'id' = doc_d::text) = false,
    'Documento sem envio não vem marcado';
  assert (select (x->>'comprovante_enviado')::boolean from jsonb_array_elements(r->'documentos') x where x->>'id' = doc_c::text) = false,
    'Comprovante já aceito não pausa o aviso';
  assert jsonb_typeof(r->'cobrancas') = 'array' and jsonb_typeof(r->'portal') = 'array' and jsonb_typeof(r->'clientes') = 'array',
    'O resto da leitura deveria continuar vindo';

  raise notice 'Verificação do comprovante enviado no WhatsApp: OK';
end $$;
rollback;
