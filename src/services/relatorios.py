"""Consultas de relatórios e exportações compatíveis com Excel."""

import csv
from io import StringIO, BytesIO
from decimal import Decimal
from openpyxl import Workbook
from src.domain.relatorios import consolidar
from src.repositories import relatorios


def resultado_por_moto(inicio, fim):
    if fim < inicio:
        raise ValueError("A data final deve ser igual ou posterior à inicial.")
    d = relatorios.dados()
    return consolidar(
        d["motos"],
        d["contratos"],
        d["cobrancas"],
        d["pagamentos"],
        d["manutencoes"],
        d["documentos_moto"],
        d["historico_km"],
        inicio,
        fim,
    )


def _seguro(valor):
    if isinstance(valor, str) and valor.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + valor
    return valor


def exportar_csv(linhas):
    texto = StringIO(newline="")
    if linhas:
        escritor = csv.DictWriter(texto, fieldnames=list(linhas[0]), delimiter=";")
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow(
                {
                    k: (
                        str(v).replace(".", ",")
                        if isinstance(v, Decimal)
                        else _seguro(v)
                    )
                    for k, v in linha.items()
                }
            )
    return texto.getvalue().encode("utf-8-sig")


def exportar_excel(linhas):
    livro = Workbook()
    aba = livro.active
    aba.title = "Relatório"
    if linhas:
        aba.append(list(linhas[0]))
        for linha in linhas:
            aba.append([_seguro(v) for v in linha.values()])
        aba.freeze_panes = "A2"
        aba.auto_filter.ref = aba.dimensions
        for coluna in aba.columns:
            aba.column_dimensions[coluna[0].column_letter].width = 24
            for celula in coluna[1:]:
                if isinstance(celula.value, Decimal):
                    celula.number_format = "#,##0.00"
    saida = BytesIO()
    livro.save(saida)
    return saida.getvalue()
