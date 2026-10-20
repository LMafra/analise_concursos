import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium

from concursos.modelo import Estado, Origem, RespostaMarcada

logger = logging.getLogger(__name__)

TEMPLATES = {'cebraspe_ce': 'CE'}
DPI = 300
VAZIO = 0.2
CHEIO = 0.9
LIMIAR_MARCADA = 0.5
_CIRCULARIDADE_MINIMA = 0.8
_RAIO_AMOSTRA = 0.35
_ANGULO_MAXIMO = 5.0
_PASSO_ANGULO = 0.1


class FolhaIlegivelError(ValueError):
    pass


@dataclass(frozen=True)
class Marcacao:
    questao: int
    alternativa: str | None
    estado: Estado
    confianca: float
    preenchimentos: tuple[float, ...]
    centros: tuple[tuple[int, int], ...]
    raio: int


def ler_folha(
    caminho: Path,
    template: str,
    total_itens: int,
    itens_por_coluna: int | None,
    pasta_depuracao: Path,
    limiar: float,
) -> list[RespostaMarcada]:
    """Lê a primeira página do arquivo que contenha a grade e grava a imagem de depuração."""
    alternativas = TEMPLATES.get(template)
    if alternativas is None:
        raise FolhaIlegivelError(
            f'{caminho.name}: template {template!r} não suportado (use {", ".join(TEMPLATES)})'
        )
    erros = []
    for pagina, imagem in enumerate(carregar_paginas(caminho), start=1):
        try:
            marcacoes = ler_marcacoes(imagem, alternativas, total_itens, itens_por_coluna)
        except FolhaIlegivelError as erro:
            erros.append(f'página {pagina}: {erro}')
            continue
        pasta_depuracao.mkdir(parents=True, exist_ok=True)
        depuracao = pasta_depuracao / f'{caminho.stem}_p{pagina}.png'
        cv2.imwrite(str(depuracao), desenhar_depuracao(imagem, marcacoes, limiar))
        revisar = sum(m.confianca < limiar for m in marcacoes)
        logger.info(
            '%s: página %d lida, %d questões para revisar (%s)', caminho.name, pagina, revisar, depuracao
        )
        return [
            RespostaMarcada(
                m.questao, m.alternativa, m.estado, m.confianca, Origem.FOLHA, caminho.name, pagina
            )
            for m in marcacoes
        ]
    raise FolhaIlegivelError(f'{caminho.name}: ' + '; '.join(erros))


def carregar_paginas(caminho: Path) -> list[np.ndarray]:
    """Páginas em tons de cinza: PDFs renderizados a 300 dpi, imagens lidas diretamente."""
    if caminho.suffix.lower() != '.pdf':
        imagem = cv2.imread(str(caminho), cv2.IMREAD_GRAYSCALE)
        if imagem is None:
            raise FolhaIlegivelError(f'{caminho.name}: imagem ilegível ou formato não suportado')
        return [imagem]
    documento = pdfium.PdfDocument(caminho)
    paginas = []
    for pagina in documento:
        rgb = pagina.render(scale=DPI / 72, grayscale=True).to_numpy()
        paginas.append(rgb if rgb.ndim == 2 else cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY))
    return paginas


