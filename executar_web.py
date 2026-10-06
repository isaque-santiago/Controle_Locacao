r"""Sobe o app web (FastAPI) em desenvolvimento, com recarga automática.

    .venv\Scripts\python.exe executar_web.py

Em desenvolvimento a rota /componentes fica disponível (LOCACAO_AMBIENTE=dev).
Em produção use:  uvicorn --factory src.web.app:criar_app --workers 1 --proxy-headers
(um único worker: as sessões ficam na memória do processo).
"""

import os

import uvicorn

if __name__ == "__main__":
    os.environ.setdefault("LOCACAO_AMBIENTE", "dev")
    uvicorn.run(
        "src.web.app:criar_app",
        factory=True,
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
        reload_dirs=["src", "static"],
    )
