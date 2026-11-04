"""Dívidas: lista com saldo e próxima parcela de cada uma e a ficha de cada dívida com parcelas e pagamentos."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from src.web import dados_dividas
from src.web.dependencias import exigir_dono
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


# Rotas fixas (como /dividas/nova) devem ser declaradas antes desta, senão caem em /dividas/{divida_id}.
@router.get("/dividas/{divida_id}")
def ficha(request: Request, divida_id: str, _: Sessao = Depends(exigir_dono)):
    f = dados_dividas.ficha(_uuid_ou_404(divida_id))
    if f is None:
        raise HTTPException(status_code=404)
    return renderizar(request, "dividas/ficha.html", {"titulo": f["divida"]["credor"], "f": f})
