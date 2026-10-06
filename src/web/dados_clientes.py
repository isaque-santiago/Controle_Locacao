"""Fronteira de leitura das telas web de Clientes."""

from decimal import Decimal

from src.domain import clientes_lista
from src.domain.cnh_regras import situacao_cnh
from src.domain.valores import hoje_br
from src.services import clientes, cobrancas, configuracoes, contratos, motos


def carregar_lista(status, busca, pagina, por_pagina):
    registros = clientes.listar()
    itens, recorte, contagem = clientes_lista.montar_pagina(registros, status, busca, pagina, por_pagina)
    contratos_ativos = {c["cliente_id"]: c for c in contratos.listar() if c["status"] == "ativo"}
    placas = {m["id"]: m["placa"] for m in motos.listar()}
    alerta = configuracoes.obter()["alerta_cnh_dias"]
    hoje = hoje_br()
    saida = []
    for cliente in itens:
        validade = cliente.get("cnh_validade")
        if validade:
            from datetime import date
            validade = date.fromisoformat(str(validade)[:10])
        contrato = contratos_ativos.get(cliente["id"])
        saida.append({
            "cliente": cliente,
            "cnh_situacao": situacao_cnh(validade, hoje, alerta),
            "placa": placas.get(contrato["moto_id"]) if contrato else None,
        })
    return {"itens": saida, "pagina": recorte, "contagem": contagem, "total_cadastrados": len(registros)}


def obter_cliente(cliente_id):
    return clientes.obter(cliente_id)


def carregar_ficha(cliente, aba):
    todos_contratos = [c for c in contratos.listar() if c["cliente_id"] == cliente["id"]]
    frota = {m["id"]: m for m in motos.listar()}
    contratos_com_moto = [{**c, "moto": frota.get(c["moto_id"])} for c in sorted(todos_contratos, key=lambda x: x["data_inicio"], reverse=True)]
    parcelas = []
    historicos = {}
    for contrato in todos_contratos:
        for cobranca in cobrancas.listar_por_contrato(contrato["id"]):
            parcelas.append(cobranca)
    historicos = cobrancas.historicos_pagamentos([c["id"] for c in parcelas])
    pago = sum((Decimal(str(p["valor"])) + Decimal(str(p.get("multa_juros") or 0)) for ps in historicos.values() for p in ps), Decimal(0))
    em_aberto = sum((Decimal(str(c["saldo"])) for c in parcelas if c["situacao"] == "aberta"), Decimal(0))
    atrasado = sum((Decimal(str(c["saldo"])) for c in parcelas if c["situacao"] == "atrasada"), Decimal(0))
    return {"contratos": contratos_com_moto, "parcelas": sorted(parcelas, key=lambda x: x["vencimento"], reverse=True),
            "historicos": historicos, "pago": pago, "em_aberto": em_aberto, "atrasado": atrasado}
