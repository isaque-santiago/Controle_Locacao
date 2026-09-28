-- Roteiro de verificação da Fase 7 (portal do locatário).
-- Executar no SQL Editor do projeto de HOMOLOGAÇÃO/dev, após todas as migrations e seed.sql
-- (o seed traz o item "Troca de óleo do motor"). Tudo é desfeito ao final (rollback).
-- Cria um usuário de teste em auth.users só dentro da transação.
begin;

do $$
declare
  v_user uuid := gen_random_uuid();
  v_moto uuid; v_cliente uuid; v_outro uuid; v_contrato jsonb; v_item uuid;
begin
  insert into auth.users (id, email) values (v_user, 'locatario.teste@example.com');
  insert into motos (placa, marca, modelo, km_atual) values ('TST8P88', 'Teste', 'Teste', 5000) returning id into v_moto;
  insert into clientes (nome, cpf, auth_user_id, senha_provisoria) values ('Locatário Teste', '00000000001', v_user, true) returning id into v_cliente;
  insert into clientes (nome, cpf) values ('Outro Cliente', '00000000002') returning id into v_outro;
  v_contrato := rpc_criar_contrato(jsonb_build_object('moto_id', v_moto, 'cliente_id', v_cliente,
    'data_inicio', hoje_br(), 'periodicidade', 'semanal', 'valor_periodo', 100, 'km_inicial', 5000));
  update configuracoes set multa_troca_oleo_valor = 50 where id = 1;
  v_item := item_troca_oleo_id();
  -- baseline do plano: última troca aos 5000 km, intervalo do catálogo (1000 km)
  update moto_plano_manutencao set ultima_km = 5000, ultima_data = hoje_br()
   where moto_id = v_moto and item_id = v_item;
  -- arquivos "enviados" ao Storage: 2 do cliente e 1 de outro cliente
  insert into storage.objects (bucket_id, name) values
    ('trocas_oleo', v_cliente || '/painel1.png'), ('trocas_oleo', v_cliente || '/nota1.png'),
    ('trocas_oleo', v_cliente || '/painel2.png'), ('trocas_oleo', v_cliente || '/nota2.png'),
    ('trocas_oleo', v_outro   || '/painel.png');
  perform set_config('teste.user', v_user::text, true);
  perform set_config('teste.cliente', v_cliente::text, true);
  perform set_config('teste.outro', v_outro::text, true);
  perform set_config('teste.contrato', v_contrato->>'contrato_id', true);
  perform set_config('teste.moto', v_moto::text, true);
end $$;

-- A partir daqui as consultas rodam COMO o locatário (papel authenticated + JWT dele).
select set_config('request.jwt.claim.sub', current_setting('teste.user'), true);
select set_config('request.jwt.claims',
  json_build_object('sub', current_setting('teste.user'), 'role', 'authenticated')::text, true);
set local role authenticated;

do $$
declare
  v_cliente text := current_setting('teste.cliente');
  v_contrato text := current_setting('teste.contrato');
  r jsonb;
