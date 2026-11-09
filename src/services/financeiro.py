"""Dashboard: o que cada aba mostra (Hoje, Dinheiro e Frota), todas lendo das mesmas fontes (RPCs e views do financeiro).

Cada indicador tem uma definição e um lugar só: o caixa, a receita e as despesas vêm de `rpc_resumo_financeiro`; entradas por conta,
despesas por categoria e a receita da semana vêm de `rpc_detalhe_financeiro`; o que está vencido vem das cobranças."""

import logging
from datetime import date
from decimal import Decimal
from typing import Callable, Optional

from src.domain import financeiro, painel
from src.domain.cobrar_agora import analisar_cobranca, atencao_financeira, parcelas_de_divida_atrasadas
from src.domain.valores import hoje_br
from src.repositories import contratos, financeiro as repositorio
from src.services import clientes, cobrancas, configuracoes, motos

logger = logging.getLogger(__name__)

MESES_NA_EVOLUCAO = 6


def _navegacao(mes: date, hoje: date) -> dict:
    """Mês escolhido e os endereços para andar entre os meses (valem mesmo sem os totais)."""
    primeiro = financeiro.primeiro_dia(hoje)
    return {
        "mes": mes,
        "mes_texto": mes.strftime("%Y-%m"),
        "mes_rotulo": financeiro.rotulo_mes(mes),
        "mes_anterior": financeiro.somar_meses(mes, -1).strftime("%Y-%m"),
        "mes_seguinte": financeiro.somar_meses(mes, 1).strftime("%Y-%m") if mes < primeiro else None,
        "mes_maximo": primeiro.strftime("%Y-%m"),
        "e_mes_atual": mes == primeiro,
    }


def _seguro(funcao: Callable[[], dict], rotulo: str, quando_falhar: Callable[[], dict]) -> dict:
    """Roda `funcao`; se a leitura falhar (migration pendente, banco fora do ar) o erro vai para o log e a aba mostra só o aviso
    de indisponível, em vez de derrubar o Dashboard inteiro."""
    try:
        return funcao()
    except Exception:
        logger.exception("Não foi possível montar a aba %s do Dashboard", rotulo)
        return {**quando_falhar(), "indisponivel": True}


def _corte(config: dict) -> int:
    # Banco ainda sem a coluna (migration 20261104140000 pendente): vale o corte de sempre, 15 dias.
    return int(config.get("dias_inadimplencia") or financeiro.DIAS_INADIMPLENTE)


# ------------------------------------------------------------------------------------------------ aba Hoje --


def painel_hoje(hoje: Optional[date] = None) -> dict:
    """Aba Hoje: o que cobrar agora, a frota e o caixa do mês corrente, mais as pendências de dinheiro."""
    hoje = hoje or hoje_br()
    mes = financeiro.primeiro_dia(hoje)
    config = configuracoes.obter()
    corte = _corte(config)
    frota = motos.listar()
    cobranca = analisar_cobranca(
        cobrancas.listar(),
        {c["id"]: c["nome"] for c in clientes.listar()},
        {m["id"]: m["placa"] for m in frota},
        Decimal(str(config["multa_atraso_valor"])),
        Decimal(str(config["encargo_diario_valor"])),
        hoje,
        corte,
    )
    contagem = painel.contar_por_status(frota)
    try:
        meses = [financeiro.consolidar_mes(m) for m in repositorio.resumo_mensal(mes, MESES_NA_EVOLUCAO)]
        atual = meses[-1]
        detalhe = repositorio.detalhe_mensal(mes)
        entradas = financeiro.entradas_por_conta(detalhe["entradas_por_conta"])
        caixa = {"valor": atual["caixa"], "investimento": atual["investimento"], "serie": financeiro.sparkline([m["caixa"] for m in meses])}
        pendencias = atencao_financeira(
            parcelas_de_divida_atrasadas(repositorio.parcelas_de_divida()),
            Decimal(str(detalhe["a_repassar"])),
            entradas["sem_conta"],
        )
    except Exception:
        # O dinheiro do mês (RPCs) não pode esconder quem cobrar: sem ele, só o cartão do caixa e as pendências de dinheiro somem.
        logger.exception("Não foi possível ler o caixa do mês para a aba Hoje")
        caixa, pendencias = None, []
    return {
        "mes_texto": mes.strftime("%Y-%m"),
        "cobranca": cobranca,
        "faixas": financeiro.descricao_das_faixas(corte),
        "frota": {
            "total": len(frota),
            "contagem": contagem,
            "ativas": painel.total_ativas(contagem),
            "ocupacao": painel.percentual_ocupacao(contagem),
        },
        "caixa": caixa,
        "atencao_financeira": pendencias,
    }


