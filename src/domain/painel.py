"""Regras do Dashboard: frota, cobranças do dia e alertas. Funções puras, sem Streamlit nem banco."""

from dataclasses import dataclass
from datetime import date
from calendar import monthrange
from decimal import ROUND_HALF_UP, Decimal

from src.domain.formatadores import formatar_moeda, formatar_moeda_compacta

STATUS_FROTA = ("alugada", "disponivel", "manutencao", "inativa")
# Rótulo no plural, usado na legenda do medidor de ocupação.
ROTULO_FROTA_PLURAL = {
    "alugada": "alugadas",
    "disponivel": "disponíveis",
    "manutencao": "em manutenção",
    "inativa": "inativas",
}

_DIAS = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)
_MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)

TOM_PERIGO = "perigo"
TOM_ATENCAO = "atencao"


def data_por_extenso(data: date) -> str:
    """Ex.: `terça-feira, 6 de outubro de 2026`."""
    return f"{_DIAS[data.weekday()]}, {data.day} de {_MESES[data.month - 1]} de {data.year}"


def _data_br(valor) -> str:
    return date.fromisoformat(str(valor)[:10]).strftime("%d/%m/%Y")


# --------------------------------------------------------------------- frota --

def contar_por_status(frota: list[dict]) -> dict[str, int]:
    """Quantidade de motos em cada status (todos os status aparecem, mesmo com zero)."""
    contagem = dict.fromkeys(STATUS_FROTA, 0)
    for moto in frota:
        if moto["status"] in contagem:
            contagem[moto["status"]] += 1
    return contagem


def percentual_ocupacao(contagem: dict[str, int]) -> int:
    """Alugadas sobre as motos ativas (as inativas não entram), em % inteiro."""
    ativas = sum(qtd for status, qtd in contagem.items() if status != "inativa")
    if not ativas:
        return 0
    return round(100 * contagem.get("alugada", 0) / ativas)


@dataclass(frozen=True)
class SegmentoFrota:
    status: str
    quantidade: int
    rotulo: str  # ex.: "18 alugadas"


def segmentos_frota(contagem: dict[str, int]) -> list[SegmentoFrota]:
    """Um segmento por status, na ordem do medidor e da legenda."""
    return [
        SegmentoFrota(status, contagem.get(status, 0), f"{contagem.get(status, 0)} {ROTULO_FROTA_PLURAL[status]}")
        for status in STATUS_FROTA
    ]


def segmentos_medidor(contagem: dict[str, int]) -> list[str]:
    """Um segmento por moto ativa para o medidor: `cheio` (alugada), `oficina` ou vazio (livre)."""
    return (
        ["cheio"] * contagem.get("alugada", 0)
        + ["oficina"] * contagem.get("manutencao", 0)
        + [""] * contagem.get("disponivel", 0)
    )


def segmentos_rosca(contagem: dict[str, int]) -> list[dict]:
    """Arcos da rosca de ocupação (escala 0-100): alugada, em manutenção e livre, só motos ativas."""
    ativas = sum(contagem.get(s, 0) for s in ("alugada", "manutencao", "disponivel"))
    if not ativas:
        return []
    arcos, inicio = [], Decimal(0)
    for classe, status in (("cheio", "alugada"), ("oficina", "manutencao"), ("livre", "disponivel")):
        tamanho = Decimal(100 * contagem.get(status, 0)) / ativas
        if tamanho:
            arcos.append({"classe": classe, "inicio": float(inicio), "tamanho": float(tamanho)})
        inicio += tamanho
    return arcos


def descricao_medidor(contagem: dict[str, int]) -> str:
    """Texto alternativo do medidor para leitores de tela."""
    total = sum(contagem.values())
    partes = ", ".join(s.rotulo for s in segmentos_frota(contagem))
    return f"Frota de {total} motos: {partes}"


