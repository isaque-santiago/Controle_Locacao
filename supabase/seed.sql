-- =====================================================================
-- seed.sql : catálogo padrão de itens de manutenção
-- Referência para motos de 125-160cc; ajustar por modelo em Configurações.
-- =====================================================================
insert into itens_manutencao (nome, intervalo_km, intervalo_dias) values
  ('Troca de óleo do motor', 1000, 90),
  ('Filtro de ar', 6000, 180),
  ('Kit relação (corrente, coroa, pinhão)', 15000, null),
  ('Pastilhas / lonas de freio', 8000, null),
  ('Pneu dianteiro', 15000, null),
  ('Pneu traseiro', 10000, null),
  ('Vela de ignição', 8000, null),
  ('Fluido de freio', null, 365),
  ('Revisão geral', 5000, 180)
on conflict (nome) do nothing;
