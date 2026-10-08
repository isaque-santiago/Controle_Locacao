"""Fronteira de leitura da página web de Documentos.

Os testes das rotas trocam estes serviços por dados fictícios."""

from src.domain import documentos_lista
from src.domain.valores import hoje_br
from src.services import configuracoes, documentos, motos


def carregar_lista(situacao, busca, pagina, por_pagina):
    frota = {m["id"]: m for m in motos.listar()}
    alerta_dias = int(configuracoes.obter()["alerta_documento_dias"])
    hoje = hoje_br()
    todos = documentos.listar_todos()
    itens = [
        {"documento": d, "moto": frota.get(d["moto_id"]), "placa": (frota.get(d["moto_id"]) or {}).get("placa", ""),
         **documentos_lista.classificar(d, hoje, alerta_dias)}
        for d in todos
    ]
    pagina_itens, recorte, contagem = documentos_lista.montar_pagina(itens, situacao, busca, pagina, por_pagina)
    return {"itens": pagina_itens, "pagina": recorte, "contagem": contagem, "total_cadastrados": len(todos)}


def url_comprovante(documento_id):
    """URL assinada (curta duração) do comprovante, ou None se o documento não existe ou não tem comprovante."""
    documento = documentos.obter(documento_id)
    if not documento or not documento.get("arquivo_path"):
        return None
    return documentos.url_comprovante(documento["arquivo_path"])


def motos_do_cadastro(moto_atual=None):
    """Motos que aceitam documento: as ativas na frota e, na edição, a moto do próprio documento."""
    return [m for m in motos.listar() if m["status"] != "inativa" or m["id"] == moto_atual]


def obter_documento(documento_id):
    """O documento com a moto, ou None se algum dos dois não existir."""
    documento = documentos.obter(documento_id)
    moto = motos.obter(documento["moto_id"]) if documento else None
    if documento is None or moto is None:
        return None
    return {"documento": documento, "moto": moto}
