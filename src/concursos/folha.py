import logging
from dataclasses import dataclass, replace
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium

from concursos.modelo import Estado, Origem, RespostaMarcada
from concursos.perfis import PerfilInvalidoError, PerfilOcr, ids_de_ocr, perfil_ocr

logger = logging.getLogger(__name__)


PADRAO = PerfilOcr('padrao', 'ABCDE')
PERFIL_AUTOMATICO = 'automatico'
_CIRCULARIDADE_MINIMA = 0.8
_FRACAO_TINTA = 0.5
_FRACAO_LINHA = 0.25
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


@dataclass(frozen=True)
class Amostra:
    """As primeiras questões da primeira coluna de itens, medidas sem perfil."""

    n_alternativas: int
    preenchimentos: tuple[tuple[float, ...], ...]
    centros: tuple[tuple[tuple[int, int], ...], ...]
    raio: int


def ler_folha(
    caminho: Path,
    template: str | None,
    total_itens: int,
    itens_por_coluna: int | None,
    pasta_depuracao: Path,
    limiar: float,
    alternativas: str | None = None,
    calibrado: PerfilOcr | None = None,
) -> list[RespostaMarcada]:
    """Lê a primeira página do arquivo que contenha a grade e grava a imagem de depuração.

    Tenta o perfil de OCR do `template` e, sem ele ou quando ele não lê a folha, a detecção automática da
    grade com as `alternativas` do concurso, sem número de linhas imposto, e os limiares do perfil
    `calibrado` do projeto, quando houver."""
    tentativas = []
    if template is not None:
        try:
            perfil = perfil_ocr(template)
        except PerfilInvalidoError:
            raise FolhaIlegivelError(
                f'{caminho.name}: template {template!r} não suportado (use {", ".join(ids_de_ocr())})'
            ) from None
        tentativas.append((perfil, itens_por_coluna or perfil.itens_por_coluna, ''))
        alternativas = alternativas or perfil.alternativas
    letras = alternativas or PADRAO.alternativas
    automatico = (
        replace(calibrado, alternativas=letras, itens_por_coluna=None)
        if calibrado
        else PerfilOcr(PERFIL_AUTOMATICO, letras)
    )
    tentativas.append((automatico, None, ', detecção automática' if tentativas else ''))
    erros: list[str] = []
    for perfil, por_coluna, rotulo in tentativas:
        if erros:
            logger.warning(
                '%s: o perfil %s não leu a folha (%s); tentando a detecção automática da grade',
                caminho.name,
                template,
                erros[-1],
            )
        lidas = _ler_com_perfil(
            caminho, perfil, total_itens, por_coluna, pasta_depuracao, limiar, erros, rotulo
        )
        if lidas is not None:
            return lidas
    raise FolhaIlegivelError(
        f'{caminho.name}: ' + '; '.join(erros) + '. dica: digite as respostas num respostas.csv (colunas '
        'questao e alternativa; - para branco) na pasta do candidato e rode de novo'
    )


def _ler_com_perfil(
    caminho: Path,
    perfil: PerfilOcr,
    total_itens: int,
    itens_por_coluna: int | None,
    pasta_depuracao: Path,
    limiar: float,
    erros: list[str],
    rotulo: str,
) -> list[RespostaMarcada] | None:
    for pagina, imagem in enumerate(carregar_paginas(caminho, perfil.largura), start=1):
        try:
            marcacoes = ler_marcacoes(imagem, perfil.alternativas, total_itens, itens_por_coluna, perfil)
        except FolhaIlegivelError as erro:
            erros.append(f'página {pagina}{rotulo}: {erro}')
            continue
        pasta_depuracao.mkdir(parents=True, exist_ok=True)
        depuracao = pasta_depuracao / f'{caminho.stem}_p{pagina}.png'
        cv2.imwrite(str(depuracao), desenhar_depuracao(imagem, marcacoes, limiar, perfil))
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
    return None


