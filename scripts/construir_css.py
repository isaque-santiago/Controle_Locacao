"""Gera static/css/app.css com o Tailwind CLI standalone (sem Node).

    python scripts/construir_css.py            # uma vez, minificado
    python scripts/construir_css.py --watch    # recompila ao salvar templates/CSS

O binário fica em tools/ (fora do git). Baixe a versão do seu sistema em
https://github.com/tailwindlabs/tailwindcss/releases (tailwindcss-windows-x64.exe,
tailwindcss-linux-x64, ...) e salve como tools/tailwindcss.exe (ou tools/tailwindcss).
O app.css compilado é versionado: a VPS não precisa do Tailwind.
"""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ENTRADA = RAIZ / "src" / "web" / "estilos" / "app.css"
SAIDA = RAIZ / "static" / "css" / "app.css"


def _binario() -> Path:
    for nome in ("tailwindcss.exe", "tailwindcss"):
        caminho = RAIZ / "tools" / nome
        if caminho.exists():
            return caminho
    sys.exit("Tailwind CLI não encontrado em tools/. Veja as instruções no topo deste arquivo.")


def main() -> int:
    comando = [str(_binario()), "-i", str(ENTRADA), "-o", str(SAIDA)]
    comando.append("--watch" if "--watch" in sys.argv else "--minify")
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.call(comando, cwd=RAIZ)


if __name__ == "__main__":
    raise SystemExit(main())
