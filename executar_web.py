r"""Sobe o app web (FastAPI) em desenvolvimento, com recarga automática.

    .venv\Scripts\python.exe executar_web.py

Em desenvolvimento a rota /componentes fica disponível (LOCACAO_AMBIENTE=dev).

    .venv\Scripts\python.exe executar_web.py --sem-recarga

Sem recarga automática: as sessões ficam na memória do processo, então cada arquivo .py salvo
derrubaria o login. Use quando for conferir telas no navegador e reinicie à mão depois de editar.
Em produção use:  uvicorn --factory src.web.app:criar_app --workers 1 --proxy-headers
(um único worker: as sessões ficam na memória do processo).
"""

import os
import sys

import uvicorn

if __name__ == "__main__":
    os.environ.setdefault("LOCACAO_AMBIENTE", "dev")
    uvicorn.run(
        "src.web.app:criar_app",
        factory=True,
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8000")),
        reload="--sem-recarga" not in sys.argv,
        reload_dirs=["src", "static"],
    )
