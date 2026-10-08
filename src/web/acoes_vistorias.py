"""Fronteira de escrita da página Vistorias."""

from datetime import datetime
from pathlib import PurePath
from zoneinfo import ZoneInfo

from src.domain.formulario_vistoria import TIPOS_CONTEUDO
from src.domain.vistorias import instante_da_vistoria
from src.services import vistorias

_FUSO = ZoneInfo("America/Sao_Paulo")


def registrar_vistoria(contrato_id, moto_id, tipo, dia, vistoria):
    """Registra a vistoria pela RPC (grava também o km no histórico). `dia` é a data escolhida."""
    return vistorias.registrar_vistoria(
        contrato_id, moto_id, tipo, data=instante_da_vistoria(dia, datetime.now(_FUSO)), **vistoria
    )


def anexar_fotos(vistoria_id, fotos):
    """Envia cada foto (objeto com `filename` e `file`). Devolve quantas falharam: a vistoria já está salva,
    então a falha de uma foto não pode desfazê-la nem impedir as demais."""
    falhas = 0
    for foto in fotos:
        try:
            if not vistoria_id:
                raise ValueError("Vistoria sem identificador.")
            extensao = PurePath(foto.filename).suffix.lower()
            tipo = TIPOS_CONTEUDO.get(extensao, "application/octet-stream")
            vistorias.anexar_foto(vistoria_id, foto.filename, foto.file.read(), tipo)
        except Exception:
            falhas += 1
    return falhas
