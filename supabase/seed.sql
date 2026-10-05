-- =====================================================================
-- seed.sql : catálogo padrão de itens de manutenção
-- Referência para motos de 125-160cc; ajustar por modelo em Configurações.
-- =====================================================================
-- Óleo, kit de tração e patins de freio vêm da operação (seção 14.5 do plano); os demais são
-- referência genérica. `intervalo_minimo_km` é o início do alerta nos itens com faixa de km.
insert into itens_manutencao (nome, intervalo_km, intervalo_minimo_km, intervalo_dias) values
  ('Troca de óleo do motor', 1000, null, 90),
  ('Filtro de ar', 6000, null, 180),
  ('Kit de tração (corrente, coroa, pinhão)', 5000, 3000, null),
  ('Patins de freio', 5000, 3000, null),
  ('Pneu dianteiro', 15000, null, null),
  ('Pneu traseiro', 10000, null, null),
  ('Vela de ignição', 8000, null, null),
  ('Fluido de freio', null, null, 365),
  ('Revisão geral', 5000, null, 180)
on conflict (nome) do nothing;
