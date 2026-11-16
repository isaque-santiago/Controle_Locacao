"""PDF do contrato de locação com promessa de compra e venda (fpdf2, fonte padrão Helvetica/Latin-1).

Visual do contrato de 16/11/2026: faixa preta com a logo e o nome da empresa, linha vermelha, marca d'água, quadros de
dados, resumo de multas, rubricas no rodapé e página final de assinaturas com duas testemunhas. O texto vem de
src/domain/contrato_promessa.py; aqui só se desenha. Logo e marca d'água ficam em static/contrato/ (sem elas, o
documento sai igual, só sem as imagens)."""

from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

from src.domain.contrato_modelo import Bloco

PASTA_IMAGENS = Path(__file__).resolve().parents[2] / "static" / "contrato"
EMPRESA = "L.A ALUGUEL DE MOTOS"
SUBTITULO = "Locação de motocicletas com promessa de compra e venda"

_MARGEM = 20
_TOPO_CORPO = 38
_TAMANHO = 9.5
_ALTURA_LINHA = 5.0
_PRETO = (13, 15, 17)
_VERMELHO = (200, 16, 46)
_CINZA_TEXTO = (90, 95, 102)
_CINZA_FUNDO = (243, 243, 243)
_CINZA_BORDA = (205, 205, 205)
_RESERVA_ASSINATURAS = 120  # mm: bloco de assinaturas e testemunhas


def _latin1(texto: str) -> str:
    """Caracteres fora do Latin-1 (raros em nomes) viram '?', em vez de quebrar o PDF."""
    return str(texto).encode("latin-1", "replace").decode("latin-1")


class _Documento(FPDF):
    def __init__(self, cabecalho: dict, rodape: str):
        super().__init__(format="A4")
        self._cabecalho = cabecalho
        self._rodape = _latin1(rodape)

    def header(self):
        # Marca d'água primeiro, para ficar atrás do texto.
        marca = PASTA_IMAGENS / "marca-dagua.png"
        if marca.exists():
            largura = 110
            self.image(str(marca), x=(self.w - largura) / 2, y=(self.h - largura * 0.914) / 2 + 8, w=largura)
        self.set_fill_color(*_PRETO)
        self.rect(0, 0, self.w, 27, style="F")
        self.set_fill_color(*_VERMELHO)
        self.rect(0, 27, self.w, 1.3, style="F")
        logo = PASTA_IMAGENS / "logo.png"
        if logo.exists():
            self.set_fill_color(255, 255, 255)
            self.rect(_MARGEM - 8, 4.5, 27, 20, style="F", round_corners=True, corner_radius=3)
            self.image(str(logo), x=_MARGEM - 6.5, y=5.5, w=24)
        self.set_text_color(255, 255, 255)
        self.set_xy(self.w - _MARGEM - 110, 7)
        self.set_font("Helvetica", "B", 13)
        self.cell(110, 6.5, EMPRESA, align="R")
        self.set_font("Helvetica", size=7.5)
        self.set_text_color(200, 204, 208)
        self.set_xy(self.w - _MARGEM - 110, 14)
        self.cell(110, 4, _latin1(SUBTITULO), align="R")
        contato = _latin1(self._cabecalho.get("contato", ""))
        if contato:
            self.set_xy(self.w - _MARGEM - 110, 18)
            self.cell(110, 4, contato, align="R")
        self.set_text_color(0, 0, 0)
        self.set_y(_TOPO_CORPO)

    def footer(self):
        self.set_draw_color(*_CINZA_BORDA)
        self.line(_MARGEM, self.h - 17, self.w - _MARGEM, self.h - 17)
        self.set_font("Helvetica", size=7.5)
        self.set_text_color(*_CINZA_TEXTO)
        self.set_xy(_MARGEM, self.h - 15.5)
        self.cell(0, 3.8, "Rubricas: ___________   ___________")
        self.set_xy(_MARGEM, self.h - 11.5)
        self.cell(120, 3.8, self._rodape)
        self.set_xy(self.w - _MARGEM - 30, self.h - 11.5)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*_VERMELHO)
        self.cell(30, 3.8, f"Página {self.page_no()}", align="R")
        self.set_text_color(0, 0, 0)


def _quadro(pdf: _Documento, linhas: tuple) -> None:
    """Tabela de dois campos (rótulo em negrito sobre fundo cinza, valor ao lado)."""
    largura = pdf.w - 2 * _MARGEM
    rotulo = FontFace(emphasis="BOLD", fill_color=_CINZA_FUNDO)
    pdf.set_font("Helvetica", size=_TAMANHO)
    pdf.set_draw_color(*_CINZA_BORDA)
    with pdf.table(col_widths=(0.31, 0.69), width=largura, borders_layout="ALL", line_height=5.2,
                   padding=(1.4, 2, 1.4, 2), first_row_as_headings=False, markdown=False) as tabela:
        for nome, valor in linhas:
            linha = tabela.row()
            linha.cell(_latin1(nome), style=rotulo)
            linha.cell(_latin1(valor), style=FontFace(emphasis="BOLD") if nome in ("Nome completo",) else None)
    pdf.ln(3)


