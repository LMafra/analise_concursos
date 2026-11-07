from dataclasses import dataclass, field

import pandas as pd

from concursos.analytics.correcao import NotaFinal
from concursos.analytics.regras_edital import Identificacao
from concursos.atualizacao import COLUNAS_DIFF, impacto
from concursos.concurso_config import ConcursoConfig
from concursos.correcao import TOPICO_NAO_MAPEADO
from concursos.linguagem import plural
from concursos.modelo import StatusGabarito
from concursos.resultado_oficial import Validacao, ValidacaoConferida, formatar
from concursos.texto import abreviar
from concursos.topicos import ARQUIVO_REVISAO, SCORE_BAIXO

MAXIMO_TOPICOS_FRACOS = 10
LIMITE_TOPICO = 150
TITULO_DETALHES_TECNICOS = 'Detalhes técnicos'
_TIPO_DE_PROVA = {'multipla_escolha': 'múltipla escolha', 'certo_errado': 'certo ou errado'}
_COMO_A_NOTA_E_CALCULADA = {
    'simples': 'cada acerto vale um ponto, e o erro não desconta',
    'cebraspe': 'cada acerto vale um ponto, e cada erro anula um acerto',
}
_GABARITO = {
    'preliminar': 'preliminar (provisório)',
    'definitivo': 'definitivo',
    'misto': 'preliminar em algumas provas e definitivo em outras',
}
_CABECALHOS = {
    'prova': 'Prova',
    'disciplina': 'Disciplina',
    'topico': 'Tópico',
    'total': 'Questões',
    'acertos': 'Acertos',
    'erros': 'Erros',
    'em_branco': 'Em branco',
    'percentual': 'Aproveitamento',
}


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
    identificacao: Identificacao | None = None


def gerar_relatorio(config: ConcursoConfig, conteudo: ConteudoRelatorio) -> str:
    """A parte principal em linguagem leiga; as tabelas com as colunas originais vão para `## Detalhes técnicos`,
    que o `relatorio.html` fecha num `<details>`."""
    fracos = _topicos_fracos(conteudo.por_topico)
    leitura = conteudo.respostas[conteudo.respostas['revisar']]
    sugestoes = _sugestoes_a_conferir(conteudo.questoes)
    linhas = [
        f'# Relatório de desempenho: {config.nome}',
        '',
        *_identificacao(conteudo.identificacao),
        f'- Banca: {config.banca}',
        f'- Tipo de prova: {_TIPO_DE_PROVA.get(str(config.formato), str(config.formato))}',
        f'- Como a nota é calculada: '
        f'{_COMO_A_NOTA_E_CALCULADA.get(str(config.pontuacao), str(config.pontuacao))}',
        f'- Gabarito: {_GABARITO.get(config.status_gabarito, config.status_gabarito)}',
        '',
        *_selo_preliminar(config),
        *_secao_validacao(conteudo.validacao),
        *_secao_resumo(conteudo.geral, conteudo.notas_finais),
        '## Desempenho por disciplina',
        '',
        tabela_legivel(
            conteudo.por_disciplina, ['prova', 'disciplina', 'total', 'acertos', 'erros', 'em_branco']
        ),
        '',
        *_secao_graficos(conteudo.graficos),
        *_secao_onde_errou(fracos),
        *_secao_o_que_conferir(leitura, conteudo.questoes, sugestoes),
        *_secao_troca(config, conteudo.geral, conteudo.diff),
        f'## {TITULO_DETALHES_TECNICOS}',
        '',
        *_detalhes_tecnicos(conteudo, fracos, leitura, sugestoes),
    ]
    return '\n'.join(linhas)


def _identificacao(identificacao: Identificacao | None) -> list[str]:
    if identificacao is None:
        return []
    linhas = []
    if nome := identificacao.nome_oficial.valor:
        edital = identificacao.edital.valor
        linhas.append(f'- Concurso: {nome} ({edital})' if edital else f'- Concurso: {nome}')
    if cargo := identificacao.cargo.valor:
        especialidade = identificacao.especialidade.valor
        linhas.append(f'- Cargo: {cargo} – {especialidade}' if especialidade else f'- Cargo: {cargo}')
    return linhas


