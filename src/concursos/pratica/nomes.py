"""Nomes de arquivo e colunas CSV da prática TEC."""

from concursos.pratica.constantes import ARQUIVO_RESPOSTAS, ARQUIVO_TENTATIVAS, PASTA_PRATICA

APP = 'tec-erros'
APP_ESTADO = 'tec-erros-caderno'
VERSAO = 1
ARQUIVO_ESTADO = 'caderno-estado.json'
ARQUIVO_ESCOLHAS = 'pratica_tec.yaml'
ARQUIVO_ERROS = 'erros_tec.csv'
ARQUIVO_CADERNOS = 'cadernos_tec.csv'
ARQUIVO_DESEMPENHO = 'desempenho_pratica_por_disciplina.csv'
ARQUIVO_REVISAO = 'revisao_aliases.csv'
ARQUIVO_RESUMO = 'resumo_pratica.md'
ARQUIVO_SIMULADO = 'simulado_tec.html'
ARQUIVO_PCI_PROVAS = 'tec_pci_provas.csv'
ARQUIVO_IMPORT_LOG = 'tec_import_log.json'

__all__ = [
    'APP',
    'APP_ESTADO',
    'ARQUIVO_CADERNOS',
    'ARQUIVO_DESEMPENHO',
    'ARQUIVO_ERROS',
    'ARQUIVO_ESCOLHAS',
    'ARQUIVO_ESTADO',
    'ARQUIVO_IMPORT_LOG',
    'ARQUIVO_PCI_PROVAS',
    'ARQUIVO_RESPOSTAS',
    'ARQUIVO_RESUMO',
    'ARQUIVO_REVISAO',
    'ARQUIVO_SIMULADO',
    'ARQUIVO_TENTATIVAS',
    'COLUNAS_CADERNOS',
    'COLUNAS_DESEMPENHO',
    'COLUNAS_ERROS',
    'COLUNAS_RESPOSTAS',
    'COLUNAS_REVISAO',
    'PASTA_PRATICA',
    'VERSAO',
]

COLUNAS_ERROS = [
    'id', 'v', 'primeira_data', 'ultima_data', 'origem', 'materia_tec', 'disciplina', 'assunto', 'topico',
    'banca', 'orgao', 'ano', 'caderno',
]  # fmt: skip
COLUNAS_CADERNOS = [
    'id', 'caderno', 'materia_tec', 'disciplina', 'modo', 'total', 'resolvidas', 'acertos', 'erros',
    'percentual', 'amostra_insuficiente',
]  # fmt: skip
COLUNAS_DESEMPENHO = [
    'disciplina', 'n', 'acertos', 'erros', 'percentual', 'amostra_insuficiente', 'cadernos',
    'erros_registrados', 'repetidos',
]  # fmt: skip
COLUNAS_REVISAO = ['assunto', 'disciplina', 'sugestao', 'score', 'topico']
COLUNAS_RESPOSTAS = [
    'id', 'tipo_questao', 'mat', 'ass', 'banca', 'ano', 'gab', 'marc', 'resultado', 'tem_comentario',
]  # fmt: skip
