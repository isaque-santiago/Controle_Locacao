-- Multa fixa cobrada quando a troca de oleo e reportada acima do intervalo.
-- Atualiza a configuracao existente e mantém o mesmo valor como padrão para
-- eventuais novos registros de configuracao.

alter table configuracoes
  alter column multa_troca_oleo_valor set default 12.50;

update configuracoes
   set multa_troca_oleo_valor = 12.50;

notify pgrst, 'reload schema';
