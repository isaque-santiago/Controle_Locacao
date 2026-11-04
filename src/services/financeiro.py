"""Dashboard financeiro: reúne os totais do mês, a evolução de 6 meses, os devedores e as dívidas."""

from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain import financeiro
from src.domain.valores import hoje_br
from src.repositories import contratos, financeiro as repositorio
from src.services import clientes, cobrancas, configuracoes, motos

MESES_NA_EVOLUCAO = 6


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
    devedores = financeiro.analisar_devedores(
        cobrancas.listar(),
        {c["id"]: c["nome"] for c in clientes.listar()},
        {m["id"]: m["placa"] for m in motos.listar()},
        Decimal(str(config["multa_atraso_valor"])),
        Decimal(str(config["encargo_diario_valor"])),
        hoje,
    )
    dividas = financeiro.saldo_das_dividas(repositorio.saldos_dividas())
    anterior_mes = financeiro.somar_meses(mes, -1)
    return {
        "mes": mes,
        "mes_texto": mes.strftime("%Y-%m"),
        "mes_rotulo": financeiro.rotulo_mes(mes),
        "mes_anterior": anterior_mes.strftime("%Y-%m"),
        "mes_seguinte": financeiro.somar_meses(mes, 1).strftime("%Y-%m") if mes < financeiro.primeiro_dia(hoje) else None,
        "e_mes_atual": mes == financeiro.primeiro_dia(hoje),
        "atual": atual,
        "anterior": anterior,
        "evolucao": [{**m, "rotulo": financeiro.rotulo_mes_curto(m["mes"])} for m in meses],
        "devedores": devedores,
        "dividas": dividas,
        "receita_estimada": financeiro.receita_mensal_estimada(contratos.listar()),
    }
