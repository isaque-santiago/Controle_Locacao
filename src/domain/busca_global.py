"""Busca global (paleta de comandos): veículos, clientes e contratos num só termo.

Funções puras: recebem as listas já carregadas e devolvem, por grupo, no máximo `LIMITE_POR_GRUPO` itens.
Arquivados ficam de fora. Termos com menos de `MINIMO_CARACTERES` caracteres não buscam nada."""

import re

from src.domain.arquivamento import esta_arquivado

LIMITE_POR_GRUPO = 5
MINIMO_CARACTERES = 2
TAMANHO_MAXIMO_TERMO = 80

_ORDEM_STATUS_CONTRATO = {"ativo": 0}


def normalizar_termo(termo: str | None) -> str:
    return " ".join((termo or "").split())[:TAMANHO_MAXIMO_TERMO]


def _sem_hifen(texto: str) -> str:
    return texto.replace("-", "").replace(" ", "").casefold()


def _digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def _veiculo_confere(moto: dict, termo: str) -> bool:
    texto = f"{moto.get('marca') or ''} {moto.get('modelo') or ''}".casefold()
    return termo.casefold() in texto or _sem_hifen(termo) in _sem_hifen(moto.get("placa") or "")


def _cliente_confere(cliente: dict, termo: str) -> bool:
    digitos = _digitos(termo)
    return termo.casefold() in (cliente.get("nome") or "").casefold() or bool(
        digitos and digitos in _digitos(cliente.get("cpf"))
    )


def buscar(termo: str | None, motos: list[dict], clientes: list[dict], contratos: list[dict]) -> dict:
    """Resultados por grupo: `{"veiculos": [...], "clientes": [...], "contratos": [...], "total": n}`.

    Cada contrato achado vem como `{"contrato": {...}, "cliente": {...} | None, "moto": {...} | None}`. Um contrato entra quando
    o termo bate com o nome ou o CPF do cliente, ou com a placa, a marca ou o modelo do veículo principal; ativos primeiro."""
    termo = normalizar_termo(termo)
    vazio = {"veiculos": [], "clientes": [], "contratos": [], "total": 0}
    if len(termo) < MINIMO_CARACTERES:
        return vazio

    motos_ativas = [m for m in motos if not esta_arquivado(m)]
    clientes_ativos = [c for c in clientes if not esta_arquivado(c)]
    por_cliente = {c["id"]: c for c in clientes}
    por_moto = {m["id"]: m for m in motos}

    veiculos = [m for m in motos_ativas if _veiculo_confere(m, termo)]
    achados = [c for c in clientes_ativos if _cliente_confere(c, termo)]

    ligados = []
    for contrato in contratos:
        cliente = por_cliente.get(contrato.get("cliente_id"))
        moto = por_moto.get(contrato.get("moto_id"))
        if (cliente and _cliente_confere(cliente, termo)) or (moto and _veiculo_confere(moto, termo)):
            ligados.append({"contrato": contrato, "cliente": cliente, "moto": moto})
    ligados.sort(key=lambda i: (
        _ORDEM_STATUS_CONTRATO.get(i["contrato"].get("status"), 1),
        str(i["contrato"].get("data_inicio") or ""),
    ))

    resultado = {
        "veiculos": veiculos[:LIMITE_POR_GRUPO],
        "clientes": achados[:LIMITE_POR_GRUPO],
        "contratos": ligados[:LIMITE_POR_GRUPO],
    }
    resultado["total"] = sum(len(v) for v in resultado.values())
    return resultado
