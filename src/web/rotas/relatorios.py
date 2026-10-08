"""Relatórios: resultado por moto, custo de manutenção, inadimplência e fluxo de caixa, com exportação em CSV e Excel.

O período vai na URL (`de` e `ate`), então o endereço da página pode ser guardado ou compartilhado e o botão Voltar do
navegador funciona entre as abas. A exportação refaz a montagem da aba com os mesmos parâmetros, para o arquivo
trazer exatamente os dados da tabela."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from src.domain import relatorios_lista as lista
from src.domain.valores import hoje_br
from src.web import dados_relatorios
from src.web.dependencias import exigir_dono
from src.web.sessao import Sessao
from src.web.templates import renderizar

router = APIRouter()

_FORMATOS = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _url(base, aba, visao, de, ate, **extra):
    parametros = {}
    if base == "/relatorios" and aba != lista.ABAS[0][0]:
        parametros["aba"] = aba
    if aba == "custo" and visao != lista.VISOES_CUSTO[0][0]:
        parametros["visao"] = visao
    if aba != "inadimplencia":
        if de:
            parametros["de"] = de
        if ate:
            parametros["ate"] = ate
    parametros.update(extra)
    return base + (f"?{urlencode(parametros)}" if parametros else "")


def _contexto(aba, visao, de, ate):
    hoje = hoje_br()
    inicio, fim, erro = lista.ler_periodo(de, ate, hoje)
    de_iso, ate_iso = inicio.isoformat(), fim.isoformat()
    # Só vão para a URL as datas que o usuário escolheu: sem elas vale o padrão do dia.
    de_url, ate_url = (de if lista.data_valida(de) else ""), (ate if lista.data_valida(ate) else "")
    d = None if erro else dados_relatorios.carregar(aba, visao, inicio, fim, hoje)
    contexto = {
        "titulo": "Relatórios", "aba": aba, "visao": visao, "d": d, "erro_periodo": erro, "de": de_iso, "ate": ate_iso,
        # A inadimplência é a posição de hoje: o período do cabeçalho não se aplica a ela.
        "subtitulo": "Posição de hoje" if aba == "inadimplencia" else ("" if erro else dados_relatorios.periodo_texto(inicio, fim)),
        "abas_da_lista": [(chave, rotulo, _url(f"/relatorios/abas/{chave}", chave, visao, de_url, ate_url),
                           _url("/relatorios", chave, visao, de_url, ate_url)) for chave, rotulo in lista.ABAS],
        "visoes": [(chave, rotulo, _url("/relatorios", "custo", chave, de_url, ate_url),
                    _url("/relatorios/abas/custo", "custo", chave, de_url, ate_url)) for chave, rotulo in lista.VISOES_CUSTO],
    }
    if d and d["exportacao"]:
        contexto["exportar"] = [
            (rotulo, _url("/relatorios/exportar", aba, visao, de_iso, ate_iso, formato=formato))
            for formato, rotulo in (("csv", "Exportar CSV"), ("xlsx", "Exportar Excel"))
        ]
    return contexto


def _so_painel(request):
    return (request.headers.get("HX-Request") == "true" and request.headers.get("HX-Target") == "painel-aba"
            and not request.headers.get("HX-History-Restore-Request"))


@router.get("/relatorios")
def pagina(request: Request, aba: str | None = None, visao: str | None = None, de: str | None = None,
           ate: str | None = None, _: Sessao = Depends(exigir_dono)):
    modelo = "relatorios/_resposta_aba.html" if _so_painel(request) else "relatorios/lista.html"
    return renderizar(request, modelo, _contexto(lista.aba_valida(aba), lista.visao_valida(visao), de, ate))


@router.get("/relatorios/abas/{aba}")
def painel(request: Request, aba: str, visao: str | None = None, de: str | None = None, ate: str | None = None,
           _: Sessao = Depends(exigir_dono)):
    if aba not in dict(lista.ABAS):
        raise HTTPException(status_code=404)
    return renderizar(request, "relatorios/_resposta_aba.html", _contexto(aba, lista.visao_valida(visao), de, ate))


@router.get("/relatorios/exportar")
async def exportar(aba: str | None = None, visao: str | None = None, de: str | None = None, ate: str | None = None,
                   formato: str = "csv", _: Sessao = Depends(exigir_dono)):
    if formato not in _FORMATOS:
        raise HTTPException(status_code=404)
    aba, visao = lista.aba_valida(aba), lista.visao_valida(visao)
    hoje = hoje_br()
    inicio, fim, erro = lista.ler_periodo(de, ate, hoje)
    if erro:
        raise HTTPException(status_code=422, detail=erro)
    dados = await run_in_threadpool(dados_relatorios.carregar, aba, visao, inicio, fim, hoje)
    if not dados["exportacao"]:
        raise HTTPException(status_code=404)
    conteudo = await run_in_threadpool(dados_relatorios.exportar, formato, dados["exportacao"])
    return Response(conteudo, media_type=_FORMATOS[formato],
                    headers={"Content-Disposition": f'attachment; filename="relatorio_{dados["chave"]}.{formato}"'})
