import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from concursos import manifesto
from concursos.agregacao import agregar
from concursos.analytics.catalogo_edital import gravar_catalogo
from concursos.analytics.correcao import (
    ConfiguracaoCorrecao,
    gravar_correcao,
    notas_finais,
    resolver_correcao,
)
from concursos.analytics.regras_edital import RegrasEdital, extrair_regras
from concursos.analytics.taxonomia import DisciplinaCanonica, TaxonomiaInvalidaError, carregar_taxonomia
from concursos.analytics.validacao_edital import gravar_discrepancias, validar_edital
from concursos.atualizacao import ARQUIVO_DIFF, diff_gabarito, questoes_preliminares, trocar_gabaritos
from concursos.caderno import faixas_do_caderno
from concursos.candidatos import ler_respostas_do_csv
from concursos.concurso_config import ConcursoConfig, ProvaConfig
from concursos.config.contexto import resolver_contexto
from concursos.configuracao import ConfiguracaoGlobal
from concursos.consolidado import consolidar
from concursos.correcao import ARQUIVO_QUESTOES, TOPICO_NAO_MAPEADO, corrigir
from concursos.doctor import comando_de_correcao
from concursos.edital import (
    ARQUIVO_EDITAL_ESTRUTURADO,
    Edital,
    EditalNaoEstruturadoError,
    carregar_edital_manual,
    estruturar_edital,
)
from concursos.edital_a_confirmar import gravar_confirmacao
from concursos.edital_llm import completar_com_llm
from concursos.erros import avisar
from concursos.folha import FolhaIlegivelError, ler_folha
from concursos.gabarito import carregar_gabarito, validar_contagem
from concursos.graficos import gerar_graficos
from concursos.linguagem import SITUACAO_DO_GABARITO
from concursos.llm import ClienteLlm
from concursos.modelo import Etapa, ItemGabarito, RespostaMarcada
from concursos.perfis import PerfilOcr, perfil_da_banca
from concursos.prova import segmentar, texto_em_colunas
from concursos.relatorio import ConteudoRelatorio, gerar_relatorio
from concursos.respostas import ler_respostas_txt
from concursos.resultado_oficial import gravar_validacao, validar_resultado
from concursos.status import Situacao, StatusConcurso, avaliar, listar_concursos
from concursos.texto import MINIMO_CARACTERES_PAGINA, OcrIndisponivelError, extrair_paginas
from concursos.topicos import ARQUIVO_REVISAO, gravar_revisao, ler_revisao, sugerir_topicos

if TYPE_CHECKING:
    from concursos.analytics.dicionario_topicos import Dicionario

logger = logging.getLogger(__name__)

ARQUIVO_RESPOSTAS = 'respostas_extraidas.csv'
COLUNAS_QUESTOES = [
    'questao',
    'prova',
    'disciplina',
    'topico_sugerido',
    'score',
    'topico',
    'revisado',
    'gabarito',
    'anulada',
    'resposta',
    'resultado',
]

COLUNAS_DICIONARIO = ['score_tfidf', 'topico_tfidf', 'score_expandido']

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
        taxonomia = _taxonomia_do_contexto()
    anunciar(Etapa.LENDO_ARQUIVOS)
    documentos = _paginas_dos_documentos(config)
    edital = _ler_edital(config, documentos)
    gabaritos = {prova.chave: _ler_gabarito(config, prova) for prova in config.provas}
    anunciar(Etapa.LENDO_FOLHA)
    respostas = _ler_respostas(config, destino, configuracao.limiar_confianca, configuracao.perfil_calibrado)
    anunciar(Etapa.CORRIGINDO)
    resultados = corrigir(config, gabaritos, respostas, _disciplinas_por_questao(config))
    anunciar(Etapa.CLASSIFICANDO)
    resultados = _classificar_topicos(config, edital, resultados, configuracao.dicionario, taxonomia)
    validacao = validar_resultado(config, resultados)
    if validacao is not None and validacao.alerta:
        avisar(logger, f'{config.nome}: {validacao.descricao}', detalhe=f'arquivo {validacao.arquivo}')

    anunciar(Etapa.GERANDO_RELATORIOS)
    destino.mkdir(parents=True, exist_ok=True)
    tabela = _tabela_respostas(config, respostas, configuracao.limiar_confianca)
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
    regras = _regras_do_edital(
        config, documentos_da_regra, resultados, correcoes, destino, taxonomia, configuracao.cliente_llm
    )
    diff = _diff_da_troca(destino, resultados)
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


