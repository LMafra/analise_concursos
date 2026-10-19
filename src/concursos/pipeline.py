import logging
from pathlib import Path

import pandas as pd

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


def analisar_todos(raiz_provas: Path, raiz_analises: Path) -> bool:
    """Analisa todos os concursos completos; retorna False se algum falhou durante a análise."""
    sucesso = True
    for pasta in listar_concursos(raiz_provas):
        situacao = avaliar(pasta)
        if situacao.situacao is not Situacao.COMPLETO:
            logger.warning(
                '%s: %s, pulando: %s', situacao.nome, situacao.situacao, '; '.join(situacao.motivos)
            )
            continue
        try:
            analisar_concurso(situacao.config, raiz_analises / pasta.name)
        except (ValueError, FileNotFoundError, RuntimeError) as erro:
            logger.error('%s: falha na análise: %s', situacao.nome, erro)
            sucesso = False
    return sucesso


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
