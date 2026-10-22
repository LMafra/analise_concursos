import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import yaml

from concursos.folha import (
    Amostra,
    FolhaIlegivelError,
    carregar_paginas,
    desenhar_depuracao,
    marcacoes_da_amostra,
    medir_amostra,
)
from concursos.modelo import LETRAS
from concursos.perfis import PerfilInvalidoError, PerfilOcr, de_dict_ocr

logger = logging.getLogger(__name__)

ARQUIVO_CALIBRADO = 'folha_calibrada.yaml'
ARQUIVO_DEPURACAO = 'calibracao.png'
PERFIL_CALIBRADO = 'calibrado'
QUESTOES_CALIBRACAO = 5
BRANCO = '-'
_CONTRASTE_MINIMO = 0.05
_LIMIAR_MINIMO, _LIMIAR_MAXIMO = 0.05, 0.95


class CalibracaoError(ValueError):
    def __init__(self, causa: str, dica: str) -> None:
        super().__init__(causa)
        self.causa = causa
        self.dica = dica


@dataclass(frozen=True)
class Calibracao:
    perfil: PerfilOcr
    depuracao: np.ndarray


def calibrar(caminho: Path, digitadas: str, limiar_confianca: float = 0.75) -> Calibracao:
    """Ajusta vazio, cheio e limiar de marcação às `digitadas` (as 5 primeiras questões, letra ou `-`)."""
    digitadas = ''.join(c for c in digitadas.upper() if not c.isspace() and c != ',')
    if len(digitadas) != QUESTOES_CALIBRACAO or any(c != BRANCO and c not in LETRAS for c in digitadas):
        raise CalibracaoError(
            f'digite as respostas das {QUESTOES_CALIBRACAO} primeiras questões, recebido {digitadas!r}',
            f'use uma letra por questão e {BRANCO} para branco, por exemplo ABCD{BRANCO}',
        )
    imagem, amostra = _amostra(caminho)
    letras = _letras(amostra.n_alternativas, digitadas)
    if fora := sorted({c for c in digitadas if c != BRANCO and c not in letras}):
        raise CalibracaoError(
            f'você digitou {", ".join(fora)}, mas a folha tem {amostra.n_alternativas} alternativas '
            f'({letras[0]} a {letras[-1]})',
            'confira as respostas digitadas e se a folha é a do concurso',
        )
    perfil = _ajustar(amostra, letras, digitadas)
    marcacoes = marcacoes_da_amostra(amostra, perfil)
    lidas = ''.join(m.alternativa or BRANCO for m in marcacoes)
    if lidas != digitadas:
        raise CalibracaoError(
            f'as respostas digitadas não batem com a folha: digitadas {digitadas}, lidas {lidas}',
            _DICA_CONTRADICAO,
        )
    return Calibracao(perfil, desenhar_depuracao(imagem, marcacoes, limiar_confianca, perfil))


def gravar_calibracao(projeto: Path, calibracao: Calibracao) -> Path:
    projeto.mkdir(parents=True, exist_ok=True)
    caminho = projeto / ARQUIVO_CALIBRADO
    dados = {
        'id': calibracao.perfil.id,
        'alternativas': calibracao.perfil.alternativas,
        'vazio': calibracao.perfil.vazio,
        'cheio': calibracao.perfil.cheio,
        'limiar_marcada': calibracao.perfil.limiar_marcada,
    }
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=False), encoding='utf-8')
    cv2.imwrite(str(projeto / ARQUIVO_DEPURACAO), calibracao.depuracao)
    logger.info('perfil de OCR calibrado gravado em %s', caminho)
    return caminho


def carregar_calibrado(projeto: Path) -> PerfilOcr | None:
    caminho = projeto / ARQUIVO_CALIBRADO
    if not caminho.exists():
        return None
    try:
        return de_dict_ocr(yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}, str(caminho))
    except (yaml.YAMLError, PerfilInvalidoError) as erro:
        raise PerfilInvalidoError(
            f'{caminho}: {erro}; apague o arquivo e calibre de novo com `init`'
        ) from erro


_DICA_CONTRADICAO = (
    'confira as respostas das 5 primeiras questões e se a folha é a certa; sem calibração, a leitura usa a '
    'detecção automática'
)


def _amostra(caminho: Path) -> tuple[np.ndarray, Amostra]:
    erros = []
    for pagina, imagem in enumerate(carregar_paginas(caminho), start=1):
        try:
            return imagem, medir_amostra(imagem, QUESTOES_CALIBRACAO)
        except FolhaIlegivelError as erro:
            erros.append(f'página {pagina}: {erro}')
    raise CalibracaoError(
        f'{caminho.name}: grade de bolhas não encontrada ({"; ".join(erros)})',
        'use uma foto ou um PDF nítido da folha inteira, sem cortes',
    )


def _letras(n_alternativas: int, digitadas: str) -> str:
    if n_alternativas == 2 and set(digitadas) <= {'C', 'E', BRANCO}:
        return 'CE'
    return LETRAS[:n_alternativas]


def _ajustar(amostra: Amostra, letras: str, digitadas: str) -> PerfilOcr:
    marcadas, vazias = [], []
    for resposta, preenchimentos in zip(digitadas, amostra.preenchimentos, strict=True):
        for letra, preenchimento in zip(letras, preenchimentos, strict=True):
            (marcadas if letra == resposta else vazias).append(preenchimento)
    if not marcadas:
        raise CalibracaoError(
            f'as {QUESTOES_CALIBRACAO} respostas digitadas estão em branco',
            'calibre com uma folha em que alguma das 5 primeiras questões esteja marcada',
        )
    vazio, cheio = float(np.median(vazias)), float(np.median(marcadas))
    if min(marcadas) <= max(vazias) or cheio - vazio < _CONTRASTE_MINIMO:
        raise CalibracaoError(
            'as respostas digitadas não batem com a folha: alguma bolha digitada tem menos tinta que outra '
            'não digitada',
            _DICA_CONTRADICAO,
        )
    corte = (min(marcadas) + max(vazias)) / 2
    limiar = float(min(_LIMIAR_MAXIMO, max(_LIMIAR_MINIMO, (corte - vazio) / (cheio - vazio))))
    return PerfilOcr(
        PERFIL_CALIBRADO,
        letras,
        vazio=round(vazio, 3),
        cheio=round(cheio, 3),
        limiar_marcada=round(limiar, 3),
    )
