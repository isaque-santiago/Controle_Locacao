"""Fronteira de leitura da página web de Manutenção."""

from src.domain.paginacao import OPCOES_POR_PAGINA, calcular_pagina
from src.services import alertas, manutencao, motos

ABAS = (("alertas", "Alertas"), ("historico", "Histórico"), ("catalogo", "Catálogo"))
SITUACOES_ALERTA = (("todas", "Todas"), ("vencida", "Vencidas"), ("proxima", "Próximas"))
TIPOS_MANUTENCAO = (("todas", "Todas"), ("preventiva", "Preventiva"), ("corretiva", "Corretiva"))
STATUS_ROTULO = {"aberta": "Aberta", "concluida": "Concluída", "cancelada": "Cancelada"}


def aba_valida(valor):
    return valor if valor in dict(ABAS) else ABAS[0][0]


def _alertas(situacao):
    todos = [a for a in alertas.listar_manutencao() if a.get("situacao") in ("vencida", "proxima")]
    contagem = {
        "todas": len(todos),
        "vencida": sum(a["situacao"] == "vencida" for a in todos),
        "proxima": sum(a["situacao"] == "proxima" for a in todos),
    }
    itens = [a for a in todos if situacao == "todas" or a["situacao"] == situacao]
    itens.sort(key=lambda a: (
        a["situacao"] != "vencida",
        a.get("km_restantes") if a.get("km_restantes") is not None else float("inf"),
        a.get("dias_restantes") if a.get("dias_restantes") is not None else float("inf"),
    ))
    return {"itens": itens, "contagem": contagem}


def _historico(tipo, busca, pagina):
    frota = {m["id"]: m for m in motos.listar()}
    todos = sorted(manutencao.listar_manutencoes(), key=lambda m: str(m["data_entrada"]), reverse=True)
    contagem = {
        "todas": len(todos),
        "preventiva": sum(m["tipo"] == "preventiva" for m in todos),
        "corretiva": sum(m["tipo"] == "corretiva" for m in todos),
    }
    termo = busca.casefold()
    filtrados = [
        {**m, "moto": frota.get(m["moto_id"])}
        for m in todos
        if (tipo == "todas" or m["tipo"] == tipo)
        and termo in f"{frota.get(m['moto_id'], {}).get('placa', '')} {m.get('oficina') or ''}".casefold()
    ]
    recorte = calcular_pagina(len(filtrados), pagina, OPCOES_POR_PAGINA[0])
    return {"itens": filtrados[recorte.inicio:recorte.fim], "pagina": recorte, "contagem": contagem}


def carregar(aba, situacao="todas", tipo="todas", busca="", pagina=1):
    alertas_ = _alertas(situacao)
    dados = {
        "aba": aba,
        "vencidas": alertas_["contagem"]["vencida"],
        "proximas": alertas_["contagem"]["proxima"],
    }
    if aba == "alertas":
        dados["alertas"] = alertas_
    elif aba == "historico":
        dados["historico"] = _historico(tipo, busca, pagina)
    else:
        dados["catalogo"] = manutencao.listar_catalogo()
    return dados


def opcoes_do_registro():
    """Motos não inativas e itens ativos disponíveis no formulário."""
    frota = [m for m in motos.listar() if m["status"] != "inativa"]
    catalogo = [i for i in manutencao.listar_catalogo() if i["ativo"]]
    return frota, catalogo


def obter_aberta(manutencao_id):
    registro = manutencao.obter_manutencao(manutencao_id)
    if registro is None or registro.get("status") != "aberta":
        return None
    moto = next((m for m in motos.listar() if m["id"] == registro["moto_id"]), None)
    return {"manutencao": registro, "moto": moto} if moto else None


def obter_item(item_id):
    return next((item for item in manutencao.listar_catalogo() if item["id"] == item_id), None)
