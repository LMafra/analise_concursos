import logging
from pathlib import Path

import pandas as pd

from concursos.agregacao import agregar
from concursos.concurso_config import ARQUIVO_CONFIG, ConcursoConfig, carregar_concurso
from concursos.correcao import corrigir
from concursos.gabarito import ler_gabarito_texto
from concursos.modelo import ItemGabarito, RespostaMarcada
from concursos.relatorio import gerar_relatorio
from concursos.respostas import ler_respostas_txt

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


def analisar_todos(raiz_provas: Path, raiz_analises: Path) -> None:
    for pasta in listar_concursos(raiz_provas):
        analisar_concurso(pasta, raiz_analises / pasta.name)


def analisar_concurso(pasta: Path, destino: Path) -> None:
    config = carregar_concurso(pasta)
    logger.info('Analisando %s', config.nome)
    gabaritos = {prova.chave: _ler_gabarito(config, prova.gabarito.arquivo) for prova in config.provas}
    respostas = _ler_respostas(config)
    resultados = corrigir(config, gabaritos, respostas)

    destino.mkdir(parents=True, exist_ok=True)
    _tabela_respostas(config, respostas).to_csv(destino / 'respostas_extraidas.csv', index=False)
    por_disciplina = agregar(resultados, ['concurso', 'prova', 'disciplina'])
    por_topico = agregar(resultados, ['concurso', 'prova', 'disciplina', 'topico'])
    geral = agregar(resultados, ['concurso', 'prova'])
    por_disciplina.to_csv(destino / 'desempenho_por_disciplina.csv', index=False)
    por_topico.to_csv(destino / 'desempenho_por_topico.csv', index=False)
    (destino / 'relatorio.md').write_text(gerar_relatorio(config, por_disciplina, geral), encoding='utf-8')
    logger.info('Saídas de %s gravadas em %s', config.nome, destino)


def _ler_gabarito(config: ConcursoConfig, arquivo: str) -> list[ItemGabarito]:
    texto = config.caminho(arquivo).read_text(encoding='utf-8')
    return ler_gabarito_texto(texto, config.formato, arquivo)


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