begin
  assert rpc_meu_papel() = 'locatario', 'Papel do locatário incorreto';

  r := rpc_portal_locatario();
  assert jsonb_array_length(r->'contratos') = 1, 'Portal deveria listar 1 contrato ativo';
  assert (r->'contratos'->0->>'km_atual')::int = 5000, 'Km da moto incorreto no portal';

  assert (r->>'trocar_senha')::boolean = true, 'Senha provisória deveria estar pendente';

  -- com a senha provisória pendente, não registra troca
  begin
    perform rpc_registrar_troca_oleo_locatario(jsonb_build_object('contrato_id', v_contrato, 'km', 5500,
      'foto_painel_path', v_cliente || '/painel1.png', 'nota_fiscal_path', v_cliente || '/nota1.png'));
    raise exception using errcode = 'ZX000', message = 'Troca aceita com senha provisória';
  exception when raise_exception then null;
  end;
  perform rpc_confirmar_troca_senha();
  assert (rpc_portal_locatario()->>'trocar_senha')::boolean = false, 'Troca de senha não confirmada';

  -- RLS: o locatário não lê nenhuma tabela diretamente
  assert (select count(*) from clientes) = 0, 'Locatário enxergou clientes';
  assert (select count(*) from contratos) = 0, 'Locatário enxergou contratos';
  assert (select count(*) from motos) = 0, 'Locatário enxergou motos';
  assert (select count(*) from cobrancas) = 0, 'Locatário enxergou cobranças';

  -- km menor que o atual
  begin
    perform rpc_registrar_troca_oleo_locatario(jsonb_build_object('contrato_id', v_contrato, 'km', 4999,
      'foto_painel_path', v_cliente || '/painel1.png', 'nota_fiscal_path', v_cliente || '/nota1.png'));
    raise exception using errcode = 'ZX001', message = 'Km regredido foi aceito';
  exception when raise_exception then null;
  end;

  -- arquivo de outro cliente
  begin
    perform rpc_registrar_troca_oleo_locatario(jsonb_build_object('contrato_id', v_contrato, 'km', 5500,
      'foto_painel_path', current_setting('teste.outro') || '/painel.png', 'nota_fiscal_path', v_cliente || '/nota1.png'));
    raise exception using errcode = 'ZX002', message = 'Arquivo de outro cliente foi aceito';
  exception when raise_exception then null;
  end;

  -- arquivo inexistente no Storage
  begin
    perform rpc_registrar_troca_oleo_locatario(jsonb_build_object('contrato_id', v_contrato, 'km', 5500,
      'foto_painel_path', v_cliente || '/nao_existe.png', 'nota_fiscal_path', v_cliente || '/nota1.png'));
    raise exception using errcode = 'ZX003', message = 'Arquivo inexistente foi aceito';
  exception when raise_exception then null;
  end;

  -- dentro do intervalo (5500 <= 6000): registra, sem multa
  r := rpc_registrar_troca_oleo_locatario(jsonb_build_object('contrato_id', v_contrato, 'km', 5500,
    'foto_painel_path', v_cliente || '/painel1.png', 'nota_fiscal_path', v_cliente || '/nota1.png'));
  assert (r->>'excedeu')::boolean = false, 'Não deveria exceder o intervalo';
  assert r->'multa_valor' = 'null'::jsonb, 'Não deveria gerar multa';

  -- mesmo hodômetro de novo: duplicado
  begin
    perform rpc_registrar_troca_oleo_locatario(jsonb_build_object('contrato_id', v_contrato, 'km', 5500,
      'foto_painel_path', v_cliente || '/painel2.png', 'nota_fiscal_path', v_cliente || '/nota2.png'));
    raise exception using errcode = 'ZX004', message = 'Troca duplicada foi aceita';
  exception when raise_exception then null;
  end;

  -- 6501 > 5500 + 1000: passou do intervalo => multa fixa de 50
  r := rpc_registrar_troca_oleo_locatario(jsonb_build_object('contrato_id', v_contrato, 'km', 6501,
    'foto_painel_path', v_cliente || '/painel2.png', 'nota_fiscal_path', v_cliente || '/nota2.png'));
  assert (r->>'excedeu')::boolean = true, 'Deveria exceder o intervalo';
  assert (r->>'km_excedente')::int = 1, 'Km excedente incorreto';
  assert (r->>'multa_valor')::numeric = 50, 'Multa fixa incorreta';
end $$;

reset role;

do $$
declare v_contrato uuid := current_setting('teste.contrato')::uuid; v_moto uuid := current_setting('teste.moto')::uuid;
begin
  assert (select count(*) from cobrancas where contrato_id = v_contrato and tipo = 'multa_manutencao' and valor = 50) = 1,
    'Cobrança multa_manutencao não foi criada';
  assert (select count(*) from trocas_oleo where contrato_id = v_contrato) = 2, 'Trocas não gravadas';
  assert (select count(*) from manutencoes where moto_id = v_moto and tipo = 'preventiva' and status = 'concluida') = 2,
    'Manutenções não gravadas';
  assert (select km_atual from motos where id = v_moto) = 6501, 'Km da moto não atualizado';
  assert (select ultima_km from moto_plano_manutencao where moto_id = v_moto and item_id = item_troca_oleo_id()) = 6501,
    'Plano de óleo não reiniciado';
  raise notice 'Portal do locatário verificado.';
end $$;

rollback;
