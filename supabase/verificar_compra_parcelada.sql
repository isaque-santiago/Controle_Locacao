-- Executar no SQL Editor de DESENVOLVIMENTO (nunca em produção) após aplicar a migration
--   20261103130000_compra_parcelada.sql
-- Verifica a compra a prazo como dívida (Celta: entrada de R$ 5.000 + 9 parcelas mensais de R$ 1.000):
--   calendário, parcelas pagas, saldo, pagamento de parcela (parcial e total) e restrições.
-- Todas as alterações deste roteiro são desfeitas ao final (ROLLBACK).
begin;
do $$
declare
  r jsonb; d uuid; p7 uuid; p8 uuid; pg jsonb; n int;
begin
  -- Celta: entrada 5.000 + 9 x 1.000, primeira parcela em 28/05/2026, 6 parcelas já pagas
  r := rpc_criar_compra_parcelada(jsonb_build_object('credor', 'Celta (teste)', 'valor_total', 14000, 'valor_entrada', 5000,
    'numero_parcelas', 9, 'valor_parcela', 1000, 'primeira_parcela', '2026-05-28', 'data_entrada', '2026-05-01', 'parcelas_pagas', 6));
  d := (r->>'divida_id')::uuid;
  assert (r->>'parcelas')::int = 9 and (r->>'saldo')::numeric = 3000, 'Resposta incorreta: ' || r::text;
  assert (select count(*) from dividas_vencimentos where divida_id = d) = 9, 'Deveriam existir 9 parcelas';
  assert (select vencimento from dividas_vencimentos where divida_id = d and numero = 1) = date '2026-05-28', 'Primeira parcela incorreta';
  assert (select vencimento from dividas_vencimentos where divida_id = d and numero = 7) = date '2026-11-28', 'Sétima parcela incorreta';
  assert (select vencimento from dividas_vencimentos where divida_id = d and numero = 9) = date '2027-01-28', 'Última parcela incorreta';
  assert (select count(*) from dividas_vencimentos where divida_id = d and paga_em is not null) = 6, 'Deveriam existir 6 parcelas pagas';
  assert (select saldo_calculado from vw_saldo_dividas where divida_id = d) = 3000, 'Saldo calculado incorreto';
  assert (select dia_vencimento from dividas where id = d) = 28, 'Dia de vencimento incorreto';
  assert (select count(*) from pagamentos_divida where divida_id = d and data_estimada) = 6, 'As 6 parcelas pagas deveriam ter data estimada';
  assert (select count(*) from pagamentos_divida where divida_id = d and vencimento_id is null and valor = 5000 and data = date '2026-05-01' and not data_estimada) = 1, 'Entrada incorreta';
  assert (select count(*) from vw_parcelas_divida where divida_id = d and situacao = 'paga') = 6, 'A view deveria mostrar 6 parcelas pagas';
  assert (select count(*) from vw_parcelas_divida where divida_id = d and situacao in ('atrasada', 'a_vencer')) = 3, 'A view deveria mostrar 3 parcelas em aberto';

  -- Pagamento parcial e depois do resto
  select id into p7 from dividas_vencimentos where divida_id = d and numero = 7;
  pg := rpc_pagar_parcela_divida(p7, date '2026-11-28', 400, null, 'metade');
  assert not (pg->>'parcela_paga')::boolean and (pg->>'saldo_da_parcela')::numeric = 600, 'Pagamento parcial incorreto';
  assert (select paga_em from dividas_vencimentos where id = p7) is null, 'Parcela parcial não pode estar paga';
  assert (select valor_pago from vw_parcelas_divida where vencimento_id = p7) = 400, 'valor_pago incorreto';
  pg := rpc_pagar_parcela_divida(p7, date '2026-12-01');
  assert (pg->>'parcela_paga')::boolean, 'O resto deveria quitar a parcela';
  assert (select paga_em from dividas_vencimentos where id = p7) = date '2026-12-01', 'paga_em deveria ser a data do último pagamento';
  assert (select saldo_calculado from vw_saldo_dividas where divida_id = d) = 2000, 'Saldo depois de pagar a parcela 7 incorreto';

  -- Recusas
  begin
    perform rpc_pagar_parcela_divida(p7, date '2026-12-02');
    raise exception using errcode = 'ZX401', message = 'Pagou parcela já quitada';
  exception when raise_exception then null;
  end;
  select id into p8 from dividas_vencimentos where divida_id = d and numero = 8;
  begin
    perform rpc_pagar_parcela_divida(p8, date '2026-12-28', 1500);
    raise exception using errcode = 'ZX402', message = 'Pagou mais que o saldo da parcela';
  exception when raise_exception then null;
  end;
  begin
    insert into pagamentos_divida(divida_id, vencimento_id, data, valor) values (d, p8, date '2026-12-28', 1200);
    raise exception using errcode = 'ZX403', message = 'O gatilho aceitou pagamento acima do saldo da parcela';
  exception when raise_exception then null;
  end;
  begin
    perform rpc_criar_compra_parcelada(jsonb_build_object('credor', 'X', 'valor_total', 9999, 'valor_entrada', 5000,
      'numero_parcelas', 9, 'valor_parcela', 1000, 'primeira_parcela', '2026-05-28'));
    raise exception using errcode = 'ZX404', message = 'Total que não fecha foi aceito';
  exception when raise_exception then null;
  end;
  begin
    perform rpc_criar_compra_parcelada(jsonb_build_object('credor', 'X', 'valor_total', 9000, 'numero_parcelas', 9,
      'valor_parcela', 1000, 'primeira_parcela', '2026-05-28', 'parcelas_pagas', 10));
    raise exception using errcode = 'ZX405', message = 'Parcelas pagas acima do número de parcelas foi aceito';
  exception when raise_exception then null;
  end;
  begin
    insert into dividas(tipo, credor, valor_original, numero_parcelas, valor_parcela, primeira_parcela, valor_entrada)
    values ('compra_parcelada', 'Direta', 1, 9, 1000, date '2026-05-28', 0);
    raise exception using errcode = 'ZX406', message = 'A restrição ck_dividas_compra_parcelada não barrou o total inconsistente';
  exception when check_violation then null;
  end;

  -- Mês curto: parcelas a partir de 31/01 mantêm o dia 31 quando o mês permite
  r := rpc_criar_compra_parcelada(jsonb_build_object('credor', 'Mes curto', 'valor_total', 3000, 'numero_parcelas', 3,
    'valor_parcela', 1000, 'primeira_parcela', '2026-01-31'));
  assert (select array_agg(vencimento order by numero) from dividas_vencimentos where divida_id = (r->>'divida_id')::uuid)
       = array[date '2026-01-31', date '2026-02-28', date '2026-03-31'], 'Calendário de mês curto incorreto';

  -- Um pagamento apagado reabre a parcela
  delete from pagamentos_divida where vencimento_id = p7;
  assert (select paga_em from dividas_vencimentos where id = p7) is null, 'Apagar os pagamentos deveria reabrir a parcela';

  raise notice 'Verificação da compra parcelada: OK';
end $$;
rollback;
