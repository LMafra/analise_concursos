import logging
from pathlib import Path

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
from concursos.folha import FolhaIlegivelError, ler_folha
from concursos.gabarito import carregar_gabarito, validar_contagem
from concursos.graficos import gerar_graficos
from concursos.llm import ClienteLlm
from concursos.modelo import ItemGabarito, RespostaMarcada
from concursos.perfis import PerfilOcr, perfil_da_banca
from concursos.prova import segmentar, texto_em_colunas
from concursos.relatorio import ConteudoRelatorio, gerar_relatorio
from concursos.respostas import ler_respostas_txt
from concursos.resultado_oficial import gravar_validacao, validar_resultado
from concursos.status import Situacao, avaliar, listar_concursos
from concursos.texto import MINIMO_CARACTERES_PAGINA, OcrIndisponivelError, extrair_paginas
from concursos.topicos import ARQUIVO_REVISAO, gravar_revisao, ler_revisao, sugerir_topicos

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
) -> bool:
    """Analisa os concursos completos que mudaram; retorna False se algum falhou durante a análise.

    Com candidato, `raiz_analises` é a pasta dele e só entram os concursos com `candidatos/<candidato>/`.
    """
    configuracao = configuracao or ConfiguracaoGlobal()
    sucesso = True
    for pasta in _selecionar(raiz_provas, apenas):
        destino = raiz_analises / pasta.name
        sucesso &= _analisar_se_necessario(pasta, destino, forcar, configuracao, taxonomia, candidato)
    consolidar(raiz_provas, raiz_analises, configuracao.limiar_topico_baixo, candidato)
    return sucesso


def planejar(
    raiz_provas: Path,
    raiz_analises: Path,
    forcar: bool = False,
    apenas: str | None = None,
    candidato: str | None = None,
) -> list[tuple[str, str]]:
    """O que `analisar_todos` faria com cada concurso, sem gravar nada."""
    plano = []
    for pasta in _selecionar(raiz_provas, apenas):
        situacao = avaliar(pasta, candidato)
        if situacao.situacao is not Situacao.COMPLETO:
            plano.append((pasta.name, f'pularia ({situacao.situacao}: {"; ".join(situacao.motivos)})'))
        elif situacao.trocas:
            plano.append((pasta.name, 'analisaria (gabarito definitivo novo)'))
        elif not forcar and manifesto.atualizado(pasta, raiz_analises / pasta.name, candidato):
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
) -> bool:
    situacao = avaliar(pasta, candidato)
    if situacao.trocas:
        trocar_gabaritos(situacao.config, situacao.trocas, destino)
        situacao = avaliar(pasta, candidato)
    elif (
        situacao.situacao is Situacao.COMPLETO
        and not forcar
        and manifesto.atualizado(pasta, destino, candidato)
    ):
        logger.info('%s: sem mudanças desde a última análise', situacao.nome)
        return True
    if situacao.situacao is not Situacao.COMPLETO:
        logger.warning('%s: %s, pulando: %s', situacao.nome, situacao.situacao, '; '.join(situacao.motivos))
        return True
    manifesto.invalidar(destino)
    try:
        analisar_concurso(situacao.config, destino, configuracao, taxonomia)
    except (ValueError, FileNotFoundError, RuntimeError) as erro:
        logger.error('%s: falha na análise: %s', situacao.nome, erro)
        return False
    manifesto.gravar(pasta, destino, candidato)
    return True


