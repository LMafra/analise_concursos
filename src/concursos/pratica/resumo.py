import pandas as pd

from concursos.analytics.consolidado import N_MINIMO_TOPICO
from concursos.pratica.nomes import ARQUIVO_ERROS
from concursos.topicos import NAO_MAPEADO, chave_de_palavras

FORA_DO_EDITAL = 'fora_do_edital'
MAXIMO_REPETIDOS = 20


def _numero(valor: float) -> str:
    return f'{float(valor):.1f}'.replace('.', ',')


def _celula(valor) -> str:
    from concursos.texto import abreviar

    texto = ' '.join(str(valor if valor not in (None, '') else '—').split())
    return abreviar(texto, 80).replace('|', '\\|')


def _rotulo_do_topico(topico: str) -> str:
    return {NAO_MAPEADO: 'não mapeado', FORA_DO_EDITAL: 'fora do edital'}.get(topico, topico)


def _desempenho(acertos: int, n: int) -> str:
    if n < N_MINIMO_TOPICO:
        return f'poucas questões para avaliar ({n})'
    return f'{_numero(100 * acertos / n)}% de {n} questões'


def _plural(n: int, singular: str, plural: str) -> str:
    return f'{n} {singular if n == 1 else plural}'


def _prioridades(repetidos: list[dict], fracos: pd.DataFrame | None) -> list[str]:
    if fracos is None or fracos.empty:
        return ['Nenhum tópico ficou abaixo do esperado em mais de um concurso.', '']
    por_topico: dict[str, list[dict]] = {}
    for e in repetidos:
        if e['topico'] not in (NAO_MAPEADO, FORA_DO_EDITAL):
            por_topico.setdefault(chave_de_palavras(e['topico']), []).append(e)
    linhas = []
    for fraco in fracos.itertuples():
        if cruzados := por_topico.get(chave_de_palavras(str(fraco.topico))):
            linhas.append(
                f'| {_celula(fraco.disciplina)} | {_celula(cruzados[0]["topico"])} | '
                f'{_numero(fraco.percentual)}% de {int(fraco.n)} questões | {len(cruzados)} |'
            )
    if not linhas:
        return ['Nenhum tópico fraco da prova tem questão errada mais de uma vez no TEC.', '']
    cabecalho = [
        '| Disciplina | Tópico | Na prova, descontado o chute | Questões erradas mais de uma vez no TEC |',
        '|---|---|---|---|',
    ]
    return [*cabecalho, *linhas, '']


def resumo_markdown(
    erros: list[dict], cadernos: list[dict], desempenho: list[dict], fracos: pd.DataFrame | None
) -> str:
    """A seção "Prática no TEC" do `index.html`: prioridade de revisão, erros repetidos e desempenho."""
    repetidos = [e for e in erros if e['v'] >= 2]
    resolvidas = sum(c['resolvidas'] for c in cadernos)
    linhas = [
        '# Prática no TEC',
        '',
        f'{_plural(len(erros), "erro registrado", "erros registrados")} '
        f'({_plural(len(repetidos), "repetido", "repetidos")}, errado 2 vezes ou mais); '
        f'{_plural(resolvidas, "questão resolvida", "questões resolvidas")} nos cadernos acompanhados.',
        '',
        '## O que revisar primeiro',
        '',
        'Tópicos que ficaram abaixo do esperado em mais de um concurso e em que você também errou a mesma '
        'questão mais de uma vez no TEC.',
        '',
        *_prioridades(repetidos, fracos),
        '## Questões que você errou mais de uma vez',
        '',
    ]
    if repetidos:
        linhas += [
            '| Vezes | Tópico do edital | Assunto no TEC | Última vez | Disciplina |',
            '|---|---|---|---|---|',
        ]
        linhas += [
            f'| {e["v"]} | {_celula(_rotulo_do_topico(e["topico"]))} | {_celula(e["assunto"])} | '
            f'{_celula(e["ultima_data"])} | {_celula(e["disciplina"])} |'
            for e in repetidos[:MAXIMO_REPETIDOS]
        ]
        if len(repetidos) > MAXIMO_REPETIDOS:
            linhas += ['', f'Mais {len(repetidos) - MAXIMO_REPETIDOS} em `pratica/{ARQUIVO_ERROS}`.']
    else:
        linhas.append('Nenhuma questão errada mais de uma vez.')
    linhas += ['', '## Cadernos acompanhados', '']
    if cadernos:
        linhas += ['| Caderno | Modo | Acertos | Desempenho |', '|---|---|---|---|']
        linhas += [
            f'| {_celula(c["caderno"] or c["id"])} | {c["modo"]} | {c["acertos"]} | '
            f'{_desempenho(c["acertos"], c["resolvidas"])} |'
            for c in cadernos
        ]
    else:
        linhas.append('Nenhum caderno acompanhado.')
    if desempenho:
        linhas += ['', '## Desempenho por disciplina', '']
        linhas += ['| Disciplina | Nos cadernos | Erros registrados | Repetidos |', '|---|---|---|---|']
        linhas += [
            f'| {_celula(d["disciplina"])} | {_desempenho(d["acertos"], d["n"])} | {d["erros_registrados"]} | '
            f'{d["repetidos"]} |'
            for d in desempenho
        ]
    return '\n'.join(linhas).rstrip() + '\n'
