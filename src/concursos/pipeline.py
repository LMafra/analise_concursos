import logging
from pathlib import Path

import pandas as pd

from concursos import manifesto
from concursos.agregacao import agregar
from concursos.concurso_config import ARQUIVO_CONFIG, ConcursoConfig, ProvaConfig
from concursos.correcao import corrigir
from concursos.gabarito import carregar_gabarito, validar_contagem
from concursos.modelo import ItemGabarito, RespostaMarcada
from concursos.relatorio import gerar_relatorio
from concursos.respostas import ler_respostas_txt
from concursos.status import Situacao, avaliar

logger = logging.getLogger(__name__)

COLUNAS_RESPOSTAS = [
    'concurso',
    'prova',
    'questao',
    'alternativa_marcada',
    'estado',
    'confianca_ocr',
    'revisar',
    'origem',
    'arquivo',
    'pagina',
]


def listar_concursos(raiz_provas: Path) -> list[Path]:
    return sorted(p for p in raiz_provas.iterdir() if (p / ARQUIVO_CONFIG).exists())


class ConcursoNaoEncontradoError(ValueError):
    pass


def analisar_todos(
    raiz_provas: Path, raiz_analises: Path, forcar: bool = False, apenas: str | None = None
) -> bool:
    """Analisa os concursos completos que mudaram; retorna False se algum falhou durante a análise."""
    pastas = listar_concursos(raiz_provas)
    if apenas is not None:
        pastas = [p for p in pastas if p.name == apenas]
        if not pastas:
            raise ConcursoNaoEncontradoError(f'{raiz_provas / apenas}: concurso não encontrado')
    sucesso = True
    for pasta in pastas:
        sucesso &= _analisar_se_necessario(pasta, raiz_analises / pasta.name, forcar)
    return sucesso


def _analisar_se_necessario(pasta: Path, destino: Path, forcar: bool) -> bool:
    situacao = avaliar(pasta)
    if situacao.situacao is not Situacao.COMPLETO:
        logger.warning('%s: %s, pulando: %s', situacao.nome, situacao.situacao, '; '.join(situacao.motivos))
        return True
    if not forcar and manifesto.atualizado(pasta, destino):
        logger.info('%s: sem mudanças desde a última análise', situacao.nome)
        return True
    manifesto.invalidar(destino)
    try:
        analisar_concurso(situacao.config, destino)
    except (ValueError, FileNotFoundError, RuntimeError) as erro:
        logger.error('%s: falha na análise: %s', situacao.nome, erro)
        return False
    manifesto.gravar(pasta, destino)
    return True


def analisar_concurso(config: ConcursoConfig, destino: Path) -> None:
    logger.info('Analisando %s', config.nome)
    gabaritos = {prova.chave: _ler_gabarito(config, prova) for prova in config.provas}
    respostas = _ler_respostas(config)
    resultados = corrigir(config, gabaritos, respostas)

    destino.mkdir(parents=True, exist_ok=True)
    _tabela_respostas(config, respostas).to_csv(destino / 'respostas_extraidas.csv', index=False)
    por_disciplina = agregar(resultados, ['concurso', 'prova', 'disciplina'], config.pontuacao)
    por_topico = agregar(resultados, ['concurso', 'prova', 'disciplina', 'topico'], config.pontuacao)
    geral = agregar(resultados, ['concurso', 'prova'], config.pontuacao)
    por_disciplina.to_csv(destino / 'desempenho_por_disciplina.csv', index=False)
    por_topico.to_csv(destino / 'desempenho_por_topico.csv', index=False)
    (destino / 'relatorio.md').write_text(gerar_relatorio(config, por_disciplina, geral), encoding='utf-8')
    logger.info('Saídas de %s gravadas em %s', config.nome, destino)


def _ler_gabarito(config: ConcursoConfig, prova: ProvaConfig) -> list[ItemGabarito]:
    arquivo = prova.gabarito.arquivo
    gabarito = carregar_gabarito(
        config.caminho(arquivo), config.formato, config.banca, config.cargo, config.tipo
    )
    if gabarito.status_detectado and gabarito.status_detectado != prova.gabarito.status:
        logger.warning(
            '%s: gabarito configurado como %s, mas o arquivo indica %s',
            arquivo,
            prova.gabarito.status,
            gabarito.status_detectado,
        )
    validar_contagem(gabarito.itens, prova.questoes, prova.chave, arquivo)
    return gabarito.itens


def _ler_respostas(config: ConcursoConfig) -> list[RespostaMarcada]:
    questoes = [q for prova in config.provas for q in prova.questoes]
    texto = config.caminho(config.respostas_arquivo).read_text(encoding='utf-8')
    return ler_respostas_txt(texto, config.formato, questoes, config.respostas_arquivo)


def _tabela_respostas(config: ConcursoConfig, respostas: list[RespostaMarcada]) -> pd.DataFrame:
    linhas = []
    for resposta in respostas:
        linhas.append(
            {
                'concurso': config.nome,
                'prova': config.prova_da_questao(resposta.questao).chave,
                'questao': resposta.questao,
                'alternativa_marcada': resposta.alternativa or '',
                'estado': resposta.estado.value,
                'confianca_ocr': resposta.confianca,
                'revisar': False,
                'origem': resposta.origem.value,
                'arquivo': resposta.arquivo,
                'pagina': resposta.pagina if resposta.pagina is not None else '',
            }
        )
    return pd.DataFrame(linhas, columns=COLUNAS_RESPOSTAS)
