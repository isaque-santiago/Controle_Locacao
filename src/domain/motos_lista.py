"""Regras da lista e da ficha de motos: filtro, busca, próxima manutenção, abas. Funções puras."""

from dataclasses import dataclass
from datetime import date

STATUS_ROTULO = {
    "disponivel": "Disponível",
    "alugada": "Alugada",
    "manutencao": "Manutenção",
    "inativa": "Inativa",
}
STATUS_ORDEM = ("disponivel", "alugada", "manutencao", "inativa")
TODAS = "todas"

ABAS_FICHA = (
    ("resumo", "Resumo"),
    ("plano", "Plano de manutenção"),
    ("historico", "Histórico"),
    ("documentos", "Documentos"),
    ("contratos", "Contratos"),
    ("financeiro", "Financeiro"),
)
ABA_PADRAO = ABAS_FICHA[0][0]


def situacao_valida(valor: str | None) -> str:
    """Valor do filtro vindo da URL: um status conhecido ou `todas`."""
    valor = (valor or "").strip().lower()
    return valor if valor in STATUS_ORDEM else TODAS


def aba_valida(valor: str | None) -> str:
    return valor if valor in {chave for chave, _ in ABAS_FICHA} else ABA_PADRAO


def contagem_por_status(motos: list[dict]) -> dict[str, int]:
    """Total de motos e quantas há em cada status (chave `todas` para o total)."""
    contagem = {TODAS: len(motos), **dict.fromkeys(STATUS_ORDEM, 0)}
    for moto in motos:
        if moto["status"] in contagem:
            contagem[moto["status"]] += 1
    return contagem


def _sem_hifen(texto: str) -> str:
    return texto.replace("-", "").casefold()


def filtrar_motos(
    motos: list[dict],
    situacao: str = TODAS,
    busca: str = "",
    locatarios: dict[str, str] | None = None,
) -> list[dict]:
    """Filtra por status e por texto em placa (com ou sem hífen), marca, modelo e locatário.

    `locatarios` mapeia o id da moto ao nome do cliente do contrato ativo."""
    locatarios = locatarios or {}
    termo = (busca or "").strip()
    termo_texto = termo.casefold()
    termo_placa = _sem_hifen(termo)
    resultado = []
    for moto in motos:
        if situacao != TODAS and moto["status"] != situacao:
            continue
        if termo:
            texto = f"{moto['marca']} {moto['modelo']} {locatarios.get(moto['id'], '')}".casefold()
            if termo_texto not in texto and termo_placa not in _sem_hifen(moto["placa"]):
                continue
        resultado.append(moto)
    return resultado


@dataclass(frozen=True)
class ProximaManutencao:
    texto: str
    situacao: str  # "vencida", "proxima", "em_dia" ou "sem_plano"


_PESO_SITUACAO = {"vencida": 0, "proxima": 1, "em_dia": 2}


def _milhar(numero: int) -> str:
    return f"{abs(int(numero)):,}".replace(",", ".")


def proxima_manutencao(alertas_da_moto: list[dict]) -> ProximaManutencao:
    """Resume o plano da moto: o item mais urgente (vencida, depois próxima, depois em dia).

    `alertas_da_moto` são as linhas de `vw_alertas_manutencao` da moto (com `situacao`,
    `km_restantes` e `dias_restantes`). Sem plano, não há o que mostrar."""
    if not alertas_da_moto:
        return ProximaManutencao("—", "sem_plano")

    def chave(linha):
        km = linha.get("km_restantes")
        dias = linha.get("dias_restantes")
        return (
            _PESO_SITUACAO.get(linha["situacao"], 3),
            km if km is not None else float("inf"),
            dias if dias is not None else float("inf"),
        )

    pior = min(alertas_da_moto, key=chave)
    km, dias = pior.get("km_restantes"), pior.get("dias_restantes")
    if pior["situacao"] == "vencida":
        if km is not None and km <= 0:
            return ProximaManutencao(f"vencida há {_milhar(km)} km" if km < 0 else "vencida agora", "vencida")
        if dias is not None and dias <= 0:
            return ProximaManutencao(f"vencida há {_milhar(dias)} dias" if dias < 0 else "vencida hoje", "vencida")
        return ProximaManutencao("vencida", "vencida")
    if km is not None and (dias is None or km >= 0):
        return ProximaManutencao(f"em {_milhar(km)} km", pior["situacao"])
    if dias is not None:
        return ProximaManutencao(f"em {_milhar(dias)} dias", pior["situacao"])
    return ProximaManutencao("em dia", pior["situacao"])


def situacao_documento(documento: dict, hoje: date) -> tuple[str, str]:
    """(chave, texto) do documento da moto: ok, a_vencer ou vencido."""
    if documento["regularizado"]:
        return "ok", "Em dia"
    if date.fromisoformat(str(documento["vencimento"])[:10]) < hoje:
        return "vencido", "Vencido"
    return "a_vencer", "A vencer"


@dataclass(frozen=True)
class LinhaPlano:
    item: str
    intervalo: str
    ultima: str
    proxima: str
    restante: str
    situacao: str  # em_dia, proxima ou vencida


_ROTULO_SITUACAO_PLANO = {"vencida": "Vencida", "proxima": "Próxima", "em_dia": "Em dia"}


def rotulo_situacao_plano(situacao: str) -> str:
    return _ROTULO_SITUACAO_PLANO.get(situacao, situacao)


def _como_data(valor) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


def descrever_item_plano(linha: dict, km_atual: int, situacao: str, hoje: date) -> LinhaPlano:
    """Textos de uma linha do plano de manutenção da moto (já com intervalos efetivos e próxima km/data)."""
    partes = []
    if linha.get("intervalo_km_efetivo"):
        faixa = f"{_milhar(linha['intervalo_minimo_km_efetivo'])} a " if linha.get("intervalo_minimo_km_efetivo") else ""
        partes.append(f"{faixa}{_milhar(linha['intervalo_km_efetivo'])} km")
    if linha.get("intervalo_dias_efetivo"):
        partes.append(f"{linha['intervalo_dias_efetivo']} dias")

    proxima_km = linha.get("proxima_km")
    if proxima_km is not None:
        falta = proxima_km - km_atual
        restante = f"{_milhar(falta)} km" if falta >= 0 else f"vencida há {_milhar(falta)} km"
    elif linha.get("proxima_data"):
        dias = (_como_data(linha["proxima_data"]) - hoje).days
        restante = f"{dias} dias" if dias >= 0 else f"vencida há {abs(dias)} dias"
    else:
        restante = "—"

    return LinhaPlano(
        item=linha["item"]["nome"],
        intervalo=" / ".join(partes) or "—",
        ultima=f"{_milhar(linha['ultima_km'])} km" if linha.get("ultima_km") else "—",
        proxima=f"{_milhar(proxima_km)} km" if proxima_km else "—",
        restante=restante,
        situacao=situacao,
    )
