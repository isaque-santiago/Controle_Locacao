"""Gera o contrato de locação em PDF (fpdf2, fonte padrão Helvetica/Latin-1)."""

from fpdf import FPDF

from src.config import get_locador
from src.domain.contrato_modelo import Bloco, montar

_MARGEM = 22
_TAMANHO = 10.5
_ALTURA_LINHA = 5.6
_RESERVA_ASSINATURA = 100  # mm: última cláusula + fecho + linhas de assinatura


class _Documento(FPDF):
    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", size=8)
        self.set_text_color(90, 95, 102)
        self.cell(0, 8, f"Página {self.page_no()} de {{nb}}", align="C")
        self.set_text_color(0, 0, 0)


def _latin1(texto: str) -> str:
    """Caracteres fora do Latin-1 (raros em nomes) viram '?', em vez de quebrar o PDF."""
    return texto.encode("latin-1", "replace").decode("latin-1")


def _linha_assinatura(pdf: _Documento, x: float, largura: float, nome: str, y: float):
    pdf.line(x, y, x + largura, y)
    pdf.set_xy(x, y + 1.5)
    pdf.set_font("Helvetica", "B", 9)
    pdf.multi_cell(largura, 4.6, _latin1(nome), align="C")


def renderizar(blocos: list[Bloco]) -> bytes:
    pdf = _Documento(format="A4")
    pdf.set_margins(_MARGEM, 20, _MARGEM)
    pdf.set_auto_page_break(True, margin=20)
    pdf.set_title("Contrato de locação de motocicleta")
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 13)
    pdf.multi_cell(0, 7, "CONTRATO DE LOCAÇÃO DE MOTOCICLETA", align="C")
    pdf.ln(5)

    assinaturas = [b for b in blocos if b.tipo == "assinatura"]
    itens = [i for i, b in enumerate(blocos) if b.tipo in ("item", "subitem")]
    ultimo_item = itens[-1] if itens else -1
    for indice_bloco, bloco in enumerate(blocos):
        if bloco.tipo == "assinatura":
            continue
        if indice_bloco == ultimo_item and pdf.get_y() > pdf.h - _RESERVA_ASSINATURA:
            pdf.add_page()  # a última cláusula nunca fica separada do fecho e das assinaturas
        texto = _latin1(bloco.texto)
        if bloco.tipo == "preambulo":
            pdf.set_font("Helvetica", size=_TAMANHO)
            pdf.multi_cell(0, _ALTURA_LINHA, texto, align="J", markdown=True)
            pdf.ln(2)
        elif bloco.tipo == "clausula":
            if pdf.get_y() > pdf.h - 45:
                pdf.add_page()
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", _TAMANHO)
            pdf.multi_cell(0, 6, texto, align="L")
            pdf.ln(1)
        elif bloco.tipo in ("item", "subitem"):
            recuo = 8 if bloco.tipo == "subitem" else 0
            pdf.set_font("Helvetica", size=_TAMANHO)
            pdf.set_x(_MARGEM + recuo)
            pdf.multi_cell(
                pdf.w - _MARGEM - (_MARGEM + recuo),
                _ALTURA_LINHA,
                f"{bloco.numero} {texto}",
                align="J",
                markdown=True,
            )
            pdf.ln(1.5)
        elif bloco.tipo == "fecho":
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", _TAMANHO)
            pdf.multi_cell(0, 6, texto, align="L")

    y = pdf.get_y() + 22
    largura = (pdf.w - 2 * _MARGEM - 14) / 2
    for indice, assinatura in enumerate(assinaturas[:2]):
        _linha_assinatura(pdf, _MARGEM + indice * (largura + 14), largura, assinatura.texto, y)
    pdf.set_font("Helvetica", size=8)
    pdf.set_xy(_MARGEM, y + 14)
    pdf.cell(largura, 4, "LOCADOR", align="C")
    pdf.set_x(_MARGEM + largura + 14)
    pdf.cell(largura, 4, "LOCATÁRIO", align="C")

    return bytes(pdf.output())


def gerar(contrato: dict, cliente: dict, moto: dict) -> bytes:
    """PDF do contrato a partir dos dados já carregados na ficha."""
    return renderizar(montar(contrato, cliente, moto, get_locador()))
