"""Prática no TEC: lê as exportações do tec-erros, liga matéria e assunto à disciplina canônica e ao tópico do
edital do `concurso_alvo` e grava o desempenho em `analises/<candidato>/pratica/`.

As regras de mesclagem repetem as de `core/nucleo.js` do tec-erros (`docs/contrato.md` de lá)."""

import csv
import io
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from concursos.analytics.taxonomia import DisciplinaCanonica
from concursos.assistente import Interacao
from concursos.pratica.caderno_texto import textos_do_caderno as textos_do_caderno
from concursos.pratica.caderno_texto import textos_para_normas as textos_para_normas
from concursos.pratica.configuracao import SECAO as SECAO
from concursos.pratica.configuracao import ler_configuracao as ler_configuracao
from concursos.pratica.constantes import ARQUIVO_RESPOSTAS as ARQUIVO_RESPOSTAS
from concursos.pratica.constantes import ARQUIVO_TENTATIVAS as ARQUIVO_TENTATIVAS
from concursos.pratica.constantes import PASTA_PRATICA as PASTA_PRATICA
from concursos.pratica.constantes import RESULTADO_ACERTO as RESULTADO_ACERTO
from concursos.pratica.constantes import RESULTADO_BRANCO as RESULTADO_BRANCO
from concursos.pratica.constantes import RESULTADO_ERRO as RESULTADO_ERRO
from concursos.pratica.edital_pratica import carregar_edital
from concursos.pratica.edital_pratica import disciplina_da_materia as disciplina_da_materia
from concursos.pratica.entrada import ler_entrada as _ler_entrada
from concursos.pratica.entrada import mesclar_cadernos as mesclar_cadernos
from concursos.pratica.erros import CompletudeInvalidaError as CompletudeInvalidaError
from concursos.pratica.erros import ExportacaoInvalidaError as ExportacaoInvalidaError
from concursos.pratica.escolhas_io import gravar_escolhas
from concursos.pratica.escolhas_io import ler_escolhas as ler_escolhas
from concursos.pratica.exportacao import ler_exportacao as ler_exportacao
from concursos.pratica.importacao import importar_pratica as _importar_pratica
from concursos.pratica.mesclagem import fundir as fundir
from concursos.pratica.mesclagem import mesclar_erros as _mesclar_erros
from concursos.pratica.mesclagem import verificar_completude as verificar_completude
from concursos.pratica.nomes import APP as APP
from concursos.pratica.nomes import APP_ESTADO as APP_ESTADO
from concursos.pratica.nomes import ARQUIVO_CADERNOS as ARQUIVO_CADERNOS
from concursos.pratica.nomes import ARQUIVO_DESEMPENHO as ARQUIVO_DESEMPENHO
from concursos.pratica.nomes import ARQUIVO_ERROS as ARQUIVO_ERROS
from concursos.pratica.nomes import ARQUIVO_ESCOLHAS as ARQUIVO_ESCOLHAS
from concursos.pratica.nomes import ARQUIVO_ESTADO as ARQUIVO_ESTADO
from concursos.pratica.nomes import ARQUIVO_IMPORT_LOG as ARQUIVO_IMPORT_LOG
from concursos.pratica.nomes import ARQUIVO_PCI_PROVAS as ARQUIVO_PCI_PROVAS
from concursos.pratica.nomes import ARQUIVO_RESUMO as ARQUIVO_RESUMO
from concursos.pratica.nomes import ARQUIVO_REVISAO as ARQUIVO_REVISAO
from concursos.pratica.nomes import ARQUIVO_SIMULADO as ARQUIVO_SIMULADO
from concursos.pratica.nomes import COLUNAS_CADERNOS as COLUNAS_CADERNOS
from concursos.pratica.nomes import COLUNAS_DESEMPENHO as COLUNAS_DESEMPENHO
from concursos.pratica.nomes import COLUNAS_ERROS as COLUNAS_ERROS
from concursos.pratica.nomes import COLUNAS_RESPOSTAS as COLUNAS_RESPOSTAS
from concursos.pratica.nomes import COLUNAS_REVISAO as COLUNAS_REVISAO
from concursos.pratica.nomes import VERSAO as VERSAO
from concursos.pratica.resolucao import NENHUM as NENHUM
from concursos.pratica.resolucao import OPCAO_DEPOIS as OPCAO_DEPOIS
from concursos.pratica.resolucao import OPCAO_NENHUM as OPCAO_NENHUM
from concursos.pratica.resolucao import OPCOES_MODO as OPCOES_MODO
from concursos.pratica.respostas import TIPO_CERTO_ERRADO as TIPO_CERTO_ERRADO
from concursos.pratica.respostas import TIPO_MULTIPLA as TIPO_MULTIPLA
from concursos.pratica.respostas import impressao_digital as impressao_digital
from concursos.pratica.respostas import linha_de_resposta as linha_de_resposta
from concursos.pratica.respostas import normalizar as normalizar
from concursos.pratica.respostas import resultado_questao as resultado_questao
from concursos.pratica.respostas import so_erros as so_erros
from concursos.pratica.respostas import tipo_questao as tipo_questao
from concursos.pratica.resumo import resumo_markdown as resumo_markdown
from concursos.pratica.simulado import questoes_do_simulado as questoes_do_simulado
from concursos.pratica.simulado import simulado_html as simulado_html
from concursos.pratica.tipos import ConfiguracaoPratica as ConfiguracaoPratica
from concursos.pratica.tipos import Escolhas as Escolhas
from concursos.pratica.tipos import Pendencia as Pendencia
from concursos.pratica.tipos import Pratica as Pratica
from concursos.pratica.tipos import ResultadoPratica as ResultadoPratica
from concursos.topicos import NAO_MAPEADO as NAO_MAPEADO

