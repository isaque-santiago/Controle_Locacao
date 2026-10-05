-- =====================================================================
-- 20261005120000_encargos_fixos.sql
-- Decisão de negócio (seção 14.1 do plano): o encargo de atraso passa a ser FIXO,
--   R$ 15,00 já no dia do vencimento + R$ 7,00 por dia a partir do dia seguinte,
--   sem carência, só sobre cobranças de locação.
-- Substitui multa percentual, juros mensais e carência. O cálculo é feito no app
-- (domain/encargos.py) e gravado em pagamentos.multa_juros no pagamento.
-- =====================================================================

alter table configuracoes
  add column if not exists multa_atraso_valor   numeric(12,2) not null default 15.00
    check (multa_atraso_valor >= 0),    -- valor fixo cobrado já no dia do vencimento
  add column if not exists encargo_diario_valor numeric(12,2) not null default 7.00
    check (encargo_diario_valor >= 0);  -- valor fixo por dia após o vencimento

alter table configuracoes
  drop column if exists multa_atraso_percentual,
  drop column if exists juros_mensal_percentual,
  drop column if exists carencia_dias;

notify pgrst, 'reload schema';