def percentual_recebido(recebido: Decimal, previsto: Decimal) -> int:
    """Quanto do previsto no mês já foi recebido, de 0 a 100."""
    if not previsto:
        return 0
    return max(0, min(100, round(100 * recebido / previsto)))


# ----------------------------------------------------- variação mês a mês --

SENTIDO_MAIS = "mais"
SENTIDO_MENOS = "menos"
SENTIDO_IGUAL = "igual"
SENTIDO_SEM_BASE = "sem_base"
TOM_BOM = "bom"
TOM_RUIM = "ruim"
TOM_NEUTRO = "neutro"


def nome_do_mes(data: date) -> str:
    return _MESES[data.month - 1]


def periodo_anterior(hoje: date) -> tuple[date, date]:
    """Mesmo intervalo do mês anterior: do dia 1 até o dia de `hoje` (limitado ao último dia, se o mês anterior for mais curto).

    Em 23/10 compara 01–23/09; em 31/10 compara 01–30/09. Comparar com o mês anterior inteiro faria todo começo de mês parecer queda."""
    ano, mes = (hoje.year - 1, 12) if hoje.month == 1 else (hoje.year, hoje.month - 1)
    return date(ano, mes, 1), date(ano, mes, min(hoje.day, monthrange(ano, mes)[1]))


@dataclass(frozen=True)
class Variacao:
    sentido: str  # SENTIDO_*
    diferenca: Decimal  # atual - anterior
    percentual: Decimal | None  # None sem base de comparação


def variacao(atual: Decimal, anterior: Decimal) -> Variacao | None:
    """None quando os dois valores são zero (nada a comparar)."""
    atual, anterior = Decimal(str(atual or 0)), Decimal(str(anterior or 0))
    if not atual and not anterior:
        return None
    diferenca = atual - anterior
    if not anterior:
        return Variacao(SENTIDO_SEM_BASE, diferenca, None)
    percentual = 100 * diferenca / anterior
    if not diferenca:
        return Variacao(SENTIDO_IGUAL, diferenca, percentual)
    return Variacao(SENTIDO_MAIS if diferenca > 0 else SENTIDO_MENOS, diferenca, percentual)


def _valor_da_diferenca(diferenca: Decimal) -> str:
    """Reais inteiros; com diferença menor que R$ 1, mostra os centavos para não aparecer `R$ 0` ao lado de "a mais"."""
    absoluta = abs(diferenca)
    return formatar_moeda(absoluta) if absoluta < 1 else formatar_moeda_compacta(absoluta)


def _percentual_texto(percentual: Decimal) -> str:
    arredondado = abs(percentual).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if not arredondado:
        return "menos de 1%"
    return f"{'+' if percentual > 0 else '−'}{arredondado}%"


def descrever_variacao(v: Variacao | None, mes_anterior: str, subir_e_bom: bool) -> dict | None:
    """Texto, seta e tom (bom/ruim/neutro) da linha de variação de um indicador.

    `subir_e_bom`: recebido sobe = bom; custo de manutenção sobe = ruim. O texto sempre diz "a mais" ou "a menos":
    a seta e a cor nunca são a única indicação."""
    if v is None:
        return None
    periodo = f"no mesmo período de {mes_anterior}"
    if v.sentido == SENTIDO_SEM_BASE:
        return {"seta": "", "tom": TOM_NEUTRO, "texto": f"Sem base de comparação: nada registrado {periodo}."}
    if v.sentido == SENTIDO_IGUAL:
        return {"seta": "=", "tom": TOM_NEUTRO, "texto": f"Igual ao que foi registrado {periodo}."}
    subiu = v.sentido == SENTIDO_MAIS
    tom = TOM_BOM if subiu == subir_e_bom else TOM_RUIM
    quanto = f"{_valor_da_diferenca(v.diferenca)} a {'mais' if subiu else 'menos'} ({_percentual_texto(v.percentual)})"
    return {"seta": "↑" if subiu else "↓", "tom": tom, "texto": f"{quanto} que {periodo}."}


# ---------------------------------------------------------------- cobranças --

