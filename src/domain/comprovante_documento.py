"""Comprovante de documento da moto enviado pelo locatário pelo portal (Etapa 6 da seção 20 do plano). Funções puras.

O locatário manda a foto ou o PDF do comprovante (IPVA, licenciamento, seguro...); o envio NÃO regulariza o documento: fica
aguardando o dono, que aceita (regulariza) ou recusa com um motivo. Cada envio tem situação `enviado`, `aceito` ou `recusado`."""

from datetime import date

from src.domain.arquivos import TAMANHO_MAXIMO_BYTES, validar_arquivo
from src.domain.documentos_lista import TIPOS_ROTULO
from src.domain.formulario_moto import ErroDeCampos, _data_iso, _texto
from src.domain.painel import TOM_ATENCAO, ItemAlerta

EXTENSOES = (".pdf", ".jpg", ".jpeg", ".png")
OBSERVACAO_MAXIMA = 200
MOTIVO_MINIMO, MOTIVO_MAXIMO = 3, 200

STATUS_ROTULO = {"enviado": "Aguardando conferência", "aceito": "Aceito", "recusado": "Recusado"}
STATUS_TOM = {"enviado": "atencao", "aceito": "ok", "recusado": "perigo"}


def nome_do_documento(tipo: str, descricao: str | None = None, ano_referencia: int | None = None) -> str:
    """«IPVA 2026», «Seguro», ou a descrição quando o tipo é «outro»."""
    if tipo == "outro" and descricao:
        return descricao
    rotulo = TIPOS_ROTULO.get(tipo, tipo)
    return f"{rotulo} {ano_referencia}" if ano_referencia else rotulo


def pode_enviar(documento: dict) -> bool:
    """O locatário pode mandar comprovante enquanto não houver um aguardando conferência (depois de uma recusa pode mandar outro)."""
    return documento.get("envio_status") != "enviado"


# ------------------------------------------------------------- envio (portal) --


def ler_envio(entrada: dict, arquivo) -> str | None:
    """Observação (opcional, até 200 caracteres) depois de conferir o arquivo.

    `arquivo`: (nome, tamanho, cabeçalho) ou None. Levanta `ErroDeCampos` com todos os erros, cada um no seu campo."""
    erros: dict[str, str] = {}
    if arquivo is None:
        erros["comprovante"] = "Comprovante: anexe a foto ou o PDF do comprovante."
    else:
        nome, tamanho, cabecalho = arquivo
        if tamanho > TAMANHO_MAXIMO_BYTES:
            erros["comprovante"] = f"Comprovante: o arquivo tem mais de {TAMANHO_MAXIMO_BYTES // (1024 * 1024)} MB."
        else:
            try:
                validar_arquivo(nome, cabecalho if tamanho > 0 else b"", EXTENSOES)
            except ValueError as erro:
                erros["comprovante"] = f"Comprovante: {str(erro).rstrip('.')}."
    observacao = _texto(entrada, "observacao")
    if len(observacao) > OBSERVACAO_MAXIMA:
        erros["observacao"] = f"Observação: use no máximo {OBSERVACAO_MAXIMA} caracteres."
    if erros:
        raise ErroDeCampos(erros)
    return observacao or None


# ------------------------------------------------------------------ dono --


def ler_recusa(entrada: dict) -> str:
    """Motivo da recusa (3 a 200 caracteres): o locatário vê no portal para saber o que corrigir."""
    motivo = _texto(entrada, "motivo")
    if len(motivo) < MOTIVO_MINIMO:
        raise ErroDeCampos({"motivo": f"Motivo: explique o que está errado (mínimo {MOTIVO_MINIMO} letras)."})
    if len(motivo) > MOTIVO_MAXIMO:
        raise ErroDeCampos({"motivo": f"Motivo: use no máximo {MOTIVO_MAXIMO} caracteres."})
    return motivo


def ler_aceite(entrada: dict, hoje: date) -> dict:
    """Data da regularização (obrigatória, não futura) e se o dono quer cadastrar em seguida o documento do ano seguinte."""
    erros: dict[str, str] = {}
    try:
        data = date.fromisoformat(_data_iso(_texto(entrada, "data"), "Data de regularização", True))
        if data > hoje:
            erros["data"] = "Data de regularização: não pode ser uma data futura."
    except ValueError as erro:
        erros["data"] = str(erro)
        data = None
    if erros:
        raise ErroDeCampos(erros)
    return {"data": data, "criar_proximo": bool(entrada.get("criar_proximo"))}


def alertas_de_comprovantes(envios: list[dict]) -> list[ItemAlerta]:
    """Item do Dashboard: comprovantes aguardando conferência do dono (leva para Documentos)."""
    if not envios:
        return []
    primeiro = envios[0]
    resto = f" e mais {len(envios) - 1}" if len(envios) > 1 else ""
    descricao = f"{primeiro.get('cliente') or 'Locatário'} · {primeiro.get('documento') or 'documento'}{resto}"
    return [ItemAlerta(len(envios), "Comprovante a conferir", descricao, TOM_ATENCAO, "documentos")]
