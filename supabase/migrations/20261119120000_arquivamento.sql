-- =====================================================================
-- 20261119120000_arquivamento.sql
-- Arquivamento de veículos vendidos e de ex-locatários (decisão de 19/11/2026: arquivar, não apagar).
--   * motos.arquivada_em / motivo_arquivamento ('vendida' ou 'outro') / vendida_em;
--   * clientes.arquivado_em;
--   * só arquiva quem não tem pendências: contrato ativo, manutenção aberta ou cobrança em aberto
--     (inclui o débito de contratos já encerrados). As RPCs recusam e dizem o que falta resolver;
--   * arquivar o veículo o deixa "inativa"; arquivar o cliente o deixa "inativo";
--   * desarquivar só tira a marca: o veículo continua inativo até ser reativado;
--   * contrato novo não aceita veículo nem cliente arquivado.
-- O histórico financeiro (contratos, cobranças, pagamentos) não é tocado.
-- =====================================================================

alter table motos
  add column if not exists arquivada_em         timestamptz,
  add column if not exists motivo_arquivamento  text,
  add column if not exists vendida_em           date;
alter table motos drop constraint if exists ck_motos_motivo_arquivamento;
alter table motos add constraint ck_motos_motivo_arquivamento
  check (motivo_arquivamento is null or motivo_arquivamento in ('vendida', 'outro'));
alter table motos drop constraint if exists ck_motos_arquivada_coerente;
alter table motos add constraint ck_motos_arquivada_coerente
  check ((arquivada_em is null) = (motivo_arquivamento is null)
         and (vendida_em is null or motivo_arquivamento = 'vendida'));

alter table motos drop constraint if exists ck_motos_arquivada_inativa;
alter table motos add constraint ck_motos_arquivada_inativa
  check (arquivada_em is null or status = 'inativa');

alter table clientes add column if not exists arquivado_em timestamptz;

-- ---------------------------------------------------------------------
-- Pendências (a mesma regra de src/domain/arquivamento.py)
-- ---------------------------------------------------------------------
create or replace function fn_pendencias_moto(p_moto uuid) returns jsonb
language sql stable security invoker set search_path = public as $$
  select jsonb_build_object(
    'contratos_ativos',
      (select count(*) from contratos c where c.status = 'ativo'
          and (c.moto_id = p_moto or exists (select 1 from contrato_motos cm
                                              where cm.contrato_id = c.id and cm.moto_id = p_moto))),
    'manutencoes_abertas',
      (select count(*) from manutencoes m where m.moto_id = p_moto and m.status = 'aberta'),
    'cobrancas_abertas',
      (select count(*) from vw_cobrancas v where v.moto_id = p_moto and v.situacao in ('aberta', 'atrasada')),
    'saldo_aberto',
      (select coalesce(sum(v.saldo), 0) from vw_cobrancas v
        where v.moto_id = p_moto and v.situacao in ('aberta', 'atrasada')));
$$;

create or replace function fn_pendencias_cliente(p_cliente uuid) returns jsonb
language sql stable security invoker set search_path = public as $$
  select jsonb_build_object(
    'contratos_ativos',
      (select count(*) from contratos c where c.cliente_id = p_cliente and c.status = 'ativo'),
    'manutencoes_abertas', 0,
    'cobrancas_abertas',
      (select count(*) from vw_cobrancas v where v.cliente_id = p_cliente and v.situacao in ('aberta', 'atrasada')),
    'saldo_aberto',
      (select coalesce(sum(v.saldo), 0) from vw_cobrancas v
        where v.cliente_id = p_cliente and v.situacao in ('aberta', 'atrasada')));
$$;

-- Texto da recusa, em português, com o que impede o arquivamento.
create or replace function fn_texto_pendencias(p jsonb, p_quem text) returns text
language plpgsql immutable set search_path = public as $$
declare
  v_partes text[] := '{}';
begin
  if (p->>'contratos_ativos')::int > 0 then
    v_partes := v_partes || ((p->>'contratos_ativos') || ' contrato(s) ativo(s)');
  end if;
  if (p->>'manutencoes_abertas')::int > 0 then
    v_partes := v_partes || ((p->>'manutencoes_abertas') || ' manutenção(ões) aberta(s)');
  end if;
  if (p->>'cobrancas_abertas')::int > 0 then
    v_partes := v_partes || ((p->>'cobrancas_abertas') || ' cobrança(s) em aberto');
  end if;
  return 'Não é possível arquivar ' || p_quem || ': ' || array_to_string(v_partes, ', ') || '.';
end $$;

