"""Ações da lista de Cobranças (pagar, cancelar) que atualizam a lista no lugar, sem recarregar a página.

Quando o formulário em diálogo foi aberto a partir de /cobrancas (cabeçalho `HX-Current-URL` do HTMX), a resposta de
sucesso traz o aviso, as abas com as contagens novas, o resumo de atraso e o painel da aba aberta, tudo como troca
fora de banda (`hx-swap-oob`), e fecha o diálogo (evento `dialogo-concluido`). Nos demais casos (página sem JavaScript,
Dashboard, outra tela) segue o caminho de sempre: aviso guardado na sessão e redirecionamento."""

from urllib.parse import parse_qs, urlparse

from fastapi import Request
from fastapi.responses import Response

from src.domain import cobrancas_lista
from src.web.rotas import cobrancas as lista_cobrancas
from src.web.rotas.motos_formularios import _concluir, _tipo_do_aviso
from src.web.sessao import Sessao
from src.web.templates import renderizar


def _consulta_da_lista(request: Request) -> dict | None:
    """Parâmetros da lista de Cobranças de onde veio o pedido; None se ele não veio de lá (ou não é do HTMX)."""
    if request.headers.get("HX-Request") != "true":
        return None
    atual = urlparse(request.headers.get("HX-Current-URL", ""))
    if atual.path != "/cobrancas":
        return None
    return {chave: valores[0] for chave, valores in parse_qs(atual.query).items() if valores}


def concluir_na_lista(request: Request, sessao: Sessao, destino: str, aviso):
    """Atualiza a lista de Cobranças no lugar quando o pedido veio dela; senão, o `_concluir` comum."""
    consulta = _consulta_da_lista(request)
    if consulta is None:
        return _concluir(request, sessao, destino, aviso)
    aba = cobrancas_lista.aba_valida(consulta.get("aba"))
    contexto = lista_cobrancas._contexto(aba, lista_cobrancas._inteiro(consulta.get("pagina"), 1), lista_cobrancas._busca(consulta.get("q")))
    contexto.update(oob_painel=True, aviso_tipo=_tipo_do_aviso(aviso), aviso_texto=aviso.texto)
    resposta = renderizar(request, "cobrancas/_atualizacao_na_lista.html", contexto)
    resposta.headers["HX-Reswap"] = "none"
    resposta.headers["HX-Trigger"] = "dialogo-concluido"
    return resposta
