"""Fronteira de leitura da página web de Vistorias: lista e comparação entrega x devolução.

Os testes das rotas trocam estes serviços por dados fictícios."""

from src.domain import vistorias_lista
from src.domain.vistorias import (
    comparar_checklists,
    contar_avarias,
    itens_ordenados,
    km_rodados,
    resumo_avarias,
    rotulo_item,
)
from src.services import clientes, contratos, motos, vistorias


def carregar_lista(tipo, busca, pagina, por_pagina):
    todas = vistorias.listar()
    contratos_por_id = {c["id"]: c for c in contratos.listar()}
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    frota = {m["id"]: m for m in motos.listar()}
    itens = []
    for v in todas:
        contrato = contratos_por_id.get(v["contrato_id"])
        moto = frota.get(contrato["moto_id"]) if contrato else None
        itens.append({
            "vistoria": v,
            "contrato_id": contrato["id"] if contrato else None,
            "cliente_nome": nomes.get(contrato["cliente_id"], "—") if contrato else "—",
            "placa": moto["placa"] if moto else "",
            "avarias": resumo_avarias(v),
        })
    pagina_itens, recorte, contagem = vistorias_lista.montar_pagina(itens, tipo, busca, pagina, por_pagina)
    return {"itens": pagina_itens, "pagina": recorte, "contagem": contagem, "total_cadastradas": len(todas)}


def _url_foto(foto):
    """URL assinada de curta duração (bucket privado); None se não for possível gerar."""
    try:
        return vistorias.url_foto(foto["storage_path"])
    except Exception:
        return None


def _cartao(vistoria, diferentes):
    itens = [
        {"rotulo": rotulo_item(chave), "estado": estado, "alterado": chave in diferentes}
        for chave, estado in itens_ordenados(vistoria.get("checklist"))
    ]
    fotos = [{"url": _url_foto(f), "legenda": f.get("legenda") or "Foto da vistoria"} for f in vistoria.get("fotos") or []]
    return {"vistoria": vistoria, "itens": itens, "fotos": fotos, "avarias": resumo_avarias(vistoria)}


def obter_comparacao(contrato_id):
    """Contrato com cliente, moto e as duas vistorias; None se contrato, cliente ou moto não existirem."""
    contrato = next((c for c in contratos.listar() if c["id"] == contrato_id), None)
    if contrato is None:
        return None
    cliente = clientes.obter(contrato["cliente_id"])
    moto = motos.obter(contrato["moto_id"])
    if cliente is None or moto is None:
        return None
    comparacao = vistorias.comparar_entrega_devolucao(contrato_id)
    entrega, devolucao = comparacao["entrega"], comparacao["devolucao"]
    diferentes = set(comparar_checklists(entrega["checklist"], devolucao["checklist"])) if entrega and devolucao else set()
    return {
        "contrato": contrato, "cliente": cliente, "moto": moto,
        "km_rodados": km_rodados(entrega, devolucao),
        "avarias_devolucao": contar_avarias(devolucao) if devolucao else None,
        "tem_alterados": bool(diferentes),
        "cartoes": [
            {"tipo": tipo, "titulo": vistorias_lista.TIPO_ROTULO[tipo],
             "dados": _cartao(registro, diferentes) if registro else None}
            for tipo, registro in (("entrega", entrega), ("devolucao", devolucao))
        ],
    }
