-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar a migration
--   20261112120000_comprovantes_documentos.sql
-- Verifica: o locatário só vê os documentos pendentes das motos dos contratos ativos dele (principal e vinculada); só envia
--   comprovante de documento dele, não regularizado, sem outro envio aguardando e com o arquivo na pasta dele; não lê a tabela
--   de envios; só envia para a própria pasta do Storage; o dono aceita (regulariza e fecha o envio, numa transação) ou recusa
--   (com motivo) e o locatário pode enviar de novo depois de uma recusa.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  dono      uuid;
  u1        uuid := gen_random_uuid();
  u2        uuid := gen_random_uuid();
  estranho  uuid := gen_random_uuid();
  cli1      uuid;
  cli2      uuid;
  moto1     uuid; moto2 uuid; moto3 uuid;
  ct1       uuid;
  doc1      uuid; doc2 uuid; doc3 uuid; doc4 uuid;
  lista     jsonb;
  r         jsonb;
  envio1    uuid;
  n         int;
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'Precisa existir um administrador (dono)';

  insert into auth.users (id, email, created_at) values (u1, 'cpf-um@portal.example.com', now()), (u2, 'cpf-dois@portal.example.com', now());
  insert into clientes (nome, cpf, auth_user_id) values ('Locatario Um', '90000000041', u1) returning id into cli1;
  insert into clientes (nome, cpf, auth_user_id) values ('Locatario Dois', '90000000042', u2) returning id into cli2;
  insert into motos (placa, marca, modelo, km_atual) values ('CMP1A11', 'T', 'Principal', 100) returning id into moto1;
  insert into motos (placa, marca, modelo, km_atual) values ('CMP2B22', 'T', 'Vinculada', 100) returning id into moto2;
  insert into motos (placa, marca, modelo, km_atual) values ('CMP3C33', 'T', 'Do outro', 100) returning id into moto3;
  insert into contratos (moto_id, cliente_id, data_inicio, periodicidade, valor_periodo, km_inicial)
    values (moto1, cli1, hoje_br() - 10, 'semanal', 450, 100) returning id into ct1;
  insert into contrato_motos (contrato_id, moto_id) values (ct1, moto2);
  insert into contratos (moto_id, cliente_id, data_inicio, periodicidade, valor_periodo, km_inicial)
    values (moto3, cli2, hoje_br() - 10, 'semanal', 450, 100);

  insert into documentos_moto (moto_id, tipo, vencimento) values (moto1, 'ipva', hoje_br() - 3) returning id into doc1;
  insert into documentos_moto (moto_id, tipo, vencimento) values (moto2, 'seguro', hoje_br() + 5) returning id into doc2;
  insert into documentos_moto (moto_id, tipo, vencimento) values (moto3, 'ipva', hoje_br() - 1) returning id into doc3;
  insert into documentos_moto (moto_id, tipo, vencimento, regularizado, data_regularizacao) values (moto1, 'licenciamento', hoje_br() - 30, true, hoje_br() - 20) returning id into doc4;

  -- arquivos "enviados" ao Storage (simulados pelo superusuário)
  insert into storage.objects (bucket_id, name) values
    ('documentos', 'portal/' || cli1 || '/a.pdf'), ('documentos', 'portal/' || cli1 || '/b.pdf'),
    ('documentos', 'portal/' || cli2 || '/de-outro.pdf');

  -- quem não é locatário não vê nem envia
  perform set_config('request.jwt.claim.sub', estranho::text, true);
  set local role authenticated;
  begin
    perform rpc_portal_documentos();
    raise exception 'Usuário sem vínculo não deveria listar documentos';
  exception when insufficient_privilege then null;
  end;
  begin
    perform rpc_portal_enviar_comprovante(jsonb_build_object('documento_id', doc1, 'arquivo_path', 'portal/x/a.pdf'));
    raise exception 'Usuário sem vínculo não deveria enviar comprovante';
  exception when insufficient_privilege then null;
  end;
  reset role;

  -- o locatário vê os pendentes das motos dele (principal e vinculada), com a situação certa
  perform set_config('request.jwt.claim.sub', u1::text, true);
  set local role authenticated;
  lista := rpc_portal_documentos();
  reset role;
  assert jsonb_array_length(lista) = 2, 'Deveria ver 2 documentos pendentes: ' || lista::text;
  assert (select count(*) from jsonb_array_elements(lista) x where x->>'documento_id' = doc1::text and x->>'situacao' = 'vencido' and x->>'placa' = 'CMP1A11') = 1, 'IPVA da principal vencido';
  assert (select count(*) from jsonb_array_elements(lista) x where x->>'documento_id' = doc2::text and x->>'situacao' = 'a_vencer') = 1, 'Seguro da vinculada a vencer';
  assert (select count(*) from jsonb_array_elements(lista) x where x->>'documento_id' in (doc3::text, doc4::text)) = 0, 'Não deve ver documento de outro locatário nem regularizado';

  -- o locatário só envia para a própria pasta do Storage
  perform set_config('request.jwt.claim.sub', u1::text, true);
  set local role authenticated;
  insert into storage.objects (bucket_id, name) values ('documentos', 'portal/' || cli1 || '/c.pdf');
  begin
    insert into storage.objects (bucket_id, name) values ('documentos', 'portal/' || cli2 || '/invasor.pdf');
    raise exception 'Não deveria enviar para a pasta de outro locatário';
  exception when insufficient_privilege then null;
  end;
  begin
    insert into storage.objects (bucket_id, name) values ('documentos', cli1 || '/fora-do-portal.pdf');
    raise exception 'Não deveria enviar fora da pasta portal';
  exception when insufficient_privilege then null;
  end;
  reset role;

  -- enviar: as recusas
  perform set_config('request.jwt.claim.sub', u1::text, true);
  set local role authenticated;
  begin
    perform rpc_portal_enviar_comprovante(jsonb_build_object('documento_id', doc3, 'arquivo_path', 'portal/' || cli1 || '/a.pdf'));
    raise exception 'Documento de outro locatário deveria ser recusado';
  exception when others then
    if sqlerrm like 'Documento de outro%' then raise; end if;
    assert sqlerrm = 'Documento não encontrado.', 'Mensagem: ' || sqlerrm;
  end;
  begin
    perform rpc_portal_enviar_comprovante(jsonb_build_object('documento_id', doc4, 'arquivo_path', 'portal/' || cli1 || '/a.pdf'));
    raise exception 'Documento regularizado deveria ser recusado';
  exception when others then
    if sqlerrm like 'Documento regularizado deveria%' then raise; end if;
    assert sqlerrm = 'Documento não encontrado.' or sqlerrm like '%já está regularizado%', 'Mensagem: ' || sqlerrm;
  end;
  begin
    perform rpc_portal_enviar_comprovante(jsonb_build_object('documento_id', doc1, 'arquivo_path', 'portal/' || cli2 || '/de-outro.pdf'));
    raise exception 'Arquivo da pasta de outro deveria ser recusado';
  exception when others then
    if sqlerrm like 'Arquivo da pasta%' then raise; end if;
    assert sqlerrm = 'Arquivo do comprovante inválido.', 'Mensagem: ' || sqlerrm;
  end;
  begin
    perform rpc_portal_enviar_comprovante(jsonb_build_object('documento_id', doc1, 'arquivo_path', 'portal/' || cli1 || '/nao-existe.pdf'));
    raise exception 'Arquivo inexistente deveria ser recusado';
  exception when others then
    if sqlerrm like 'Arquivo inexistente%' then raise; end if;
    assert sqlerrm like 'O arquivo do comprovante não foi encontrado%', 'Mensagem: ' || sqlerrm;
  end;
  begin
    perform rpc_portal_enviar_comprovante(jsonb_build_object('documento_id', doc1, 'arquivo_path', 'portal/' || cli1 || '/a.pdf', 'observacao', repeat('x', 201)));
    raise exception 'Observação longa deveria ser recusada';
  exception when others then
    if sqlerrm like 'Observação longa%' then raise; end if;
    assert sqlerrm like 'A observação pode ter no máximo 200%', 'Mensagem: ' || sqlerrm;
  end;

  -- enviar: o caminho feliz, e um segundo envio enquanto o primeiro aguarda é recusado
  r := rpc_portal_enviar_comprovante(jsonb_build_object('documento_id', doc1, 'arquivo_path', 'portal/' || cli1 || '/a.pdf', 'observacao', '  Paguei hoje  '));
  assert r->>'status' = 'enviado', 'Envio deveria ficar aguardando: ' || r::text;
  envio1 := (r->>'id')::uuid;
  begin
    perform rpc_portal_enviar_comprovante(jsonb_build_object('documento_id', doc1, 'arquivo_path', 'portal/' || cli1 || '/b.pdf'));
    raise exception 'Segundo envio aguardando deveria ser recusado';
  exception when others then
    if sqlerrm like 'Segundo envio%' then raise; end if;
    assert sqlerrm like 'Já existe um comprovante aguardando%', 'Mensagem: ' || sqlerrm;
  end;
  assert (select count(*) from documento_comprovantes) = 0, 'O locatário não deveria ler a tabela de envios';
  update documento_comprovantes set status = 'aceito', conferido_em = now();
  get diagnostics n = row_count;
  assert n = 0, 'O locatário não deveria alterar envios (a RLS esconde a tabela dele)';
  lista := rpc_portal_documentos();
  reset role;
  assert (select x->>'envio_status' from jsonb_array_elements(lista) x where x->>'documento_id' = doc1::text) = 'enviado', 'A lista deveria mostrar o envio aguardando';
  assert (select observacao from documento_comprovantes where id = envio1) = 'Paguei hoje', 'A observação deveria ser aparada';

  -- um segundo pendente no mesmo documento é barrado pelo índice único
  begin
    insert into documento_comprovantes (documento_id, cliente_id, arquivo_path) values (doc1, cli1, 'portal/' || cli1 || '/b.pdf');
    raise exception 'O índice único deveria barrar o segundo envio aguardando';
  exception when unique_violation then null;
  end;

  -- o dono não aceita data futura nem de quem não é dono; o locatário não aceita
  perform set_config('request.jwt.claim.sub', u1::text, true);
  set local role authenticated;
  begin
    perform rpc_aceitar_comprovante_documento(envio1, hoje_br());
    raise exception 'O locatário não deveria aceitar o próprio comprovante';
  exception when insufficient_privilege then null;
  end;
  reset role;

  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  assert (select count(*) from documento_comprovantes) = 1, 'O dono deveria ler os envios';
  begin
    perform rpc_aceitar_comprovante_documento(envio1, hoje_br() + 1);
    raise exception 'Data futura deveria ser recusada';
  exception when others then
    if sqlerrm like 'Data futura%' then raise; end if;
    assert sqlerrm like 'A data de regularização%', 'Mensagem: ' || sqlerrm;
  end;

  -- recusar: só com motivo; depois o locatário envia outro
  begin
    update documento_comprovantes set status = 'recusado', conferido_em = now() where id = envio1;
    raise exception 'Recusa sem motivo deveria ser recusada';
  exception when check_violation then null;
  end;
  update documento_comprovantes set status = 'recusado', motivo_recusa = 'Foto cortada', conferido_em = now() where id = envio1;
  reset role;

  perform set_config('request.jwt.claim.sub', u1::text, true);
  set local role authenticated;
  lista := rpc_portal_documentos();
  assert (select x->>'envio_motivo' from jsonb_array_elements(lista) x where x->>'documento_id' = doc1::text) = 'Foto cortada', 'O locatário deveria ver o motivo da recusa';
  r := rpc_portal_enviar_comprovante(jsonb_build_object('documento_id', doc1, 'arquivo_path', 'portal/' || cli1 || '/b.pdf'));
  reset role;
  assert r->>'status' = 'enviado', 'Depois da recusa o locatário deveria poder enviar de novo';
  envio1 := (r->>'id')::uuid;

  -- aceitar: regulariza o documento com o arquivo do envio e fecha o envio; aceitar de novo é recusado
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  r := rpc_aceitar_comprovante_documento(envio1, hoje_br());
  begin
    perform rpc_aceitar_comprovante_documento(envio1, hoje_br());
    raise exception 'Aceitar duas vezes deveria ser recusado';
  exception when others then
    if sqlerrm like 'Aceitar duas vezes%' then raise; end if;
    assert sqlerrm like 'Este comprovante já foi conferido%', 'Mensagem: ' || sqlerrm;
  end;
  reset role;
  assert r->>'status' = 'aceito', 'Deveria aceitar: ' || r::text;
  assert (select regularizado and data_regularizacao = hoje_br() and arquivo_path = 'portal/' || cli1 || '/b.pdf' from documentos_moto where id = doc1),
    'O documento deveria ficar regularizado com o arquivo do envio';
  select count(*) into n from documento_comprovantes where documento_id = doc1 and status = 'aceito' and conferido_em is not null;
  assert n = 1, 'O envio aceito deveria ter data de conferência';

  -- regularizado, o documento some da lista do locatário
  perform set_config('request.jwt.claim.sub', u1::text, true);
  set local role authenticated;
  lista := rpc_portal_documentos();
  reset role;
  assert (select count(*) from jsonb_array_elements(lista) x where x->>'documento_id' = doc1::text) = 0, 'Documento regularizado sai da lista do locatário';

  raise notice 'Verificação dos comprovantes de documentos: OK';
end $$;
rollback;
