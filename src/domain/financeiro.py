"""Regras do Dashboard financeiro (mês, caixa, devedores). Funções puras, sem banco nem tela.

Mesmas definições da RPC `rpc_resumo_financeiro`:
  resultado = receita - despesas (custo operacional, sem investimento em veículo);
  caixa     = receita - despesas - investimento - parcelas de dívida - retiradas + aportes.
"""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from src.domain.painel import descrever_variacao, variacao


# A partir de quantos dias de atraso o contrato passa de "em atraso" para "inadimplente".
DIAS_INADIMPLENTE = 15
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


def previsto_ate_hoje(cobrancas: list[dict], mes: date, hoje: date) -> Decimal:
    """Do previsto do mês, o que já deveria ter entrado: as cobranças que vencem até `hoje` (mês passado: o mês todo)."""
    prefixo = mes.strftime("%Y-%m")
    limite = hoje.isoformat()
    return sum(
        (Decimal(str(c.get("valor") or 0)) for c in cobrancas
         if str(c["vencimento"])[:7] == prefixo and str(c["vencimento"])[:10] <= limite
         and c.get("tipo") != "caucao" and c.get("situacao") != "cancelada"),
        _ZERO,
    )


def sparkline(valores: list, largura: int = 120, altura: int = 24, margem: int = 3) -> Optional[dict]:
    """Pontos de uma linha mínima (sem eixos) para ler a tendência; o número exato fica no cartão. Série de valores iguais vira linha reta
    no meio; com menos de 2 valores devolve None (sem tendência a mostrar). `margem` deixa o ponto final inteiro dentro do quadro."""
    numeros = [Decimal(str(v)) for v in valores]
    if len(numeros) < 2:
        return None
    minimo, maximo = min(numeros), max(numeros)
    faixa = maximo - minimo
    util = altura - 2 * margem
    pontos = []
    for i, v in enumerate(numeros):
        x = round(margem + i * (largura - 2 * margem) / (len(numeros) - 1), 1)
        y = round(altura / 2 if not faixa else margem + util - float((v - minimo) / faixa) * util, 1)
        pontos.append((x, y))
    return {
        "pontos": " ".join(f"{x},{y}" for x, y in pontos), "ultimo": {"x": pontos[-1][0], "y": pontos[-1][1]},
        "largura": largura, "altura": altura, "primeiro": numeros[0], "final": numeros[-1], "minimo": minimo, "maximo": maximo,
    }


def variacoes_do_mes(atual: dict, anterior: Optional[dict], nome_do_mes_anterior: str) -> Optional[dict]:
    """Variação de receita, despesas, resultado e caixa contra o mês anterior, só para mês fechado (mês inteiro contra mês inteiro; no mês
    corrente a comparação seria injusta). Cor pelo resultado: receita, resultado e caixa subindo é bom; despesa subindo é ruim."""
    if anterior is None:
        return None
    sobe_e_bom = {"receita": True, "despesas": False, "resultado": True, "caixa": True}
    return {
        k: descrever_variacao(variacao(atual[k], anterior[k]), nome_do_mes_anterior, bom) for k, bom in sobe_e_bom.items()
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


def descricao_das_faixas(corte: int = DIAS_INADIMPLENTE) -> dict:
    """Texto de cada faixa de atraso para a tela, conforme o corte configurado."""
    dias = f"{corte} dia" if corte == 1 else f"{corte} dias"
    return {
        "em_atraso": f"até {corte - 1} dias" if corte > 2 else ("até 1 dia" if corte == 2 else "nenhum (todo atraso é inadimplência)"),
        "inadimplente": f"{dias} ou mais",
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
# Etapa 2: entradas por conta, despesas por categoria, resultado por veículo, previsto e gráfico
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


def previsto_do_mes(cobrancas: list[dict], mes: date) -> Decimal:
    """O que o mês deveria render: as cobranças que vencem nele, sem caução e sem as canceladas (mesma regra de sempre)."""
    prefixo = mes.strftime("%Y-%m")
    return sum(
        (Decimal(str(c.get("valor") or 0)) for c in cobrancas
         if str(c["vencimento"])[:7] == prefixo and c.get("tipo") != "caucao" and c.get("situacao") != "cancelada"),
        _ZERO,
    )


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


# Abas do Dashboard: cada uma tem URL própria (`/?aba=dinheiro`), funciona sem JavaScript e mantém `compacto` e `ocultar`.
ABAS = (("hoje", "Hoje"), ("dinheiro", "Dinheiro"), ("frota", "Frota"))
ABA_PADRAO = "hoje"


def aba_do_painel(texto: Optional[str]) -> str:
    """Aba pedida na URL; vazia ou desconhecida vale a aba Hoje."""
    return texto if texto in dict(ABAS) else ABA_PADRAO


def consulta(mes: Optional[str] = None, compacto: bool = False, ocultar: bool = False, aba: Optional[str] = None) -> str:
    """Texto do parâmetro da URL do Dashboard (`?aba=dinheiro&mes=2026-09&compacto=1&ocultar=1`); vazio se nada foi escolhido.
    A aba padrão (Hoje) não aparece na URL."""
    partes = []
    if aba and aba != ABA_PADRAO:
        partes.append(f"aba={aba}")
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


def links_do_painel(
    mes: Optional[str], mes_anterior: Optional[str], mes_seguinte: Optional[str], compacto: bool, ocultar: bool, aba: str = ABA_PADRAO
) -> dict:
    """Endereços (sem a barra inicial) dos botões do Dashboard. Os interruptores e a navegação de mês mantêm o que já está ligado, e os
    do mês só existem na aba Dinheiro (nas outras, `mes` vem vazio). `abas` traz o endereço de cada aba."""
    return {
        "anterior": consulta(mes_anterior, compacto, ocultar, aba) if mes_anterior else None,
        "seguinte": consulta(mes_seguinte, compacto, ocultar, aba) if mes_seguinte else None,
        "atual": consulta(None, compacto, ocultar, aba),
        "compacto": consulta(mes, not compacto, ocultar, aba),
        "ocultar": consulta(mes, compacto, not ocultar, aba),
        "abas": {chave: consulta(None, compacto, ocultar, chave) for chave, _ in ABAS},
    }
