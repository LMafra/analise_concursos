import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pdfplumber

from concursos.concurso_config import ConcursoConfig, ResultadoOficialConfig
from concursos.modelo import Pontuacao, Resultado
from concursos.texto import NUMERO_DECIMAL, normalizar, numero_decimal

_TOLERANCIA = 0.005
ARQUIVO_VALIDACAO = 'validacao_oficial.json'
_NUMERO = re.compile(rf'^{NUMERO_DECIMAL}$')
_DATA = re.compile(r'^\d{2}/\d{2}/\d{4}$')
_LINHA_CPNU = re.compile(r'^\d+\s+\([^)]*\)')


class ResultadoOficialError(ValueError):
    pass


@dataclass(frozen=True)
class ResultadoOficial:
    """Desempenho do candidato no resultado oficial: acertos (CPNU) ou pontos (listas por inscrição)."""

    medida: str
    total: float
    componentes: tuple[float, ...]
    somente_objetiva: bool
    pagina: int


@dataclass(frozen=True)
class ValidacaoIlegivel:
    arquivo: str
    erro: str

    @property
    def alerta(self) -> bool:
        return True

    @property
    def descricao(self) -> str:
        return f'Não foi possível ler o resultado oficial: {self.erro}'


@dataclass(frozen=True)
class ValidacaoConferida:
    arquivo: str
    oficial: ResultadoOficial
    calculado: float

    @property
    def divergente(self) -> bool:
        return self.oficial.somente_objetiva and abs(self.oficial.total - self.calculado) > _TOLERANCIA

    @property
    def alerta(self) -> bool:
        return self.divergente

    @property
    def descricao(self) -> str:
        oficial = f'{formatar(self.oficial.total)} {self.oficial.medida}'
        calculado = formatar(self.calculado)
        if not self.oficial.somente_objetiva:
            return (
                f'O resultado oficial ({oficial}) inclui outras fases além da prova objetiva; '
                f'calculado na objetiva: {calculado}. Comparação apenas informativa.'
            )
        if self.divergente:
            return (
                f'O desempenho calculado diverge do resultado oficial: oficial {oficial}, calculado {calculado}. '
                'Confira o tipo da prova, o gabarito e a leitura das respostas.'
            )
        return f'O desempenho calculado confere com o resultado oficial ({oficial}).'


Validacao = ValidacaoConferida | ValidacaoIlegivel


def gravar_validacao(validacao: Validacao | None, destino: Path) -> None:
    """Resumo da validação para o consolidado; sem resultado oficial, remove o resumo antigo."""
    caminho = destino / ARQUIVO_VALIDACAO
    if validacao is None:
        caminho.unlink(missing_ok=True)
        return
    resumo = {'arquivo': validacao.arquivo, 'descricao': validacao.descricao, 'alerta': validacao.alerta}
    caminho.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding='utf-8')


def ler_validacao(destino: Path) -> dict | None:
    caminho = destino / ARQUIVO_VALIDACAO
    return json.loads(caminho.read_text(encoding='utf-8')) if caminho.exists() else None


def validar_resultado(config: ConcursoConfig, resultados: pd.DataFrame) -> Validacao | None:
    """Compara os resultados corrigidos com o resultado oficial configurado; erro de leitura vira ValidacaoIlegivel."""
    configuracao = config.resultado_oficial
    if configuracao is None:
        return None
    arquivo = configuracao.arquivo
    try:
        oficial = ler_resultado_oficial(config.caminho(arquivo), configuracao.identificador)
    except (ResultadoOficialError, OSError) as erro:
        return ValidacaoIlegivel(arquivo, str(erro))
    return ValidacaoConferida(
        arquivo, oficial, _calcular(oficial.medida, resultados, configuracao, config.pontuacao)
    )


def _calcular(
    medida: str, resultados: pd.DataFrame, configuracao: ResultadoOficialConfig, pontuacao: Pontuacao
) -> float:
    total = 0.0
    for questao, resultado in zip(resultados['questao'], resultados['resultado'], strict=True):
        peso = 1.0 if medida == 'acertos' else configuracao.peso_de(questao)
        if resultado == Resultado.ACERTO:
            total += peso
        elif resultado == Resultado.ERRO and medida == 'pontos' and pontuacao.fator_penalidade:
            total -= peso
    return total


def formatar(valor: float) -> str:
    return f'{valor:g}'.replace('.', ',')


def ler_resultado_oficial(caminho: Path, identificador: str | None) -> ResultadoOficial:
    return interpretar_resultado(_paginas(caminho), identificador, caminho.name)


def interpretar_resultado(
    paginas: Iterable[str], identificador: str | None, arquivo: str
) -> ResultadoOficial:
    """Localiza o candidato no texto: resultado individual da CPNU ou lista com uma linha por inscrição."""
    somente_objetiva = True
    for numero, texto in enumerate(paginas, start=1):
        if numero == 1:
            somente_objetiva = 'RESULTADO FINAL DO CONCURSO' not in normalizar(texto[:600])
        if 'EIXO 1' in normalizar(texto):
            return _cpnu(texto, arquivo, numero)
        if identificador is None:
            raise ResultadoOficialError(
                f'{arquivo}: lista de resultados exige resultado_oficial.identificador (sua inscrição) no concurso.yaml'
            )
        for linha in texto.splitlines():
            tokens = linha.split()
            if tokens and tokens[0] == identificador:
                return _linha_da_lista(tokens, identificador, arquivo, numero, somente_objetiva)
    raise ResultadoOficialError(f'{arquivo}: inscrição {identificador} não encontrada')


def _cpnu(texto: str, arquivo: str, pagina: int) -> ResultadoOficial:
    """Primeira opção de cargo: acertos de conhecimentos gerais e dos eixos 1 a 5 (iguais em todas as opções)."""
    for linha in texto.splitlines():
        if _LINHA_CPNU.match(linha.strip()):
            numeros = [_numero(t) for t in linha.split() if _NUMERO.match(t)]
            if len(numeros) >= 9:
                acertos = tuple(numeros[-9:-3])
                return ResultadoOficial('acertos', sum(acertos), acertos, True, pagina)
    raise ResultadoOficialError(f'{arquivo}: página {pagina}: linha de acertos por eixo não encontrada')


def _linha_da_lista(
    tokens: list[str], identificador: str, arquivo: str, pagina: int, somente_objetiva: bool
) -> ResultadoOficial:
    numeros = [_numero(t) for t in tokens[1:] if _NUMERO.match(t) and not _DATA.match(t)]
    if not numeros:
        raise ResultadoOficialError(f'{arquivo}: página {pagina}: inscrição {identificador} sem nota')
    return ResultadoOficial('pontos', numeros[-1], tuple(numeros[:-1]), somente_objetiva, pagina)


def _numero(token: str) -> float:
    valor = numero_decimal(token)
    return int(valor) if valor.is_integer() else valor


def _paginas(caminho: Path) -> Iterator[str]:
    """Texto página a página, sob demanda: listas longas param na página do candidato."""
    if caminho.suffix.lower() != '.pdf':
        yield caminho.read_text(encoding='utf-8')
        return
    with pdfplumber.open(caminho) as pdf:
        for pagina in pdf.pages:
            yield pagina.extract_text() or ''
