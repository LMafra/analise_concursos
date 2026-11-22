"""Gera o ícone do executável (`.ico` do Windows, `.icns` do macOS e `.png` do Linux) só com o Pillow.

Paleta Gabarito Vivo: tinta-teal (#0F766E) + acento verde (#15803D).
Também grava os nomes legados `gabarito-vivo.*` para scripts que ainda os citam.

Uso: uv run python empacotamento/icones/gerar_icones.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

PASTA = Path(__file__).parent
LADO = 1024
TEAL = (15, 118, 110, 255)
BRANCO = (255, 255, 255, 255)
VERDE = (21, 128, 61, 255)
NOMES = ('gabarito-vivo', 'gabarito-vivo')


def desenhar() -> Image.Image:
    imagem = Image.new('RGBA', (LADO, LADO), (0, 0, 0, 0))
    pincel = ImageDraw.Draw(imagem)
    pincel.rounded_rectangle((48, 48, LADO - 48, LADO - 48), radius=200, fill=TEAL)
    # Folha de respostas: três linhas de alternativas, a do meio marcada.
    for linha, y in enumerate((250, 420, 590)):
        for coluna, x in enumerate((300, 450, 600, 750)):
            marcada = linha == 1 and coluna == 2
            pincel.ellipse(
                (x - 55, y - 55, x + 55, y + 55),
                fill=BRANCO if marcada else None,
                outline=BRANCO,
                width=18,
            )
    pincel.line([(370, 790), (480, 880), (680, 700)], fill=VERDE, width=64, joint='curve')
    return imagem


def main() -> None:
    imagem = desenhar()
    for nome in NOMES:
        imagem.save(PASTA / f'{nome}.png')
        imagem.resize((256, 256), Image.Resampling.LANCZOS).save(PASTA / f'{nome}-256.png')
        imagem.save(PASTA / f'{nome}.ico', sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
        imagem.save(PASTA / f'{nome}.icns')


if __name__ == '__main__':
    main()
