"""Dívidas: lista com saldo e próxima parcela de cada uma (a ficha, o pagamento de parcela e a compra parcelada vêm em seguida)."""

from fastapi import APIRouter, Depends, Request

from src.web import dados_dividas
from src.web.dependencias import exigir_dono
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()


@router.get("/dividas")
def lista(request: Request, _: Sessao = Depends(exigir_dono)):
    return renderizar(request, "dividas/lista.html", {"titulo": "Dívidas", "d": dados_dividas.resumo()})
