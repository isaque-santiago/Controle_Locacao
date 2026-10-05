-- =====================================================================
-- seed_e2e.sql : massa de dados EXTREMOS para os testes de UI/UX (e2e/)
-- =====================================================================
-- Não faz parte da aplicação. Rode manualmente no SQL Editor do projeto
-- Supabase de DESENVOLVIMENTO (nunca em produção), depois das migrations,
-- do seed.sql e, se quiser, do seed_exemplos.sql.
--
-- Cobre o que os dados de exemplo não cobrem, para provocar quebra de layout:
--   * textos longos (marca, modelo, observações, nome, endereço, e-mail);
--   * valores grandes (R$ 1.234.567,89 por período; quilometragem de 6 dígitos);
--   * listas extensas (24 motos, 24 clientes, 1 contrato diário com ~180 cobranças).
--
-- Os três estados de dados da suíte (variável E2E_DADOS):
--   vazio   -> projeto só com migrations + seed.sql (não rode nenhum seed de exemplo);
--   normal  -> seed_exemplos.sql;
--   extremo -> seed_exemplos.sql + este arquivo.
--
-- Idempotente: se a placa E2E0A01 já existir, o script não faz nada.
begin;
do $$
declare
  v_i           int;
  v_base        text;
  v_dv1         int;
  v_dv2         int;
  v_cpf         text;
  v_moto_dia    uuid;
  v_moto_valor  uuid;
  v_cli_dia     uuid;
  v_cli_valor   uuid;
  v_longo       text := 'Texto muito longo para testar quebra de linha, corte e rolagem em telas estreitas, '
                        || 'com palavras compridas como paralelepipedo_hipopotomonstrosesquipedaliofobia e '
                        || 'https://exemplo.com.br/caminho/muito/longo/que/nao/tem/espacos/para/quebrar/0123456789';