def _resumo(pdf: _Documento, linhas: tuple) -> None:
    largura = pdf.w - 2 * _MARGEM
    cabecalho = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=_PRETO)
    pdf.set_font("Helvetica", size=8.5)
    pdf.set_draw_color(*_CINZA_BORDA)
    with pdf.table(col_widths=(0.52, 0.33, 0.15), width=largura, borders_layout="ALL", line_height=4.8,
                   padding=(1.2, 2, 1.2, 2), headings_style=cabecalho, markdown=False) as tabela:
        cab = tabela.row()
        for titulo in ("Situação", "Valor / Consequência", "Cláusula"):
            cab.cell(_latin1(titulo))
        for situacao, valor, clausula in linhas:
            linha = tabela.row()
            linha.cell(_latin1(situacao))
            linha.cell(_latin1(valor))
            linha.cell(_latin1(clausula))
    pdf.ln(4)


def _assinaturas(pdf: _Documento, assinaturas: list[Bloco]) -> None:
    if pdf.get_y() > pdf.h - _RESERVA_ASSINATURAS:
        pdf.add_page()
    largura = pdf.w - 2 * _MARGEM
    pdf.ln(18)
    for assinatura in assinaturas:
        x = _MARGEM + largura / 2 - 52
        pdf.line(x, pdf.get_y(), x + 104, pdf.get_y())
        pdf.set_xy(_MARGEM, pdf.get_y() + 1.5)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(largura, 4.6, _latin1(assinatura.texto), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=8.5)
        pdf.cell(largura, 4.4, _latin1(assinatura.numero), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(15)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(largura, 5, "TESTEMUNHAS:", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(12)
    coluna = (largura - 12) / 2
    topo = pdf.get_y()
    for indice in range(2):
        x = _MARGEM + indice * (coluna + 12)
        pdf.line(x, topo, x + coluna, topo)
        pdf.set_xy(x, topo + 1.5)
        pdf.set_font("Helvetica", size=8.5)
        pdf.cell(coluna, 4.4, f"Testemunha {indice + 1}", align="C", new_x="LEFT", new_y="NEXT")
        pdf.set_x(x)
        pdf.cell(coluna, 5.2, "Nome: " + "_" * 30, new_x="LEFT", new_y="NEXT")
        pdf.set_x(x)
        pdf.cell(coluna, 5.2, "CPF: " + "_" * 31)
    pdf.set_text_color(0, 0, 0)


def renderizar(blocos: list[Bloco], cabecalho: dict | None = None, rodape: str = "") -> bytes:
    """`cabecalho`: {"contato": "Crato/CE · (88) 9 9806-4387"} (linha sob o subtítulo, opcional)."""
    pdf = _Documento(cabecalho or {}, rodape)
    pdf.set_margins(_MARGEM, _TOPO_CORPO, _MARGEM)
    pdf.set_auto_page_break(True, margin=22)
    pdf.set_title("Contrato de locação de veículo com promessa de compra e venda")
    pdf.add_page()

    assinaturas = [b for b in blocos if b.tipo == "assinatura"]
    largura = pdf.w - 2 * _MARGEM
    for bloco in blocos:
        texto = _latin1(bloco.texto)
        if bloco.tipo == "assinatura":
            continue
        if bloco.tipo == "titulo":
            pdf.set_font("Helvetica", "B", 12.5)
            pdf.multi_cell(0, 6.5, texto, align="C")
            pdf.ln(4)
        elif bloco.tipo == "texto":
            pdf.set_font("Helvetica", size=_TAMANHO)
            pdf.multi_cell(0, _ALTURA_LINHA, texto, align="J", markdown=True)
            pdf.ln(1.8)
        elif bloco.tipo == "legenda":
            titulo = texto.isupper()
            pdf.set_font("Helvetica", "B" if titulo else "", 9 if titulo else 8)
            pdf.set_text_color(*_VERMELHO if titulo else _CINZA_TEXTO)
            pdf.multi_cell(0, 5, texto, align="L")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1)
        elif bloco.tipo == "quadro":
            _quadro(pdf, bloco.linhas)
        elif bloco.tipo == "resumo":
            _resumo(pdf, bloco.linhas)
        elif bloco.tipo == "clausula":
            if pdf.get_y() > pdf.h - 55:
                pdf.add_page()
            pdf.ln(2.5)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*_VERMELHO)
            pdf.multi_cell(0, 6, texto, align="L")
            pdf.set_text_color(0, 0, 0)
            pdf.ln(0.8)
        elif bloco.tipo in ("item", "subitem"):
            recuo = 8 if bloco.tipo == "subitem" else 0
            pdf.set_font("Helvetica", size=_TAMANHO)
            pdf.set_x(_MARGEM + recuo)
            pdf.multi_cell(largura - recuo, _ALTURA_LINHA, f"{bloco.numero} {texto}", align="J", markdown=True)
            pdf.ln(1.4)
        elif bloco.tipo == "fecho":
            pdf.ln(2)
            pdf.set_font("Helvetica", size=_TAMANHO + 0.5)
            pdf.multi_cell(0, 6, texto, align="C")
    _assinaturas(pdf, assinaturas)
    return bytes(pdf.output())