-- ---------------------------------------------------------------------
-- Veículo
-- ---------------------------------------------------------------------
create or replace function rpc_arquivar_moto(p_moto uuid, p_motivo text, p_vendida_em date default null)
returns jsonb
language plpgsql security invoker set search_path = public as $$
declare
  v_moto motos%rowtype;
  v_pend jsonb;
begin
  if p_motivo not in ('vendida', 'outro') then
    raise exception 'Informe o motivo do arquivamento: vendida ou outro.';
  end if;
  select * into v_moto from motos where id = p_moto for update;
  if not found then
    raise exception 'Veículo não encontrado.';
  end if;
  if v_moto.arquivada_em is not null then
    raise exception 'Este veículo já está arquivado.';
  end if;
  v_pend := fn_pendencias_moto(p_moto);
  if (v_pend->>'contratos_ativos')::int + (v_pend->>'manutencoes_abertas')::int
     + (v_pend->>'cobrancas_abertas')::int > 0 then
    raise exception '%', fn_texto_pendencias(v_pend, 'o veículo');
  end if;
  update motos
     set status = 'inativa',
         arquivada_em = now(),
         motivo_arquivamento = p_motivo,
         vendida_em = case when p_motivo = 'vendida' then coalesce(p_vendida_em, hoje_br()) end
   where id = p_moto;
  return jsonb_build_object('moto_id', p_moto, 'arquivada', true);
end $$;

create or replace function rpc_desarquivar_moto(p_moto uuid) returns jsonb
language plpgsql security invoker set search_path = public as $$
begin
  update motos set arquivada_em = null, motivo_arquivamento = null, vendida_em = null
   where id = p_moto and arquivada_em is not null;
  if not found then
    raise exception 'Este veículo não está arquivado.';
  end if;
  return jsonb_build_object('moto_id', p_moto, 'arquivada', false);
end $$;

-- ---------------------------------------------------------------------
-- Cliente
-- ---------------------------------------------------------------------
create or replace function rpc_arquivar_cliente(p_cliente uuid) returns jsonb
language plpgsql security invoker set search_path = public as $$
declare
  v_cliente clientes%rowtype;
  v_pend jsonb;
begin
  select * into v_cliente from clientes where id = p_cliente for update;
  if not found then
    raise exception 'Cliente não encontrado.';
  end if;
  if v_cliente.arquivado_em is not null then
    raise exception 'Este cliente já está arquivado.';
  end if;
  v_pend := fn_pendencias_cliente(p_cliente);
  if (v_pend->>'contratos_ativos')::int + (v_pend->>'cobrancas_abertas')::int > 0 then
    raise exception '%', fn_texto_pendencias(v_pend, 'o cliente');
  end if;
  update clientes set status = 'inativo', arquivado_em = now() where id = p_cliente;
  return jsonb_build_object('cliente_id', p_cliente, 'arquivado', true);
end $$;

create or replace function rpc_desarquivar_cliente(p_cliente uuid) returns jsonb
language plpgsql security invoker set search_path = public as $$
begin
  update clientes set arquivado_em = null where id = p_cliente and arquivado_em is not null;
  if not found then
    raise exception 'Este cliente não está arquivado.';
  end if;
  return jsonb_build_object('cliente_id', p_cliente, 'arquivado', false);
end $$;

-- ---------------------------------------------------------------------
-- Contrato novo não aceita veículo nem cliente arquivado.
-- ---------------------------------------------------------------------
create or replace function fn_bloqueia_contrato_arquivado() returns trigger
language plpgsql security invoker set search_path = public as $$
begin
  if exists (select 1 from motos where id = new.moto_id and arquivada_em is not null) then
    raise exception 'Este veículo está arquivado. Desarquive-o para criar um contrato.';
  end if;
  if exists (select 1 from clientes where id = new.cliente_id and arquivado_em is not null) then
    raise exception 'Este cliente está arquivado. Desarquive-o para criar um contrato.';
  end if;
  return new;
end $$;

drop trigger if exists trg_contratos_bloqueia_arquivado on contratos;
create trigger trg_contratos_bloqueia_arquivado
before insert on contratos
for each row execute function fn_bloqueia_contrato_arquivado();

revoke all on function rpc_arquivar_moto(uuid, text, date), rpc_desarquivar_moto(uuid),
  rpc_arquivar_cliente(uuid), rpc_desarquivar_cliente(uuid) from public, anon;
grant execute on function rpc_arquivar_moto(uuid, text, date), rpc_desarquivar_moto(uuid),
  rpc_arquivar_cliente(uuid), rpc_desarquivar_cliente(uuid) to authenticated;
