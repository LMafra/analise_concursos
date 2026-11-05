"""Gera o ícone do executável (`.ico` do Windows, `.icns` do macOS e `.png` do Linux) só com o Pillow.

Uso: uv run python empacotamento/icones/gerar_icones.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

PASTA = Path(__file__).parent
LADO = 1024
AZUL = (25, 118, 210, 255)
BRANCO = (255, 255, 255, 255)
VERDE = (102, 187, 106, 255)


def desenhar() -> Image.Image:
    imagem = Image.new('RGBA', (LADO, LADO), (0, 0, 0, 0))
    pincel = ImageDraw.Draw(imagem)
    pincel.rounded_rectangle((48, 48, LADO - 48, LADO - 48), radius=200, fill=AZUL)
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
    imagem.save(PASTA / 'concurso-analise.png')
    imagem.save(PASTA / 'concurso-analise.ico', sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    imagem.save(PASTA / 'concurso-analise.icns')


if __name__ == '__main__':
    main()
