-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar a migration
--   20261112160000_arquivos_orfaos_portal.sql
-- Verifica: só o dono lista; entram os arquivos do portal (bucket trocas_oleo; pasta portal/ do bucket documentos) com mais de N horas
--   e sem nenhuma linha que os referencie; NÃO entram os referenciados (troca, comprovante recusado, documento da moto), os recentes,
--   os placeholders de pasta, os do bucket vistorias nem os arquivos do próprio dono no bucket documentos.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  dono     uuid;
  u1       uuid := gen_random_uuid();
  cli1     uuid;
  moto1    uuid;
  ct1      uuid;
  man1     uuid;
  doc1     uuid; doc2 uuid;
  velho    timestamptz := now() - interval '3 days';
  lista    jsonb;
  caminhos text[];
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'Precisa existir um administrador (dono)';

  insert into auth.users (id, email, created_at) values (u1, 'cpf-orfao@portal.example.com', now());
  insert into clientes (nome, cpf, auth_user_id) values ('Locatario Orfao', '90000000071', u1) returning id into cli1;
  insert into motos (placa, marca, modelo, km_atual) values ('ORF1A11', 'T', 'Teste', 100) returning id into moto1;
  insert into contratos (moto_id, cliente_id, data_inicio, periodicidade, valor_periodo, km_inicial)
    values (moto1, cli1, hoje_br() - 10, 'semanal', 450, 100) returning id into ct1;
  insert into manutencoes (moto_id, tipo, status, data_entrada, km, descricao) values (moto1, 'preventiva', 'concluida', hoje_br(), 100, 'Troca de óleo') returning id into man1;
  insert into trocas_oleo (cliente_id, contrato_id, moto_id, manutencao_id, km, foto_painel_path, nota_fiscal_path)
    values (cli1, ct1, moto1, man1, 100, cli1 || '/ref-painel.jpg', cli1 || '/ref-nota.jpg');
  insert into documentos_moto (moto_id, tipo, vencimento) values (moto1, 'ipva', hoje_br() - 3) returning id into doc1;
  insert into documentos_moto (moto_id, tipo, vencimento, arquivo_path) values (moto1, 'seguro', hoje_br() + 5, 'portal/' || cli1 || '/no-documento.pdf') returning id into doc2;
  insert into documento_comprovantes (documento_id, cliente_id, arquivo_path, status, motivo_recusa, conferido_em)
    values (doc1, cli1, 'portal/' || cli1 || '/recusado.pdf', 'recusado', 'Ilegível', now());

  insert into storage.objects (bucket_id, name, created_at) values
    -- órfãos antigos: devem ser listados
    ('trocas_oleo', cli1 || '/orfa-painel.jpg', velho),
    ('trocas_oleo', cli1 || '/orfa-nota.jpg', velho + interval '1 minute'),
    ('documentos', 'portal/' || cli1 || '/orfao.pdf', velho + interval '2 minutes'),
    -- referenciados: NÃO listar
    ('trocas_oleo', cli1 || '/ref-painel.jpg', velho),
    ('trocas_oleo', cli1 || '/ref-nota.jpg', velho),
    ('documentos', 'portal/' || cli1 || '/recusado.pdf', velho),
    ('documentos', 'portal/' || cli1 || '/no-documento.pdf', velho),
    -- recente, placeholder, bucket das vistorias e arquivo do dono: NÃO listar
    ('trocas_oleo', cli1 || '/recente.jpg', now() - interval '2 hours'),
    ('trocas_oleo', cli1 || '/.emptyFolderPlaceholder', velho),
    ('vistorias', 'qualquer/orfa.jpg', velho),
    ('documentos', 'dono/orfao.pdf', velho);

  -- quem não é o dono não lista (nem o locatário)
  perform set_config('request.jwt.claim.sub', u1::text, true);
  set local role authenticated;
  begin
    perform rpc_listar_arquivos_orfaos(24);
    raise exception 'O locatário não deveria listar arquivos órfãos';
  exception when insufficient_privilege then null;
  end;
  reset role;

  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  begin
    perform rpc_listar_arquivos_orfaos(0);
    raise exception 'Zero hora deveria ser recusado';
  exception when others then
    if sqlerrm like 'Zero hora%' then raise; end if;
    assert sqlerrm like 'Informe pelo menos 1 hora%', 'Mensagem: ' || sqlerrm;
  end;
  lista := rpc_listar_arquivos_orfaos(24);
  reset role;

  select array_agg(x->>'caminho' order by x->>'caminho') into caminhos from jsonb_array_elements(lista) x
   where x->>'caminho' like cli1 || '/%' or x->>'caminho' like 'portal/' || cli1 || '/%' or x->>'caminho' like 'qualquer/%' or x->>'caminho' like 'dono/%';
  assert caminhos = array[cli1 || '/orfa-nota.jpg', cli1 || '/orfa-painel.jpg', 'portal/' || cli1 || '/orfao.pdf'],
    'Só os três órfãos antigos do portal deveriam ser listados: ' || coalesce(caminhos::text, 'nenhum');
  assert (select (x->>'bucket') from jsonb_array_elements(lista) x where x->>'caminho' = 'portal/' || cli1 || '/orfao.pdf') = 'documentos', 'O bucket deveria vir junto';

  -- com um prazo maior que a idade dos arquivos, nada é listado
  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;
  lista := rpc_listar_arquivos_orfaos(24 * 30);
  reset role;
  assert (select count(*) from jsonb_array_elements(lista) x where x->>'caminho' like '%' || cli1 || '%') = 0, 'Com 30 dias de prazo, nenhum arquivo deste roteiro é órfão';

  raise notice 'Verificação dos arquivos órfãos do portal: OK';
end $$;
rollback;
