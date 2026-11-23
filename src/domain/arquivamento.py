"""Arquivamento de veículos vendidos e de ex-locatários. Funções puras.

Decisão do dono (19/11/2026): arquivar, não apagar, e só quando não houver mais pendências. A mesma regra
é aplicada no banco (`fn_pendencias_moto`, `fn_pendencias_cliente` e as RPCs `rpc_arquivar_*`); aqui ela
serve para a ficha mostrar o que falta resolver antes de o dono tentar arquivar.
Pendência = contrato ativo, manutenção aberta (veículo) ou cobrança em aberto (inclui o débito de
contratos já encerrados)."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

ARQUIVADOS = "arquivados"  # valor do filtro das listas que mostra só o que está arquivado

MOTIVOS_ARQUIVAMENTO = {"vendida": "Vendido", "outro": "Outro motivo"}
MOTIVO_PADRAO = "vendida"

_SITUACOES_EM_ABERTO = ("aberta", "atrasada")


@dataclass(frozen=True)
class Pendencias:
    contratos_ativos: int = 0
    manutencoes_abertas: int = 0
    cobrancas_abertas: int = 0
    saldo_aberto: Decimal = Decimal("0")

    @property
    def pode_arquivar(self) -> bool:
        return not (self.contratos_ativos or self.manutencoes_abertas or self.cobrancas_abertas)

    def impedimentos(self) -> list[str]:
        """O que impede o arquivamento, em português, na ordem em que o dono resolve."""
        itens = []
        if self.contratos_ativos:
            itens.append(_plural(self.contratos_ativos, "contrato ativo", "contratos ativos"))
        if self.manutencoes_abertas:
            itens.append(_plural(self.manutencoes_abertas, "manutenção aberta", "manutenções abertas"))
        if self.cobrancas_abertas:
            itens.append(_plural(self.cobrancas_abertas, "cobrança em aberto", "cobranças em aberto"))
        return itens


def _plural(quantidade: int, singular: str, plural: str) -> str:
    return f"{quantidade} {singular if quantidade == 1 else plural}"


def _em_aberto(cobrancas: Iterable[dict], chave: str, valor: str) -> list[dict]:
    return [c for c in cobrancas if c.get(chave) == valor and c.get("situacao") in _SITUACOES_EM_ABERTO]


def _saldo(cobrancas: Iterable[dict]) -> Decimal:
    return sum((Decimal(str(c.get("saldo") or 0)) for c in cobrancas), Decimal("0"))


def pendencias_da_moto(
    moto_id: str,
    contratos: Iterable[dict],
    vinculos: Iterable[dict],
    manutencoes: Iterable[dict],
    cobrancas: Iterable[dict],
) -> Pendencias:
    """`vinculos`: linhas de `contrato_motos`. A cobrança conta no veículo principal do contrato."""
    vinculados = {v["contrato_id"] for v in vinculos if v["moto_id"] == moto_id}
    ativos = [c for c in contratos if c.get("status") == "ativo" and (c["moto_id"] == moto_id or c["id"] in vinculados)]
    abertas = _em_aberto(cobrancas, "moto_id", moto_id)
    return Pendencias(
        contratos_ativos=len(ativos),
        manutencoes_abertas=sum(1 for m in manutencoes if m.get("moto_id") == moto_id and m.get("status") == "aberta"),
        cobrancas_abertas=len(abertas),
        saldo_aberto=_saldo(abertas),
    )


def pendencias_do_cliente(cliente_id: str, contratos: Iterable[dict], cobrancas: Iterable[dict]) -> Pendencias:
    ativos = [c for c in contratos if c.get("cliente_id") == cliente_id and c.get("status") == "ativo"]
    abertas = _em_aberto(cobrancas, "cliente_id", cliente_id)
    return Pendencias(contratos_ativos=len(ativos), cobrancas_abertas=len(abertas), saldo_aberto=_saldo(abertas))


def esta_arquivado(registro: dict) -> bool:
    """Veículo (`arquivada_em`) ou cliente (`arquivado_em`) arquivado."""
    return bool(registro.get("arquivada_em") or registro.get("arquivado_em"))


def motivo_valido(valor: str | None) -> str:
    return valor if valor in MOTIVOS_ARQUIVAMENTO else MOTIVO_PADRAO


def texto_recusa(pendencias: Pendencias, quem: str) -> str:
    """Mensagem de quando o arquivamento é recusado (`quem`: "o veículo" ou "o cliente")."""
    return f"Não é possível arquivar {quem}: {', '.join(pendencias.impedimentos())}."
