-- Executar no SQL Editor de DESENVOLVIMENTO após aplicar a migration
--   20261112140000_cancelar_cobranca.sql
-- Verifica: só o dono cancela; o motivo é obrigatório (3 a 200 caracteres); cobrança em aberto e sem pagamento é cancelada
--   (com motivo e data) e passa a `cancelada` em vw_cobrancas; cobrança com pagamento, paga, já cancelada ou inexistente é recusada.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  dono     uuid;
  u1       uuid := gen_random_uuid();
  estranho uuid := gen_random_uuid();
  cli1     uuid;
  moto1    uuid;
  ct1      uuid;
  c_livre  uuid;
  c_parc   uuid;
  c_paga   uuid;
  r        jsonb;
begin
  select user_id into dono from administradores order by criado_em limit 1;
  assert dono is not null, 'Precisa existir um administrador (dono)';

  insert into auth.users (id, email, created_at) values (u1, 'cpf-canc@portal.example.com', now());
  insert into clientes (nome, cpf, auth_user_id) values ('Locatario Cancela', '90000000051', u1) returning id into cli1;
  insert into motos (placa, marca, modelo, km_atual) values ('CAN1A11', 'T', 'Teste', 100) returning id into moto1;
  insert into contratos (moto_id, cliente_id, data_inicio, periodicidade, valor_periodo, km_inicial)
    values (moto1, cli1, hoje_br() - 10, 'semanal', 450, 100) returning id into ct1;

  insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao) values (ct1, 'multa_transito', hoje_br() + 3, 200, 'Sem pagamento') returning id into c_livre;
  insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao) values (ct1, 'dano', hoje_br() - 2, 300, 'Com pagamento parcial') returning id into c_parc;
  insert into cobrancas (contrato_id, tipo, vencimento, valor, descricao) values (ct1, 'outros', hoje_br() - 5, 100, 'Paga') returning id into c_paga;
  insert into pagamentos (cobranca_id, data_pagamento, valor) values (c_parc, hoje_br(), 100), (c_paga, hoje_br(), 100);
  assert (select status from cobrancas where id = c_paga) = 'paga', 'O gatilho deveria marcar a cobrança como paga';

  -- quem não é o dono não cancela (nem o locatário)
  foreach r in array array[to_jsonb(estranho), to_jsonb(u1)] loop
    perform set_config('request.jwt.claim.sub', trim(both '"' from r::text), true);
    set local role authenticated;
    begin
      perform rpc_cancelar_cobranca(c_livre, 'Lançada por engano');
      raise exception 'Quem não é dono não deveria cancelar';
    exception when insufficient_privilege then null;
    end;
    reset role;
  end loop;
  assert (select status from cobrancas where id = c_livre) = 'aberta', 'A cobrança não deveria ter sido cancelada';

  perform set_config('request.jwt.claim.sub', dono::text, true);
  set local role authenticated;

  -- motivo obrigatório (vazio, só espaços, curto e longo demais)
  begin perform rpc_cancelar_cobranca(c_livre, null); raise exception 'Motivo nulo deveria ser recusado';
  exception when others then if sqlerrm like 'Motivo nulo%' then raise; end if; assert sqlerrm like 'Informe o motivo%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_cancelar_cobranca(c_livre, '   '); raise exception 'Motivo em branco deveria ser recusado';
  exception when others then if sqlerrm like 'Motivo em branco%' then raise; end if; assert sqlerrm like 'Informe o motivo%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_cancelar_cobranca(c_livre, 'ab'); raise exception 'Motivo curto deveria ser recusado';
  exception when others then if sqlerrm like 'Motivo curto%' then raise; end if; assert sqlerrm like 'Informe o motivo%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_cancelar_cobranca(c_livre, repeat('x', 201)); raise exception 'Motivo longo deveria ser recusado';
  exception when others then if sqlerrm like 'Motivo longo%' then raise; end if; assert sqlerrm like '%no máximo 200%', 'Mensagem: ' || sqlerrm; end;

  -- com pagamento (parcial), paga e inexistente: recusadas, e nada muda
  begin perform rpc_cancelar_cobranca(c_parc, 'Contestada'); raise exception 'Cobrança com pagamento deveria ser recusada';
  exception when others then if sqlerrm like 'Cobrança com pagamento%' then raise; end if; assert sqlerrm like '%já tem pagamento registrado%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_cancelar_cobranca(c_paga, 'Contestada'); raise exception 'Cobrança paga deveria ser recusada';
  exception when others then if sqlerrm like 'Cobrança paga deveria%' then raise; end if; assert sqlerrm like '%paga não pode ser cancelada%', 'Mensagem: ' || sqlerrm; end;
  begin perform rpc_cancelar_cobranca(gen_random_uuid(), 'Contestada'); raise exception 'Inexistente deveria ser recusada';
  exception when others then if sqlerrm like 'Inexistente%' then raise; end if; assert sqlerrm like 'Cobrança não encontrada%', 'Mensagem: ' || sqlerrm; end;

  -- o caminho feliz: cobrança em aberto e sem pagamento
  r := rpc_cancelar_cobranca(c_livre, '  Multa lançada por engano  ');
  assert r->>'status' = 'cancelada', 'Deveria cancelar: ' || r::text;
  assert (select situacao from vw_cobrancas where id = c_livre) = 'cancelada', 'A view deveria mostrar cancelada';

  -- cancelar de novo é recusado
  begin perform rpc_cancelar_cobranca(c_livre, 'De novo'); raise exception 'Cancelar duas vezes deveria ser recusado';
  exception when others then if sqlerrm like 'Cancelar duas vezes%' then raise; end if; assert sqlerrm like 'Esta cobrança já está cancelada%', 'Mensagem: ' || sqlerrm; end;
  reset role;

  assert (select status = 'cancelada' and motivo_cancelamento = 'Multa lançada por engano' and cancelada_em is not null from cobrancas where id = c_livre),
    'Deveria guardar o motivo (sem os espaços das pontas) e a data do cancelamento';
  assert (select status = 'aberta' and motivo_cancelamento is null from cobrancas where id = c_parc), 'A cobrança com pagamento não pode ter mudado';

  raise notice 'Verificação do cancelamento de cobrança: OK';
end $$;
rollback;