begin
  if exists (select 1 from motos where placa = 'E2E0A01') then
    raise notice 'Massa e2e já cadastrada (placa E2E0A01 encontrada) — nada a fazer.';
    return;
  end if;

  -- -------------------------------------------------------------
  -- Motos: 24 registros; os 3 primeiros com textos e valores extremos
  -- -------------------------------------------------------------
  for v_i in 1..24 loop
    insert into motos (placa, renavam, chassi, marca, modelo, ano_fabricacao, ano_modelo, cor,
                       km_atual, status, valor_aquisicao, data_aquisicao, valor_locacao_sugerido, observacoes)
    values (
      'E2E0A' || lpad(v_i::text, 2, '0'),
      lpad((90000000000 + v_i)::text, 11, '0'),
      '9BE2E' || lpad(v_i::text, 12, '0'),
      case when v_i <= 3 then 'Marca-com-nome-extraordinariamente-comprido-Internacional' else 'Honda' end,
      case when v_i <= 3 then 'Modelo Especial Edição Limitada Aniversário 50 Anos Cilindrada 160 ABS Flex Ultra Plus'
           else 'CG 160 Start ' || v_i end,
      2020 + (v_i % 5), 2021 + (v_i % 5),
      case when v_i % 3 = 0 then 'Vermelha' when v_i % 3 = 1 then 'Preta' else 'Cinza-chumbo metálico' end,
      case when v_i = 1 then 999999 else 5000 + v_i * 731 end,
      case when v_i % 8 = 0 then 'inativa' when v_i % 6 = 0 then 'manutencao' else 'disponivel' end,
      case when v_i = 1 then 9999999.99 else 12000 + v_i * 100 end,
      hoje_br() - (100 + v_i * 20),
      case when v_i = 1 then 1234567.89 else 200 + v_i end,
      case when v_i <= 3 then v_longo else null end
    );
  end loop;

  -- -------------------------------------------------------------
  -- Clientes: 24 registros, CPFs válidos gerados; os 3 primeiros com textos extremos
  -- -------------------------------------------------------------
  for v_i in 1..24 loop
    v_base := lpad((700000000 + v_i * 7919)::text, 9, '0');
    v_dv1 := (11 - (
      (substr(v_base,1,1)::int*10 + substr(v_base,2,1)::int*9 + substr(v_base,3,1)::int*8 +
       substr(v_base,4,1)::int*7  + substr(v_base,5,1)::int*6 + substr(v_base,6,1)::int*5 +
       substr(v_base,7,1)::int*4  + substr(v_base,8,1)::int*3 + substr(v_base,9,1)::int*2) % 11)) % 11;
    if v_dv1 >= 10 then v_dv1 := 0; end if;
    v_dv2 := (11 - (
      (substr(v_base,1,1)::int*11 + substr(v_base,2,1)::int*10 + substr(v_base,3,1)::int*9 +
       substr(v_base,4,1)::int*8  + substr(v_base,5,1)::int*7  + substr(v_base,6,1)::int*6 +
       substr(v_base,7,1)::int*5  + substr(v_base,8,1)::int*4  + substr(v_base,9,1)::int*3 +
       v_dv1*2) % 11)) % 11;
    if v_dv2 >= 10 then v_dv2 := 0; end if;
    v_cpf := v_base || v_dv1::text || v_dv2::text;

    insert into clientes (nome, cpf, telefone, whatsapp, email, endereco,
                          cnh_numero, cnh_categoria, cnh_validade, status, observacoes)
    values (
      case when v_i <= 3
           then 'Maria das Graças Nascimento de Albuquerque e Vasconcelos Figueiredo Junior ' || v_i
           else 'Cliente Exemplo ' || v_i end,
      v_cpf,
      '119' || lpad((80000000 + v_i)::text, 8, '0'),
      case when v_i % 2 = 0 then '119' || lpad((80000000 + v_i)::text, 8, '0') else null end,
      case when v_i <= 3
           then 'endereco.de.email.extremamente.comprido.para.testar.overflow.' || v_i || '@dominio-muito-longo-de-teste.com.br'
           else 'cliente' || v_i || '@example.com' end,
      case when v_i <= 3
           then 'Avenida Governador Doutor Professor Engenheiro Sebastião de Almeida Barbosa Neto, 12345, Bloco C, Apto 1702, Bairro Jardim das Acácias - São Paulo/SP'
           else 'Rua Exemplo, ' || v_i || ' - São Paulo/SP' end,
      lpad((50000000000 + v_i)::text, 11, '0'), 'A',
      hoje_br() + (v_i * 40 - 200),
      case when v_i % 9 = 0 then 'bloqueado' when v_i % 11 = 0 then 'inativo' else 'ativo' end,
      case when v_i <= 3 then v_longo else null end
    );
  end loop;

  -- -------------------------------------------------------------
  -- Contrato A: diário, ~180 cobranças (lista extensa de cobranças)
  -- Contrato B: mensal, valor por período muito alto (KPIs e tabelas com números grandes)
  -- Usam as motos/clientes que estão 'disponivel' e 'ativo'.
  -- -------------------------------------------------------------
  select id into v_moto_dia   from motos    where placa = 'E2E0A02';
  select id into v_moto_valor from motos    where placa = 'E2E0A05';
  select c.id into v_cli_dia   from clientes c where c.status = 'ativo' and c.nome like 'Cliente Exemplo %' order by c.nome limit 1;
  select c.id into v_cli_valor from clientes c where c.status = 'ativo' and c.nome like 'Cliente Exemplo %' and c.id <> v_cli_dia order by c.nome limit 1;

  perform rpc_criar_contrato_com_vistoria(
    jsonb_build_object(
      'moto_id', v_moto_dia, 'cliente_id', v_cli_dia,
      'data_inicio', hoje_br() - 30, 'data_fim_prevista', hoje_br() + 150,
      'periodicidade', 'diario', 'valor_periodo', 45, 'caucao_valor', 500,
      'km_inicial', 6462
    ),
    jsonb_build_object('km', 6462, 'nivel_combustivel', 'cheio',
      'checklist', '{"farol_dianteiro":"ok","farol_traseiro":"ok","pneus":"ok","freios":"ok","retrovisores":"ok"}'::jsonb)
  );

  perform rpc_criar_contrato_com_vistoria(
    jsonb_build_object(
      'moto_id', v_moto_valor, 'cliente_id', v_cli_valor,
      'data_inicio', hoje_br() - 20, 'data_fim_prevista', hoje_br() + 340,
      'periodicidade', 'mensal', 'valor_periodo', 1234567.89, 'caucao_valor', 9999999.99,
      'km_inicial', 8655
    ),
    jsonb_build_object('km', 8655, 'nivel_combustivel', 'cheio',
      'checklist', '{"farol_dianteiro":"ok","farol_traseiro":"ok","pneus":"ok","freios":"ok","retrovisores":"ok"}'::jsonb)
  );

  raise notice 'Massa e2e criada: 24 motos, 24 clientes, 2 contratos (diário extenso e mensal de valor alto).';
end $$;
commit;