def cobrancas_de_hoje(cobrancas: list[dict], hoje: date) -> list[dict]:
    """Atrasadas e abertas que vencem hoje, da mais antiga para a mais recente."""
    hoje_iso = hoje.isoformat()
    selecionadas = [
        c
        for c in cobrancas
        if c["situacao"] == "atrasada"
        or (c["situacao"] == "aberta" and str(c["vencimento"])[:10] == hoje_iso)
    ]
    return sorted(selecionadas, key=lambda c: c["vencimento"])


def dias_em_atraso(vencimento, hoje: date) -> int:
    return max((hoje - date.fromisoformat(str(vencimento)[:10])).days, 0)


def ordens_concluidas_no_mes(manutencoes: list[dict], hoje: date) -> int:
    """Manutenções concluídas com entrada no mês de `hoje`."""
    mes = hoje.isoformat()[:7]
    return sum(
        1 for m in manutencoes if m["status"] == "concluida" and str(m["data_entrada"])[:7] == mes
    )


# ------------------------------------------------------------------ alertas --

@dataclass(frozen=True)
class ItemAlerta:
    quantidade: int
    titulo: str
    descricao: str
    tom: str  # TOM_PERIGO ou TOM_ATENCAO
    area: str  # onde resolver: "manutencao", "documentos" ou "clientes"


def _com_restante(texto: str, total: int, exibidos: int = 1) -> str:
    return f"{texto} e mais {total - exibidos}" if total > exibidos else texto


def agrupar_alertas(
    config: dict,
    manutencao: list[dict],
    documentos: list[dict],
    cnh: list[dict],
) -> list[ItemAlerta]:
    """Itens do cartão Alertas: vencidos primeiro em cada área, depois os a vencer."""
    itens: list[ItemAlerta] = []

    vencidas = [a for a in manutencao if a["situacao"] == "vencida"]
    if vencidas:
        # Nomes distintos (o mesmo item vence em várias motos); mostra dois e conta o resto.
        distintos = list(dict.fromkeys(a["item"] for a in vencidas))
        descricao = _com_restante(", ".join(distintos[:2]), len(distintos), 2)
        itens.append(ItemAlerta(len(vencidas), "Manutenção vencida", descricao, TOM_PERIGO, "manutencao"))

    proximas = [a for a in manutencao if a["situacao"] == "proxima"]
    if proximas:
        descricao = (
            f"nos próximos {config['alerta_manutencao_km']} km ou "
            f"{config['alerta_manutencao_dias']} dias"
        )
        itens.append(ItemAlerta(len(proximas), "Manutenção próxima", descricao, TOM_ATENCAO, "manutencao"))

    doc_vencidos = [a for a in documentos if a["situacao"] == "vencido"]
    if doc_vencidos:
        primeiro = doc_vencidos[0]
        descricao = _com_restante(f"{primeiro['tipo'].upper()} · moto {primeiro['placa']}", len(doc_vencidos))
        itens.append(ItemAlerta(len(doc_vencidos), "Documento vencido", descricao, TOM_PERIGO, "documentos"))

    doc_a_vencer = [a for a in documentos if a["situacao"] == "a_vencer"]
    if doc_a_vencer:
        descricao = f"próximos {config['alerta_documento_dias']} dias"
        itens.append(ItemAlerta(len(doc_a_vencer), "Documento a vencer", descricao, TOM_ATENCAO, "documentos"))

    for situacao, titulo, tom in (("vencida", "CNH vencida", TOM_PERIGO), ("a_vencer", "CNH a vencer", TOM_ATENCAO)):
        lista = [a for a in cnh if a["situacao"] == situacao]
        if lista:
            primeiro = lista[0]
            descricao = _com_restante(f"{primeiro['nome']} · {_data_br(primeiro['cnh_validade'])}", len(lista))
            itens.append(ItemAlerta(len(lista), titulo, descricao, tom, "clientes"))

    return itens
