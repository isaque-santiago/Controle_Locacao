"""Regressão visual: compara a captura atual com a referência aprovada.

As referências ficam em `e2e/referencia/<sistema>/...` (ignoradas pelo git: dependem do sistema
operacional, das fontes e dos dados do ambiente de desenvolvimento). A primeira execução, ou a
execução com `--atualizar-referencia`, grava a referência; as seguintes só comparam."""

import sys
from pathlib import Path

from PIL import Image, ImageChops

PASTA_E2E = Path(__file__).parent
PASTA_ATUAL = PASTA_E2E / "capturas_atuais"
PASTA_REFERENCIA = PASTA_E2E / "referencia" / "web" / sys.platform
PASTA_DIFERENCAS = PASTA_E2E / "resultados" / "diferencas"

# Diferença de canal (0–255) abaixo da qual o pixel conta como igual (serrilhado de fontes).
_LIMIAR_CANAL = 24


def caminho_referencia(atual: Path) -> Path:
    return PASTA_REFERENCIA / atual.relative_to(PASTA_ATUAL)


def comparar(atual: Path, tolerancia_percentual: float, atualizar: bool) -> tuple[bool, str]:
    """Devolve (aprovado, mensagem). Sem referência, grava a atual e aprova."""
    referencia = caminho_referencia(atual)
    if atualizar or not referencia.exists():
        referencia.parent.mkdir(parents=True, exist_ok=True)
        referencia.write_bytes(atual.read_bytes())
        return True, "referência gravada"
    a, r = Image.open(atual).convert("RGB"), Image.open(referencia).convert("RGB")
    if a.size != r.size:
        return False, f"dimensões diferentes: {a.size[0]}×{a.size[1]} contra {r.size[0]}×{r.size[1]} da referência"
    diferenca = ImageChops.difference(a, r).convert("L").point(lambda v: 255 if v > _LIMIAR_CANAL else 0)
    pixels = sum(1 for v in diferenca.getdata() if v)
    percentual = 100 * pixels / (a.size[0] * a.size[1])
    if percentual <= tolerancia_percentual:
        return True, f"{percentual:.3f}% de pixels diferentes"
    PASTA_DIFERENCAS.mkdir(parents=True, exist_ok=True)
    nome = "__".join(atual.relative_to(PASTA_ATUAL).parts)
    diferenca.save(PASTA_DIFERENCAS / nome)
    return False, f"{percentual:.2f}% de pixels diferentes (limite {tolerancia_percentual}%); diferença em resultados/diferencas/{nome}"
