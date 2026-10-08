"""Mensagem de cobrança pronta para colar no WhatsApp: em diálogo (HTMX) ou em página, com botão de copiar."""

from fastapi import APIRouter, Depends, HTTPException, Request

from src.domain.painel_cobrancas import mensagem_cobranca
from src.domain.valores import hoje_br
from src.web import dados_cobrancas
from src.web.apresentacao import formatar_data, formatar_moeda, formatar_placa
from src.web.dependencias import exigir_dono
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


@router.get("/cobrancas/{cobranca_id}/mensagem")
def mensagem(request: Request, cobranca_id: str, _: Sessao = Depends(exigir_dono)):
    c = dados_cobrancas.obter_para_pagamento(cobranca_id)
    if c is None:
        raise HTTPException(status_code=404)
    dias = dados_cobrancas.encargos_em(c, hoje_br())["dias_atraso"]
    texto = mensagem_cobranca(
        c["cliente"] or "cliente", formatar_placa(c["placa"]) if c["placa"] else "—",
        formatar_data(c["vencimento"]), formatar_moeda(c["saldo"]), dias,
    )
    modelo = "cobrancas/_mensagem.html" if request.headers.get("HX-Request") == "true" else "cobrancas/mensagem.html"
    return renderizar(request, modelo, {"titulo": "Mensagem de cobrança", "c": c, "texto": texto})
