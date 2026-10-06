"""Dados do Dashboard: reúne os serviços e as regras de src/domain num único dicionário.

É a fronteira entre a rota e a camada de dados: a rota só renderiza o que esta função devolve
(e os testes das rotas trocam esta função por dados fictícios)."""

from datetime import date

from src.domain import painel
from src.domain.valores import hoje_br
from src.services import (
    alertas,
    clientes,
    cobrancas,
    configuracoes,
    dashboard,
    manutencao,
)


def carregar(hoje: date | None = None) -> dict:
    hoje = hoje or hoje_br()
    cobrancas.gerar_cobrancas_pendentes()
    dados = dashboard.resumo()
    frota = dados["frota"]
    contagem = painel.contar_por_status(frota)
    placas = {m["id"]: m["placa"] for m in frota}
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}

    linhas_hoje = [
        {
            "id": c["id"],
            "cliente": nomes.get(c["cliente_id"], "—"),
            "placa": placas.get(c["moto_id"], "—"),
            "vencimento": c["vencimento"],
            "valor": c["valor"],
            "atrasada": c["situacao"] == "atrasada",
            "dias_atraso": painel.dias_em_atraso(c["vencimento"], hoje),
        }
        for c in painel.cobrancas_de_hoje(dados["cobrancas"], hoje)
    ]

    return {
        "data_extenso": painel.data_por_extenso(hoje),
        "frota_total": len(frota),
        "contagem": contagem,
        "ocupacao": painel.percentual_ocupacao(contagem),
        "segmentos_medidor": painel.segmentos_medidor(contagem),
        "descricao_medidor": painel.descricao_medidor(contagem),
        "legenda": painel.segmentos_frota(contagem),
        "recebido": dados["recebido"],
        "previsto": dados["previsto"],
        "percentual_recebido": painel.percentual_recebido(dados["recebido"], dados["previsto"]),
        "atrasado": dados["atrasado"],
        "clientes_atrasados": len(dados["devedores"]),
        "manutencao_mes": dados["manutencao"],
        "ordens_concluidas": painel.ordens_concluidas_no_mes(manutencao.listar_manutencoes(), hoje),
        "hoje": linhas_hoje,
        "alertas": painel.agrupar_alertas(
            configuracoes.obter(),
            alertas.listar_manutencao(),
            alertas.listar_documentos(),
            alertas.listar_cnh(),
        ),
    }