def carregar_paginas(caminho: Path, largura: int = PADRAO.largura) -> list[np.ndarray]:
    """Páginas em tons de cinza com largura normalizada (A4 a 300 dpi no padrão), de PDF ou imagem."""
    if caminho.suffix.lower() != '.pdf':
        imagem = cv2.imread(str(caminho), cv2.IMREAD_GRAYSCALE)
        if imagem is None:
            raise FolhaIlegivelError(f'{caminho.name}: imagem ilegível ou formato não suportado')
        return [_normalizar_largura(imagem, largura)]
    paginas = []
    for pagina in pdfium.PdfDocument(caminho):
        renderizada = pagina.render(scale=largura / pagina.get_width(), grayscale=True).to_numpy()
        if renderizada.ndim == 3:
            renderizada = cv2.cvtColor(renderizada, cv2.COLOR_BGR2GRAY)
        paginas.append(_normalizar_largura(renderizada, largura))
    return paginas


def _normalizar_largura(imagem: np.ndarray, alvo: int) -> np.ndarray:
    altura, largura = imagem.shape
    if largura == alvo:
        return imagem
    return cv2.resize(imagem, (alvo, round(altura * alvo / largura)), interpolation=cv2.INTER_AREA)


def ler_marcacoes(
    imagem: np.ndarray,
    alternativas: str,
    total_itens: int,
    itens_por_coluna: int | None = None,
    perfil: PerfilOcr = PADRAO,
) -> list[Marcacao]:
    """Localiza a grade de bolhas (itens numerados por coluna) e mede a tinta dentro de cada bolha."""
    tinta, rotacao, alinhados, diametro = _grade(imagem, len(alternativas))
    linhas = _linhas(alinhados[:, 1], diametro)
    if itens_por_coluna is not None and len(linhas) != itens_por_coluna:
        raise FolhaIlegivelError(
            f'grade detectada com {len(linhas)} linhas, mas itens_por_coluna = {itens_por_coluna}'
        )
    grupos = -(-total_itens // len(linhas))
    colunas = _colunas(alinhados, linhas, diametro, grupos * len(alternativas))
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
        preenchimentos = tuple(_preenchimento(tinta, c, raio) for c in centros)
        marcacoes.append(
            _classificar(questao, alternativas, preenchimentos, centros, round(diametro / 2), perfil)
        )
    return marcacoes


def medir_amostra(imagem: np.ndarray, questoes: int) -> Amostra:
    """A tinta das bolhas das primeiras `questoes` da primeira coluna de itens; o número de alternativas sai
    do espaçamento entre as colunas de bolhas, maior entre itens do que dentro de um item."""
    tinta, rotacao, alinhados, diametro = _grade(imagem, 2)
    linhas = _linhas(alinhados[:, 1], diametro)
    if len(linhas) < questoes:
        raise FolhaIlegivelError(f'grade com {len(linhas)} linhas; são precisas pelo menos {questoes}')
    colunas = np.array(_colunas(alinhados, linhas, diametro, len(alinhados)))
    if len(colunas) < 2:
        raise FolhaIlegivelError('nenhuma grade de bolhas encontrada')
    distancias = np.diff(colunas)
    itens = np.split(colunas, np.where(distancias > distancias.min() * 1.5)[0] + 1)
    if len({len(item) for item in itens}) != 1:
        raise FolhaIlegivelError(
            f'colunas de bolhas irregulares ({", ".join(str(len(item)) for item in itens)} por item)'
        )
    inversa = cv2.invertAffineTransform(rotacao)
    raio = max(2, round(diametro * _RAIO_AMOSTRA))
    centros = []
    for linha in linhas[:questoes]:
        pontos = _transformar(inversa, np.array([(x, linha) for x in itens[0]]))
        centros.append(tuple((round(x), round(y)) for x, y in pontos))
    return Amostra(
        len(itens[0]),
        tuple(tuple(_preenchimento(tinta, c, raio) for c in linha) for linha in centros),
        tuple(centros),
        round(diametro / 2),
    )


def marcacoes_da_amostra(amostra: Amostra, perfil: PerfilOcr) -> list[Marcacao]:
    return [
        _classificar(questao, perfil.alternativas, preenchimentos, centros, amostra.raio, perfil)
        for questao, (preenchimentos, centros) in enumerate(
            zip(amostra.preenchimentos, amostra.centros, strict=True), start=1
        )
    ]


def _grade(imagem: np.ndarray, minimo: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """A máscara de tinta, a rotação que alinha a grade e os centros das bolhas já alinhados."""
    suave = cv2.GaussianBlur(imagem, (5, 5), 0)
    escuras = cv2.adaptiveThreshold(suave, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 51, 4)
    claras = cv2.adaptiveThreshold(suave, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 51, -4)
    candidatos = _candidatos([*_circulos(escuras), *_circulos(claras)])
    tinta = ((imagem < np.median(imagem) * _FRACAO_TINTA) * 255).astype(np.uint8)
    if len(candidatos) < minimo:
        raise FolhaIlegivelError('nenhuma grade de bolhas encontrada')
    diametro = float(np.median(candidatos[:, 2]))
    centro = (imagem.shape[1] / 2, imagem.shape[0] / 2)
    rotacao = cv2.getRotationMatrix2D(centro, _angulo(candidatos[:, :2], centro, diametro), 1.0)
    return tinta, rotacao, _transformar(rotacao, candidatos[:, :2]), diametro


def _circulos(binaria: np.ndarray) -> list[tuple[float, float, float]]:
    """Contornos aproximadamente circulares (x, y, diâmetro) do tamanho de uma bolha."""
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
    return achados


def _candidatos(achados: list[tuple[float, float, float]]) -> np.ndarray:
    """Círculos sem duplicatas (anel e miolo da mesma bolha) e com o diâmetro típico da folha."""
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
    return [float(g.mean()) for g in grupos if len(g) >= maior * _FRACAO_LINHA]


def _colunas(pontos: np.ndarray, linhas: list[float], diametro: float, esperadas: int) -> list[float]:
    """As `esperadas` colunas com mais bolhas nas linhas da grade; números dos itens geram colunas fracas."""
    na_grade = np.min(np.abs(pontos[:, 1, None] - np.array(linhas)[None, :]), axis=1) < diametro / 2
    grupos = _agrupar(pontos[na_grade, 0], diametro / 2)
    fortes = [g for g in grupos if len(g) >= len(linhas) * 0.3]
    escolhidas = sorted(fortes, key=len, reverse=True)[:esperadas]
    return sorted(float(g.mean()) for g in escolhidas)


def _preenchimento(binaria: np.ndarray, centro: tuple[int, int], raio: int) -> float:
    x, y = centro
    recorte = binaria[max(0, y - raio) : y + raio + 1, max(0, x - raio) : x + raio + 1]
    mascara = np.zeros_like(recorte)
    cv2.circle(mascara, (min(x, raio), min(y, raio)), raio, 255, -1)
    total = np.count_nonzero(mascara)
    return float(np.count_nonzero(recorte & mascara)) / total if total else 0.0


def _nota(preenchimento: float, perfil: PerfilOcr) -> float:
    """Preenchimento normalizado: 0 = bolha vazia típica, 1 = bolha cheia típica."""
    return min(1.0, max(0.0, (preenchimento - perfil.vazio) / (perfil.cheio - perfil.vazio)))


def _classificar(
    questao: int, alternativas: str, preenchimentos: tuple[float, ...], centros, raio: int, perfil: PerfilOcr
) -> Marcacao:
    """Estado pelas bolhas acima do limiar; confiança = margem entre a decisão e a alternativa mais próxima."""
    notas = [_nota(p, perfil) for p in preenchimentos]
    marcadas = [
        letra for letra, nota in zip(alternativas, notas, strict=True) if nota >= perfil.limiar_marcada
    ]
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


def desenhar_depuracao(
    imagem: np.ndarray, marcacoes: list[Marcacao], limiar: float, perfil: PerfilOcr = PADRAO
) -> np.ndarray:
    """Bolhas lidas sobrepostas: verde = marcada, azul = múltipla, cinza = vazia; anel vermelho = revisar."""
    colorida = cv2.cvtColor(imagem, cv2.COLOR_GRAY2BGR)
    for marcacao in marcacoes:
        for preenchimento, centro in zip(marcacao.preenchimentos, marcacao.centros, strict=True):
            if _nota(preenchimento, perfil) < perfil.limiar_marcada:
                cor = (160, 160, 160)
            elif marcacao.estado is Estado.MULTIPLA:
                cor = (255, 0, 0)
            else:
                cor = (0, 180, 0)
            cv2.circle(colorida, centro, marcacao.raio, cor, 2)
        if marcacao.confianca < limiar:
            cv2.circle(colorida, marcacao.centros[0], marcacao.raio * 3, (0, 0, 255), 2)
    return colorida
