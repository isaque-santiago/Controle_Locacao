-- =====================================================================
-- 20261022150000_importacao_rastreio_lotes.sql
-- Migration 4 da importação dos dados reais (Arquivos/Importacao_Dados_Reais.md):
-- registra, por lote de carga, cada linha gravada a partir da planilha (tabela, id gravado,
-- aba e linha de origem). Dá idempotência à carga (não duplicar) e permite desfazer um lote
-- inteiro. Cada carga roda numa transação única, colada no SQL Editor (sem service_role).
-- Compatível com a versão anterior do app: só tabela nova.
-- =====================================================================

create table if not exists importacoes_lote (
  id              uuid primary key default gen_random_uuid(),
  lote            text not null,                 -- ex.: 'planilha-2026-10-21-dev'
  tabela          text not null,                 -- tabela de destino (ex.: 'despesas')
  registro_id     uuid not null,                 -- id gravado na tabela de destino
  aba_origem      text not null,                 -- aba da planilha
  linha_origem    int  not null,                 -- número da linha na aba
  importado_em    timestamptz not null default now(),
  unique (lote, tabela, aba_origem, linha_origem)
);
create index if not exists ix_importacoes_lote_lote on importacoes_lote (lote);

alter table importacoes_lote enable row level security;
drop policy if exists "dono_total" on importacoes_lote;
create policy "dono_total" on importacoes_lote for all to authenticated using (is_dono()) with check (is_dono());
grant select, insert, update, delete on importacoes_lote to authenticated;

notify pgrst, 'reload schema';
