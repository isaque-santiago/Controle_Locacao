-- =====================================================================
-- 20261005150000_manutencao_faixa_km.sql
-- Decisão de negócio (seção 14.5 do plano): alguns itens têm FAIXA de km, não um valor
-- único — kit de tração e patins de freio, de 3.000 a 5.000 km. O mínimo da faixa é
-- quando o alerta começa; o máximo (`intervalo_km`) é quando o item fica vencido.
-- Itens sem `intervalo_minimo_km` continuam avisando pela antecedência global
-- `configuracoes.alerta_manutencao_km`.
-- A regra é espelhada em src/domain/manutencao_regras.py.
-- =====================================================================

alter table itens_manutencao
  add column if not exists intervalo_minimo_km int check (intervalo_minimo_km > 0);
alter table itens_manutencao
  drop constraint if exists itens_manutencao_faixa_km_check;
alter table itens_manutencao
  add constraint itens_manutencao_faixa_km_check
  check (intervalo_minimo_km is null or (intervalo_km is not null and intervalo_minimo_km < intervalo_km));

alter table moto_plano_manutencao
  add column if not exists intervalo_minimo_km int check (intervalo_minimo_km > 0);  -- null = usa o do catálogo

-- Catálogo conforme a operação. Só renomeia/ajusta o que ainda está no valor genérico original,
-- para não sobrescrever um ajuste feito pelo dono. Os planos das motos mantêm o mesmo item.
update itens_manutencao
   set nome = 'Kit de tração (corrente, coroa, pinhão)', intervalo_minimo_km = 3000, intervalo_km = 5000
 where nome = 'Kit relação (corrente, coroa, pinhão)' and intervalo_km = 15000
   and not exists (select 1 from itens_manutencao where nome = 'Kit de tração (corrente, coroa, pinhão)');
update itens_manutencao
   set nome = 'Patins de freio', intervalo_minimo_km = 3000, intervalo_km = 5000
 where nome = 'Pastilhas / lonas de freio' and intervalo_km = 8000
   and not exists (select 1 from itens_manutencao where nome = 'Patins de freio');

-- A view ganha a coluna intervalo_minimo_km no meio de `c.*`, então precisa ser recriada.
drop view if exists vw_alertas_manutencao;
create view vw_alertas_manutencao with (security_invoker = true) as
with base as (
  select
    m.id   as moto_id,
    m.placa,
    m.modelo,
    m.km_atual,
    i.id   as item_id,
    i.nome as item,
    pl.ultima_km,
    pl.ultima_data,
    coalesce(pl.intervalo_km,        i.intervalo_km)        as intervalo_km,
    coalesce(pl.intervalo_minimo_km, i.intervalo_minimo_km) as intervalo_minimo_km,
    coalesce(pl.intervalo_dias,      i.intervalo_dias)      as intervalo_dias
  from moto_plano_manutencao pl
  join motos m            on m.id = pl.moto_id and m.status <> 'inativa'
  join itens_manutencao i on i.id = pl.item_id and i.ativo
),
calc as (
  select b.*,
    case when b.intervalo_km is not null
         then coalesce(b.ultima_km, 0) + b.intervalo_km end                as proxima_km,
    case when b.intervalo_dias is not null and b.ultima_data is not null
         then b.ultima_data + b.intervalo_dias end                          as proxima_data,
    -- só vale a faixa quando o mínimo é menor que o máximo efetivo (uma sobrescrita por moto
    -- pode deixar o par incoerente; nesse caso vale a antecedência global)
    case when b.intervalo_minimo_km is not null and b.intervalo_km is not null
              and b.intervalo_minimo_km < b.intervalo_km
         then coalesce(b.ultima_km, 0) + b.intervalo_minimo_km end         as alerta_inicio_km
  from base b
)
select
  c.*,
  (c.proxima_km - c.km_atual)     as km_restantes,
  (c.proxima_data - hoje_br())    as dias_restantes,
  case
    when (c.proxima_km   is not null and c.km_atual >= c.proxima_km)
      or (c.proxima_data is not null and hoje_br() >= c.proxima_data)
      then 'vencida'
    when (c.proxima_km   is not null and c.proxima_km - c.km_atual   <= cfg.alerta_manutencao_km)
      or (c.alerta_inicio_km is not null and c.km_atual >= c.alerta_inicio_km)
      or (c.proxima_data is not null and c.proxima_data - hoje_br() <= cfg.alerta_manutencao_dias)
      then 'proxima'
    else 'em_dia'
  end as situacao
from calc c
cross join configuracoes cfg;

grant select on vw_alertas_manutencao to authenticated;

notify pgrst, 'reload schema';
