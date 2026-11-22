import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from concursos.analytics.tec_estatisticas import markdown_resumo
from concursos.arquivos import gravar_se_mudou
from concursos.assistente import Interacao
from concursos.pratica.constantes import (
    PASTA_PRATICA,
    RESULTADO_ACERTO,
    RESULTADO_BRANCO,
)
from concursos.pratica.nomes import (
    ARQUIVO_CADERNOS,
    ARQUIVO_DESEMPENHO,
    ARQUIVO_ERROS,
    ARQUIVO_IMPORT_LOG,
    ARQUIVO_RESPOSTAS,
    ARQUIVO_RESUMO,
    ARQUIVO_REVISAO,
    ARQUIVO_SIMULADO,
    COLUNAS_CADERNOS,
    COLUNAS_DESEMPENHO,
    COLUNAS_ERROS,
    COLUNAS_RESPOSTAS,
    COLUNAS_REVISAO,
)
from concursos.pratica.resolucao import ler_revisao, resolver_assuntos, resolver_cadernos
from concursos.pratica.tabelas import linhas_de_cadernos, linhas_de_desempenho, linhas_de_erros
from concursos.pratica.tipos import Escolhas, Pendencia, Pratica, ResultadoPratica

if TYPE_CHECKING:
    from concursos.analytics.dicionario_topicos import Dicionario
    from concursos.edital import Edital

logger = logging.getLogger(__name__)


def aviso_materias_sem_disciplina(disciplinas: dict[str, str | None]) -> str | None:
    if desconhecidas := sorted(m for m, d in disciplinas.items() if d is None):
        return (
            f'prática: matéria do TEC sem disciplina ({", ".join(desconhecidas)}); acrescente-a em `nomes:` '
            'da disciplina no .gabarito-vivo/taxonomia.yaml'
        )
    return None


def aviso_sem_edital(concurso_alvo: str | None, tem_assuntos: bool) -> str | None:
    if not tem_assuntos:
        return None
    motivo = (
        'sem concurso_alvo em [analise]' if not concurso_alvo else f'{concurso_alvo} sem edital estruturado'
    )
    return f'prática: {motivo}; os assuntos do TEC ficam sem tópico do edital'


def aviso_pendentes(pendentes: list[Pendencia], revisao: Path) -> str | None:
    if not pendentes:
        return None
    return (
        f'prática: {len(pendentes)} assunto(s) do TEC sem tópico; preencha a coluna topico de '
        f'{revisao} (ou "nenhum") e rode de novo'
    )


def resolver_topicos(
    pratica: Pratica,
    disciplinas: dict[str, str | None],
    concurso_alvo: str | None,
    pasta_candidato: Path,
    escolhas: Escolhas,
    revisao: Path,
    interacao: Interacao | None,
    dicionario: 'Dicionario | None',
    *,
    carregar_edital,
) -> tuple[list[Pendencia] | None, list[str]]:
    assuntos = {e['ass']: disciplinas.get(e.get('mat') or '') for e in pratica.erros if e.get('ass')}
    avisos: list[str] = []
    edital: Edital | None = carregar_edital(pasta_candidato / concurso_alvo) if concurso_alvo else None
    pendentes: list[Pendencia] | None = None
    if edital is None:
        if aviso := aviso_sem_edital(concurso_alvo, bool(assuntos)):
            avisos.append(aviso)
    else:
        sugeridos = {a: t for a, t in (pratica.estado.get('aliases') or {}).items() if a in assuntos}
        pendentes = resolver_assuntos(
            assuntos, edital, escolhas, sugeridos, ler_revisao(revisao), interacao, dicionario
        )
        if aviso := aviso_pendentes(pendentes, revisao):
            avisos.append(aviso)
    return pendentes, avisos


