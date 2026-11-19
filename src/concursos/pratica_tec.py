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
from concursos.pratica.caderno_texto import textos_do_caderno, textos_para_normas
from concursos.pratica.configuracao import SECAO, ler_configuracao
from concursos.pratica.constantes import (
    ARQUIVO_RESPOSTAS,
    ARQUIVO_TENTATIVAS,
    PASTA_PRATICA,
    RESULTADO_ACERTO,
    RESULTADO_BRANCO,
    RESULTADO_ERRO,
)
from concursos.pratica.edital_pratica import carregar_edital, disciplina_da_materia
from concursos.pratica.entrada import ler_entrada as _ler_entrada
from concursos.pratica.entrada import mesclar_cadernos
from concursos.pratica.erros import CompletudeInvalidaError, ExportacaoInvalidaError
from concursos.pratica.escolhas_io import gravar_escolhas, ler_escolhas
from concursos.pratica.exportacao import ler_exportacao
from concursos.pratica.importacao import importar_pratica as _importar_pratica
from concursos.pratica.mesclagem import fundir, mesclar_erros as _mesclar_erros, verificar_completude
from concursos.pratica.nomes import (
    APP,
    APP_ESTADO,
    ARQUIVO_CADERNOS,
    ARQUIVO_DESEMPENHO,
    ARQUIVO_ERROS,
    ARQUIVO_ESCOLHAS,
    ARQUIVO_ESTADO,
    ARQUIVO_IMPORT_LOG,
    ARQUIVO_PCI_PROVAS,
    ARQUIVO_RESUMO,
    ARQUIVO_REVISAO,
    ARQUIVO_SIMULADO,
    COLUNAS_CADERNOS,
    COLUNAS_DESEMPENHO,
    COLUNAS_ERROS,
    COLUNAS_RESPOSTAS,
    COLUNAS_REVISAO,
    VERSAO,
)
from concursos.pratica.resolucao import NENHUM, OPCAO_DEPOIS, OPCAO_NENHUM, OPCOES_MODO
from concursos.pratica.respostas import (
    TIPO_CERTO_ERRADO,
    TIPO_MULTIPLA,
    impressao_digital,
    linha_de_resposta,
    normalizar,
    resultado_questao,
    so_erros,
    tipo_questao,
)
from concursos.pratica.resumo import resumo_markdown
from concursos.pratica.simulado import questoes_do_simulado, simulado_html
from concursos.pratica.tipos import ConfiguracaoPratica, Escolhas, Pendencia, Pratica, ResultadoPratica
from concursos.topicos import NAO_MAPEADO

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