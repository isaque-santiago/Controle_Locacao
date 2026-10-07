"""Textos e formatos de exibição do app web."""

from src.domain.acesso_locatario import eh_email_de_locatario
from src.ui.formatadores import (
    formatar_data,
    formatar_moeda,
    formatar_moeda_compacta,
    formatar_placa,
)

TEMAS_VALIDOS = ("claro", "escuro")

# Tom do selo (macro `selo`) para cada status de moto.
TOM_STATUS_MOTO = {
    "alugada": "ok",
    "disponivel": "neutro",
    "manutencao": "atencao",
    "inativa": "neutro",
}


def nome_de_exibicao(email: str) -> str:
    """Nome mostrado no menu. O e-mail interno do locatário é o CPF e não aparece na tela."""
    if eh_email_de_locatario(email):
        return "Locatário"
    nome = email.split("@")[0].replace(".", " ").replace("_", " ").title()
    return nome or email


def tema_do_cookie(valor: str | None) -> str:
    """'claro' ou 'escuro' forçado pelo usuário; vazio segue o tema do sistema."""
    return valor if valor in TEMAS_VALIDOS else ""


def destino_seguro(destino: str | None, padrao: str = "/") -> str:
    """Só aceita caminho interno ('/x'); recusa endereço externo (//x, http://x, \\x)."""
    if not destino or not destino.startswith("/"):
        return padrao
    if destino.startswith("//") or "\\" in destino or "\n" in destino or "\r" in destino:
        return padrao
    return destino


def formatar_milhar(numero) -> str:
    """Inteiro com ponto de milhar: 18420 -> '18.420'. Vazio vira travessão."""
    if numero is None or numero == "":
        return "—"
    return f"{int(numero):,}".replace(",", ".")


__all__ = [
    "formatar_data",
    "formatar_moeda",
    "formatar_moeda_compacta",
    "formatar_placa",
    "formatar_milhar",
    "TOM_STATUS_MOTO",
    "nome_de_exibicao",
    "tema_do_cookie",
    "destino_seguro",
]


_TIPOS_COBRANCA = {"locacao": "Locação", "caucao": "Caução", "dano": "Dano", "multa_transito": "Multa de trânsito", "outros": "Outros"}


def rotulo_tipo_cobranca(tipo) -> str:
    """'locacao' -> 'Locação'; tipo desconhecido vira texto legível em vez de quebrar a tela."""
    return _TIPOS_COBRANCA.get(tipo) or str(tipo or "—").replace("_", " ").capitalize()
