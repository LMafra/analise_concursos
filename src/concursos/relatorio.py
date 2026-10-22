from dataclasses import dataclass, field

import pandas as pd

from concursos.analytics.correcao import NotaFinal
from concursos.atualizacao import COLUNAS_DIFF, impacto
from concursos.concurso_config import ConcursoConfig
from concursos.correcao import TOPICO_NAO_MAPEADO
from concursos.resultado_oficial import Validacao, formatar
from concursos.topicos import ARQUIVO_REVISAO, SCORE_BAIXO

MAXIMO_TOPICOS_FRACOS = 10


@dataclass(frozen=True)
class ConteudoRelatorio:
    geral: pd.DataFrame
    por_disciplina: pd.DataFrame
    por_topico: pd.DataFrame
    questoes: pd.DataFrame
    respostas: pd.DataFrame
    graficos: dict[str, str] = field(default_factory=dict)
    validacao: Validacao | None = None
    diff: pd.DataFrame | None = None
    notas_finais: list[NotaFinal] = field(default_factory=list)


def gerar_relatorio(config: ConcursoConfig, conteudo: ConteudoRelatorio) -> str:
    linhas = [
        f'# Relatório de desempenho: {config.nome}',
        '',
        f'- Banca: {config.banca}',
        f'- Formato: {config.formato}',
        f'- Pontuação: {config.pontuacao}',
        f'- Gabarito: {config.status_gabarito}',
        '',
        *_selo_preliminar(config),
        *_secao_validacao(conteudo.validacao),
        '## Resumo por prova',
        '',
        tabela_markdown(
            conteudo.geral,
            ['prova', 'total', 'acertos', 'erros', 'em_branco', 'anuladas', 'nota_liquida', 'percentual'],
        ),
        '',
        '_Anuladas contam como acerto e ficam fora do percentual (de mérito)._',
        '',
        *_secao_nota_final(conteudo.notas_finais),
        '## Desempenho por disciplina',
        '',
        tabela_markdown(
            conteudo.por_disciplina,
            ['prova', 'disciplina', 'total', 'acertos', 'erros', 'em_branco', 'percentual'],
        ),
        '',
        *_secao_graficos(conteudo.graficos),
        *_secao_topicos_fracos(conteudo.por_topico),
        *_secao_revisar(conteudo.respostas, conteudo.questoes),
        *_secao_troca(config, conteudo.geral, conteudo.diff),
    ]
    return '\n'.join(linhas)


def _selo_preliminar(config: ConcursoConfig) -> list[str]:
    preliminares = [p.chave for p in config.provas if p.gabarito.status == 'preliminar']
    if not preliminares:
        return []
    return [
        f'> **Gabarito preliminar (provisório)** nas provas {", ".join(preliminares)}: '
        'os resultados podem mudar quando o definitivo sair.',
        '',
    ]


def _secao_nota_final(notas: list[NotaFinal]) -> list[str]:
    if not notas:
        return []
    if len(notas) == 1 and notas[0].variante is None:
        return [f'**Nota final** (regra do edital): {notas[0].texto}.', '']
    return [
        '**Nota final** (regra do edital), por opção de cargo:',
        '',
        *(f'- {n.rotulado}.' for n in notas),
        '',
    ]


def _secao_validacao(validacao: Validacao | None) -> list[str]:
    if validacao is None:
        return []
    texto = validacao.descricao
    if validacao.alerta:
        texto = f'> **Atenção:** {texto}'
    linhas = ['## Validação com o resultado oficial', '', texto, '']
    if validacao.oficial is not None:
        linhas += [f'_Fonte: {validacao.arquivo}, página {validacao.oficial.pagina}._', '']
    return linhas


def _secao_graficos(graficos: dict[str, str]) -> list[str]:
    if not graficos:
        return []
    return ['## Gráficos', '', *(f'![{titulo}]({caminho})\n' for titulo, caminho in graficos.items())]


def _secao_topicos_fracos(por_topico: pd.DataFrame) -> list[str]:
    mapeados = por_topico[por_topico['topico'] != TOPICO_NAO_MAPEADO]
    if mapeados.empty:
        return []
    fracos = mapeados.sort_values(['percentual', 'total'], ascending=[True, False]).head(
        MAXIMO_TOPICOS_FRACOS
    )
    return [
        f'## Tópicos com menor desempenho (até {MAXIMO_TOPICOS_FRACOS})',
        '',
        tabela_markdown(fracos, ['prova', 'disciplina', 'topico', 'total', 'acertos', 'erros', 'percentual']),
        '',
    ]


def _secao_revisar(respostas: pd.DataFrame, questoes: pd.DataFrame) -> list[str]:
    linhas = ['## Questões para revisar', '', '### Leitura das respostas', '']
    leitura = respostas[respostas['revisar']]
    if leitura.empty:
        linhas += ['Nenhuma leitura abaixo do limiar de confiança.', '']
    else:
        linhas += [
            tabela_markdown(
                leitura,
                ['questao', 'prova', 'alternativa_marcada', 'estado', 'confianca_ocr', 'arquivo', 'pagina'],
            ),
            '',
        ]
    linhas += ['### Classificação de tópico', '']
    if (questoes['topico'] == TOPICO_NAO_MAPEADO).all() and not questoes['revisado'].any():
        return [*linhas, 'Nenhum tópico classificado (sem edital estruturado ou sem texto do caderno).', '']
    fracas = questoes[~questoes['revisado'] & (questoes['score'] < SCORE_BAIXO)]
    if fracas.empty:
        return [*linhas, 'Nenhuma sugestão de tópico com score baixo.', '']
    return [
        *linhas,
        f'Sugestões com score abaixo de {formatar(SCORE_BAIXO)} ainda não revisadas; '
        f'corrija em `{ARQUIVO_REVISAO}` (colunas disciplina e topico).',
        '',
        tabela_markdown(fracas, ['questao', 'prova', 'disciplina', 'topico', 'score']),
        '',
    ]


def _secao_troca(config: ConcursoConfig, geral: pd.DataFrame, diff: pd.DataFrame | None) -> list[str]:
    if diff is None:
        return []
    acertos, nota = int(geral['acertos'].sum()), float(geral['nota_liquida'].sum())
    delta_acertos, delta_nota = impacto(diff, config.pontuacao)
    anuladas = int((diff['mudanca'] == 'anulada').sum())
    linhas = [
        '## Preliminar → Definitivo',
        '',
        f'{len(diff)} questões mudaram ({anuladas} anuladas). '
        f'Acertos: {acertos - delta_acertos} → {acertos}; '
        f'nota líquida: {formatar(nota - delta_nota)} → {formatar(nota)}.',
        '',
    ]
    if not diff.empty:
        linhas += [tabela_markdown(diff, COLUNAS_DIFF), '']
    return linhas


def tabela_markdown(dados: pd.DataFrame, colunas: list[str]) -> str:
    cabecalho = '| ' + ' | '.join(colunas) + ' |'
    separador = '|' + '|'.join('---' for _ in colunas) + '|'
    corpo = [
        '| ' + ' | '.join(str(valor) for valor in linha) + ' |'
        for linha in dados[colunas].itertuples(index=False)
    ]
    return '\n'.join([cabecalho, separador, *corpo])
