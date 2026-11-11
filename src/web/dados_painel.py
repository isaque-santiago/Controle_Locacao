"""Dados do Dashboard: reúne os serviços e as regras de src/domain num único dicionário, só o que a aba pedida mostra.

É a fronteira entre a rota e a camada de dados: a rota só renderiza o que esta função devolve
(e os testes das rotas trocam esta função por dados fictícios).

Três abas (`/?aba=hoje|dinheiro|frota`), cada uma com a sua leitura, e todas com os números das mesmas fontes (ver `services/financeiro`)."""

from datetime import date

from src.domain import financeiro, painel
from src.domain.cobrar_agora import ordenar_atencao
from src.domain.valores import hoje_br
from src.services import (
    alertas,
    clientes,
    cobrancas,
    configuracoes,
    documentos,
    manutencao,
    motos,
    whatsapp_painel,
)
from src.services import financeiro as financeiro_servico


def _hoje(hoje: date) -> dict:
    """Aba Hoje: cobrar agora, os quatro indicadores do topo e a lista única de atenção."""
    dados = financeiro_servico.painel_hoje_seguro(hoje)
    config = configuracoes.obter()
    if dados.get("indisponivel"):
        atencao = []
    else:
        atencao = dados["atencao_financeira"]
    itens = painel.agrupar_alertas(
        config, alertas.listar_manutencao(), alertas.listar_documentos(), alertas.listar_cnh()
    ) + documentos.alertas_de_comprovantes() + whatsapp_painel.alertas(config) + atencao
    return {"hoje": {**dados, "atencao": ordenar_atencao(itens)}, "mes": None, "mes_anterior": None, "mes_seguinte": None}


def _dinheiro(hoje: date, mes: str | None) -> dict:
    dados = financeiro_servico.painel_dinheiro_seguro(mes, hoje)
    return {"dinheiro": dados, "mes": dados["mes_texto"], "mes_anterior": dados["mes_anterior"], "mes_seguinte": dados["mes_seguinte"]}


def _frota(hoje: date) -> dict:
    frota = motos.listar()
    contagem = painel.contar_por_status(frota)
    ordens = manutencao.listar_manutencoes()
    dados = {
        "total": len(frota),
        "contagem": contagem,
        "ocupacao": painel.percentual_ocupacao(contagem),
        "ativas": painel.total_ativas(contagem),
        "rosca": painel.segmentos_rosca(contagem),
        "descricao_medidor": painel.descricao_medidor(contagem),
        "legenda": painel.segmentos_frota(contagem),
        "ordens_concluidas": painel.ordens_concluidas_no_mes(ordens, hoje),
        "manutencao_aberta": painel.manutencao_em_andamento(ordens),
        **financeiro_servico.painel_frota_seguro(hoje),
    }
    return {"frota": dados, "mes": None, "mes_anterior": None, "mes_seguinte": None}


def carregar(
    hoje: date | None = None, mes: str | None = None, compacto: bool = False, ocultar: bool = False, aba: str | None = None
) -> dict:
    """`aba` escolhe o que carregar (Hoje por padrão); `mes` (aaaa-mm) só vale na aba Dinheiro.

    `compacto` mostra só os indicadores e a atenção; `ocultar` esconde valores, nomes e placas."""
    hoje = hoje or hoje_br()
    aba = financeiro.aba_do_painel(aba)
    cobrancas.gerar_cobrancas_pendentes()
    conteudo = {"hoje": lambda: _hoje(hoje), "dinheiro": lambda: _dinheiro(hoje, mes), "frota": lambda: _frota(hoje)}[aba]()
    links = financeiro.links_do_painel(
        conteudo.pop("mes"), conteudo.pop("mes_anterior"), conteudo.pop("mes_seguinte"), compacto, ocultar, aba
    )
    return {
        "data_extenso": painel.data_por_extenso(hoje),
        "aba": aba,
        "abas": [{"chave": chave, "rotulo": rotulo, "href": "/" + links["abas"][chave], "ativa": chave == aba} for chave, rotulo in financeiro.ABAS],
        "compacto": compacto,
        "ocultar": ocultar,
        "links": links,
        **conteudo,
    }
