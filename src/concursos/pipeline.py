import logging
from pathlib import Path

import pandas as pd

from concursos import manifesto
from concursos.agregacao import agregar
from concursos.atualizacao import ARQUIVO_DIFF, diff_gabarito, questoes_preliminares, trocar_gabaritos
from concursos.caderno import faixas_do_caderno
from concursos.concurso_config import ConcursoConfig, ProvaConfig
from concursos.configuracao import ConfiguracaoGlobal
from concursos.consolidado import consolidar
from concursos.correcao import TOPICO_NAO_MAPEADO, corrigir
from concursos.edital import Edital, EditalNaoEstruturadoError, carregar_edital_manual, estruturar_edital
from concursos.folha import FolhaIlegivelError, ler_folha
from concursos.gabarito import carregar_gabarito, validar_contagem
from concursos.graficos import gerar_graficos
from concursos.modelo import ItemGabarito, RespostaMarcada
from concursos.prova import segmentar, texto_em_colunas
from concursos.relatorio import ConteudoRelatorio, gerar_relatorio
from concursos.respostas import ler_respostas_txt
from concursos.resultado_oficial import gravar_validacao, validar_resultado
from concursos.status import Situacao, avaliar, listar_concursos
from concursos.texto import MINIMO_CARACTERES_PAGINA, extrair_paginas
from concursos.topicos import ARQUIVO_REVISAO, gravar_revisao, ler_revisao, sugerir_topicos

logger = logging.getLogger(__name__)

BANCAS_COM_CABECALHO = {'fgv', 'selecon'}
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
) -> bool:
    """Analisa os concursos completos que mudaram; retorna False se algum falhou durante a análise."""
    configuracao = configuracao or ConfiguracaoGlobal()
    pastas = listar_concursos(raiz_provas)
    if apenas is not None:
        pastas = [p for p in pastas if p.name == apenas]
        if not pastas:
            raise ConcursoNaoEncontradoError(f'{raiz_provas / apenas}: concurso não encontrado')
    sucesso = True
    for pasta in pastas:
        sucesso &= _analisar_se_necessario(pasta, raiz_analises / pasta.name, forcar, configuracao)
    consolidar(raiz_provas, raiz_analises, configuracao.limiar_topico_baixo)
    return sucesso


def _analisar_se_necessario(
    pasta: Path, destino: Path, forcar: bool, configuracao: ConfiguracaoGlobal
) -> bool:
    situacao = avaliar(pasta)
    if situacao.trocas:
        trocar_gabaritos(situacao.config, situacao.trocas, destino)
        situacao = avaliar(pasta)
    elif situacao.situacao is Situacao.COMPLETO and not forcar and manifesto.atualizado(pasta, destino):
        logger.info('%s: sem mudanças desde a última análise', situacao.nome)
        return True
    if situacao.situacao is not Situacao.COMPLETO:
        logger.warning('%s: %s, pulando: %s', situacao.nome, situacao.situacao, '; '.join(situacao.motivos))
        return True
    manifesto.invalidar(destino)
    try:
        analisar_concurso(situacao.config, destino, configuracao)
    except (ValueError, FileNotFoundError, RuntimeError) as erro:
        logger.error('%s: falha na análise: %s', situacao.nome, erro)
        return False
    manifesto.gravar(pasta, destino)
    return True