def _selo_preliminar(config: ConcursoConfig) -> list[str]:
    preliminares = [p.chave for p in config.provas if p.gabarito.status is StatusGabarito.PRELIMINAR]
    if not preliminares:
        return []
    return [
        f'> **Gabarito preliminar (provisório)** nas provas {", ".join(preliminares)}: '
        'os resultados podem mudar quando o definitivo sair.',
        '',
    ]


def _secao_resumo(geral: pd.DataFrame, notas: list[NotaFinal]) -> list[str]:
    linhas = ['## Resumo', '']
    for prova in geral.itertuples(index=False):
        anuladas = int(prova.anuladas)
        linhas.append(
            f'- Prova {prova.prova}: {plural(int(prova.acertos), "acerto")} em '
            f'{plural(int(prova.total), "questão", "questões")}, aproveitamento de '
            f'{formatar(float(prova.percentual))}%; nota depois dos descontos: '
            f'{formatar(float(prova.nota_liquida))}.'
            + (f' {plural(anuladas, "questão anulada", "questões anuladas")}.' if anuladas else '')
        )
    return [
        *linhas,
        '',
        '_Questões anuladas contam como acerto, mas ficam fora do aproveitamento._',
        '',
        *_secao_nota_final(notas),
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
    if isinstance(validacao, ValidacaoConferida):
        linhas += [f'_Fonte: {validacao.arquivo}, página {validacao.oficial.pagina}._', '']
    return linhas


def _secao_graficos(graficos: dict[str, str]) -> list[str]:
    if not graficos:
        return []
    return ['## Gráficos', '', *(f'![{titulo}]({caminho})\n' for titulo, caminho in graficos.items())]


def _topicos_fracos(por_topico: pd.DataFrame) -> pd.DataFrame:
    mapeados = por_topico[por_topico['topico'] != TOPICO_NAO_MAPEADO]
    fracos = mapeados.sort_values(['percentual', 'total'], ascending=[True, False]).head(
        MAXIMO_TOPICOS_FRACOS
    )
    return fracos.assign(topico=[abreviar(topico, LIMITE_TOPICO) for topico in fracos['topico']])


def _secao_onde_errou(fracos: pd.DataFrame) -> list[str]:
    if fracos.empty:
        return []
    return [
        '## Onde você mais errou',
        '',
        f'Os {plural(len(fracos), "tópico")} com menor aproveitamento nesta prova.',
        '',
        tabela_legivel(fracos, ['prova', 'disciplina', 'topico', 'total', 'acertos', 'erros']),
        '',
    ]


def _sem_tema(questoes: pd.DataFrame) -> bool:
    return bool((questoes['topico'] == TOPICO_NAO_MAPEADO).all() and not questoes['revisado'].any())


def _sugestoes_a_conferir(questoes: pd.DataFrame) -> pd.DataFrame:
    if _sem_tema(questoes):
        return questoes.iloc[0:0]
    return questoes[~questoes['revisado'] & (questoes['score'] < SCORE_BAIXO)]


def _numeros(questoes: pd.Series) -> str:
    return ', '.join(str(numero) for numero in questoes)


def _secao_o_que_conferir(
    leitura: pd.DataFrame, questoes: pd.DataFrame, sugestoes: pd.DataFrame
) -> list[str]:
    linhas = ['## O que conferir', '']
    if not leitura.empty:
        linhas.append(
            f'- {plural(len(leitura), "resposta lida da folha ficou incerta", "respostas lidas da folha ficaram incertas")} '
            f'(questões {_numeros(leitura["questao"])}). Confira na folha; se alguma estiver errada, digite as '
            'respostas na tela do concurso (Digitar respostas).'
        )
    if _sem_tema(questoes):
        linhas.append(
            '- As questões ficaram sem tema, porque o app não leu o conteúdo do edital ou o texto da prova.'
        )
    elif not sugestoes.empty:
        linhas.append(
            f'- {plural(len(sugestoes), "tema escolhido pelo app pode estar errado", "temas escolhidos pelo app podem estar errados")} '
            f'(questões {_numeros(sugestoes["questao"])}). Confira em Concursos > Conferir.'
        )
    if len(linhas) == 2:
        linhas.append(
            'Nada a conferir: as respostas foram lidas com segurança, e os temas estão confirmados.'
        )
    return [*linhas, '']


def _detalhes_tecnicos(
    conteudo: ConteudoRelatorio, fracos: pd.DataFrame, leitura: pd.DataFrame, sugestoes: pd.DataFrame
) -> list[str]:
    linhas = [
        '### Resumo por prova',
        '',
        tabela_markdown(
            conteudo.geral,
            ['prova', 'total', 'acertos', 'erros', 'em_branco', 'anuladas', 'nota_liquida', 'percentual'],
        ),
        '',
    ]
    if not fracos.empty:
        linhas += [
            f'### Tópicos com menor desempenho (até {MAXIMO_TOPICOS_FRACOS})',
            '',
            tabela_markdown(
                fracos, ['prova', 'disciplina', 'topico', 'total', 'acertos', 'erros', 'percentual']
            ),
            '',
        ]
    linhas += ['### Leitura das respostas abaixo do limiar de confiança', '']
    if leitura.empty:
        linhas += ['Nenhuma.', '']
    else:
        linhas += [
            tabela_markdown(
                leitura,
                ['questao', 'prova', 'alternativa_marcada', 'estado', 'confianca_ocr', 'arquivo', 'pagina'],
            ),
            '',
        ]
    linhas += ['### Sugestões de tópico com score baixo', '']
    if _sem_tema(conteudo.questoes):
        linhas += ['Nenhum tópico classificado (sem edital estruturado ou sem texto do caderno).', '']
    elif sugestoes.empty:
        linhas += ['Nenhuma.', '']
    else:
        linhas += [
            f'Score abaixo de {formatar(SCORE_BAIXO)}, ainda não revisadas; a revisão fica em `{ARQUIVO_REVISAO}` '
            '(colunas disciplina e topico).',
            '',
            tabela_markdown(sugestoes, ['questao', 'prova', 'disciplina', 'topico', 'score']),
            '',
        ]
    if conteudo.diff is not None and not conteudo.diff.empty:
        linhas += ['### Mudanças do gabarito', '', tabela_markdown(conteudo.diff, COLUNAS_DIFF), '']
    return linhas


def _secao_troca(config: ConcursoConfig, geral: pd.DataFrame, diff: pd.DataFrame | None) -> list[str]:
    if diff is None:
        return []
    acertos, nota = int(geral['acertos'].sum()), float(geral['nota_liquida'].sum())
    delta_acertos, delta_nota = impacto(diff, config.pontuacao)
    anuladas = int((diff['mudanca'] == 'anulada').sum())
    return [
        '## Gabarito preliminar → definitivo',
        '',
        f'{plural(len(diff), "questão mudou", "questões mudaram")} ({anuladas} anuladas). '
        f'Acertos: {acertos - delta_acertos} → {acertos}; '
        f'nota depois dos descontos: {formatar(nota - delta_nota)} → {formatar(nota)}.',
        '',
    ]


def tabela_legivel(dados: pd.DataFrame, colunas: list[str]) -> str:
    """Cabeçalhos em português e o aproveitamento com `%`, para a parte principal do relatório."""
    legivel = dados[[*colunas, 'percentual']].assign(
        percentual=[f'{formatar(float(valor))}%' for valor in dados['percentual']]
    )
    return tabela_markdown(
        legivel.rename(columns=_CABECALHOS), [_CABECALHOS[c] for c in [*colunas, 'percentual']]
    )


def tabela_markdown(dados: pd.DataFrame, colunas: list[str]) -> str:
    cabecalho = '| ' + ' | '.join(colunas) + ' |'
    separador = '|' + '|'.join('---' for _ in colunas) + '|'
    corpo = [
        '| ' + ' | '.join(str(valor) for valor in linha) + ' |'
        for linha in dados[colunas].itertuples(index=False)
    ]
    return '\n'.join([cabecalho, separador, *corpo])
