"""Fronteira de leitura da página web de Relatórios: monta a aba pedida e as linhas de exportação.

A tabela e a exportação saem da mesma montagem, então o arquivo baixado tem sempre os mesmos dados da tela.
Os testes das rotas trocam este serviço por dados fictícios."""

from src.domain.relatorios import agrupar_por_modelo, destaques, proporcoes
from src.services import relatorios
from src.ui.formatadores import formatar_data, formatar_mes, formatar_placa


def periodo_texto(inicio, fim):
    if (inicio.year, inicio.month) == (fim.year, fim.month):
        return formatar_mes(inicio)
    return f"{formatar_data(inicio)} a {formatar_data(fim)}"


def _tom(valor):
    return "ok" if valor >= 0 else "perigo"


def _resumo(itens, total_rotulo, unidade, rotulo_maior="Maior", rotulo_menor="Menor"):
    """Alternativa em texto às barras: total e extremos da série (`itens`: (rótulo, valor) na ordem exibida)."""
    resumo = destaques(itens)
    if resumo is None:
        return None
    return {**resumo, "total_rotulo": total_rotulo, "unidade": unidade[0] if resumo["quantidade"] == 1 else unidade[1],
            "rotulo_maior": rotulo_maior, "rotulo_menor": rotulo_menor}


def _resultado(dados):
    linhas = sorted(dados["resultado"], key=lambda r: (-r["resultado"], r["placa"]))
    larguras = proporcoes([r["resultado"] for r in linhas])
    return {
        "chave": "resultado_por_moto",
        "linhas": [{**r, "largura": largura, "tom": _tom(r["resultado"])} for r, largura in zip(linhas, larguras)],
        "resumo": _resumo([(formatar_placa(r["placa"]), r["resultado"]) for r in linhas], "Resultado total",
                          ("moto", "motos"), "Melhor", "Pior"),
        "exportacao": [
            {"Placa": formatar_placa(r["placa"]), "Modelo": r["modelo"], "Receita recebida": r["receita_recebida"],
             "Manutenção": r["custo_manutencao"], "Documentos": r["custo_documentos"], "Resultado": r["resultado"],
             "Km rodados": r["km_rodados"], "Custo por km": r["custo_por_km"]}
            for r in linhas
        ],
    }


def _custo(dados, visao):
    if visao == "modelo":
        grupos = agrupar_por_modelo(dados["resultado"])
        larguras = proporcoes([g["custo_total"] for g in grupos])
        return {
            "chave": "custo_manutencao_modelo",
            "linhas": [{**g, "largura": largura, "tom": "neutro"} for g, largura in zip(grupos, larguras)],
            "resumo": _resumo([(g["modelo"], g["custo_total"]) for g in grupos], "Custo total", ("modelo", "modelos"),
                              "Maior custo", "Menor custo"),
            "exportacao": [
                {"Modelo": g["modelo"], "Motos": g["motos"], "Custo total": g["custo_total"],
                 "Custo médio por moto": g["custo_medio"]}
                for g in grupos
            ],
        }
    linhas = sorted(dados["resultado"], key=lambda r: (-r["custo_manutencao"], r["placa"]))
    larguras = proporcoes([r["custo_manutencao"] for r in linhas])
    return {
        "chave": "custo_manutencao_moto",
        "linhas": [{**r, "largura": largura, "tom": "neutro"} for r, largura in zip(linhas, larguras)],
        "resumo": _resumo([(formatar_placa(r["placa"]), r["custo_manutencao"]) for r in linhas], "Custo total",
                          ("moto", "motos"), "Maior custo", "Menor custo"),
        "exportacao": [
            {"Placa": formatar_placa(r["placa"]), "Modelo": r["modelo"], "Custo de manutenção": r["custo_manutencao"],
             "Km rodados": r["km_rodados"], "Custo por km": r["custo_por_km"]}
            for r in linhas
        ],
    }


def _inadimplencia(hoje):
    dados = relatorios.inadimplencia(hoje)
    percentual = dados["percentual_carteira"]
    return {
        "chave": "inadimplencia",
        "linhas": dados["linhas"], "total_atraso": dados["total_atraso"], "clientes": dados["clientes"],
        "percentual": f"{percentual}%".replace(".", ",") if percentual is not None else "—",
        "exportacao": [
            {"Cliente": l["cliente"], "Placa": formatar_placa(l["placa"]) if l["placa"] else "",
             "Vencimento": formatar_data(l["vencimento"]), "Dias em atraso": l["dias_atraso"], "Saldo": l["saldo"],
             "Valor com encargos": l["total_com_encargos"]}
            for l in dados["linhas"]
        ],
    }


def _fluxo(dados, hoje):
    meses = dados["fluxo"]
    larguras = proporcoes([m["resultado"] for m in meses])
    mes_atual = hoje.isoformat()[:7]
    return {
        "chave": "fluxo_de_caixa",
        "linhas": [{**m, "rotulo_mes": formatar_mes(m["mes"]), "parcial": m["mes"] == mes_atual, "largura": largura,
                    "tom": _tom(m["resultado"])} for m, largura in zip(meses, larguras)],
        "resumo": _resumo([(formatar_mes(m["mes"]), m["resultado"]) for m in meses], "Líquido do período",
                          ("mês", "meses"), "Melhor mês", "Pior mês"),
        "exportacao": [
            {"Mês": formatar_mes(m["mes"]), "Recebido": m["receita_recebida"], "Manutenção": m["custo_manutencao"],
             "Documentos": m["custo_documentos"], "Líquido": m["resultado"]}
            for m in meses
        ],
    }


def carregar(aba, visao, inicio, fim, hoje):
    """Dados da aba pedida: `linhas` (tabela), `resumo` em texto, `exportacao` (linhas do arquivo) e `chave`
    (nome do arquivo). A inadimplência é a posição de hoje e não depende do período."""
    if aba == "inadimplencia":
        return _inadimplencia(hoje)
    dados = relatorios.resultado_por_moto(inicio, fim)
    if aba == "custo":
        return _custo(dados, visao)
    if aba == "fluxo":
        return _fluxo(dados, hoje)
    return _resultado(dados)


def exportar(formato, linhas):
    return relatorios.exportar_csv(linhas) if formato == "csv" else relatorios.exportar_excel(linhas)