def _regras_do_edital(
    config: ConcursoConfig,
    documentos: dict[str, list[str]],
    resultados: pd.DataFrame,
    correcoes: list[ConfiguracaoCorrecao],
    destino: Path,
    taxonomia: dict[str, DisciplinaCanonica] | None,
    cliente_llm: ClienteLlm | None = None,
) -> RegrasEdital | None:
    """Regras do edital no edital estruturado e as discrepâncias com a prova; só quando há PDF do edital."""
    if not documentos:
        return None
    retificacoes = {
        arquivo: extrair_paginas(config.caminho(arquivo), ocr=False) for arquivo in config.edital.retificacoes
    }
    regras = extrair_regras(config, documentos, retificacoes)
    if cliente_llm is not None:
        regras = completar_com_llm(regras, documentos, cliente_llm)
    regras.gravar_json(destino / ARQUIVO_EDITAL_ESTRUTURADO)
    gravar_confirmacao(config, regras, correcoes)
    gravar_discrepancias(validar_edital(config, regras, resultados, taxonomia, correcoes), destino)
    gravar_catalogo(config, regras, destino)
    return regras


def _taxonomia_do_contexto() -> dict[str, DisciplinaCanonica] | None:
    """Taxonomia do projeto (`.concurso/` ou legado na raiz); vazia ou inválida vira None na validação."""
    caminho = resolver_contexto().taxonomia
    if not caminho.exists():
        return None
    try:
        mapeamento = carregar_taxonomia(caminho)
    except TaxonomiaInvalidaError as erro:
        avisar(
            logger,
            'não consegui ler a lista de disciplinas equivalentes; comparei as disciplinas do edital só pelo nome.',
            'corrija a lista em Disciplinas e temas.',
            str(erro),
        )
        return None
    return mapeamento or None


def _diff_da_troca(destino: Path, resultados: pd.DataFrame) -> pd.DataFrame | None:
    preliminar = questoes_preliminares(destino)
    if preliminar is None:
        (destino / ARQUIVO_DIFF).unlink(missing_ok=True)
        return None
    diff = diff_gabarito(preliminar, resultados)
    diff.to_csv(destino / ARQUIVO_DIFF, index=False)
    return diff


def _paginas_dos_documentos(config: ConcursoConfig) -> dict[str, list[str]]:
    """Texto (sem OCR) de cada documento do edital, lido uma vez para o conteúdo programático e a correção."""
    if config.edital is None:
        return {}
    return {
        arquivo: extrair_paginas(config.caminho(arquivo), ocr=False) for arquivo in config.edital.documentos
    }


def _ler_edital(config: ConcursoConfig, documentos: dict[str, list[str]]) -> Edital | None:
    if config.edital is None:
        return None
    cargo = config.simulado.cargo_alvo if config.simulado and config.simulado.cargo_alvo else config.cargo
    if config.edital.manual:
        return carregar_edital_manual(config.caminho(config.edital.manual), cargo)
    erros, sem_ocr = [], []
    for arquivo, paginas in documentos.items():
        try:
            return _estruturar_documento(config.caminho(arquivo), paginas, cargo)
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


def _estruturar_documento(caminho: Path, paginas: list[str], cargo: str | None) -> Edital:
    try:
        return estruturar_edital(paginas, cargo, caminho.name)
    except EditalNaoEstruturadoError:
        if all(len(p.strip()) >= MINIMO_CARACTERES_PAGINA for p in paginas):
            raise
    logger.info('%s: conteúdo programático não encontrado no texto; tentando com OCR', caminho.name)
    return estruturar_edital(extrair_paginas(caminho), cargo, caminho.name)


