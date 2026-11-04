"""Dashboard financeiro: totais do mês, evolução de 6 meses, entradas, despesas, devedores, dívidas, veículos e alertas."""

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
    detalhe = repositorio.detalhe_mensal(mes)
    entradas = financeiro.entradas_por_conta(detalhe["entradas_por_conta"])
    a_repassar = Decimal(str(detalhe["a_repassar"]))
    contratos_lista = contratos.listar()
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    locatarios = {c["moto_id"]: nomes.get(c["cliente_id"], "—") for c in contratos_lista if c["status"] == "ativo"}
    em_manutencao = sum(1 for m in motos.listar() if m["status"] == "manutencao")
    anterior_mes = financeiro.somar_meses(mes, -1)
    return {
        "mes": mes,
        "mes_texto": mes.strftime("%Y-%m"),
        "mes_rotulo": financeiro.rotulo_mes(mes),
        "mes_anterior": anterior_mes.strftime("%Y-%m"),
        "mes_seguinte": financeiro.somar_meses(mes, 1).strftime("%Y-%m") if mes < financeiro.primeiro_dia(hoje) else None,
        "mes_maximo": financeiro.primeiro_dia(hoje).strftime("%Y-%m"),
        "e_mes_atual": mes == financeiro.primeiro_dia(hoje),
        "atual": atual,
        "anterior": anterior,
        "evolucao": [{**m, "rotulo": financeiro.rotulo_mes_curto(m["mes"])} for m in meses],
        "devedores": devedores,
        "dividas": dividas,
        "receita_estimada": financeiro.receita_mensal_estimada(contratos_lista),
        "receita_semana": Decimal(str(detalhe["receita_semana"])),
        "entradas": entradas,
        "categorias": financeiro.despesas_por_categoria(detalhe["despesas_por_categoria"]),
        "veiculos": financeiro.resultado_por_veiculo(repositorio.resultado_por_veiculo(), locatarios),
        "grafico": financeiro.colunas_evolucao(meses),
        "alertas": financeiro.alertas_financeiros(devedores, atual, a_repassar, entradas["sem_conta"], em_manutencao),
    }
