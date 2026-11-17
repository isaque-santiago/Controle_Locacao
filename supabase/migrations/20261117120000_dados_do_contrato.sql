-- Dados que o contrato de locação com promessa de compra e venda (modelo L.A Aluguel, 16/11/2026) pede e o cadastro não tinha.
-- Todos opcionais: cadastros antigos continuam valendo e o contrato deixa linha em branco para o que faltar.
-- Idempotente (`if not exists`): o banco já tinha estas colunas quando a integração Supabase ↔ GitHub rodou a migration
-- depois do merge, e ela falhava com "column already exists" (aplicar à mão antes do merge é a regra do Deploy_VPS.md).

alter table clientes
  add column if not exists nacionalidade   text,
  add column if not exists naturalidade    text,
  add column if not exists estado_civil    text,
  add column if not exists profissao       text,
  add column if not exists data_nascimento date,
  add column if not exists rg              text,
  add column if not exists rg_orgao        text,
  add column if not exists cep             text,
  add column if not exists referencias     text;  -- pessoas de contato (ex.: "Rute (esposa) (88) 9 2180-1972")

alter table motos
  add column if not exists motor        text,
  add column if not exists combustivel  text;