def gravar_tabelas(
    pasta: Path,
    *,
    escolhas: Escolhas,
    arquivo_escolhas: Path,
    respostas: list[dict],
    erros: list[dict],
    cadernos: list[dict],
    desempenho: list[dict],
    so_erros_itens: list[dict],
    aliases: dict[str, str | None],
    fracos: pd.DataFrame | None,
    pendentes: list[Pendencia] | None,
    revisao: Path,
    avisos: list[str],
    pratica: Pratica,
    gravar_escolhas,
    csv,
    resumo_markdown,
    simulado_html,
) -> bool:
    pasta.mkdir(parents=True, exist_ok=True)
    mudou = gravar_escolhas(arquivo_escolhas, escolhas)
    mudou |= gravar_se_mudou(pasta / ARQUIVO_RESPOSTAS, csv(COLUNAS_RESPOSTAS, respostas))
    mudou |= gravar_se_mudou(pasta / ARQUIVO_ERROS, csv(COLUNAS_ERROS, erros))
    mudou |= gravar_se_mudou(pasta / ARQUIVO_CADERNOS, csv(COLUNAS_CADERNOS, cadernos))
    mudou |= gravar_se_mudou(pasta / ARQUIVO_DESEMPENHO, csv(COLUNAS_DESEMPENHO, desempenho))
    mudou |= gravar_se_mudou(pasta / ARQUIVO_RESUMO, resumo_markdown(erros, cadernos, desempenho, fracos))
    if so_erros_itens:
        mudou |= gravar_se_mudou(pasta / ARQUIVO_SIMULADO, simulado_html(so_erros_itens, aliases, fracos))
    log = {
        'n_itens': len(pratica.erros),
        'n_erros': len(so_erros_itens),
        'n_acertos': sum(1 for r in respostas if r['resultado'] == RESULTADO_ACERTO),
        'n_brancos': sum(1 for r in respostas if r['resultado'] == RESULTADO_BRANCO),
        'avisos': avisos,
    }
    mudou |= gravar_se_mudou(pasta / ARQUIVO_IMPORT_LOG, json.dumps(log, ensure_ascii=False, indent=2) + '\n')
    if pendentes or (pendentes is not None and revisao.exists()):
        linhas = [
            {'assunto': p.assunto, 'disciplina': p.disciplina, 'sugestao': p.sugestao, 'score': p.score}
            for p in (pendentes or [])
        ]
        mudou |= gravar_se_mudou(revisao, csv(COLUNAS_REVISAO, linhas))
    return mudou


def importar_pratica(
    lido: ResultadoPratica,
    pasta_candidato: Path,
    arquivo_escolhas: Path,
    concurso_alvo: str | None,
    interacao: Interacao | None,
    fracos: pd.DataFrame | None,
    dicionario: 'Dicionario | None',
    *,
    carregar_edital,
    gravar_escolhas,
    csv,
    linha_de_resposta,
    so_erros,
    resumo_markdown,
    simulado_html,
) -> ResultadoPratica:
    pratica, avisos, escolhas, disciplinas = lido.pratica, list(lido.avisos), lido.escolhas, lido.disciplinas
    pasta = pasta_candidato / PASTA_PRATICA
    revisao = pasta / ARQUIVO_REVISAO
    if aviso := aviso_materias_sem_disciplina(disciplinas):
        avisos.append(aviso)
    pendentes, avisos_topicos = resolver_topicos(
        pratica,
        disciplinas,
        concurso_alvo,
        pasta_candidato,
        escolhas,
        revisao,
        interacao,
        dicionario,
        carregar_edital=carregar_edital,
    )
    avisos.extend(avisos_topicos)
    resolver_cadernos(pratica.cadernos, escolhas, pratica.estado, interacao)
    respostas = [linha_de_resposta(item) for item in pratica.erros]
    so_erros_itens = so_erros(pratica.erros)
    pratica_erros = Pratica(erros=so_erros_itens, cadernos=pratica.cadernos, estado=pratica.estado)
    erros = linhas_de_erros(pratica_erros, escolhas, disciplinas)
    cadernos = linhas_de_cadernos(pratica, escolhas, disciplinas)
    desempenho = linhas_de_desempenho(erros, cadernos)
    mudou = gravar_tabelas(
        pasta,
        escolhas=escolhas,
        arquivo_escolhas=arquivo_escolhas,
        respostas=respostas,
        erros=erros,
        cadernos=cadernos,
        desempenho=desempenho,
        so_erros_itens=so_erros_itens,
        aliases=escolhas.aliases,
        fracos=fracos,
        pendentes=pendentes,
        revisao=revisao,
        avisos=avisos,
        pratica=pratica,
        gravar_escolhas=gravar_escolhas,
        csv=csv,
        resumo_markdown=resumo_markdown,
        simulado_html=simulado_html,
    )
    mudou |= gravar_se_mudou(pasta / 'tec_estatisticas.md', markdown_resumo(pasta_candidato))
    for aviso in avisos:
        logger.warning(aviso)
    return ResultadoPratica(mudou, avisos, pratica, escolhas, disciplinas)
