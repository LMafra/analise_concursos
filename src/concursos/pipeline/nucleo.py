"""Orquestração da análise: escolhe concursos e chama as etapas em `pipeline.etapas`."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from concursos import manifesto
from concursos.agregacao import agregar
from concursos.analytics.correcao import gravar_correcao, notas_finais, resolver_correcao
from concursos.analytics.taxonomia import DisciplinaCanonica
from concursos.artefatos import ARQUIVO_RESPOSTAS
from concursos.atualizacao import trocar_gabaritos
from concursos.concurso_config import ConcursoConfig
from concursos.configuracao import ConfiguracaoGlobal
from concursos.consolidado import consolidar
from concursos.correcao import ARQUIVO_QUESTOES, corrigir
from concursos.edital import ARQUIVO_EDITAL_ESTRUTURADO
from concursos.erros import avisar
from concursos.graficos import gerar_graficos
from concursos.modelo import Etapa
from concursos.pipeline.etapas.classificacao import classificar_topicos
from concursos.pipeline.etapas.constantes import COLUNAS_DICIONARIO, COLUNAS_QUESTOES
from concursos.pipeline.etapas.leitura import (
    disciplinas_por_questao,
    ler_edital,
    ler_gabarito,
    ler_respostas,
    paginas_dos_documentos,
    tabela_respostas,
)
from concursos.pipeline.etapas.regras import diff_da_troca, regras_do_edital, taxonomia_do_contexto
from concursos.relatorio import ConteudoRelatorio, gerar_relatorio
from concursos.resultado_oficial import gravar_validacao, validar_resultado
from concursos.status import Situacao, StatusConcurso, avaliar, listar_concursos
from concursos.topicos import ARQUIVO_REVISAO

logger = logging.getLogger(__name__)


class ConcursoNaoEncontradoError(ValueError):
    pass


def analisar_todos(
    raiz_provas: Path,
    raiz_analises: Path,
    forcar: bool = False,
    apenas: str | None = None,
    configuracao: ConfiguracaoGlobal | None = None,
    taxonomia: dict[str, DisciplinaCanonica] | None = None,
    candidato: str | None = None,
    ao_progresso: Callable[[str, int, int], None] | None = None,
    ao_etapa: Callable[[str, Etapa], None] | None = None,
    extras: manifesto.Extras | None = None,
) -> bool:
    """Analisa os concursos completos que mudaram; retorna False se algum falhou durante a análise.

    Com candidato, `raiz_analises` é a pasta dele e só entram os concursos com `candidatos/<candidato>/`.
    `ao_progresso(concurso, indice, total)` é chamado antes de cada concurso, a partir de 1;
    `ao_etapa(concurso, etapa)`, em cada etapa de um concurso analisado e com `''` antes do consolidado.
    """
    configuracao = configuracao or ConfiguracaoGlobal()
    sucesso = True
    situacoes = {}
    pastas = _selecionar(raiz_provas, apenas)
    for indice, pasta in enumerate(pastas, start=1):
        if ao_progresso is not None:
            ao_progresso(pasta.name, indice, len(pastas))
        destino = raiz_analises / pasta.name
        etapa = (lambda e, nome=pasta.name: ao_etapa(nome, e)) if ao_etapa is not None else None
        situacao, analisado = _analisar_se_necessario(
            pasta, destino, forcar, configuracao, taxonomia, candidato, etapa, extras
        )
        situacoes[pasta.name] = situacao
        sucesso &= analisado
    if ao_etapa is not None:
        ao_etapa('', Etapa.CONSOLIDANDO)
    consolidar(
        raiz_provas,
        raiz_analises,
        configuracao.limiar_topico_baixo,
        candidato,
        situacoes,
        configuracao.incluir_simulados,
    )
    return sucesso


def planejar(
    raiz_provas: Path,
    raiz_analises: Path,
    forcar: bool = False,
    apenas: str | None = None,
    candidato: str | None = None,
    extras: manifesto.Extras | None = None,
) -> list[tuple[str, str]]:
    """O que `analisar_todos` faria com cada concurso, sem gravar nada."""
    plano = []
    for pasta in _selecionar(raiz_provas, apenas):
        situacao = avaliar(pasta, candidato)
        if situacao.situacao is not Situacao.COMPLETO:
            plano.append((pasta.name, f'pularia ({situacao.situacao}: {"; ".join(situacao.motivos)})'))
        elif situacao.trocas:
            plano.append((pasta.name, 'analisaria (gabarito definitivo novo)'))
        elif not forcar and manifesto.atualizado(pasta, raiz_analises / pasta.name, candidato, extras):
            plano.append((pasta.name, 'sem mudanças'))
        else:
            plano.append((pasta.name, 'analisaria'))
    return plano


def _selecionar(raiz_provas: Path, apenas: str | None) -> list[Path]:
    pastas = listar_concursos(raiz_provas)
    if apenas is None:
        return pastas
    if selecionadas := [p for p in pastas if p.name == apenas]:
        return selecionadas
    raise ConcursoNaoEncontradoError(f'{raiz_provas / apenas}: concurso não encontrado')


def _analisar_se_necessario(
    pasta: Path,
    destino: Path,
    forcar: bool,
    configuracao: ConfiguracaoGlobal,
    taxonomia: dict[str, DisciplinaCanonica] | None,
    candidato: str | None,
    etapa: Callable[[Etapa], None] | None = None,
    extras: manifesto.Extras | None = None,
) -> tuple[StatusConcurso, bool]:
    """A situação do concurso depois da troca de gabarito, se houve, e se a análise não falhou."""
    situacao = avaliar(pasta, candidato)
    if situacao.trocas:
        trocar_gabaritos(situacao.config, situacao.trocas, destino)
        situacao = avaliar(pasta, candidato)
    elif (
        situacao.situacao is Situacao.COMPLETO
        and not forcar
        and manifesto.atualizado(pasta, destino, candidato, extras)
    ):
        logger.info('%s: sem mudanças desde a última análise', situacao.nome)
        return situacao, True
    if situacao.situacao is not Situacao.COMPLETO:
        avisar(
            logger,
            f'{situacao.nome}: o cadastro deste concurso não está completo; pulei a análise dele.',
            'complete o que falta em Concursos (ou rode concurso-analise status para ver o quê).',
            f'{situacao.situacao}: {"; ".join(situacao.motivos)}',
        )
        return situacao, True
    manifesto.invalidar(destino)
    try:
        analisar_concurso(situacao.config, destino, configuracao, taxonomia, etapa)
    except (ValueError, FileNotFoundError, RuntimeError) as erro:
        logger.error(
            '%s',
            f'{situacao.nome}: não consegui analisar este concurso; os outros seguem normalmente.',
            extra={
                'dica': getattr(erro, 'dica', None) or 'confira os arquivos do concurso em Concursos.',
                'detalhe': f'falha na análise: {erro}',
            },
        )
        return situacao, False
    manifesto.gravar(pasta, destino, candidato, extras)
    return situacao, True


def analisar_concurso(
    config: ConcursoConfig,
    destino: Path,
    configuracao: ConfiguracaoGlobal,
    taxonomia: dict[str, DisciplinaCanonica] | None = None,
    etapa: Callable[[Etapa], None] | None = None,
) -> None:
    def anunciar(atual: Etapa) -> None:
        if etapa is not None:
            etapa(atual)

    logger.info('Analisando %s', config.nome)
    if taxonomia is None:
        taxonomia = taxonomia_do_contexto()
    anunciar(Etapa.LENDO_ARQUIVOS)
    documentos = paginas_dos_documentos(config)
    edital = ler_edital(config, documentos)
    gabaritos = {prova.chave: ler_gabarito(config, prova) for prova in config.provas}
    anunciar(Etapa.LENDO_FOLHA)
    respostas = ler_respostas(config, destino, configuracao.limiar_confianca, configuracao.perfil_calibrado)
    anunciar(Etapa.CORRIGINDO)
    resultados = corrigir(config, gabaritos, respostas, disciplinas_por_questao(config))
    anunciar(Etapa.CLASSIFICANDO)
    resultados = classificar_topicos(config, edital, resultados, configuracao.dicionario, taxonomia)
    validacao = validar_resultado(config, resultados)
    if validacao is not None and validacao.alerta:
        avisar(logger, f'{config.nome}: {validacao.descricao}', detalhe=f'arquivo {validacao.arquivo}')

    anunciar(Etapa.GERANDO_RELATORIOS)
    destino.mkdir(parents=True, exist_ok=True)
    tabela = tabela_respostas(config, respostas, configuracao.limiar_confianca)
    tabela.to_csv(destino / ARQUIVO_RESPOSTAS, index=False)
    colunas = COLUNAS_QUESTOES + (COLUNAS_DICIONARIO if configuracao.dicionario is not None else [])
    resultados[colunas].to_csv(destino / ARQUIVO_QUESTOES, index=False)
    if edital is not None:
        edital.gravar_json(destino / ARQUIVO_EDITAL_ESTRUTURADO)
    por_disciplina = agregar(resultados, ['concurso', 'prova', 'disciplina'], config.pontuacao)
    por_topico = agregar(resultados, ['concurso', 'prova', 'disciplina', 'topico'], config.pontuacao)
    geral = agregar(resultados, ['concurso', 'prova'], config.pontuacao)
    por_disciplina.to_csv(destino / 'desempenho_por_disciplina.csv', index=False)
    por_topico.to_csv(destino / 'desempenho_por_topico.csv', index=False)
    documentos_da_regra = {} if config.simulado else documentos
    correcoes = resolver_correcao(config, documentos_da_regra)
    gravar_correcao(correcoes, destino)
    regras = regras_do_edital(
        config, documentos_da_regra, resultados, correcoes, destino, taxonomia, configuracao.cliente_llm
    )
    diff = diff_da_troca(destino, resultados)
    gravar_validacao(validacao, destino)
    conteudo = ConteudoRelatorio(
        geral=geral,
        por_disciplina=por_disciplina,
        por_topico=por_topico,
        questoes=resultados,
        respostas=tabela,
        graficos=gerar_graficos(por_disciplina, por_topico, destino),
        validacao=validacao,
        diff=diff,
        notas_finais=notas_finais(resultados, correcoes, config.formato),
        identificacao=regras.identificacao if regras else None,
    )
    (destino / 'relatorio.md').write_text(gerar_relatorio(config, conteudo), encoding='utf-8')
    logger.info('Saídas de %s gravadas em %s', config.nome, destino)


def preparar_revisao(
    config: ConcursoConfig,
    configuracao: ConfiguracaoGlobal,
    taxonomia: dict[str, DisciplinaCanonica] | None = None,
) -> Path:
    """Classifica as questões de uma prova ainda sem respostas (a prova anterior importada) e grava só a
    revisão de tópicos, que o simulado focado lê; a análise da prova continua exigindo as respostas."""
    edital = ler_edital(config, paginas_dos_documentos(config))
    gabaritos = {prova.chave: ler_gabarito(config, prova) for prova in config.provas}
    resultados = corrigir(config, gabaritos, [], disciplinas_por_questao(config))
    classificar_topicos(
        config, edital, resultados, configuracao.dicionario, taxonomia or taxonomia_do_contexto()
    )
    return config.caminho(ARQUIVO_REVISAO)
