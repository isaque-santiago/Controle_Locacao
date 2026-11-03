"""Regras puras da página Cobranças do frontend web: abas, ordem e página.

A classificação em abas reaproveita `painel_cobrancas.pertence_a_aba` (a mesma do Streamlit)."""

from datetime import date

from src.domain.paginacao import calcular_pagina
from src.domain.painel_cobrancas import pertence_a_aba

POR_PAGINA = 10
ABA_PADRAO = "hoje"
# (chave na URL, rótulo, nome usado em `pertence_a_aba`)
_ABAS = (
    ("hoje", "Hoje", "Hoje"),
    ("atrasadas", "Atrasadas", "Atrasadas"),
    ("proximos", "Próximos 7 dias", "Próximos 7 dias"),
    ("pagas", "Pagas", "Pagas"),
)
ABAS = tuple((chave, rotulo) for chave, rotulo, _ in _ABAS)
FORMAS_ROTULO = {
    "pix": "Pix",
    "dinheiro": "Dinheiro",
    "cartao": "Cartão",
    "transferencia": "Transferência",
    "outro": "Outro",
}
VAZIO = {
    "hoje": "Nenhuma cobrança vence hoje.",
    "atrasadas": "Nenhuma cobrança em atraso.",
    "proximos": "Nenhuma cobrança vence nos próximos 7 dias.",
    "pagas": "Nenhuma cobrança paga.",
}


def aba_valida(valor: str | None) -> str:
    return valor if valor in dict(ABAS) else ABA_PADRAO


def _data(valor) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


def classificar(linhas: list[dict], hoje: date) -> dict[str, list[dict]]:
    """Cobranças de cada aba (chave -> lista), na ordem em que chegaram."""
    return {
        chave: [c for c in linhas if pertence_a_aba(c["situacao"], _data(c["vencimento"]), nome, hoje)]
        for chave, _, nome in _ABAS
    }


def ordenar(aba: str, linhas: list[dict]) -> list[dict]:
    """Pagas: pagamento mais recente primeiro. Demais abas: o vencimento mais antigo primeiro."""
    if aba == "pagas":
        return sorted(linhas, key=lambda c: str(c.get("pago_em") or ""), reverse=True)
    return sorted(linhas, key=lambda c: str(c["vencimento"]))


def montar_pagina(linhas: list[dict], pagina: int, por_pagina: int = POR_PAGINA):
    recorte = calcular_pagina(len(linhas), pagina, por_pagina)
    return linhas[recorte.inicio:recorte.fim], recorte
