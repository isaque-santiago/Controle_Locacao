"""Fábrica do app FastAPI (Fase 1 da migração do frontend).

Rodar em desenvolvimento:  .venv\\Scripts\\python.exe executar_web.py
Rodar em produção:         uvicorn --factory src.web.app:criar_app --workers 1 --proxy-headers

Use SEMPRE um único worker: as sessões ficam na memória do processo (src/web/sessao.py).
"""

import logging
import os
from time import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.services.autenticacao import ServicoAutenticacao
from src.web.erros import registrar_tratadores
from src.web.limitador import LimitadorTentativas
from src.web.rotas import autenticacao as rotas_autenticacao
from src.web.rotas import componentes as rotas_componentes
from src.web.rotas import clientes as rotas_clientes
from src.web.rotas import cobrancas as rotas_cobrancas
from src.web.rotas import cobrancas_mensagem as rotas_cobrancas_mensagem
from src.web.rotas import cobrancas_pagamento as rotas_cobrancas_pagamento
from src.web.rotas import clientes_formularios as rotas_clientes_formularios
from src.web.rotas import clientes_portal as rotas_clientes_portal
from src.web.rotas import contratos as rotas_contratos
from src.web.rotas import contratos_encerramento as rotas_contratos_encerramento
from src.web.rotas import contratos_novo as rotas_contratos_novo
from src.web.rotas import motos as rotas_motos
from src.web.rotas import motos_formularios as rotas_motos_formularios
from src.web.rotas import manutencao as rotas_manutencao
from src.web.rotas import manutencao_registro as rotas_manutencao_registro
from src.web.rotas import manutencao_finalizacao as rotas_manutencao_finalizacao
from src.web.rotas import manutencao_catalogo as rotas_manutencao_catalogo
from src.web.rotas import documentos as rotas_documentos
from src.web.rotas import relatorios as rotas_relatorios
from src.web.rotas import documentos_formularios as rotas_documentos_formularios
from src.web.rotas import documentos_regularizacao as rotas_documentos_regularizacao
from src.web.rotas import vistorias as rotas_vistorias
from src.web.rotas import vistorias_registro as rotas_vistorias_registro
from src.web.rotas import paginas as rotas_paginas
from src.web.seguranca import CabecalhosSeguranca
from src.web.sessao import ArmazemSessoes
from src.web.templates import PASTA_ESTATICOS

logger = logging.getLogger(__name__)

# 5 falhas por e-mail/CPF e 20 por IP (IP de operadora pode ser compartilhado) em 15 min.
FALHAS_POR_IDENTIFICADOR = 5
FALHAS_POR_IP = 20
JANELA_LIMITE_SEGUNDOS = 900


def ambiente_de_desenvolvimento() -> bool:
    return os.getenv("LOCACAO_AMBIENTE", "").lower() == "dev"


def criar_app(
    servico=None,
    armazem: ArmazemSessoes | None = None,
    relogio=time,
    desenvolvimento: bool | None = None,
) -> FastAPI:
    """Monta o app. Os parâmetros existem para os testes injetarem fakes e um relógio."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    app.state.relogio = relogio
    app.state.servico = servico or ServicoAutenticacao()
    app.state.armazem = armazem or ArmazemSessoes(relogio=relogio)
    app.state.limitador_ip = LimitadorTentativas(
        FALHAS_POR_IP, JANELA_LIMITE_SEGUNDOS, relogio
    )
    app.state.limitador_identificador = LimitadorTentativas(
        FALHAS_POR_IDENTIFICADOR, JANELA_LIMITE_SEGUNDOS, relogio
    )

    app.add_middleware(CabecalhosSeguranca)
    app.mount("/static", StaticFiles(directory=str(PASTA_ESTATICOS)), name="static")

    app.include_router(rotas_paginas.router)
    app.include_router(rotas_clientes_formularios.router)
    app.include_router(rotas_clientes_portal.router)
    app.include_router(rotas_clientes.router)
    # O assistente antes da ficha: /contratos/novo não pode cair em /contratos/{contrato_id}
    app.include_router(rotas_cobrancas_mensagem.router)
    app.include_router(rotas_cobrancas_pagamento.router)
    app.include_router(rotas_cobrancas.router)
    app.include_router(rotas_contratos_novo.router)
    app.include_router(rotas_contratos_encerramento.router)
    app.include_router(rotas_contratos.router)
    app.include_router(rotas_manutencao_registro.router)
    app.include_router(rotas_manutencao_catalogo.router)
    app.include_router(rotas_manutencao.router)
    # As abas estáticas precisam vir antes de /manutencao/{id}/{acao}.
    app.include_router(rotas_manutencao_finalizacao.router)
    app.include_router(rotas_documentos_formularios.router)
    app.include_router(rotas_documentos_regularizacao.router)
    app.include_router(rotas_documentos.router)
    app.include_router(rotas_relatorios.router)
    app.include_router(rotas_vistorias_registro.router)
    app.include_router(rotas_vistorias.router)
    # Formulários antes da ficha: /motos/nova não pode cair em /motos/{moto_id}
    app.include_router(rotas_motos_formularios.router)
    app.include_router(rotas_motos.router)
    app.include_router(rotas_autenticacao.router)
    if desenvolvimento if desenvolvimento is not None else ambiente_de_desenvolvimento():
        app.include_router(rotas_componentes.router)

    registrar_tratadores(app)
    return app