def painel_hoje_seguro(hoje: Optional[date] = None) -> dict:
    """Se a leitura de cobranças e frota falhar, a aba mostra o aviso; se só o caixa falhar, `caixa` vem vazio e o resto aparece."""
    hoje = hoje or hoje_br()
    return _seguro(lambda: painel_hoje(hoje), "Hoje", lambda: {"mes_texto": financeiro.primeiro_dia(hoje).strftime("%Y-%m")})


# -------------------------------------------------------------------------------------------- aba Dinheiro --


def painel_dinheiro(mes_texto: Optional[str] = None, hoje: Optional[date] = None) -> dict:
    """Aba Dinheiro para o mês pedido (`aaaa-mm`; vazio = mês atual).

    Receita, despesas, resultado e caixa são do mês escolhido. Dívidas e receita estimada são a posição de hoje."""
    hoje = hoje or hoje_br()
    mes = financeiro.mes_da_consulta(mes_texto, hoje)
    meses = [financeiro.consolidar_mes(m) for m in repositorio.resumo_mensal(mes, MESES_NA_EVOLUCAO)]
    atual = meses[-1]
    detalhe = repositorio.detalhe_mensal(mes)
    lista_cobrancas = cobrancas.listar()
    previsto = financeiro.previsto_do_mes(lista_cobrancas, mes)
    esperado = financeiro.previsto_ate_hoje(lista_cobrancas, mes, hoje)
    return {
        **_navegacao(mes, hoje),
        "atual": atual,
        "anterior": meses[-2] if len(meses) > 1 else None,
        "evolucao": [{**m, "rotulo": financeiro.rotulo_mes_curto(m["mes"])} for m in meses],
        "previsto": previsto,
        "percentual_previsto": painel.percentual_recebido(atual["receita"], previsto),
        # Onde a receita deveria estar hoje (as cobranças que já venceram), para o bullet: marca = esperado ÷ previsto do mês
        "esperado_ate_hoje": esperado,
        "percentual_esperado": painel.percentual_recebido(esperado, previsto),
        "variacoes": None if mes == financeiro.primeiro_dia(hoje) else financeiro.variacoes_do_mes(
            atual, meses[-2] if len(meses) > 1 else None, painel.nome_do_mes(financeiro.somar_meses(mes, -1))),
        "dividas": financeiro.saldo_das_dividas(repositorio.saldos_dividas()),
        "receita_estimada": financeiro.receita_mensal_estimada(contratos.listar()),
        "receita_semana": Decimal(str(detalhe["receita_semana"])),
        "entradas": financeiro.entradas_por_conta(detalhe["entradas_por_conta"]),
        "categorias": financeiro.despesas_por_categoria(detalhe["despesas_por_categoria"]),
        "grafico": financeiro.colunas_evolucao(meses),
    }


def painel_dinheiro_seguro(mes_texto: Optional[str] = None, hoje: Optional[date] = None) -> dict:
    hoje = hoje or hoje_br()
    return _seguro(
        lambda: painel_dinheiro(mes_texto, hoje), "Dinheiro",
        lambda: _navegacao(financeiro.mes_da_consulta(mes_texto, hoje), hoje),
    )


# ---------------------------------------------------------------------------------------------- aba Frota --


def painel_frota(hoje: Optional[date] = None) -> dict:
    """Aba Frota: resultado de cada veículo (desde o início) e o gasto com manutenção do mês, que é o mesmo da aba Dinheiro."""
    hoje = hoje or hoje_br()
    mes = financeiro.primeiro_dia(hoje)
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    locatarios = {c["moto_id"]: nomes.get(c["cliente_id"], "—") for c in contratos.listar() if c["status"] == "ativo"}
    categorias = financeiro.despesas_por_categoria(repositorio.detalhe_mensal(mes)["despesas_por_categoria"])
    manutencao = next((c["valor"] for c in categorias["linhas"] if c["categoria"] == "manutencao"), Decimal("0.00"))
    return {
        "veiculos": financeiro.resultado_por_veiculo(repositorio.resultado_por_veiculo(), locatarios),
        "manutencao_mes": manutencao,
        "mes_rotulo": financeiro.rotulo_mes(mes),
    }


def painel_frota_seguro(hoje: Optional[date] = None) -> dict:
    return _seguro(lambda: painel_frota(hoje), "Frota", lambda: {})