def analisar_concurso(
    config: ConcursoConfig,
    destino: Path,
    configuracao: ConfiguracaoGlobal,
    taxonomia: dict[str, DisciplinaCanonica] | None = None,
) -> None:
    logger.info('Analisando %s', config.nome)
    if taxonomia is None:
        taxonomia = _taxonomia_do_contexto()
    documentos = _paginas_dos_documentos(config)
    edital = _ler_edital(config, documentos)
    gabaritos = {prova.chave: _ler_gabarito(config, prova) for prova in config.provas}
    respostas = _ler_respostas(config, destino, configuracao.limiar_confianca, configuracao.perfil_calibrado)
    resultados = corrigir(config, gabaritos, respostas, _disciplinas_por_questao(config))
    resultados = _classificar_topicos(config, edital, resultados)
    validacao = validar_resultado(config, resultados)
    if validacao is not None and validacao.alerta:
        logger.warning('%s: %s', config.nome, validacao.descricao)

    destino.mkdir(parents=True, exist_ok=True)
    tabela = _tabela_respostas(config, respostas, configuracao.limiar_confianca)
    tabela.to_csv(destino / ARQUIVO_RESPOSTAS, index=False)
    resultados[COLUNAS_QUESTOES].to_csv(destino / ARQUIVO_QUESTOES, index=False)
    if edital is not None:
        edital.gravar_json(destino / ARQUIVO_EDITAL_ESTRUTURADO)
    por_disciplina = agregar(resultados, ['concurso', 'prova', 'disciplina'], config.pontuacao)
    por_topico = agregar(resultados, ['concurso', 'prova', 'disciplina', 'topico'], config.pontuacao)
    geral = agregar(resultados, ['concurso', 'prova'], config.pontuacao)
    por_disciplina.to_csv(destino / 'desempenho_por_disciplina.csv', index=False)
    por_topico.to_csv(destino / 'desempenho_por_topico.csv', index=False)
    correcoes = resolver_correcao(config, documentos)
    gravar_correcao(correcoes, destino)
    regras = _regras_do_edital(
        config, documentos, resultados, correcoes, destino, taxonomia, configuracao.cliente_llm
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
        logger.warning('%s; disciplinas do edital comparadas só pelo nome', erro)
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
    if config.edital.manual:
        return carregar_edital_manual(config.caminho(config.edital.manual), config.cargo)
    erros, sem_ocr = [], []
    for arquivo, paginas in documentos.items():
        try:
            return _estruturar_documento(config.caminho(arquivo), paginas, config.cargo)
        except EditalNaoEstruturadoError as erro:
            erros.append(str(erro))
        except OcrIndisponivelError:
            sem_ocr.append(arquivo)
    if sem_ocr:
        logger.warning(
            '%s: %s sem texto e o Tesseract não está instalado; seguindo em modo mínimo, sem o conteúdo '
            'programático. dica: instale o Tesseract com o idioma português (%s) ou rode '
            '`concurso-analise doctor`',
            config.nome,
            ', '.join(sem_ocr),
            comando_de_correcao('tesseract'),
        )
    else:
        logger.warning(
            '%s: %s; seguindo sem o conteúdo programático, com os tópicos como nao_mapeado. dica: forneça um '
            'edital manual (edital.manual no concurso.yaml; formato em docs/modelo.md)',
            config.nome,
            '; '.join(erros),
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
        if not faixas and _caderno_pdf(prova) and perfil_da_banca(config.banca).disciplinas_pelo_caderno:
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


def _caderno_pdf(prova: ProvaConfig) -> bool:
    return bool(prova.caderno) and prova.caderno.lower().endswith('.pdf')


def _classificar_topicos(
    config: ConcursoConfig, edital: Edital | None, resultados: pd.DataFrame
) -> pd.DataFrame:
    """Tópico sugerido por similaridade com o edital; a revisão manual (revisao/) tem prioridade."""
    resultados = resultados.assign(topico_sugerido=TOPICO_NAO_MAPEADO, score=0.0, revisado=False)
    if edital is None:
        return resultados
    textos = _textos_das_questoes(config)
    conhecidas = {
        q: d
        for q, d in zip(resultados['questao'], resultados['disciplina'], strict=True)
        if d != TOPICO_NAO_MAPEADO
    }
    sugestoes = sugerir_topicos(edital, {q: textos.get(q, '') for q in resultados['questao']}, conhecidas)
    resultados['disciplina'] = [sugestoes[q].disciplina or TOPICO_NAO_MAPEADO for q in resultados['questao']]
    resultados['topico_sugerido'] = [sugestoes[q].topico for q in resultados['questao']]
    resultados['score'] = [sugestoes[q].score for q in resultados['questao']]
    resultados['topico'] = resultados['topico_sugerido']

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
        if not prova.caderno:
            continue
        texto = texto_em_colunas(config.caminho(prova.caderno))
        da_prova = segmentar(
            texto, prova.questoes, cebraspe=perfil_da_banca(config.banca).segmentacao == 'itens'
        )
        logger.info('%s: texto de %d de %d questões', prova.caderno, len(da_prova), len(prova.questoes))
        textos.update(da_prova)
    return textos


def _ler_gabarito(config: ConcursoConfig, prova: ProvaConfig) -> list[ItemGabarito]:
    arquivo = prova.gabarito.arquivo
    gabarito = carregar_gabarito(
        config.caminho(arquivo),
        config.formato,
        config.banca,
        config.cargo,
        config.tipo,
        config.n_alternativas,
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
