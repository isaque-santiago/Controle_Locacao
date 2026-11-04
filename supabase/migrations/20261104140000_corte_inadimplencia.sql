-- =====================================================================
-- 20261104140000_corte_inadimplencia.sql
-- A partir de quantos dias de atraso um contrato passa de "em atraso" para "inadimplente" no Dashboard financeiro
-- (antes fixo em 15). Parâmetro em Configurações, de 1 a 100000 dias.
-- Compatível com a versão anterior do app: só uma coluna com padrão (15, o valor que já valia).
-- Aplique antes de publicar o app novo: a tela de Configurações passa a gravar esse campo.
-- =====================================================================

alter table configuracoes
  add column if not exists dias_inadimplencia int not null default 15
    check (dias_inadimplencia between 1 and 100000);

notify pgrst, 'reload schema';
