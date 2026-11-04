"""Dados do Dashboard: reúne os serviços e as regras de src/domain num único dicionário.

É a fronteira entre a rota e a camada de dados: a rota só renderiza o que esta função devolve
(e os testes das rotas trocam esta função por dados fictícios)."""

from datetime import date

from src.domain import financeiro, painel
from src.domain.valores import hoje_br
from src.services import (
    alertas,
    clientes,
    cobrancas,
    configuracoes,
    dashboard,
    manutencao,
)
from src.services import financeiro as financeiro_servico


def carregar(hoje: date | None = None, mes: str | None = None, compacto: bool = False, ocultar: bool = False) -> dict:
    """`mes` (aaaa-mm) escolhe o mês da seção Financeiro; o resto do Dashboard é sempre de hoje.

    `compacto` mostra só os indicadores e os alertas; `ocultar` esconde valores, nomes e placas."""
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

    mes_anterior = painel.nome_do_mes(painel.periodo_anterior(hoje)[0])
    resumo_financeiro = financeiro_servico.painel_seguro(mes, hoje)

    return {
        "data_extenso": painel.data_por_extenso(hoje),
        "frota_total": len(frota),
        "contagem": contagem,
        "ocupacao": painel.percentual_ocupacao(contagem),
        "segmentos_medidor": painel.segmentos_medidor(contagem),
        "rosca": painel.segmentos_rosca(contagem),
        "descricao_medidor": painel.descricao_medidor(contagem),
        "legenda": painel.segmentos_frota(contagem),
        "recebido": dados["recebido"],
        "previsto": dados["previsto"],
        "percentual_recebido": painel.percentual_recebido(dados["recebido"], dados["previsto"]),
        "atrasado": dados["atrasado"],
        "clientes_atrasados": len(dados["devedores"]),
        "manutencao_mes": dados["manutencao"],
        "variacoes": {
            "recebido": painel.descrever_variacao(
                painel.variacao(dados["recebido"], dados["recebido_anterior"]), mes_anterior, subir_e_bom=True
            ),
            "manutencao": painel.descrever_variacao(
                painel.variacao(dados["manutencao"], dados["manutencao_anterior"]), mes_anterior, subir_e_bom=False
            ),
        },
        "ordens_concluidas": painel.ordens_concluidas_no_mes(manutencao.listar_manutencoes(), hoje),
        "hoje": linhas_hoje,
        "financeiro": resumo_financeiro,
        "compacto": compacto,
        "ocultar": ocultar,
        "links": financeiro.links_do_painel(
            resumo_financeiro["mes_texto"], resumo_financeiro["mes_anterior"], resumo_financeiro["mes_seguinte"], compacto, ocultar
        ),
        "alertas": painel.agrupar_alertas(
            configuracoes.obter(),
            alertas.listar_manutencao(),
            alertas.listar_documentos(),
            alertas.listar_cnh(),
        ),
    }