def _disciplinas_por_questao(config: ConcursoConfig) -> dict[int, str]:
    """Faixas manuais do concurso.yaml; sem elas, cabeçalhos do caderno, nas bancas que os têm."""
    disciplinas = {}
    for prova in config.provas:
        faixas = prova.disciplinas
        if (
            not faixas
            and prova.caderno_pdf
            and perfil_da_banca(config.banca).disciplinas_pelo_caderno
            and _caderno_presente(config, prova)
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


def preparar_revisao(
    config: ConcursoConfig,
    configuracao: ConfiguracaoGlobal,
    taxonomia: dict[str, DisciplinaCanonica] | None = None,
) -> Path:
    """Classifica as questões de uma prova ainda sem respostas (a prova anterior importada) e grava só a
    revisão de tópicos, que o simulado focado lê; a análise da prova continua exigindo as respostas."""
    edital = _ler_edital(config, _paginas_dos_documentos(config))
    gabaritos = {prova.chave: _ler_gabarito(config, prova) for prova in config.provas}
    resultados = corrigir(config, gabaritos, [], _disciplinas_por_questao(config))
    _classificar_topicos(
        config, edital, resultados, configuracao.dicionario, taxonomia or _taxonomia_do_contexto()
    )
    return config.caminho(ARQUIVO_REVISAO)


def _classificar_topicos(
    config: ConcursoConfig,
    edital: Edital | None,
    resultados: pd.DataFrame,
    dicionario: 'Dicionario | None' = None,
    taxonomia: dict[str, DisciplinaCanonica] | None = None,
) -> pd.DataFrame:
    """Tópico sugerido por similaridade com o edital; a revisão manual (revisao/) tem prioridade.

    Sem tópicos no edital, a revisão sai do mesmo jeito, com a disciplina das faixas e o tópico nao_mapeado.
    """
    resultados = resultados.assign(topico_sugerido=TOPICO_NAO_MAPEADO, score=0.0, revisado=False)
    textos = _textos_das_questoes(config)
    conhecidas = {
        q: d
        for q, d in zip(resultados['questao'], resultados['disciplina'], strict=True)
        if d != TOPICO_NAO_MAPEADO
    }
    canonicas = {bruto: disciplina.nome for bruto, disciplina in (taxonomia or {}).items()}
    sugestoes = sugerir_topicos(
        edital, {q: textos.get(q, '') for q in resultados['questao']}, conhecidas, dicionario, canonicas
    )
    resultados['disciplina'] = [sugestoes[q].disciplina or TOPICO_NAO_MAPEADO for q in resultados['questao']]
    resultados['topico_sugerido'] = [sugestoes[q].topico for q in resultados['questao']]
    resultados['score'] = [sugestoes[q].score for q in resultados['questao']]
    resultados['topico'] = resultados['topico_sugerido']
    if dicionario is not None:
        resultados['score_tfidf'] = [sugestoes[q].score_tfidf for q in resultados['questao']]
        resultados['topico_tfidf'] = [sugestoes[q].topico_tfidf for q in resultados['questao']]
        resultados['score_expandido'] = resultados['score']

    caminho = config.caminho(ARQUIVO_REVISAO)
    revisao = ler_revisao(caminho)
    for indice, linha in resultados.iterrows():
        disciplina, topico = revisao.get((linha['questao'], linha['prova']), ('', ''))
        if disciplina or topico:
            resultados.loc[indice, ['disciplina', 'topico', 'revisado']] = [
                disciplina or linha['disciplina'],
                topico or linha['topico'],
                True,
            ]
    gravar_revisao(
        caminho,
        [
            {
                'questao': linha.questao,
                'prova': linha.prova,
                'disciplina_sugerida': linha.disciplina,
                'topico_sugerido': linha.topico_sugerido,
                'score': linha.score,
                'enunciado': textos.get(linha.questao, ''),
            }
            for linha in resultados.itertuples()
        ],
    )
    return resultados


def _textos_das_questoes(config: ConcursoConfig) -> dict[int, str]:
    textos = {}
    for prova in config.provas:
        if not prova.caderno or not _caderno_presente(config, prova):
            continue
        texto = texto_em_colunas(config.caminho(prova.caderno))
        da_prova = segmentar(
            texto, prova.questoes, por_itens=perfil_da_banca(config.banca).segmentacao == 'itens'
        )
        logger.info('%s: texto de %d de %d questões', prova.caderno, len(da_prova), len(prova.questoes))
        textos.update(da_prova)
    return textos


def _caderno_presente(config: ConcursoConfig, prova: ProvaConfig) -> bool:
    if config.caminho(prova.caderno).exists():
        return True
    avisar(
        logger,
        f'{prova.caderno}: não encontrei o caderno de questões; a prova {prova.chave} segue sem o texto delas.',
        'coloque o PDF do caderno na pasta do concurso, com esse nome.',
        'caderno ausente',
    )
    return False


def _ler_gabarito(config: ConcursoConfig, prova: ProvaConfig) -> list[ItemGabarito]:
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


def _ler_respostas(
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


def _tabela_respostas(
    config: ConcursoConfig, respostas: list[RespostaMarcada], limiar: float
) -> pd.DataFrame:
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
