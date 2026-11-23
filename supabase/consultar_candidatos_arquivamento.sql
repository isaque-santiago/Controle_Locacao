-- SOMENTE LEITURA (nenhuma alteração). Rode no SQL Editor do projeto onde quer arquivar, DEPOIS de aplicar
--   20261119120000_arquivamento.sql.
-- Lista quem já pode ser arquivado (sem pendências) e quem ainda não pode (com o motivo), para o dono escolher.
-- Veículos: o sistema não sabe quais foram vendidos; o dono diz as placas e arquiva pela ficha ("Arquivar").

-- Ex-locatários inativos: podem arquivar (sem contrato ativo nem cobrança em aberto) ou não.
select c.nome,
       c.status,
       (fn_pendencias_cliente(c.id)->>'contratos_ativos')::int  as contratos_ativos,
       (fn_pendencias_cliente(c.id)->>'cobrancas_abertas')::int as cobrancas_abertas,
       (fn_pendencias_cliente(c.id)->>'saldo_aberto')::numeric  as saldo_aberto,
       case when (fn_pendencias_cliente(c.id)->>'contratos_ativos')::int
                 + (fn_pendencias_cliente(c.id)->>'cobrancas_abertas')::int = 0
            then 'pode arquivar' else 'tem pendência' end        as situacao
  from clientes c
 where c.status = 'inativo' and c.arquivado_em is null
 order by situacao, c.nome;

-- Veículos inativos: o mesmo, com as manutenções abertas.
select m.placa, m.marca, m.modelo,
       (fn_pendencias_moto(m.id)->>'contratos_ativos')::int      as contratos_ativos,
       (fn_pendencias_moto(m.id)->>'manutencoes_abertas')::int   as manutencoes_abertas,
       (fn_pendencias_moto(m.id)->>'cobrancas_abertas')::int     as cobrancas_abertas,
       case when (fn_pendencias_moto(m.id)->>'contratos_ativos')::int
                 + (fn_pendencias_moto(m.id)->>'manutencoes_abertas')::int
                 + (fn_pendencias_moto(m.id)->>'cobrancas_abertas')::int = 0
            then 'pode arquivar' else 'tem pendência' end        as situacao
  from motos m
 where m.status = 'inativa' and m.arquivada_em is null
 order by situacao, m.placa;