def analisar_concurso(config: ConcursoConfig, destino: Path, configuracao: ConfiguracaoGlobal) -> None:
    logger.info('Analisando %s', config.nome)
    edital = _ler_edital(config)
    gabaritos = {prova.chave: _ler_gabarito(config, prova) for prova in config.provas}
    respostas = _ler_respostas(config, destino, configuracao.limiar_confianca)
    resultados = corrigir(config, gabaritos, respostas, _disciplinas_por_questao(config))
    resultados = _classificar_topicos(config, edital, resultados)
    validacao = validar_resultado(config, resultados)
    if validacao is not None and validacao.alerta:
        logger.warning('%s: %s', config.nome, validacao.descricao)

    destino.mkdir(parents=True, exist_ok=True)
    tabela = _tabela_respostas(config, respostas, configuracao.limiar_confianca)
    tabela.to_csv(destino / 'respostas_extraidas.csv', index=False)
    resultados[COLUNAS_QUESTOES].to_csv(destino / 'questoes.csv', index=False)
    if edital is not None:
        edital.gravar_json(destino / 'edital_estruturado.json')
    por_disciplina = agregar(resultados, ['concurso', 'prova', 'disciplina'], config.pontuacao)
    por_topico = agregar(resultados, ['concurso', 'prova', 'disciplina', 'topico'], config.pontuacao)
    geral = agregar(resultados, ['concurso', 'prova'], config.pontuacao)
    por_disciplina.to_csv(destino / 'desempenho_por_disciplina.csv', index=False)
    por_topico.to_csv(destino / 'desempenho_por_topico.csv', index=False)
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
    )
    (destino / 'relatorio.md').write_text(gerar_relatorio(config, conteudo), encoding='utf-8')
    logger.info('Saídas de %s gravadas em %s', config.nome, destino)


def _diff_da_troca(destino: Path, resultados: pd.DataFrame) -> pd.DataFrame | None:
    preliminar = questoes_preliminares(destino)
    if preliminar is None:
        (destino / ARQUIVO_DIFF).unlink(missing_ok=True)
        return None
    diff = diff_gabarito(preliminar, resultados)
    diff.to_csv(destino / ARQUIVO_DIFF, index=False)
    return diff


def _ler_edital(config: ConcursoConfig) -> Edital | None:
    if config.edital is None:
        return None
    if config.edital.manual:
        return carregar_edital_manual(config.caminho(config.edital.manual), config.cargo)
    erros = []
    for arquivo in config.edital.documentos:
        caminho = config.caminho(arquivo)
        try:
            return _estruturar_documento(caminho, config.cargo)
        except EditalNaoEstruturadoError as erro:
            erros.append(str(erro))
    raise EditalNaoEstruturadoError(
        f'{"; ".join(erros)}. Forneça o conteúdo programático num edital manual '
        '(edital.manual no concurso.yaml; formato em docs/modelo.md)'
    )


def _estruturar_documento(caminho: Path, cargo: str | None) -> Edital:
    paginas = extrair_paginas(caminho, ocr=False)
    try:
        return estruturar_edital(paginas, cargo, caminho.name)
    except EditalNaoEstruturadoError:
        if all(len(p.strip()) >= MINIMO_CARACTERES_PAGINA for p in paginas):
            raise
    logger.info('%s: conteúdo programático não encontrado no texto; tentando com OCR', caminho.name)
    return estruturar_edital(extrair_paginas(caminho), cargo, caminho.name)


def _disciplinas_por_questao(config: ConcursoConfig) -> dict[int, str]:
    """Faixas manuais do concurso.yaml; sem elas, cabeçalhos do caderno (FGV e SELECON)."""
    disciplinas = {}
    for prova in config.provas:
        faixas = prova.disciplinas
        if not faixas and _caderno_pdf(prova) and config.banca in BANCAS_COM_CABECALHO:
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
        da_prova = segmentar(texto, prova.questoes, cebraspe=config.banca == 'cebraspe')
        logger.info('%s: texto de %d de %d questões', prova.caderno, len(da_prova), len(prova.questoes))
        textos.update(da_prova)
    return textos


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


def _ler_respostas(config: ConcursoConfig, destino: Path, limiar: float) -> list[RespostaMarcada]:
    questoes = [q for prova in config.provas for q in prova.questoes]
    if config.respostas_arquivo is not None:
        texto = config.caminho(config.respostas_arquivo).read_text(encoding='utf-8')
        return ler_respostas_txt(texto, config.formato, questoes, config.respostas_arquivo)
    folha = config.folha
    lidas = ler_folha(
        config.caminho(folha.arquivo),
        folha.template,
        folha.total_itens or max(questoes),
        folha.itens_por_coluna,
        destino / 'depuracao',
        limiar,
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
