"""Gera os ícones PNG do app instalável (PWA) em static/icones/, no desenho do static/favicon.svg ("CL" em amarelo).

    python scripts/gerar_icones_pwa.py

Usa o Pillow e uma fonte sem serifa em negrito do sistema (Liberation Sans ou DejaVu Sans). Os PNGs gerados são
versionados: a VPS não precisa rodar este script."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "static" / "icones"
AMARELO = (242, 183, 5, 255)
GRAFITE = (30, 34, 39, 255)
FONTES = (
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


def _fonte(tamanho: int) -> ImageFont.FreeTypeFont:
    for caminho in FONTES:
        if Path(caminho).exists():
            return ImageFont.truetype(caminho, tamanho)
    sys.exit("Nenhuma fonte em negrito encontrada; ajuste a lista FONTES do script.")


def _icone(lado: int, raio: float, texto_proporcao: float) -> Image.Image:
    """Quadrado amarelo com "CL" centralizado. raio: fração do lado (0 = quadrado inteiro, para o ícone "maskable");
    texto_proporcao: altura do texto em relação ao lado."""
    ampliacao = 4  # desenha maior e reduz, para bordas suaves
    grande = lado * ampliacao
    imagem = Image.new("RGBA", (grande, grande), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    desenho.rounded_rectangle((0, 0, grande - 1, grande - 1), radius=int(grande * raio), fill=AMARELO)
    fonte = _fonte(int(grande * texto_proporcao))
    esquerda, topo, direita, base = desenho.textbbox((0, 0), "CL", font=fonte)
    posicao = ((grande - (direita - esquerda)) / 2 - esquerda, (grande - (base - topo)) / 2 - topo)
    desenho.text(posicao, "CL", font=fonte, fill=GRAFITE)
    return imagem.resize((lado, lado), Image.LANCZOS)


def main() -> int:
    SAIDA.mkdir(parents=True, exist_ok=True)
    arquivos = {
        "icone-192.png": _icone(192, 0.22, 0.46),
        "icone-512.png": _icone(512, 0.22, 0.46),
        # Maskable: o sistema recorta (círculo, "squircle"...), então fundo cheio e texto na zona segura (~60%)
        "icone-maskable-512.png": _icone(512, 0.0, 0.34),
        # iOS arredonda sozinho: fundo cheio
        "apple-touch-icon.png": _icone(180, 0.0, 0.42),
    }
    for nome, imagem in arquivos.items():
        imagem.save(SAIDA / nome, optimize=True)
        print("gerado", SAIDA.relative_to(RAIZ) / nome)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
