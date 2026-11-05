"""Fronteira de leitura da página web de Vistorias: lista e comparação entrega x devolução.

Os testes das rotas trocam estes serviços por dados fictícios."""

from src.domain import vistorias_lista
from src.domain.contrato_motos import todas_as_motos
from src.domain.vistorias import (
    comparar_checklists,
    contar_avarias,
    itens_ordenados,
    km_rodados,
    resumo_avarias,
    rotulo_item,
    tipos_faltantes,
)
from src.services import clientes, contratos, motos, vistorias
from src.web.apresentacao import formatar_placa


def carregar_lista(tipo, busca, pagina, por_pagina):
    todas = vistorias.listar()
    contratos_por_id = {c["id"]: c for c in contratos.listar()}
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    frota = {m["id"]: m for m in motos.listar()}
    itens = []
    for v in todas:
        contrato = contratos_por_id.get(v["contrato_id"])
        moto = frota.get(v.get("moto_id")) or (frota.get(contrato["moto_id"]) if contrato else None)
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


def _vinculos_por_contrato():
    """{contrato_id: [moto_id das vinculadas]}, numa consulta só."""
    mapa: dict = {}
    for v in contratos.listar_vinculos():
        mapa.setdefault(v["contrato_id"], []).append(v["moto_id"])
    return mapa


def _valor_do_registro(contrato, moto_id):
    """Valor do campo `contrato` do formulário de registro: o id do contrato (moto principal) ou `contrato:moto`."""
    return contrato["id"] if moto_id == contrato["moto_id"] else f"{contrato['id']}:{moto_id}"


def _grupo(contrato, moto, comparacao):
    """Cartões de entrega e devolução de UMA moto do contrato, com os totais que a página mostra."""
    entrega, devolucao = comparacao["entrega"], comparacao["devolucao"]
    diferentes = set(comparar_checklists(entrega["checklist"], devolucao["checklist"])) if entrega and devolucao else set()
    registrar = "/vistorias/registrar?contrato=" + _valor_do_registro(contrato, moto["id"])
    return {
        "moto": moto,
        "km_rodados": km_rodados(entrega, devolucao),
        "avarias_devolucao": contar_avarias(devolucao) if devolucao else None,
        "tem_alterados": bool(diferentes),
        "cartoes": [
            {"tipo": tipo, "titulo": vistorias_lista.TIPO_ROTULO[tipo], "registrar": registrar,
             "dados": _cartao(registro, diferentes) if registro else None}
            for tipo, registro in (("entrega", entrega), ("devolucao", devolucao))
        ],
    }


def obter_comparacao(contrato_id):
    """Contrato com cliente, moto principal e as duas vistorias dela (`cartoes`, `km_rodados`...), mais um grupo igual
    para cada moto vinculada em `outras`; None se contrato, cliente ou moto principal não existirem."""
    contrato = next((c for c in contratos.listar() if c["id"] == contrato_id), None)
    if contrato is None:
        return None
    cliente = clientes.obter(contrato["cliente_id"])
    moto = motos.obter(contrato["moto_id"])
    if cliente is None or moto is None:
        return None
    principal = _grupo(contrato, moto, vistorias.comparar_entrega_devolucao(contrato_id))
    outras = []
    for moto_id in _vinculos_por_contrato().get(contrato_id, []):
        vinculada = motos.obter(moto_id)
        if vinculada is not None:
            outras.append(_grupo(contrato, vinculada, vistorias.comparar_entrega_devolucao(contrato_id, moto_id)))
    return {"contrato": contrato, "cliente": cliente, **principal, "outras": outras,
            "algum_alterado": principal["tem_alterados"] or any(g["tem_alterados"] for g in outras)}


def contratos_pendentes():
    """Pares (contrato, moto) que ainda não têm as duas vistorias, como (valor, rótulo), os contratos ativos primeiro.
    O valor é o id do contrato (moto principal) ou `contrato:moto` (moto vinculada)."""
    feitas: dict = {}
    for v in vistorias.listar():
        feitas.setdefault((v["contrato_id"], v["moto_id"]), []).append(v)
    nomes = {c["id"]: c["nome"] for c in clientes.listar()}
    frota = {m["id"]: m for m in motos.listar()}
    vinculos = _vinculos_por_contrato()
    ordenados = sorted(contratos.listar(), key=lambda c: (c.get("status") != "ativo", str(c["data_inicio"])))
    pendentes = []
    for c in ordenados:
        for moto_id in todas_as_motos(c["moto_id"], vinculos.get(c["id"])):
            if moto_id in frota and tipos_faltantes(feitas.get((c["id"], moto_id), [])):
                moto = frota[moto_id]
                rotulo = (f"{nomes.get(c['cliente_id'], '—')} → {formatar_placa(moto['placa'])}"
                          f" · {moto.get('marca', '')} {moto.get('modelo', '')} ({c['status']})")
                pendentes.append((_valor_do_registro(c, moto_id), rotulo + ("" if moto_id == c["moto_id"] else " · vinculada")))
    return pendentes


def vistoria_para_fotos(vistoria_id):
    """Vistoria com o rótulo do contrato (cliente e placa) para "Adicionar fotos"; None se algo não existir."""
    vistoria = vistorias.obter(vistoria_id)
    if vistoria is None:
        return None
    moto = motos.obter(vistoria["moto_id"])
    contrato = next((c for c in contratos.listar() if c["id"] == vistoria["contrato_id"]), None)
    cliente = clientes.obter(contrato["cliente_id"]) if contrato else None
    if moto is None or cliente is None:
        return None
    return {"vistoria": vistoria, "contrato": contrato, "moto": moto, "cliente": cliente,
            "tipo_rotulo": vistorias_lista.TIPO_ROTULO[vistoria["tipo"]], "fotos_atuais": len(vistoria.get("fotos") or [])}


def obter_para_registro(valor):
    """Contrato com cliente, a moto (a principal ou uma vinculada, `valor` = `contrato` ou `contrato:moto`) e os tipos de
    vistoria que faltam nela; None se contrato, cliente ou moto não existirem ou a moto não for do contrato."""
    contrato_id, _, moto_pedida = valor.partition(":")
    contrato = next((c for c in contratos.listar() if c["id"] == contrato_id), None)
    if contrato is None:
        return None
    moto_id = moto_pedida or contrato["moto_id"]
    if moto_id not in todas_as_motos(contrato["moto_id"], _vinculos_por_contrato().get(contrato_id)):
        return None
    cliente = clientes.obter(contrato["cliente_id"])
    moto = motos.obter(moto_id)
    if cliente is None or moto is None:
        return None
    return {"contrato": contrato, "cliente": cliente, "moto": moto, "valor": _valor_do_registro(contrato, moto_id),
            "vinculada": moto_id != contrato["moto_id"],
            "faltantes": tipos_faltantes(vistorias.listar_por_contrato(contrato_id, moto_id))}
