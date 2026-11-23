"""Pré-visualização em gaveta: os dados principais de um veículo, cliente ou contrato sem sair da lista.

Devolve só o fragmento (o HTMX o coloca em `#gaveta-conteudo`); sem JavaScript o link "Abrir ficha completa" e as próprias
listas continuam levando à ficha. Dados lidos pelas mesmas funções das fichas (rota -> dados_* -> serviço)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from src.domain import clientes_lista, contratos_lista, motos_lista
from src.web import dados_clientes, dados_contratos, dados_motos
from src.web.dependencias import exigir_dono
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


def _uuid_ou_404(valor: str) -> str:
    try:
        UUID(valor)
    except ValueError:
        raise HTTPException(status_code=404)
    return valor


@router.get("/motos/{moto_id}/previa")
def previa_moto(request: Request, moto_id: str, _: Sessao = Depends(exigir_dono)):
    moto = dados_motos.obter_moto(_uuid_ou_404(moto_id))
    if moto is None:
        raise HTTPException(status_code=404)
    contexto = {"moto": moto, "cabecalho": dados_motos.carregar_cabecalho(moto), "status_rotulo": motos_lista.STATUS_ROTULO}
    return renderizar(request, "previa/_moto.html", contexto)


@router.get("/clientes/{cliente_id}/previa")
def previa_cliente(request: Request, cliente_id: str, _: Sessao = Depends(exigir_dono)):
    cliente = dados_clientes.obter_cliente(_uuid_ou_404(cliente_id))
    if cliente is None:
        raise HTTPException(status_code=404)
    return renderizar(request, "previa/_cliente.html", {"cliente": cliente, "status_rotulo": clientes_lista.STATUS_ROTULO})


@router.get("/contratos/{contrato_id}/previa")
def previa_contrato(request: Request, contrato_id: str, _: Sessao = Depends(exigir_dono)):
    registro = dados_contratos.obter_contrato(_uuid_ou_404(contrato_id))
    if registro is None:
        raise HTTPException(status_code=404)
    contexto = {**registro, "status_rotulo": contratos_lista.STATUS_ROTULO, "periodos_rotulo": contratos_lista.PERIODOS_ROTULO}
    return renderizar(request, "previa/_contrato.html", contexto)
