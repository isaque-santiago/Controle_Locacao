r"""Sobe o app web (FastAPI) em desenvolvimento, com recarga automática.

    .venv\Scripts\python.exe executar_web.py

Em desenvolvimento a rota /componentes fica disponível (LOCACAO_AMBIENTE=dev).

    .venv\Scripts\python.exe executar_web.py --sem-recarga

As sessões ficam na memória do processo, mas aqui, só em desenvolvimento, elas também são espelhadas no arquivo
`.sessoes_dev.json` (fora do git; guarda tokens do Supabase), então a recarga automática ao salvar um .py NÃO derruba o
login. O `--sem-recarga` continua existindo para quando se quer o servidor parado. Apagar o arquivo encerra as sessões.

A recarga é feita por este script, não pelo `--reload` do uvicorn: no Windows o uvicorn reinicia o servidor mandando um
Ctrl+C ao console, o que não chega ao processo quando ele roda sem console (preview do Claude, serviços) e a recarga
trava. Aqui o servidor roda como processo filho, e a cada .py salvo o filho é encerrado e criado de novo.

Em produção use:  uvicorn --factory src.web.app:criar_app --workers 1 --proxy-headers
(um único worker: as sessões ficam só na memória do processo e nada é gravado em disco).
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import uvicorn

RAIZ = Path(__file__).resolve().parent
PASTAS_OBSERVADAS = ("src",)  # templates e CSS são relidos a cada requisição; só o Python exige reiniciar
INTERVALO_VERIFICACAO_SEGUNDOS = 0.5
ESPERA_ENTRE_MUDANCAS_SEGUNDOS = 0.3  # junta uma rajada de arquivos salvos de uma vez numa só recarga


def _assinatura() -> dict[str, int]:
    """Instante de modificação de cada .py observado."""
    arquivos = {}
    for pasta in PASTAS_OBSERVADAS:
        for caminho in (RAIZ / pasta).rglob("*.py"):
            try:
                arquivos[str(caminho)] = caminho.stat().st_mtime_ns
            except OSError:  # apagado entre a listagem e a leitura
                continue
    return arquivos


def _mudancas(antes: dict[str, int], depois: dict[str, int]) -> list[str]:
    return sorted(c for c in antes.keys() | depois.keys() if antes.get(c) != depois.get(c))


def _iniciar_servidor() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--sem-recarga"], cwd=RAIZ)


def _parar(processo: subprocess.Popen) -> None:
    processo.terminate()
    try:
        processo.wait(timeout=5)
    except subprocess.TimeoutExpired:
        processo.kill()
        processo.wait()


def servir_com_recarga() -> None:
    assinatura = _assinatura()
    servidor = _iniciar_servidor()
    try:
        while True:
            time.sleep(INTERVALO_VERIFICACAO_SEGUNDOS)
            mudaram = _mudancas(assinatura, _assinatura())
            if servidor.poll() is not None:  # o servidor caiu (erro de sintaxe, por exemplo): espera a próxima edição
                if mudaram:
                    assinatura = _assinatura()
                    servidor = _iniciar_servidor()
                continue
            if not mudaram:
                continue
            time.sleep(ESPERA_ENTRE_MUDANCAS_SEGUNDOS)
            assinatura = _assinatura()
            resumo = ", ".join(Path(c).name for c in mudaram[:3]) + (" e outros" if len(mudaram) > 3 else "")
            print(f"Recarregando ({resumo})...", flush=True)
            _parar(servidor)
            servidor = _iniciar_servidor()
    except KeyboardInterrupt:
        pass
    finally:
        if servidor.poll() is None:
            _parar(servidor)


def servir() -> None:
    uvicorn.run("src.web.app:criar_app", factory=True, host="127.0.0.1", port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    os.environ.setdefault("LOCACAO_AMBIENTE", "dev")
    # As sessões sobrevivem à recarga do servidor (só em desenvolvimento): arquivo local, fora do git.
    os.environ.setdefault("LOCACAO_SESSOES_ARQUIVO", str(RAIZ / ".sessoes_dev.json"))
    if "--sem-recarga" in sys.argv:
        servir()
    else:
        servir_com_recarga()
