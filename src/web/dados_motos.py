"""Dados das telas de Motos: reúne os serviços e as regras de src/domain num dicionário.

Fronteira entre a rota e a camada de dados; os testes das rotas trocam estes serviços por
dados fictícios."""

from collections import defaultdict
from datetime import date

from src.domain import motos_lista
from src.domain.paginacao import calcular_pagina
from src.domain.valores import hoje_br
from src.services import (
    alertas,
    clientes,
    cobrancas,
    contratos,
    documentos,
    manutencao,
    motos,
    relatorios,
)

_LEITURAS_DE_KM_NA_FICHA = 8


def _locatarios_por_moto() -> dict[str, str]:
    """Nome do cliente do contrato ativo de cada moto."""
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    return {
        c["moto_id"]: nomes.get(c["cliente_id"], "—")
        for c in contratos.listar()
        if c["status"] == "ativo"
    }


def carregar_lista(situacao: str, busca: str, pagina: int, por_pagina: int) -> dict:
    registros = motos.listar()
    locatarios = _locatarios_por_moto()
    filtradas = motos_lista.filtrar_motos(registros, situacao, busca, locatarios)
    recorte = calcular_pagina(len(filtradas), pagina, por_pagina)

    pagina_atual = filtradas[recorte.inicio : recorte.fim]
    ids_da_pagina = {m["id"] for m in pagina_atual}
    plano_por_moto = defaultdict(list)
    for linha in alertas.listar_manutencao():
        if linha["moto_id"] in ids_da_pagina:
            plano_por_moto[linha["moto_id"]].append(linha)

    itens = [
        {
            "moto": m,
            "locatario": locatarios.get(m["id"]),
            "proxima_manutencao": motos_lista.proxima_manutencao(plano_por_moto[m["id"]]),
        }
        for m in pagina_atual
    ]
    return {
        "itens": itens,
        "pagina": recorte,
        "contagem": motos_lista.contagem_por_status(registros),
        "total_cadastradas": len(registros),
    }


# ------------------------------------------------------------------ ficha --

def obter_moto(moto_id: str) -> dict | None:
    return motos.obter(moto_id)


def _contrato_ativo(moto_id: str) -> dict | None:
    return next(
        (c for c in contratos.listar() if c["moto_id"] == moto_id and c["status"] == "ativo"),
        None,
    )


def _nome_do_cliente(cliente_id: str) -> str:
    return next((c["nome"] for c in clientes.listar() if c["id"] == cliente_id), "—")


def carregar_cabecalho(moto: dict) -> dict:
    """Locatário atual, para a linha de resumo do topo da ficha."""
    contrato = _contrato_ativo(moto["id"]) if moto["status"] == "alugada" else None
    return {
        "locatario": _nome_do_cliente(contrato["cliente_id"]) if contrato else None,
        "desde": contrato["data_inicio"] if contrato else None,
    }


def carregar_aba(moto: dict, aba: str, hoje: date | None = None) -> dict:
    """Dados da aba pedida; cada aba só busca o que mostra (a Financeiro roda um relatório)."""
    hoje = hoje or hoje_br()
    return _ABAS[aba](moto, hoje)


def _aba_resumo(moto: dict, hoje: date) -> dict:
    contrato = _contrato_ativo(moto["id"])
    resumo_contrato = None
    if contrato:
        abertas = sorted(
            (
                c
                for c in cobrancas.listar_por_contrato(contrato["id"])
                if c["situacao"] == "aberta" and c["tipo"] == "locacao"
            ),
            key=lambda c: c["vencimento"],
        )
        resumo_contrato = {
            "cliente": _nome_do_cliente(contrato["cliente_id"]),
            "data_inicio": contrato["data_inicio"],
            "periodicidade": contrato["periodicidade"],
            "valor_periodo": contrato["valor_periodo"],
            "caucao": contrato["caucao_valor"],
            "proxima_cobranca": abertas[0]["vencimento"] if abertas else None,
        }
    # Mesma data: a leitura maior primeiro (a mais recente do dia)
    leituras = sorted(motos.historico(moto["id"]), key=lambda h: (h["data"], h["km"]), reverse=True)
    return {"contrato": resumo_contrato, "leituras": leituras[:_LEITURAS_DE_KM_NA_FICHA]}


def _aba_plano(moto: dict, hoje: date) -> dict:
    linhas = [
        motos_lista.descrever_item_plano(
            item, moto["km_atual"], manutencao.situacao_item_plano(item, moto["km_atual"]), hoje
        )
        for item in manutencao.listar_plano_moto(moto["id"])
    ]
    return {"linhas": linhas, "rotulo_situacao": motos_lista.rotulo_situacao_plano}


def _aba_historico(moto: dict, hoje: date) -> dict:
    registros = sorted(
        manutencao.listar_manutencoes(moto["id"]), key=lambda m: m["data_entrada"], reverse=True
    )
    return {"manutencoes": registros}


def _aba_documentos(moto: dict, hoje: date) -> dict:
    itens = []
    for doc in documentos.listar_por_moto(moto["id"]):
        chave, texto = motos_lista.situacao_documento(doc, hoje)
        itens.append({"documento": doc, "situacao": chave, "rotulo": texto})
    return {"documentos": itens}


def _aba_contratos(moto: dict, hoje: date) -> dict:
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    registros = sorted(
        (c for c in contratos.listar() if c["moto_id"] == moto["id"]),
        key=lambda c: c["data_inicio"],
        reverse=True,
    )
    return {"contratos": [{**c, "cliente": nomes.get(c["cliente_id"], "—")} for c in registros]}


def _aba_financeiro(moto: dict, hoje: date) -> dict:
    resultado = relatorios.resultado_por_moto(date(1900, 1, 1), hoje)["resultado"]
    return {"financeiro": next((r for r in resultado if r["moto_id"] == moto["id"]), None)}


_ABAS = {
    "resumo": _aba_resumo,
    "plano": _aba_plano,
    "historico": _aba_historico,
    "documentos": _aba_documentos,
    "contratos": _aba_contratos,
    "financeiro": _aba_financeiro,
}
