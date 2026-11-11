"""Fronteira de leitura da página web de Documentos.

Os testes das rotas trocam estes serviços por dados fictícios."""

import logging

from src.domain import comprovante_documento, documentos_lista
from src.domain.valores import hoje_br
from src.services import configuracoes, documentos, motos

log = logging.getLogger(__name__)


def _envios_aguardando() -> dict:
    """Comprovantes aguardando conferência, por documento. Se a leitura falhar (migration ainda não aplicada), a lista segue sem eles."""
    try:
        return {e["documento_id"]: e for e in documentos.comprovantes_aguardando()}
    except Exception:
        log.exception("Não foi possível ler os comprovantes aguardando conferência.")
        return {}


def carregar_lista(situacao, busca, pagina, por_pagina):
    frota = {m["id"]: m for m in motos.listar()}
    alerta_dias = int(configuracoes.obter()["alerta_documento_dias"])
    hoje = hoje_br()
    todos = documentos.listar_todos()
    envios = _envios_aguardando()
    itens = [
        {"documento": d, "moto": frota.get(d["moto_id"]), "placa": (frota.get(d["moto_id"]) or {}).get("placa", ""),
         "envio": envios.get(d["id"]), **documentos_lista.classificar(d, hoje, alerta_dias)}
        for d in todos
    ]
    pagina_itens, recorte, contagem = documentos_lista.montar_pagina(itens, situacao, busca, pagina, por_pagina)
    return {"itens": pagina_itens, "pagina": recorte, "contagem": contagem, "total_cadastrados": len(todos),
            "aguardando_conferencia": sum(1 for i in itens if i["envio"] and not i["documento"]["regularizado"])}


def _achatar(envio: dict) -> dict:
    """Envio como vem do banco (com `clientes` embutido) no formato da tela."""
    base = {k: v for k, v in envio.items() if k not in ("clientes", "documentos_moto")}
    base["cliente"] = (envio.get("clientes") or {}).get("nome")
    return base


def comprovante_do_documento(documento_id):
    """O comprovante aguardando conferência (ou None) e o histórico de envios do documento."""
    aguardando = documentos.comprovante_aguardando(documento_id)
    return {
        "envio": _achatar(aguardando) if aguardando else None,
        "historico": [_achatar(e) for e in documentos.historico_de_comprovantes(documento_id)],
    }


def url_do_comprovante_enviado(documento_id):
    """URL assinada (curta duração) do arquivo que o locatário enviou, ou None se não há envio aguardando."""
    envio = documentos.comprovante_aguardando(documento_id)
    return documentos.url_comprovante(envio["arquivo_path"]) if envio else None


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
