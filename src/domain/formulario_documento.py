"""Leitura e validação do cadastro de documento da moto (novo e edição) e do comprovante enviado.

Funções puras: recebem o que o navegador enviou (texto) e devolvem os dados prontos para o serviço,
ou levantam `ErroDeCampos` com uma mensagem por campo."""

from datetime import date

from src.domain.arquivos import TAMANHO_MAXIMO_BYTES, validar_arquivo
from src.domain.documentos_lista import TIPOS_ROTULO
from src.domain.entradas import decimal_campo, inteiro_campo, texto_moeda
from src.domain.formulario_moto import ErroDeCampos, _coletar, _data_iso, _opcional, _texto

EXTENSOES_COMPROVANTE = (".pdf", ".png", ".jpg", ".jpeg")
TIPOS_CONTEUDO = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
BYTES_DA_ASSINATURA = 16  # o suficiente para conferir o formato real do arquivo
ANO_MINIMO, ANO_MAXIMO = 1900, 2100


def documento_inicial(hoje: date, moto_id: str | None = None, tipo: str | None = None, ano: int | None = None) -> dict:
    """Texto inicial do cadastro novo; `tipo` e `ano` vêm da sugestão do ano seguinte (vencimento em branco)."""
    return {
        "moto_id": moto_id or "", "tipo": tipo if tipo in TIPOS_ROTULO else "ipva",
        "ano_referencia": str(ano or hoje.year), "vencimento": "", "valor": texto_moeda(0), "descricao": "", "observacoes": "",
    }


def valores_do_documento(documento: dict) -> dict:
    """Texto dos campos de um documento já cadastrado."""
    return {
        "moto_id": documento["moto_id"], "tipo": documento["tipo"],
        "ano_referencia": str(documento.get("ano_referencia") or ""), "vencimento": str(documento["vencimento"])[:10],
        "valor": texto_moeda(documento.get("valor")), "descricao": documento.get("descricao") or "",
        "observacoes": documento.get("observacoes") or "",
    }


def texto_do_documento(entrada: dict) -> dict:
    return {campo: _texto(entrada, campo) for campo in
            ("moto_id", "tipo", "ano_referencia", "vencimento", "valor", "descricao", "observacoes")}


def ler_documento(entrada: dict, motos_validas, moto_fixa: str | None = None) -> dict:
    """Documento pronto para `documentos.criar` / `documentos.atualizar`. Na edição a moto não muda (`moto_fixa`)."""
    erros: dict[str, str] = {}
    moto_id = moto_fixa or _texto(entrada, "moto_id")
    if moto_id not in motos_validas:
        erros["moto_id"] = "Moto: escolha uma moto da frota."
    tipo = _texto(entrada, "tipo")
    if tipo not in TIPOS_ROTULO:
        erros["tipo"] = "Tipo: escolha um dos tipos."
    ano = _coletar(erros, "ano_referencia", inteiro_campo, _texto(entrada, "ano_referencia"),
                   "Ano de referência", ANO_MINIMO, ANO_MAXIMO)
    vencimento = _coletar(erros, "vencimento", _data_iso, _texto(entrada, "vencimento"), "Vencimento", True)
    valor = _coletar(erros, "valor", decimal_campo, entrada.get("valor"), "Valor")
    if erros:
        raise ErroDeCampos(erros)
    return {
        "moto_id": moto_id, "tipo": tipo, "ano_referencia": ano, "vencimento": vencimento, "descricao": _opcional(entrada, "descricao"),
        "valor": str(valor), "observacoes": _opcional(entrada, "observacoes"),
    }


def validar_comprovante(nome: str, tamanho: int, cabecalho: bytes) -> None:
    """Confere tamanho, extensão e formato real do comprovante antes de gravar o documento."""
    if tamanho > TAMANHO_MAXIMO_BYTES:
        raise ErroDeCampos({"comprovante": f"Comprovante: o arquivo tem mais de {TAMANHO_MAXIMO_BYTES // (1024 * 1024)} MB."})
    try:
        validar_arquivo(nome, cabecalho if tamanho > 0 else b"", EXTENSOES_COMPROVANTE)
    except ValueError as erro:
        raise ErroDeCampos({"comprovante": f"Comprovante: {erro}"}) from None
