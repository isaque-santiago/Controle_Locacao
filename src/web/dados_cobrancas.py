"""Dados da página Cobranças: reúne os serviços e as regras de src/domain num dicionário.

Fronteira de leitura entre a rota e a camada de dados; os testes das rotas trocam estes serviços
por dados fictícios."""

from src.domain import cobrancas_lista
from src.domain.painel_cobrancas import resumo_atraso
from src.domain.valores import hoje_br
from src.services import clientes, cobrancas, motos

_ABERTAS = ("aberta", "atrasada")


def _linhas(hoje):
    """Todas as cobranças com cliente, placa e (se em aberto) os encargos de hoje."""
    placas = {m["id"]: m["placa"] for m in motos.listar()}
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    config = cobrancas.configuracao_encargos()
    linhas = []
    for c in cobrancas.listar():
        linha = {**c, "placa": placas.get(c["moto_id"]), "cliente": nomes.get(c["cliente_id"])}
        if c["situacao"] in _ABERTAS:
            linha["encargos"] = cobrancas.calcular_encargos_cobranca(c, hoje, config)
        linhas.append(linha)
    return linhas


def _com_pagamento(pagas):
    """Data e forma do último pagamento de cada cobrança paga."""
    historicos = cobrancas.historicos_pagamentos([c["id"] for c in pagas])
    for c in pagas:
        pagamentos = historicos.get(c["id"]) or []
        c["pago_em"] = pagamentos[-1]["data_pagamento"] if pagamentos else None
        c["forma"] = pagamentos[-1]["forma"] if pagamentos else None
    return pagas


def carregar(aba, pagina):
    """Contagem de cada aba, resumo de atraso e a página pedida da aba `aba`."""
    hoje = hoje_br()
    linhas = _linhas(hoje)
    por_aba = cobrancas_lista.classificar(linhas, hoje)
    total_atraso, clientes_atrasados = resumo_atraso(linhas)
    selecionadas = _com_pagamento(por_aba[aba]) if aba == "pagas" else por_aba[aba]
    itens, recorte = cobrancas_lista.montar_pagina(cobrancas_lista.ordenar(aba, selecionadas), pagina)
    return {
        "itens": itens, "pagina": recorte, "contagem": {chave: len(lista) for chave, lista in por_aba.items()},
        "total_atraso": total_atraso, "clientes_atrasados": clientes_atrasados,
    }


# -------------------------------------------------------------------- pagamento --

def obter_para_pagamento(cobranca_id):
    """Cobrança em aberto com cliente e placa; None se não existir ou já não estiver em aberto."""
    c = next((x for x in cobrancas.listar() if x["id"] == cobranca_id), None)
    if c is None or c["situacao"] not in _ABERTAS:
        return None
    cliente = clientes.obter(c["cliente_id"])
    moto = motos.obter(c["moto_id"])
    return {**c, "cliente": cliente["nome"] if cliente else None, "placa": moto["placa"] if moto else None}


def encargos_em(cobranca, data):
    """Multa, adicional diário e total da cobrança na `data` (None: sem encargos, só o saldo)."""
    if data is None:
        return {"dias_atraso": 0, "multa": 0, "adicional_diario": 0, "encargos": 0, "total": cobranca["saldo"]}
    return cobrancas.calcular_encargos_cobranca(cobranca, data, cobrancas.configuracao_encargos())