def ler_marcacoes(
    imagem: np.ndarray, alternativas: str, total_itens: int, itens_por_coluna: int | None = None
) -> list[Marcacao]:
    """Localiza a grade de bolhas (itens numerados por coluna) e mede o preenchimento de cada bolha."""
    binaria = cv2.threshold(
        cv2.GaussianBlur(imagem, (3, 3), 0), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )[1]
    candidatos = _candidatos(binaria)
    if len(candidatos) < len(alternativas):
        raise FolhaIlegivelError('nenhuma grade de bolhas encontrada')
    diametro = float(np.median(candidatos[:, 2]))
    centro = (imagem.shape[1] / 2, imagem.shape[0] / 2)
    rotacao = cv2.getRotationMatrix2D(centro, _angulo(candidatos[:, :2], centro, diametro), 1.0)
    alinhados = _transformar(rotacao, candidatos[:, :2])
    linhas = _linhas(alinhados[:, 1], diametro)
    if itens_por_coluna is not None and len(linhas) != itens_por_coluna:
        raise FolhaIlegivelError(
            f'grade detectada com {len(linhas)} linhas, mas itens_por_coluna = {itens_por_coluna}'
        )
    colunas = _colunas(alinhados, linhas, diametro)
    grupos = -(-total_itens // len(linhas))
    if len(colunas) != grupos * len(alternativas):
        raise FolhaIlegivelError(
            f'grade de bolhas não reconhecida: {len(colunas)} colunas de bolhas e {len(linhas)} linhas; '
            f'esperado {grupos} colunas de itens × {len(alternativas)} alternativas para {total_itens} itens'
        )
    inversa = cv2.invertAffineTransform(rotacao)
    raio = max(2, round(diametro * _RAIO_AMOSTRA))
    marcacoes = []
    for questao in range(1, total_itens + 1):
        grupo, linha = divmod(questao - 1, len(linhas))
        xs = colunas[grupo * len(alternativas) : (grupo + 1) * len(alternativas)]
        pontos = _transformar(inversa, np.array([(x, linhas[linha]) for x in xs]))
        centros = tuple((round(x), round(y)) for x, y in pontos)
        preenchimentos = tuple(_preenchimento(binaria, c, raio) for c in centros)
        marcacoes.append(_classificar(questao, alternativas, preenchimentos, centros, round(diametro / 2)))
    return marcacoes


def _candidatos(binaria: np.ndarray) -> np.ndarray:
    """Contornos aproximadamente circulares (x, y, diâmetro), sem duplicatas de anéis concêntricos."""
    largura = binaria.shape[1]
    minimo, maximo = largura * 0.008, largura * 0.035
    contornos, _ = cv2.findContours(binaria, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    achados = []
    for contorno in contornos:
        x, y, w, h = cv2.boundingRect(contorno)
        if not (minimo <= h <= maximo and 0.75 <= w / h <= 1.33):
            continue
        perimetro = cv2.arcLength(contorno, True)
        if perimetro and 4 * np.pi * cv2.contourArea(contorno) / perimetro**2 >= _CIRCULARIDADE_MINIMA:
            achados.append((x + w / 2, y + h / 2, (w + h) / 2))
    if not achados:
        return np.empty((0, 3))
    achados.sort(key=lambda c: -c[2])
    unicos: list[tuple[float, float, float]] = []
    for x, y, d in achados:
        if all(abs(x - ux) > ud / 2 or abs(y - uy) > ud / 2 for ux, uy, ud in unicos):
            unicos.append((x, y, d))
    candidatos = np.array(unicos)
    mediana = np.median(candidatos[:, 2])
    return candidatos[(candidatos[:, 2] > mediana * 0.7) & (candidatos[:, 2] < mediana * 1.3)]


def _angulo(pontos: np.ndarray, centro: tuple[float, float], diametro: float) -> float:
    """Ângulo que deixa as bolhas mais concentradas em linhas horizontais."""
    melhor, melhor_nota = 0.0, -1.0
    for angulo in np.arange(-_ANGULO_MAXIMO, _ANGULO_MAXIMO + _PASSO_ANGULO / 2, _PASSO_ANGULO):
        ys = _transformar(cv2.getRotationMatrix2D(centro, float(angulo), 1.0), pontos)[:, 1]
        nota = float((np.bincount(((ys - ys.min()) / (diametro / 2)).astype(int)) ** 2).sum())
        if nota > melhor_nota:
            melhor, melhor_nota = float(angulo), nota
    return melhor


def _transformar(matriz: np.ndarray, pontos: np.ndarray) -> np.ndarray:
    return np.hstack([pontos, np.ones((len(pontos), 1))]) @ matriz.T


def _agrupar(valores: np.ndarray, distancia: float) -> list[np.ndarray]:
    ordenados = np.sort(valores)
    cortes = np.where(np.diff(ordenados) > distancia)[0] + 1
    return np.split(ordenados, cortes)


def _linhas(ys: np.ndarray, diametro: float) -> list[float]:
    grupos = _agrupar(ys, diametro / 2)
    maior = max(len(g) for g in grupos)
    return [float(g.mean()) for g in grupos if len(g) >= maior / 2]


def _colunas(pontos: np.ndarray, linhas: list[float], diametro: float) -> list[float]:
    na_grade = np.min(np.abs(pontos[:, 1, None] - np.array(linhas)[None, :]), axis=1) < diametro / 2
    grupos = _agrupar(pontos[na_grade, 0], diametro / 2)
    return [float(g.mean()) for g in grupos if len(g) >= len(linhas) * 0.3]


def _preenchimento(binaria: np.ndarray, centro: tuple[int, int], raio: int) -> float:
    x, y = centro
    recorte = binaria[max(0, y - raio) : y + raio + 1, max(0, x - raio) : x + raio + 1]
    mascara = np.zeros_like(recorte)
    cv2.circle(mascara, (min(x, raio), min(y, raio)), raio, 255, -1)
    total = np.count_nonzero(mascara)
    return float(np.count_nonzero(recorte & mascara)) / total if total else 0.0


def _nota(preenchimento: float) -> float:
    """Preenchimento normalizado: 0 = bolha vazia típica, 1 = bolha cheia típica."""
    return min(1.0, max(0.0, (preenchimento - VAZIO) / (CHEIO - VAZIO)))


def _classificar(
    questao: int, alternativas: str, preenchimentos: tuple[float, ...], centros, raio: int
) -> Marcacao:
    """Estado pelas bolhas acima do limiar; confiança = margem entre a decisão e a alternativa mais próxima."""
    notas = [_nota(p) for p in preenchimentos]
    marcadas = [letra for letra, nota in zip(alternativas, notas, strict=True) if nota >= LIMIAR_MARCADA]
    primeira, segunda = sorted(notas, reverse=True)[:2]
    if len(marcadas) == 1:
        estado, alternativa, confianca = Estado.MARCADA, marcadas[0], primeira - segunda
    elif marcadas:
        estado, alternativa, confianca = Estado.MULTIPLA, None, segunda
    else:
        estado, alternativa, confianca = Estado.BRANCO, None, 1 - primeira
    return Marcacao(
        questao,
        alternativa,
        estado,
        round(confianca, 3),
        tuple(round(p, 3) for p in preenchimentos),
        centros,
        raio,
    )


def desenhar_depuracao(imagem: np.ndarray, marcacoes: list[Marcacao], limiar: float) -> np.ndarray:
    """Bolhas lidas sobrepostas: verde = marcada, azul = múltipla, cinza = vazia; anel vermelho = revisar."""
    colorida = cv2.cvtColor(imagem, cv2.COLOR_GRAY2BGR)
    for marcacao in marcacoes:
        for preenchimento, centro in zip(marcacao.preenchimentos, marcacao.centros, strict=True):
            if _nota(preenchimento) < LIMIAR_MARCADA:
                cor = (160, 160, 160)
            elif marcacao.estado is Estado.MULTIPLA:
                cor = (255, 0, 0)
            else:
                cor = (0, 180, 0)
            cv2.circle(colorida, centro, marcacao.raio, cor, 2)
        if marcacao.confianca < limiar:
            cv2.circle(colorida, marcacao.centros[0], marcacao.raio * 3, (0, 0, 255), 2)
    return colorida
