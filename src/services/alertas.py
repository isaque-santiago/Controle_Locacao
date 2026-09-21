"""Consolida alertas de manutenção, documentos e CNH para o Dashboard."""

from src.repositories import alertas


def listar_manutencao():
    return alertas.listar_manutencao()


def listar_documentos():
    return alertas.listar_documentos()


def listar_cnh():
    return alertas.listar_cnh()


def resumo() -> dict:
    """Contagem por situação, para os cartões de KPI do Dashboard."""
    manutencao = listar_manutencao()
    documentos = listar_documentos()
    cnh = listar_cnh()

    def _contar(itens: list, chave: str, valor: str) -> int:
        return sum(1 for item in itens if item[chave] == valor)

    return {
        "manutencao_vencida": _contar(manutencao, "situacao", "vencida"),
        "manutencao_proxima": _contar(manutencao, "situacao", "proxima"),
        "documentos_vencidos": _contar(documentos, "situacao", "vencido"),
        "documentos_a_vencer": _contar(documentos, "situacao", "a_vencer"),
        "cnh_vencidas": _contar(cnh, "situacao", "vencida"),
        "cnh_a_vencer": _contar(cnh, "situacao", "a_vencer"),
    }
