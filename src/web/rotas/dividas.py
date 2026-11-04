"""Dívidas: lista, ficha de cada dívida (parcelas e pagamentos) e o pagamento de parcela."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from src.domain import dividas_lista, formulario_divida as formulario, mensagens
from src.domain.valores import hoje_br
from src.web import acoes_dividas, dados_dividas
from src.web.apresentacao import formatar_placa
from src.web.dependencias import exigir_dono, validar_csrf
from src.web.rotas.motos_formularios import _concluir, _devolver_formulario, _entrada
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


@router.get("/dividas")
def lista(request: Request, _: Sessao = Depends(exigir_dono)):
    return renderizar(request, "dividas/lista.html", {"titulo": "Dívidas", "d": dados_dividas.resumo()})


def _uuid_ou_404(texto: str) -> str:
    """Endereço com id que não é um UUID não chega ao banco: é uma página que não existe."""
    try:
        return str(UUID(texto))
    except ValueError:
        raise HTTPException(status_code=404) from None


_PAGAMENTO = "dividas/pagar.html"


def _parcela_ou_404(vencimento_id: str) -> dict:
    parcela = dados_dividas.parcela(_uuid_ou_404(vencimento_id))
    if parcela is None:
        raise HTTPException(status_code=404)
    return parcela


def _contexto_pagamento(parcela, contas, valores, erros=None, erro_geral=None):
    return {
        "titulo": "Pagar parcela", "p": parcela, "v": valores, "erros": erros or {}, "erro_geral": erro_geral,
        "acao": f"/dividas/parcelas/{parcela['vencimento_id']}/pagar", "voltar": f"/dividas/{parcela['divida_id']}",
        "contas": [("", "Não informada"), *[(c["id"], c["nome"]) for c in contas]],
    }


def _ja_paga(request, sessao, parcela):
    return _concluir(request, sessao, f"/dividas/{parcela['divida_id']}", tipo="info", texto="Essa parcela já está paga.")


@router.get("/dividas/parcelas/{vencimento_id}/pagar")
def formulario_pagamento(request: Request, vencimento_id: str, sessao: Sessao = Depends(exigir_dono)):
    parcela = _parcela_ou_404(vencimento_id)
    if parcela["situacao"] == "paga":
        return _ja_paga(request, sessao, parcela)
    valores = formulario.pagamento_parcela_inicial(hoje_br(), parcela["saldo"])
    return renderizar(request, _PAGAMENTO, _contexto_pagamento(parcela, dados_dividas.contas(), valores))


def _pagar(request, sessao, vencimento_id, entrada):
    parcela = _parcela_ou_404(vencimento_id)
    if parcela["situacao"] == "paga":
        return _ja_paga(request, sessao, parcela)
    contas = dados_dividas.contas()
    contexto = _contexto_pagamento(parcela, contas, formulario.texto_do_pagamento_parcela(entrada))

    def pagar():
        dados = formulario.ler_pagamento_parcela(entrada, parcela["saldo"], {c["id"] for c in contas})
        acoes_dividas.pagar_parcela(parcela["vencimento_id"], dados["data"], dados["valor"], dados["conta_id"], dados["observacoes"])
        aviso = mensagens.parcela_divida_paga(dados["valor"], parcela.get("numero"), dados["quitada"])
        return _concluir(request, sessao, f"/dividas/{parcela['divida_id']}", aviso)

    return _devolver_formulario(request, _PAGAMENTO, contexto, pagar)


@router.post("/dividas/parcelas/{vencimento_id}/pagar", dependencies=[Depends(validar_csrf)])
async def pagar(request: Request, vencimento_id: str, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_pagar, request, sessao, vencimento_id, await _entrada(request))


_NOVA = "dividas/nova.html"


def _opcoes_nova(contas, motos):
    return {
        "contas": [("", "Não informada"), *[(c["id"], c["nome"]) for c in contas]],
        "motos": [("", "Nenhuma"), *[(m["id"], f"{formatar_placa(m['placa'])} · {m['modelo']}".rstrip(" ·")) for m in motos]],
    }


def _contexto_nova(contas, motos, valores, erros=None, erro_geral=None, previa=None):
    return {"titulo": "Nova compra parcelada", "v": valores, "erros": erros or {}, "erro_geral": erro_geral, "previa": previa,
            **_opcoes_nova(contas, motos)}


@router.get("/dividas/nova")
def nova(request: Request, _: Sessao = Depends(exigir_dono)):
    contexto = _contexto_nova(dados_dividas.contas(), dados_dividas.motos(), formulario.compra_inicial(hoje_br()))
    return renderizar(request, _NOVA, contexto)


def _cadastrar(request, sessao, entrada):
    contas, motos = dados_dividas.contas(), dados_dividas.motos()
    contexto = _contexto_nova(contas, motos, formulario.texto_da_compra(entrada))

    def cadastrar():
        dados = formulario.ler_compra_parcelada(entrada, {c["id"] for c in contas}, {m["id"] for m in motos})
        if entrada.get("acao") != "criar":
            contexto["previa"] = formulario.previa_da_compra(dados)
            return renderizar(request, _NOVA, contexto)
        resposta = acoes_dividas.criar_compra_parcelada(dados)
        aviso = mensagens.compra_parcelada_cadastrada(dados["credor"], dados["numero_parcelas"], dados["valor_total"])
        return _concluir(request, sessao, f"/dividas/{resposta['divida_id']}", aviso)

    return _devolver_formulario(request, _NOVA, contexto, cadastrar)


@router.post("/dividas/nova", dependencies=[Depends(validar_csrf)])
async def cadastrar(request: Request, sessao: Sessao = Depends(exigir_dono)):
    """Sem JavaScript: o botão "Conferir" mostra a prévia (total, saldo e calendário) e o "Cadastrar" grava."""
    return await run_in_threadpool(_cadastrar, request, sessao, await _entrada(request))


_NOVA_DIVIDA = "dividas/nova_divida.html"


def _contexto_nova_divida(motos, valores, erros=None, erro_geral=None):
    return {"titulo": "Nova dívida", "v": valores, "erros": erros or {}, "erro_geral": erro_geral,
            "tipos": formulario.tipos_para_selecao(),
            "motos": _opcoes_nova([], motos)["motos"]}


@router.get("/dividas/nova-divida")
def nova_divida(request: Request, _: Sessao = Depends(exigir_dono)):
    return renderizar(request, _NOVA_DIVIDA, _contexto_nova_divida(dados_dividas.motos(), formulario.divida_inicial()))


def _cadastrar_divida(request, sessao, entrada):
    motos = dados_dividas.motos()
    contexto = _contexto_nova_divida(motos, formulario.texto_da_divida(entrada))

    def cadastrar():
        dados = formulario.ler_divida(entrada, {m["id"] for m in motos})
        criada = acoes_dividas.criar_divida(dados)
        aviso = mensagens.divida_cadastrada(dados["credor"], dividas_lista.TIPOS_ROTULO[dados["tipo"]])
        return _concluir(request, sessao, f"/dividas/{criada['id']}", aviso)

    return _devolver_formulario(request, _NOVA_DIVIDA, contexto, cadastrar)


@router.post("/dividas/nova-divida", dependencies=[Depends(validar_csrf)])
async def cadastrar_divida(request: Request, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_cadastrar_divida, request, sessao, await _entrada(request))


_PAGAR_DIVIDA = "dividas/pagar_divida.html"


def _divida_para_pagar(divida_id: str) -> dict:
    f = dados_dividas.ficha(_uuid_ou_404(divida_id))
    if f is None:
        raise HTTPException(status_code=404)
    return f


def _sem_pagamento_direto(request, sessao, f):
    """Dívida quitada ou com parcelas não recebe pagamento direto (com parcelas, paga-se pela parcela)."""
    divida_id = f["divida"]["id"]
    if f["parcelas"]:
        return _concluir(request, sessao, f"/dividas/{divida_id}", tipo="info", texto="Essa dívida tem parcelas: pague pela parcela.")
    if f["saldo"] <= 0:
        return _concluir(request, sessao, f"/dividas/{divida_id}", tipo="info", texto="Essa dívida já está quitada.")
    return None


def _contexto_pagar_divida(f, contas, valores, erros=None, erro_geral=None):
    divida_id = f["divida"]["id"]
    return {
        "titulo": "Registrar pagamento", "f": f, "v": valores, "erros": erros or {}, "erro_geral": erro_geral,
        "acao": f"/dividas/{divida_id}/pagar", "voltar": f"/dividas/{divida_id}",
        "contas": [("", "Não informada"), *[(c["id"], c["nome"]) for c in contas]],
    }


@router.get("/dividas/{divida_id}/pagar")
def formulario_pagar_divida(request: Request, divida_id: str, sessao: Sessao = Depends(exigir_dono)):
    f = _divida_para_pagar(divida_id)
    recusa = _sem_pagamento_direto(request, sessao, f)
    if recusa is not None:
        return recusa
    valores = formulario.pagamento_parcela_inicial(hoje_br(), f["saldo"])
    return renderizar(request, _PAGAR_DIVIDA, _contexto_pagar_divida(f, dados_dividas.contas(), valores))


def _pagar_divida(request, sessao, divida_id, entrada):
    f = _divida_para_pagar(divida_id)
    recusa = _sem_pagamento_direto(request, sessao, f)
    if recusa is not None:
        return recusa
    contas = dados_dividas.contas()
    contexto = _contexto_pagar_divida(f, contas, formulario.texto_do_pagamento_parcela(entrada))

    def pagar():
        dados = formulario.ler_pagamento_parcela(entrada, f["saldo"], {c["id"] for c in contas}, alvo="da dívida")
        acoes_dividas.pagar_divida(f["divida"]["id"], dados["data"], dados["valor"], dados["conta_id"], dados["observacoes"])
        aviso = mensagens.pagamento_divida_registrado(dados["valor"], dados["quitada"])
        return _concluir(request, sessao, f"/dividas/{f['divida']['id']}", aviso)

    return _devolver_formulario(request, _PAGAR_DIVIDA, contexto, pagar)


@router.post("/dividas/{divida_id}/pagar", dependencies=[Depends(validar_csrf)])
async def pagar_divida(request: Request, divida_id: str, sessao: Sessao = Depends(exigir_dono)):
    return await run_in_threadpool(_pagar_divida, request, sessao, divida_id, await _entrada(request))


# Rotas fixas (como /dividas/nova) devem ser declaradas antes desta, senão caem em /dividas/{divida_id}.
@router.get("/dividas/{divida_id}")
def ficha(request: Request, divida_id: str, _: Sessao = Depends(exigir_dono)):
    f = dados_dividas.ficha(_uuid_ou_404(divida_id))
    if f is None:
        raise HTTPException(status_code=404)
    return renderizar(request, "dividas/ficha.html", {"titulo": f["divida"]["credor"], "f": f})
