-- =====================================================================
-- 20261106140000_whatsapp_painel.sql : envio automático por WhatsApp, Etapa 4 (telas; Projeto_Locação.md, seção 20)
--
-- O envio é a única forma de avisar o locatário, então ele não pode parar em silêncio. A cada rodada o script grava
-- aqui o que viu (a instância do WhatsApp estava conectada? o que foi feito?), e o Dashboard avisa o dono quando a
-- instância cai ou quando a rodada deixa de rodar.
--   * `configuracoes.whatsapp_ultima_rodada_em`, `whatsapp_ultimo_estado` e `whatsapp_ultimo_resumo`;
--   * `rpc_whatsapp_registrar_rodada(p_estado, p_resumo)`: só o usuário de serviço e os administradores.
-- As telas do dono (bloqueio no cliente, reenviar e cancelar mensagens, controles em Configurações) mexem em uma tabela
-- de cada vez, pelas políticas de RLS que já existem; não precisam de RPC.
-- Compatível com a versão anterior do app: só colunas novas, sem padrão obrigatório.
-- =====================================================================

alter table configuracoes
  add column if not exists whatsapp_ultima_rodada_em timestamptz,
  add column if not exists whatsapp_ultimo_estado text,
  add column if not exists whatsapp_ultimo_resumo jsonb;

create or replace function rpc_whatsapp_registrar_rodada(p_estado text, p_resumo jsonb default null) returns void
language plpgsql security definer set search_path = public as $$
begin
  perform fn_exige_gestao_whatsapp();
  if p_estado is null or btrim(p_estado) = '' then
    raise exception 'Informe o estado da instância.';
  end if;
  update configuracoes
     set whatsapp_ultima_rodada_em = now(), whatsapp_ultimo_estado = left(p_estado, 40), whatsapp_ultimo_resumo = p_resumo
   where id = 1;
end $$;

revoke all on function rpc_whatsapp_registrar_rodada(text, jsonb) from public, anon;
grant execute on function rpc_whatsapp_registrar_rodada(text, jsonb) to authenticated;

notify pgrst, 'reload schema';
