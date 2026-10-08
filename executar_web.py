r"""Sobe o app web (FastAPI) em desenvolvimento, com recarga automática.

    .venv\Scripts\python.exe executar_web.py

Em desenvolvimento a rota /componentes fica disponível (LOCACAO_AMBIENTE=dev).

    .venv\Scripts\python.exe executar_web.py --sem-recarga

As sessões ficam na memória do processo, mas aqui, só em desenvolvimento, elas também são espelhadas no arquivo
`.sessoes_dev.json` (fora do git; guarda tokens do Supabase), então a recarga automática ao salvar um .py NÃO derruba o
login. O `--sem-recarga` continua existindo para quando se quer o servidor parado. Apagar o arquivo encerra as sessões.
Em produção use:  uvicorn --factory src.web.app:criar_app --workers 1 --proxy-headers
(um único worker: as sessões ficam só na memória do processo e nada é gravado em disco).
"""

import os
import sys
from pathlib import Path

import uvicorn

if __name__ == "__main__":
    os.environ.setdefault("LOCACAO_AMBIENTE", "dev")
    # As sessões sobrevivem à recarga do servidor (só em desenvolvimento): arquivo local, fora do git.
    os.environ.setdefault("LOCACAO_SESSOES_ARQUIVO", str(Path(__file__).resolve().parent / ".sessoes_dev.json"))
    uvicorn.run(
        "src.web.app:criar_app",
        factory=True,
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8000")),
        reload="--sem-recarga" not in sys.argv,
        reload_dirs=["src", "static"],
    )
