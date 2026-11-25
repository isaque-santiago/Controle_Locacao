"""Planilha de conferência do histórico dos chats (xlsx), só para o dono. Contém dados pessoais (CPF, telefone e o trecho do chat)."""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from src.domain.formatadores import formatar_data
from src.domain.historico_planilha import (
    COLUNAS,
    COLUNA_DA_DECISAO,
    DECISOES,
    ROTULO_DA_SITUACAO,
    ROTULO_DO_TIPO,
    linha_da_planilha,
    ordenar,
    resumo_por_fonte,
    texto_do_periodo,
)
from src.domain.valores import hoje_br
from src.repositories import historico_chat as repositorio

_LARGURAS = {"ID": 38, "Chat": 24, "Tipo": 16, "Data": 12, "Situação": 16, "Resumo": 52, "No sistema / motivo": 50, "Trecho do chat": 60,
             "Marcas": 28, "Lote": 22, "Decisão": 18, "Observação do dono": 40}
_COR_DA_SITUACAO = {"Diverge": "FFF2CC", "Nova": "DDEBF7", "Sem comparação": "EDEDED", "Já existe": "E2EFDA"}
_CABECALHO = PatternFill("solid", fgColor="1F3864")


def _cabecalho(ws, titulos: list[str]) -> None:
    ws.append(titulos)
    for celula in ws[ws.max_row]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = _CABECALHO
        celula.alignment = Alignment(vertical="center", wrap_text=True)


def montar_planilha(conferencia: dict, lotes: list[dict], hoje=None) -> bytes:
    """Três abas: Resumo (períodos, buracos e contagens), Conferência (um registro por linha, com a coluna Decisão) e Lotes."""
    hoje = hoje or hoje_br()
    linhas = ordenar(conferencia.get("linhas") or [])
    wb = Workbook()

    resumo = wb.active
    resumo.title = "Resumo"
    resumo.append([f"Histórico dos chats entregue ao sistema (rascunho; nada foi gravado no financeiro) · gerado em {formatar_data(hoje)}"])
    resumo["A1"].font = Font(bold=True, size=13)
    resumo.append(["Contém dados pessoais (CPF, telefone, trechos do chat). Guarde em local privado."])
    for bloco in resumo_por_fonte(lotes, linhas):
        resumo.append([])
        resumo.append([bloco["nome"]])
        resumo.cell(resumo.max_row, 1).font = Font(bold=True, size=12)
        resumo.append(["Lotes", bloco["lotes"], "Registros recebidos", bloco["registros"]])
        resumo.append(["Períodos entregues", "; ".join(texto_do_periodo(a, b) for a, b in bloco["periodos"]) or "nenhum"])
        resumo.append(["Buracos", "; ".join(texto_do_periodo(a, b) for a, b in bloco["buracos"]) or "nenhum entre o primeiro e o último dia entregues"])
        _cabecalho(resumo, ["Tipo", "Diverge", "Nova", "Sem comparação", "Já existe", "Total"])
        total_geral = {s: 0 for s in ("diverge", "nova", "sem_comparacao", "ja_existe")}
        for tipo, contagens in sorted(bloco["por_tipo"].items()):
            valores = [contagens.get(s, 0) for s in total_geral]
            for s, n in zip(total_geral, valores):
                total_geral[s] += n
            resumo.append([ROTULO_DO_TIPO.get(tipo, tipo), *valores, sum(contagens.values())])
        resumo.append(["Total", *total_geral.values(), sum(total_geral.values())])
        resumo.cell(resumo.max_row, 1).font = Font(bold=True)
    resumo.column_dimensions["A"].width = 24
    for coluna in "BCDEF":
        resumo.column_dimensions[coluna].width = 22

    ws = wb.create_sheet("Conferência")
    _cabecalho(ws, list(COLUNAS))
    for linha in linhas:
        ws.append(linha_da_planilha(linha))
        atual = ws.max_row
        cor = _COR_DA_SITUACAO.get(ROTULO_DA_SITUACAO.get(linha["situacao"], ""))
        if cor:
            ws.cell(atual, COLUNAS.index("Situação") + 1).fill = PatternFill("solid", fgColor=cor)
        ws.cell(atual, COLUNAS.index("Data") + 1).number_format = "DD/MM/YYYY"
        for nome in ("Resumo", "No sistema / motivo", "Trecho do chat", "Observação do dono"):
            ws.cell(atual, COLUNAS.index(nome) + 1).alignment = Alignment(wrap_text=True, vertical="top")
    for i, nome in enumerate(COLUNAS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = _LARGURAS[nome]
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUNAS))}{max(ws.max_row, 2)}"
    letra = get_column_letter(COLUNA_DA_DECISAO)
    validacao = DataValidation(type="list", formula1='"' + ",".join(DECISOES) + '"', allow_blank=True, showErrorMessage=True,
                               errorTitle="Decisão", error="Escolha uma das opções da lista.")
    ws.add_data_validation(validacao)
    validacao.add(f"{letra}2:{letra}{max(ws.max_row, 2) + 500}")  # sobra para linhas acrescentadas à mão

    pagina = wb.create_sheet("Lotes")
    _cabecalho(pagina, ["Chat", "Lote", "Início", "Fim", "Registros recebidos", "Novos no rascunho", "Entregue em"])
    for lote in sorted(lotes, key=lambda x: (x["fonte"], str(x["periodo_inicio"]))):
        pagina.append([lote["fonte"], lote["rotulo"], lote["periodo_inicio"], lote["periodo_fim"], lote["registros_recebidos"], lote["registros_novos"],
                       str(lote["entregue_em"])[:16].replace("T", " ")])
    for coluna, largura in zip("ABCDEFG", (18, 24, 12, 12, 20, 20, 18)):
        pagina.column_dimensions[coluna].width = largura

    saida = BytesIO()
    wb.save(saida)
    return saida.getvalue()


def planilha_de_conferencia(fonte: str | None = None) -> bytes:
    """Lê o rascunho (só o dono consegue) e devolve o xlsx."""
    conferencia = repositorio.conferencia(fonte)
    lotes = [x for x in repositorio.lotes() if fonte is None or x["fonte"] == fonte]
    return montar_planilha(conferencia, lotes)
