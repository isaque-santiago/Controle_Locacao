"""Gera o contrato em PDF a partir dos dados da ficha: texto de src/domain/contrato_la.py, visual de contrato_la_pdf.py."""

from src.config import get_locador
from src.domain import contrato_la
from src.services import contrato_la_pdf


def gerar(contrato: dict, cliente: dict, moto: dict | list) -> bytes:
    """PDF do contrato. `moto`: uma moto ou a lista das motos do contrato (a principal primeiro).

    Contrato do tipo `promessa_compra` sai com promessa de compra e venda; os demais, como locação simples, no mesmo visual."""
    locador = get_locador()
    promessa = contrato.get("tipo_contrato") == "promessa_compra"
    blocos = contrato_la.montar(contrato, cliente, moto, locador)
    cabecalho = {
        "contato": " · ".join(x for x in (locador.get("cidade"), locador.get("telefones")) if x),
        "subtitulo": contrato_la_pdf.SUBTITULO_PROMESSA if promessa else contrato_la_pdf.SUBTITULO_LOCACAO,
    }
    nome = str(cliente.get("nome") or "").strip()
    titulo = "Contrato de Locação com Promessa de Compra e Venda" if promessa else "Contrato de Locação de Veículo"
    return contrato_la_pdf.renderizar(blocos, cabecalho, f"{titulo} - {nome}".rstrip(" -"))