if TYPE_CHECKING:
    from concursos.analytics.dicionario_topicos import Dicionario

MAXIMO_SIMULADO = 40
MAXIMO_SIMULADO_POR_TOPICO = 10
SEM_DISCIPLINA = 'Sem disciplina'
MAXIMO_REPETIDOS = 20
TAMANHO_DIGITAL = 300
FORA_DO_EDITAL = 'fora_do_edital'
MAXIMO_OPCOES = 30

COLUNAS_TENTATIVAS = ['id', 'data', 'resposta', 'resultado']
COLUNAS_PCI_PROVAS = ['ass', 'prova_url', 'orgao', 'banca', 'ano', 'tema_no_edital', 'fonte_tema']


def mesclar_erros(base: list[dict], novos: list[dict]) -> list[dict]:
    return _mesclar_erros(base, novos, impressao_digital=impressao_digital)


def ler_entrada(pasta: Path) -> tuple[Pratica, list[str]]:
    return _ler_entrada(pasta, impressao_digital=impressao_digital)


def _csv(colunas: list[str], linhas: list[dict]) -> str:
    saida = io.StringIO()
    escritor = csv.DictWriter(saida, fieldnames=colunas, lineterminator='\n')
    escritor.writeheader()
    for linha in linhas:
        escritor.writerow({c: '' if linha.get(c) is None else linha[c] for c in colunas})
    return saida.getvalue()


def ler_pratica(
    entrada: Path, arquivo_escolhas: Path, taxonomia: dict[str, DisciplinaCanonica]
) -> ResultadoPratica:
    """A prática mesclada e a disciplina de cada matéria, sem gravar nem perguntar nada."""
    pratica, avisos = ler_entrada(entrada)
    escolhas = ler_escolhas(arquivo_escolhas)
    materias = {**(pratica.estado.get('materias') or {}), **escolhas.materias}
    nomes = {e.get('mat') for e in pratica.erros} | {c.get('mat') for c in pratica.cadernos}
    disciplinas = {m: disciplina_da_materia(m, taxonomia, materias) for m in nomes if m}
    return ResultadoPratica(False, avisos, pratica, escolhas, disciplinas)


def importar_pratica(
    entrada: Path,
    pasta_candidato: Path,
    arquivo_escolhas: Path,
    taxonomia: dict[str, DisciplinaCanonica],
    concurso_alvo: str | None,
    interacao: Interacao | None = None,
    fracos: pd.DataFrame | None = None,
    dicionario: 'Dicionario | None' = None,
) -> ResultadoPratica:
    """Lê a pasta de exportações e grava as tabelas de `pratica/`; sem terminal (`interacao` None), o assunto
    sem tópico vai para `revisao_aliases.csv`, e o caderno novo conta desde o início."""
    lido = ler_pratica(entrada, arquivo_escolhas, taxonomia)
    return _importar_pratica(
        lido,
        pasta_candidato,
        arquivo_escolhas,
        concurso_alvo,
        interacao,
        fracos,
        dicionario,
        carregar_edital=carregar_edital,
        gravar_escolhas=gravar_escolhas,
        csv=_csv,
        linha_de_resposta=linha_de_resposta,
        so_erros=so_erros,
        resumo_markdown=resumo_markdown,
        simulado_html=simulado_html,
    )
