"""Gera folhas de resposta sintéticas no estilo das bancas, para testar a leitura de bolhas."""

import cv2
import numpy as np

DIAMETRO = 22
PASSO_LINHA = 30
PASSO_BOLHA = 28
LARGURA_GRUPO = 120
CINZA_FAIXA = 225
CINZA_ANEL = 150


def folha_cebraspe(
    marcas: dict[int, str],
    total_itens: int,
    itens_por_coluna: int,
    origem: tuple[int, int] = (80, 700),
    parciais: dict[int, str] | None = None,
    angulo: float = 0.0,
) -> np.ndarray:
    """Folha C/E: `marcas` mapeia questão → letras preenchidas ('C', 'E', 'CE'); `parciais`, meio preenchidas."""
    return _folha('CE', marcas, total_itens, itens_por_coluna, origem, parciais or {}, angulo, fgv=False)


def folha_fgv(marcas: dict[int, str], total_itens: int, itens_por_coluna: int) -> np.ndarray:
    """Cartão A–E no estilo FGV: blocos de 5 linhas com faixa cinza alternada e bolhas claras de miolo branco."""
    return _folha('ABCDE', marcas, total_itens, itens_por_coluna, (80, 700), {}, 0.0, fgv=True)


def folha_generica(
    alternativas: str, marcas: dict[int, str], total_itens: int, itens_por_coluna: int
) -> np.ndarray:
    """Grade com bolhas de anel preto e qualquer número de alternativas."""
    return _folha(alternativas, marcas, total_itens, itens_por_coluna, (80, 700), {}, 0.0, fgv=False)


def _folha(alternativas, marcas, total_itens, itens_por_coluna, origem, parciais, angulo, fgv) -> np.ndarray:
    imagem = np.full((1754, 1240), 255, np.uint8)
    cv2.putText(imagem, 'FOLHA DE RESPOSTAS', (80, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.4, 0, 3)
    cv2.circle(imagem, (300, 300), DIAMETRO // 2, 0, 2)
    for x, y in ((40, 40), (1170, 40), (40, 1680), (1170, 1680)):
        cv2.rectangle(imagem, (x, y), (x + 30, y + 8), 0, -1)
    largura_grupo = LARGURA_GRUPO + PASSO_BOLHA * (len(alternativas) - 2)
    if fgv:
        for bloco in range(0, itens_por_coluna, 10):
            y = origem[1] + bloco * PASSO_LINHA - PASSO_LINHA // 2
            cv2.rectangle(imagem, (origem[0] - 10, y), (1200, y + 5 * PASSO_LINHA), CINZA_FAIXA, -1)
    for questao in range(1, total_itens + 1):
        coluna, linha = divmod(questao - 1, itens_por_coluna)
        x0 = origem[0] + coluna * largura_grupo
        y = origem[1] + linha * PASSO_LINHA
        cv2.putText(imagem, str(questao), (x0, y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, 0, 1)
        for indice, letra in enumerate(alternativas):
            centro = (x0 + 48 + indice * PASSO_BOLHA, y)
            if letra in marcas.get(questao, ''):
                cv2.circle(imagem, centro, DIAMETRO // 2, 0, -1)
            elif letra in parciais.get(questao, ''):
                cv2.circle(imagem, centro, DIAMETRO // 2, 0, 2)
                cv2.ellipse(imagem, centro, (DIAMETRO // 2, DIAMETRO // 2), 0, 0, 180, 0, -1)
            elif fgv:
                cv2.circle(imagem, centro, DIAMETRO // 2, 255, -1)
                cv2.circle(imagem, centro, DIAMETRO // 2, CINZA_ANEL, 2)
                cv2.putText(
                    imagem,
                    letra,
                    (centro[0] - 5, centro[1] + 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    CINZA_ANEL,
                    1,
                )
            else:
                cv2.circle(imagem, centro, DIAMETRO // 2, 0, 2)
                cv2.putText(
                    imagem, letra, (centro[0] - 5, centro[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, 0, 1
                )
    if not fgv:
        for linha in range(2, itens_por_coluna, 7):
            y = origem[1] + linha * PASSO_LINHA
            cv2.rectangle(imagem, (20, y - 6), (34, y + 6), 0, -1)
    if angulo:
        matriz = cv2.getRotationMatrix2D((620, 877), angulo, 1.0)
        imagem = cv2.warpAffine(imagem, matriz, (1240, 1754), borderValue=255)
    return imagem
