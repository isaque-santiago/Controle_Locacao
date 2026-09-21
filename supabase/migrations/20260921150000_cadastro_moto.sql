-- O cadastro e o plano inicial são gravados na mesma transação.
create or replace function fn_moto_plano_inicial() returns trigger
language plpgsql security invoker set search_path = public as $$
begin
  perform rpc_aplicar_plano_padrao(new.id);
  insert into historico_km(moto_id, km, origem) values (new.id, new.km_atual, 'manual');
  return new;
end $$;
create trigger trg_moto_plano_inicial after insert on motos
for each row execute function fn_moto_plano_inicial();

create or replace function fn_validar_moto() returns trigger
language plpgsql security invoker set search_path = public as $$
begin
  if new.km_atual < old.km_atual then
    raise exception 'A quilometragem atual não pode diminuir.';
  end if;
  if new.status = 'inativa' and (exists(select 1 from contratos where moto_id = new.id and status = 'ativo')
      or exists(select 1 from manutencoes where moto_id = new.id and status = 'aberta')) then
    raise exception 'Encerre os contratos e manutenções antes de inativar a moto.';
  end if;
  return new;
end $$;
create trigger trg_validar_moto before update on motos for each row execute function fn_validar_moto();
