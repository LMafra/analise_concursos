"""Leitura de edital, gabarito, respostas, caderno e disciplinas por questão."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from concursos.caderno import faixas_do_caderno
from concursos.candidatos import ler_respostas_do_csv
from concursos.concurso_config import ConcursoConfig, ProvaConfig
from concursos.doctor import comando_de_correcao
from concursos.edital import (
    Edital,
    EditalNaoEstruturadoError,
    carregar_edital_manual,
    estruturar_edital,
)
from concursos.erros import avisar
from concursos.folha import FolhaIlegivelError, ler_folha
from concursos.gabarito import carregar_gabarito, validar_contagem
from concursos.linguagem import SITUACAO_DO_GABARITO
from concursos.modelo import ItemGabarito, RespostaMarcada
from concursos.perfis import PerfilOcr, perfil_da_banca
from concursos.pipeline.etapas.constantes import COLUNAS_RESPOSTAS
from concursos.prova import segmentar, texto_em_colunas
from concursos.respostas import ler_respostas_txt
from concursos.texto import MINIMO_CARACTERES_PAGINA, OcrIndisponivelError, extrair_paginas

logger = logging.getLogger(__name__)


def paginas_dos_documentos(config: ConcursoConfig) -> dict[str, list[str]]:
    """Texto (sem OCR) de cada documento do edital, lido uma vez para o conteúdo programático e a correção."""
    if config.edital is None:
        return {}
    return {
        arquivo: extrair_paginas(config.caminho(arquivo), ocr=False) for arquivo in config.edital.documentos
    }


def ler_edital(config: ConcursoConfig, documentos: dict[str, list[str]]) -> Edital | None:
    if config.edital is None:
        return None
    cargo = config.simulado.cargo_alvo if config.simulado and config.simulado.cargo_alvo else config.cargo
    if config.edital.manual:
        return carregar_edital_manual(config.caminho(config.edital.manual), cargo)
    erros, sem_ocr = [], []
    for arquivo, paginas in documentos.items():
        try:
            return estruturar_documento(config.caminho(arquivo), paginas, cargo)
        except EditalNaoEstruturadoError as erro:
            erros.append(str(erro))
        except OcrIndisponivelError:
            sem_ocr.append(arquivo)
    if sem_ocr:
        avisar(
            logger,
            f'{config.nome}: não consegui ler o edital escaneado porque falta o componente de leitura de PDF '
            'escaneado. Segui sem o conteúdo do edital; os tópicos das questões ficam sem classificação.',
            'o instalador já traz esse componente; na versão de terminal, instale-o com '
            f'{comando_de_correcao("tesseract")} ou rode concurso-analise doctor.',
            f'{", ".join(sem_ocr)} sem texto e o Tesseract não está instalado; modo mínimo, tópicos nao_mapeado',
        )
    else:
        avisar(
            logger,
            f'{config.nome}: não encontrei o conteúdo programático no edital. Segui sem ele; os tópicos das '
            'questões ficam sem classificação.',
            'confira se o arquivo é mesmo o edital; se for, você pode digitar o conteúdo num edital manual '
            '(formato em docs/modelo.md).',
            f'{"; ".join(erros)}; tópicos nao_mapeado',
        )
    return None


def estruturar_documento(caminho: Path, paginas: list[str], cargo: str | None) -> Edital:
    try:
        return estruturar_edital(paginas, cargo, caminho.name)
    except EditalNaoEstruturadoError:
        if all(len(p.strip()) >= MINIMO_CARACTERES_PAGINA for p in paginas):
            raise
    logger.info('%s: conteúdo programático não encontrado no texto; tentando com OCR', caminho.name)
    return estruturar_edital(extrair_paginas(caminho), cargo, caminho.name)


def disciplinas_por_questao(config: ConcursoConfig) -> dict[int, str]:
    """Faixas manuais do concurso.yaml; sem elas, cabeçalhos do caderno, nas bancas que os têm."""
    disciplinas = {}
    for prova in config.provas:
        faixas = prova.disciplinas
        if (
            not faixas
            and prova.caderno_pdf
            and perfil_da_banca(config.banca).disciplinas_pelo_caderno
            and caderno_presente(config, prova)
        ):
            faixas = tuple(faixas_do_caderno(config.caminho(prova.caderno), prova.inicio))
            cobertas = sum(f.fim - f.inicio + 1 for f in faixas)
            logger.info(
                '%s: disciplinas de %d de %d questões pelo caderno',
                prova.caderno,
                cobertas,
                len(prova.questoes),
            )
        for faixa in faixas:
            disciplinas.update(
                {q: faixa.disciplina for q in range(faixa.inicio, faixa.fim + 1) if q in prova.questoes}
            )
    return disciplinas


def textos_das_questoes(config: ConcursoConfig) -> dict[int, str]:
    textos = {}
    for prova in config.provas:
        if not prova.caderno or not caderno_presente(config, prova):
            continue
        texto = texto_em_colunas(config.caminho(prova.caderno))
        da_prova = segmentar(
            texto, prova.questoes, por_itens=perfil_da_banca(config.banca).segmentacao == 'itens'
        )
        logger.info('%s: texto de %d de %d questões', prova.caderno, len(da_prova), len(prova.questoes))
        textos.update(da_prova)
    return textos


def caderno_presente(config: ConcursoConfig, prova: ProvaConfig) -> bool:
    if config.caminho(prova.caderno).exists():
        return True
    avisar(
        logger,
        f'{prova.caderno}: não encontrei o caderno de questões; a prova {prova.chave} segue sem o texto delas.',
        'coloque o PDF do caderno na pasta do concurso, com esse nome.',
        'caderno ausente',
    )
    return False


def ler_gabarito(config: ConcursoConfig, prova: ProvaConfig) -> list[ItemGabarito]:
    arquivo = prova.gabarito.arquivo
    gabarito = carregar_gabarito(config.caminho(arquivo), config)
    if gabarito.status_detectado and gabarito.status_detectado != prova.gabarito.status:
        avisar(
            logger,
            f'{arquivo}: o cadastro diz que o gabarito é {SITUACAO_DO_GABARITO[prova.gabarito.status]}, '
            f'mas o arquivo parece ser {SITUACAO_DO_GABARITO[gabarito.status_detectado]}.',
            'confira a situação do gabarito em Concursos.',
            f'gabarito configurado como {prova.gabarito.status}, mas o arquivo indica {gabarito.status_detectado}',
        )
    validar_contagem(gabarito.itens, prova.questoes, prova.chave, arquivo)
    return gabarito.itens


def ler_respostas(
    config: ConcursoConfig, destino: Path, limiar: float, calibrado: PerfilOcr | None = None
) -> list[RespostaMarcada]:
    questoes = [q for prova in config.provas for q in prova.questoes]
    if config.respostas_arquivo is not None:
        caminho = config.caminho(config.respostas_arquivo)
        if caminho.suffix.lower() == '.csv':
            return ler_respostas_do_csv(config, caminho)
        texto = caminho.read_text(encoding='utf-8')
        return ler_respostas_txt(
            texto, config.formato, questoes, config.respostas_arquivo, config.n_alternativas
        )
    folha = config.folha
    lidas = ler_folha(
        config.caminho(folha.arquivo),
        folha.template,
        folha.total_itens or max(questoes),
        folha.itens_por_coluna,
        destino / 'depuracao',
        limiar,
        ''.join(sorted(config.formato.letras(config.n_alternativas))),
        calibrado,
    )
    por_questao = {r.questao: r for r in lidas}
    if faltando := [q for q in questoes if q not in por_questao]:
        raise FolhaIlegivelError(
            f'{folha.arquivo}: a folha tem {len(lidas)} itens, faltam as questões {faltando[0]}-{faltando[-1]}'
        )
    return [por_questao[q] for q in questoes]


def tabela_respostas(config: ConcursoConfig, respostas: list[RespostaMarcada], limiar: float) -> pd.DataFrame:
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
                'revisar': resposta.confianca < limiar,
                'origem': resposta.origem.value,
                'arquivo': resposta.arquivo,
                'pagina': resposta.pagina if resposta.pagina is not None else '',
            }
        )
    return pd.DataFrame(linhas, columns=COLUNAS_RESPOSTAS)
