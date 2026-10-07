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
