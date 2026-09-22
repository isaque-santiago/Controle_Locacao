"""Validação de arquivos enviados (comprovantes e fotos de vistoria).

O navegador informa nome e content_type do arquivo, mas nenhum dos dois é
confiável por si só (o content_type é o que o próprio cliente declara).
Aqui conferimos tamanho, extensão permitida e a assinatura binária real do
arquivo (os primeiros bytes) antes de qualquer upload para o Storage.
"""

from pathlib import PurePath

TAMANHO_MAXIMO_BYTES = 10 * 1024 * 1024  # 10 MB

_ASSINATURAS: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}


def validar_arquivo(
    nome_arquivo: str, conteudo: bytes, extensoes_permitidas: tuple[str, ...]
) -> None:
    """Levanta ValueError se o arquivo não passar nas checagens.

    extensoes_permitidas usa o ponto, ex.: (".pdf", ".png", ".jpg", ".jpeg").
    """
    if not conteudo:
        raise ValueError("Arquivo vazio.")

    if len(conteudo) > TAMANHO_MAXIMO_BYTES:
        limite_mb = TAMANHO_MAXIMO_BYTES // (1024 * 1024)
        raise ValueError(f"Arquivo maior que {limite_mb} MB.")

    extensao = PurePath(nome_arquivo).suffix.lower()
    if extensao not in extensoes_permitidas:
        permitidas = ", ".join(extensoes_permitidas)
        raise ValueError(f"Extensão não permitida. Use: {permitidas}.")

    assinaturas = _ASSINATURAS.get(extensao, ())
    if assinaturas and not any(conteudo.startswith(a) for a in assinaturas):
        raise ValueError(
            "O conteúdo do arquivo não corresponde à extensão informada."
        )
