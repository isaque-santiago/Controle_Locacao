"""Regras do Dashboard financeiro (mês, caixa, devedores). Funções puras, sem banco nem tela.

Mesmas definições da RPC `rpc_resumo_financeiro`:
  resultado = receita - despesas (custo operacional, sem investimento em veículo);
  caixa     = receita - despesas - investimento - parcelas de dívida - retiradas + aportes.
"""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from src.domain.encargos import calcular_encargos

# A partir de quantos dias de atraso o contrato passa de "em atraso" para "inadimplente".
DIAS_INADIMPLENTE = 15
MAX_DEVEDORES = 8
_ZERO = Decimal("0.00")
_CENTAVOS = Decimal("0.01")
_MESES_CURTOS = ("jan.", "fev.", "mar.", "abr.", "mai.", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez.")
_MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def _dinheiro(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(_CENTAVOS, rounding=ROUND_HALF_UP)


def primeiro_dia(data: date) -> date:
    return data.replace(day=1)


def mes_da_consulta(texto: Optional[str], hoje: date) -> date:
    """Primeiro dia do mês pedido em `aaaa-mm`. Vazio, inválido ou futuro vale o mês de hoje."""
    atual = primeiro_dia(hoje)
    try:
        ano, mes = str(texto or "").strip().split("-")
        pedido = date(int(ano), int(mes), 1)
    except ValueError:
        return atual
    return atual if pedido > atual else pedido


def somar_meses(mes: date, quantidade: int) -> date:
    indice = mes.year * 12 + (mes.month - 1) + quantidade
    return date(indice // 12, indice % 12 + 1, 1)


def rotulo_mes(mes: date) -> str:
    return f"{_MESES[mes.month - 1]} de {mes.year}"


def rotulo_mes_curto(mes: date) -> str:
    return f"{_MESES_CURTOS[mes.month - 1]}/{str(mes.year)[2:]}"


def consolidar_mes(bruto: dict) -> dict:
    """Totais de um mês da RPC (texto ou número) em Decimal, com resultado, caixa e margem."""
    receita = _dinheiro(bruto.get("receita"))
    despesas = _dinheiro(bruto.get("despesas"))
    investimento = _dinheiro(bruto.get("investimento"))
    parcelas = _dinheiro(bruto.get("parcelas_divida"))
    retiradas = _dinheiro(bruto.get("retiradas"))
    aportes = _dinheiro(bruto.get("aportes"))
    resultado = receita - despesas
    return {
        "mes": date.fromisoformat(str(bruto["mes"])[:10]),
        "receita": receita,
        "despesas": despesas,
        "investimento": investimento,
        "parcelas_divida": parcelas,
        "retiradas": retiradas,
        "aportes": aportes,
        "resultado": resultado,
        "caixa": resultado - investimento - parcelas - retiradas + aportes,
        "margem": margem(receita, resultado),
    }


def margem(receita: Decimal, resultado: Decimal) -> Optional[int]:
    """Resultado como % da receita, arredondado; None sem receita."""
    if receita <= 0:
        return None
    return int((resultado * 100 / receita).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# Quantas cobranças cada periodicidade gera por mês (52 semanas e 365 dias por ano).
_COBRANCAS_POR_MES = {
    "diario": Decimal(365) / 12,
    "semanal": Decimal(52) / 12,
    "quinzenal": Decimal(26) / 12,
    "mensal": Decimal(1),
}


def receita_mensal_estimada(contratos: list[dict]) -> Decimal:
    """Receita mensal dos contratos ativos: valor da cobrança x cobranças por mês da periodicidade."""
    total = Decimal(0)
    for c in contratos:
        if c.get("status") != "ativo":
            continue
        total += Decimal(str(c.get("valor_periodo") or 0)) * _COBRANCAS_POR_MES.get(c.get("periodicidade"), Decimal(0))
    return total.quantize(_CENTAVOS, rounding=ROUND_HALF_UP)


def faixa_de_atraso(dias: int, corte: int = DIAS_INADIMPLENTE) -> str:
    """'em_atraso' (até corte-1 dias) ou 'inadimplente' (corte dias ou mais)."""
    return "inadimplente" if dias >= corte else "em_atraso"


def analisar_devedores(
    cobrancas: list[dict],
    nomes_clientes: dict,
    placas_motos: dict,
    multa_valor: Decimal,
    adicional_diario_valor: Decimal,
    hoje: date,
    corte: int = DIAS_INADIMPLENTE,
    limite: int = MAX_DEVEDORES,
) -> dict:
    """Quem deve hoje: débito (saldo vencido), encargos de atraso e ranking por contrato.

    Só entram cobranças atrasadas e com saldo. Cada contrato tem um único dia de atraso, o da
    cobrança mais antiga em aberto. O ranking traz os `limite` maiores (débito + encargos)."""
    por_contrato = defaultdict(lambda: {"debito": _ZERO, "encargos": _ZERO, "dias": 0})
    for c in cobrancas:
        saldo = Decimal(str(c.get("saldo") or 0))
        if c.get("situacao") != "atrasada" or saldo <= 0:
            continue
        calculo = calcular_encargos(
            tipo=c["tipo"],
            saldo=saldo,
            vencimento=date.fromisoformat(str(c["vencimento"])[:10]),
            data_referencia=hoje,
            multa_valor=multa_valor,
            adicional_diario_valor=adicional_diario_valor,
        )
        item = por_contrato[(c["contrato_id"], c["cliente_id"], c["moto_id"])]
        item["debito"] += saldo
        item["encargos"] += calculo["encargos"]
        item["dias"] = max(item["dias"], calculo["dias_atraso"])

    linhas = [
        {
            "contrato_id": contrato,
            "cliente": nomes_clientes.get(cliente, "—"),
            "placa": placas_motos.get(moto, "—"),
            "dias_atraso": v["dias"],
            "faixa": faixa_de_atraso(v["dias"], corte),
            "debito": v["debito"],
            "encargos": v["encargos"],
            "total": v["debito"] + v["encargos"],
        }
        for (contrato, cliente, moto), v in por_contrato.items()
    ]
    linhas.sort(key=lambda l: (l["total"], l["dias_atraso"]), reverse=True)
    return {
        "a_receber": sum((l["debito"] for l in linhas), _ZERO),
        "encargos": sum((l["encargos"] for l in linhas), _ZERO),
        "contratos_em_aberto": len(linhas),
        "em_atraso": sum(1 for l in linhas if l["faixa"] == "em_atraso"),
        "inadimplentes": sum(1 for l in linhas if l["faixa"] == "inadimplente"),
        "ranking": linhas[:limite],
    }


def saldo_das_dividas(saldos: list[dict]) -> dict:
    """Saldo em aberto das dívidas (o confirmado pelo responsável, senão o calculado) e o total de motos fiado."""
    total = _ZERO
    fiado = _ZERO
    for s in saldos:
        confirmado = s.get("saldo_confirmado")
        saldo = Decimal(str(confirmado if confirmado is not None else s.get("saldo_calculado") or 0))
        saldo = max(saldo, _ZERO)
        total += saldo
        if s.get("tipo") == "moto_fiado":
            fiado += saldo
    return {"total": total, "moto_fiado": fiado}



# ---------------------------------------------------------------------------
# Etapa 2: entradas por conta, despesas por categoria, resultado por veículo, alertas e gráfico
# ---------------------------------------------------------------------------

SEM_CONTA = "Sem conta informada"
_CATEGORIAS = {
    "manutencao": "Manutenção",
    "documentacao": "Documentação",
    "seguro_rastreador": "Seguro e rastreador",
    "multas": "Multas",
    "combustivel": "Combustível",
    "outros": "Outros",
    "aquisicao": "Investimento em veículo",
}


def _percentuais(valores: list[Decimal]) -> list[int]:
    """Cada valor como % do maior (0 a 100); tudo zero quando não há valor positivo."""
    maior = max(valores, default=_ZERO)
    if maior <= 0:
        return [0 for _ in valores]
    return [int((v * 100 / maior).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) for v in valores]


def entradas_por_conta(linhas: list[dict]) -> dict:
    """Entradas do mês por conta, a maior primeiro; as sem conta somam em 'Sem conta informada'."""
    somas: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    for l in linhas:
        somas[l.get("conta") or SEM_CONTA] += _dinheiro(l.get("valor"))
    ordenadas = sorted(somas.items(), key=lambda par: par[1], reverse=True)
    proporcoes = _percentuais([v for _, v in ordenadas])
    return {
        "linhas": [{"conta": c, "valor": v, "proporcao": p} for (c, v), p in zip(ordenadas, proporcoes)],
        "total": sum(somas.values(), _ZERO),
        "sem_conta": somas.get(SEM_CONTA, _ZERO),
    }


def despesas_por_categoria(linhas: list[dict]) -> dict:
    """Despesas do mês por categoria, a maior primeiro, com o rótulo em português."""
    somas: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    for l in linhas:
        somas[l["categoria"]] += _dinheiro(l.get("valor"))
    ordenadas = sorted(((c, v) for c, v in somas.items() if v > 0), key=lambda par: par[1], reverse=True)
    proporcoes = _percentuais([v for _, v in ordenadas])
    return {
        "linhas": [
            {"categoria": c, "rotulo": _CATEGORIAS.get(c, c.replace("_", " ").capitalize()), "valor": v, "proporcao": p}
            for (c, v), p in zip(ordenadas, proporcoes)
        ],
        "total": sum((v for _, v in ordenadas), _ZERO),
    }


def resultado_por_veiculo(linhas: list[dict], locatarios: dict) -> list[dict]:
    """Receita, despesas e resultado de cada veículo (de `vw_resultado_moto`, desde o início), do melhor ao pior.

    Despesas = manutenção + documentos + despesas da locadora (sem aquisição, que é capital)."""
    saida = []
    for l in linhas:
        receita = _dinheiro(l.get("receita_recebida"))
        despesas = (
            _dinheiro(l.get("custo_manutencao")) + _dinheiro(l.get("custo_documentos")) + _dinheiro(l.get("custo_despesas"))
        )
        saida.append({
            "moto_id": l["moto_id"],
            "placa": l.get("placa") or "—",
            "locatario": locatarios.get(l["moto_id"], "—"),
            "receita": receita,
            "despesas": despesas,
            "resultado": receita - despesas,
        })
    saida.sort(key=lambda v: (v["resultado"], v["placa"]), reverse=True)
    return saida


def alertas_financeiros(
    devedores: dict,
    mes: dict,
    a_repassar: Decimal,
    entradas_sem_conta: Decimal,
    motos_em_manutencao: int,
) -> list[dict]:
    """Indicadores com semáforo (como o quadro "Alertas e pendências" da planilha).

    `tom` combina com os selos da tela: perigo (crítico), atencao, ok e info. `formato` diz se `valor` é dinheiro ou quantidade."""

    def nivel(condicao: bool, tom: str) -> tuple[str, str]:
        rotulos = {"perigo": "Crítico", "atencao": "Atenção", "ok": "OK", "info": "Info"}
        escolhido = tom if condicao else "ok"
        return escolhido, rotulos[escolhido]

    total_a_cobrar = devedores["a_receber"] + devedores["encargos"]
    itens = [
        ("Contratos inadimplentes (15 dias ou mais)", devedores["inadimplentes"], "qtd", *nivel(devedores["inadimplentes"] > 0, "perigo")),
        ("Contratos em atraso (até 14 dias)", devedores["em_atraso"], "qtd", *nivel(devedores["em_atraso"] > 0, "atencao")),
        ("Caixa do mês", mes["caixa"], "moeda", *nivel(mes["caixa"] < 0, "perigo")),
        ("Despesas a repassar ao locatário", a_repassar, "moeda", *nivel(a_repassar > 0, "atencao")),
        ("Entradas do mês sem conta cadastrada", entradas_sem_conta, "moeda", *nivel(entradas_sem_conta > 0, "atencao")),
        ("Motos em manutenção", motos_em_manutencao, "qtd", *nivel(motos_em_manutencao > 0, "atencao")),
        ("Total a cobrar (débito + encargos)", total_a_cobrar, "moeda", *nivel(total_a_cobrar > 0, "atencao")),
        ("Retiradas no mês", mes["retiradas"], "moeda", *nivel(mes["retiradas"] > 0, "atencao")),
        ("Aportes de fora no mês", mes["aportes"], "moeda", "info", "Info"),
    ]
    return [
        {"titulo": t, "valor": v, "formato": f, "tom": tom, "status": status}
        for t, v, f, tom, status in itens
    ]


def colunas_evolucao(meses: list[dict], largura: int = 600, altura: int = 180, margem_rotulo: int = 28) -> dict:
    """Geometria (em unidades do viewBox do SVG) das colunas de receita e despesas por mês.

    A mesma escala vale para os dois: o maior valor de toda a série ocupa a altura inteira."""
    maior = max([m["receita"] for m in meses] + [m["despesas"] for m in meses], default=_ZERO)
    faixa = Decimal(largura) / max(len(meses), 1)
    barra = faixa * Decimal("0.3")

    def retangulo(inicio: Decimal, valor: Decimal) -> dict:
        h = (valor * altura / maior).quantize(Decimal("0.1")) if maior > 0 and valor > 0 else _ZERO
        return {"x": float(inicio.quantize(Decimal("0.1"))), "y": float(Decimal(altura) - h), "largura": float(barra.quantize(Decimal("0.1"))),
                "altura": float(h), "valor": valor}

    colunas = []
    for i, m in enumerate(meses):
        base = faixa * i + faixa * Decimal("0.17")
        colunas.append({
            "rotulo": rotulo_mes_curto(m["mes"]),
            "x_rotulo": float((faixa * i + faixa / 2).quantize(Decimal("0.1"))),
            "receita": retangulo(base, m["receita"]),
            "despesas": retangulo(base + barra + Decimal(4), m["despesas"]),
        })
    return {"largura": largura, "altura": altura + margem_rotulo, "y_base": altura, "y_rotulo": altura + margem_rotulo - 8, "colunas": colunas}


def consulta(mes: Optional[str] = None, compacto: bool = False, ocultar: bool = False) -> str:
    """Texto do parâmetro da URL do Dashboard (`?mes=2026-09&compacto=1&ocultar=1`); vazio se nada foi escolhido."""
    partes = []
    if mes:
        partes.append(f"mes={mes}")
    if compacto:
        partes.append("compacto=1")
    if ocultar:
        partes.append("ocultar=1")
    return "?" + "&".join(partes) if partes else ""


def opcao_ligada(texto: Optional[str]) -> bool:
    """Interruptor da URL: só '1' liga."""
    return texto == "1"
