"""Dashboard financeiro: totais do mês, evolução de 6 meses, entradas, despesas, devedores, dívidas, veículos e alertas."""

import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain import financeiro
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


def painel_seguro(mes_texto: Optional[str] = None, hoje: Optional[date] = None) -> dict:
    """Como `painel`, mas uma falha ao ler o financeiro (migration pendente, banco fora do ar) não derruba o Dashboard:
    devolve só a navegação de mês com `indisponivel` verdadeiro, e o erro vai para o log."""
    hoje = hoje or hoje_br()
    try:
        return painel(mes_texto, hoje)
    except Exception:
        logger.exception("Não foi possível montar o painel financeiro")
        mes = financeiro.mes_da_consulta(mes_texto, hoje)
        return {**_navegacao(mes, hoje), "indisponivel": True}


def painel(mes_texto: Optional[str] = None, hoje: Optional[date] = None) -> dict:
    """Tudo o que a seção Financeiro mostra para o mês pedido (`aaaa-mm`; vazio = mês atual).

    Receita, despesas, resultado e caixa são do mês escolhido. Devedores, encargos, dívidas e receita
    estimada são a posição de hoje, qualquer que seja o mês."""
    hoje = hoje or hoje_br()
    mes = financeiro.mes_da_consulta(mes_texto, hoje)
    meses = [financeiro.consolidar_mes(m) for m in repositorio.resumo_mensal(mes, MESES_NA_EVOLUCAO)]
    atual = meses[-1]
    anterior = meses[-2] if len(meses) > 1 else None

    config = configuracoes.obter()
    # Banco ainda sem a coluna (migration 20261104140000 pendente): vale o corte de sempre, 15 dias.
    corte = int(config.get("dias_inadimplencia") or financeiro.DIAS_INADIMPLENTE)
    devedores = financeiro.analisar_devedores(
        cobrancas.listar(),
        {c["id"]: c["nome"] for c in clientes.listar()},
        {m["id"]: m["placa"] for m in motos.listar()},
        Decimal(str(config["multa_atraso_valor"])),
        Decimal(str(config["encargo_diario_valor"])),
        hoje,
        corte,
    )
    dividas = financeiro.saldo_das_dividas(repositorio.saldos_dividas())
    detalhe = repositorio.detalhe_mensal(mes)
    entradas = financeiro.entradas_por_conta(detalhe["entradas_por_conta"])
    a_repassar = Decimal(str(detalhe["a_repassar"]))
    contratos_lista = contratos.listar()
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    locatarios = {c["moto_id"]: nomes.get(c["cliente_id"], "—") for c in contratos_lista if c["status"] == "ativo"}
    em_manutencao = sum(1 for m in motos.listar() if m["status"] == "manutencao")
    return {
        **_navegacao(mes, hoje),
        "atual": atual,
        "anterior": anterior,
        "evolucao": [{**m, "rotulo": financeiro.rotulo_mes_curto(m["mes"])} for m in meses],
        "devedores": devedores,
        "faixas": financeiro.descricao_das_faixas(corte),
        "dividas": dividas,
        "receita_estimada": financeiro.receita_mensal_estimada(contratos_lista),
        "receita_semana": Decimal(str(detalhe["receita_semana"])),
        "entradas": entradas,
        "categorias": financeiro.despesas_por_categoria(detalhe["despesas_por_categoria"]),
        "veiculos": financeiro.resultado_por_veiculo(repositorio.resultado_por_veiculo(), locatarios),
        "grafico": financeiro.colunas_evolucao(meses),
        "alertas": financeiro.alertas_financeiros(devedores, atual, a_repassar, entradas["sem_conta"], em_manutencao, corte),
    }
