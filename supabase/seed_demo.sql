-- Execute somente em um projeto de demonstração, após migrations e seed.sql.
-- Reexecução não duplica o cenário identificado pela placa DEM1A23.
begin;
do $$
declare moto uuid; cliente uuid; contrato jsonb; parcela uuid;
begin
  if exists(select 1 from motos where placa = 'DEM1A23') then return; end if;
  insert into motos(placa, marca, modelo, km_atual, valor_locacao_sugerido)
  values ('DEM1A23', 'Demonstração', 'Moto de exemplo', 10000, 250) returning id into moto;
  insert into clientes(nome, cpf, telefone, cnh_categoria, cnh_validade)
  values ('Cliente fictício de demonstração', '52998224725', '11999999999', 'A', hoje_br() + 20)
  on conflict(cpf) do nothing returning id into cliente;
  if cliente is null then raise exception 'CPF de demonstração já existe. Use um projeto de demonstração vazio.'; end if;
  contrato := rpc_criar_contrato_com_vistoria(jsonb_build_object(
    'moto_id', moto, 'cliente_id', cliente, 'data_inicio', hoje_br() - 14,
    'data_fim_prevista', hoje_br() + 30, 'periodicidade', 'semanal',
    'valor_periodo', 250, 'caucao_valor', 500, 'km_inicial', 10000
  ), jsonb_build_object('km', 10000, 'nivel_combustivel', 'cheio', 'checklist', '{"farol_dianteiro":"ok"}'::jsonb));
  select id into parcela from cobrancas where contrato_id = (contrato->>'contrato_id')::uuid and tipo = 'locacao' and numero = 1;
  insert into pagamentos(cobranca_id, data_pagamento, valor) values(parcela, hoje_br() - 14, 250);
  select id into parcela from cobrancas where contrato_id = (contrato->>'contrato_id')::uuid and tipo = 'locacao' and numero = 2;
  insert into pagamentos(cobranca_id, data_pagamento, valor) values(parcela, hoje_br() - 7, 100);
  insert into documentos_moto(moto_id, tipo, ano_referencia, vencimento, valor)
  values (moto, 'ipva', extract(year from hoje_br())::int, hoje_br() - 1, 180);
  insert into historico_km(moto_id, km) values(moto, 11000);
end $$;
commit;
