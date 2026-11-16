-- Dados que o contrato de locação com promessa de compra e venda (modelo L.A Aluguel, 16/11/2026) pede e o cadastro não tinha.
-- Todos opcionais: cadastros antigos continuam valendo e o contrato deixa linha em branco para o que faltar.

alter table clientes
  add column nacionalidade   text,
  add column naturalidade    text,
  add column estado_civil    text,
  add column profissao       text,
  add column data_nascimento date,
  add column rg              text,
  add column rg_orgao        text,
  add column cep             text,
  add column referencias     text;  -- pessoas de contato (ex.: "Rute (esposa) (88) 9 2180-1972")

alter table motos
  add column motor        text,
  add column combustivel  text;
