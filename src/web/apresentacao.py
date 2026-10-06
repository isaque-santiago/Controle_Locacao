"""Textos e formatos de exibição do app web."""

from src.domain.acesso_locatario import eh_email_de_locatario
from src.ui.formatadores import formatar_data, formatar_moeda

TEMAS_VALIDOS = ("claro", "escuro")


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


__all__ = [
    "formatar_data",
    "formatar_moeda",
    "nome_de_exibicao",
    "tema_do_cookie",
    "destino_seguro",
]
