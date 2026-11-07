"""Achados da análise evolutiva: as quatro respostas do notebook de insights, a sensibilidade sem os
concursos de nível médio e o relatório de evolução em markdown."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from concursos.analytics.catalogo_edital import texto_do_valor
from concursos.analytics.consolidado import N_MINIMO_TOPICO, pasta_consolidado
from concursos.analytics.correcao import NotaFinal
from concursos.analytics.evolucao import (
    LIMIAR_TOPICO_FRACO,
    METRICAS_DO_RANKING,
    MINIMO_PONTOS_TENDENCIA,
    TENDENCIA,
    Correlacao,
    comparar_bruto_vs_corrigido,
    comparar_com_meta,
    correlacao_tempo_percentual,
    correlacao_tempo_zscore,
    percentual_por_topico,
    tendencia_por_disciplina,
    topicos_fracos_persistentes,
    zscore_por_disciplina,
)
from concursos.analytics.nome_concurso import NomeDoConcurso as NomeDoConcurso
from concursos.analytics.nome_concurso import nome_do_concurso as nome_do_concurso
from concursos.analytics.nome_concurso import rotulo_do_concurso as rotulo_do_concurso
from concursos.analytics.nome_concurso import rotulos_dos_concursos as rotulos_dos_concursos
from concursos.analytics.pistas_edital import CANDIDATOS, Impacto
from concursos.analytics.regras_edital import NAO_CALCULAVEIS, EscopoCorte, StatusExtracao, UnidadeCorte
from concursos.analytics.visualizacao import (
    exportar_heatmap_topicos,
    exportar_linha_evolucao,
    exportar_painel_correcao,
    rotulo_com_variante,
)
from concursos.consolidado import MINIMO_CONCURSOS
from concursos.modelo import Escolaridade, ModeloCorrecao

_FORA_DO_PAINEL = {'aprovacao'}
"""A régua de aprovação já é a dos cortes, na tabela de gap."""
_ALVO_DO_CORTE = {
    EscopoCorte.CONJUNTO: 'no conjunto',
    EscopoCorte.GERAL: 'nos conhecimentos gerais',
    EscopoCorte.ESPECIFICO: 'nos conhecimentos específicos',
    EscopoCorte.DISCIPLINA: 'em cada disciplina',
}
_DO_BLOCO = {
    EscopoCorte.GERAL: 'dos conhecimentos gerais',
    EscopoCorte.ESPECIFICO: 'dos conhecimentos específicos',
}
P_SIGNIFICATIVO = 0.05
TENDENCIAS_LISTADAS = 3
ARQUIVO_RELATORIO = 'relatorio_evolucao.md'
IMAGEM_LINHA = 'evolucao_zscore.png'
IMAGEM_HEATMAP = 'heatmap_topicos.png'
IMAGEM_PAINEL = 'painel_correcao.png'
_P = f'p < {P_SIGNIFICATIVO:.2f}'.replace('.', ',')
_SERIE_SUFICIENTE = f'{MINIMO_PONTOS_TENDENCIA} concursos ou mais com n ≥ {N_MINIMO_TOPICO}'
PERGUNTAS = (
    f'Em quais disciplinas melhorei de forma significativa ({_P})?',
    'Quais tópicos continuam fracos?',
    'Qual a correlação entre a ordem e o z-score médio?',
    'O ranking de concursos muda entre bruto, corrigido e ajustado?',
)


@dataclass(frozen=True)
class Achados:
    """Tabelas que respondem às quatro perguntas, todas no ajustado ao acaso."""

    tendencias: pd.DataFrame
    correlacoes: pd.DataFrame
    correlacao_geral: Correlacao
    fracos: pd.DataFrame
    ranking: pd.DataFrame
    limiar: float

    @property
    def com_tendencia(self) -> pd.DataFrame:
        return self.tendencias[self.tendencias['situacao'] == TENDENCIA]

    @property
    def nao_significativas(self) -> pd.DataFrame:
        return self.com_tendencia[~(self.com_tendencia['p_valor'] < P_SIGNIFICATIVO)]

    @property
    def melhoras(self) -> pd.DataFrame:
        return self._significativas(self.com_tendencia['slope'] > 0)

    @property
    def pioras(self) -> pd.DataFrame:
        return self._significativas(self.com_tendencia['slope'] < 0)

    @property
    def mudancas_de_posicao(self) -> pd.DataFrame:
        ranking = self.ranking
        return ranking[(ranking['deslocamento_corrigida'] != 0) | (ranking['deslocamento_ajustada'] != 0)]

    def _significativas(self, sentido: pd.Series) -> pd.DataFrame:
        tabela = self.com_tendencia
        return tabela[sentido & (tabela['p_valor'] < P_SIGNIFICATIVO)]


def calcular_achados(consolidado: pd.DataFrame, limiar: float = LIMIAR_TOPICO_FRACO) -> Achados:
    return Achados(
        tendencias=tendencia_por_disciplina(consolidado),
        correlacoes=correlacao_tempo_zscore(consolidado),
        correlacao_geral=correlacao_tempo_percentual(consolidado),
        fracos=topicos_fracos_persistentes(consolidado, limiar=limiar),
        ranking=comparar_bruto_vs_corrigido(consolidado),
        limiar=limiar,
    )


def sem_nivel_medio(consolidado: pd.DataFrame) -> pd.DataFrame:
    return consolidado[consolidado['escolaridade'] != Escolaridade.MEDIO]


def respostas(achados: Achados) -> list[str]:
    """As respostas às PERGUNTAS, em markdown e com os números (slope, p, n e posições)."""
    return [
        _resposta_melhoras(achados),
        _resposta_fracos(achados),
        _resposta_correlacao(achados),
        _resposta_ranking(achados),
    ]


def respostas_em_markdown(achados: Achados) -> str:
    return '\n\n'.join(
        f'## {numero}. {pergunta}\n\n{resposta}'
        for numero, (pergunta, resposta) in enumerate(
            zip(PERGUNTAS, respostas(achados), strict=True), start=1
        )
    )


def diferencas(com: Achados, sem: Achados) -> list[str]:
    """O que muda nos achados principais quando os concursos de nível médio saem da base."""
    return [
        _comparar(
            'Disciplinas com melhora significativa', _disciplinas(com.melhoras), _disciplinas(sem.melhoras)
        ),
        _comparar('Disciplinas com piora significativa', _disciplinas(com.pioras), _disciplinas(sem.pioras)),
        _comparar('Tópicos fracos persistentes', list(com.fracos['topico']), list(sem.fracos['topico'])),
        f'Correlação geral: {_correlacao(com.correlacao_geral)} com o nível médio; '
        f'{_correlacao(sem.correlacao_geral)} sem ele.',
        _comparar_ranking(com.ranking, sem.ranking),
    ]


def sensibilidade_em_markdown(consolidado: pd.DataFrame, com: Achados) -> str:
    """As diferenças sem os concursos de nível médio, em lista, ou o aviso de que não há nenhum."""
    medios = sorted(consolidado.loc[consolidado['escolaridade'] == Escolaridade.MEDIO, 'concurso'].unique())
    if not medios:
        return 'Nenhum concurso de nível médio na base.'
    sem = calcular_achados(sem_nivel_medio(consolidado), com.limiar)
    itens = '\n'.join(f'- {texto}' for texto in diferencas(com, sem))
    return f'Os achados recalculados sem {_lista(medios)} (nível médio):\n\n{itens}'


def gravar_relatorio_evolucao(
    consolidado: pd.DataFrame,
    pasta: Path | None = None,
    limiar: float = LIMIAR_TOPICO_FRACO,
    achados: Achados | None = None,
) -> Path:
    """Grava as três imagens (linha, heatmap e painel) e o relatório com as quatro respostas e a
    sensibilidade sem o nível médio. Sem pasta, usa a do consolidado."""
    pasta = pasta or pasta_consolidado()
    achados = achados or calcular_achados(consolidado, limiar)
    exportar_linha_evolucao(zscore_por_disciplina(consolidado), pasta / IMAGEM_LINHA)
    exportar_heatmap_topicos(
        percentual_por_topico(consolidado, min_concursos=MINIMO_CONCURSOS), pasta / IMAGEM_HEATMAP
    )
    exportar_painel_correcao(achados.ranking, pasta / IMAGEM_PAINEL)
    figuras = (
        (IMAGEM_LINHA, f'Evolução do z-score: só disciplinas com {_SERIE_SUFICIENTE}'),
        (
            IMAGEM_HEATMAP,
            f'Percentual por tópico e concurso: tópicos em {MINIMO_CONCURSOS} concursos ou mais',
        ),
        (IMAGEM_PAINEL, 'Painel de correção: bruto, corrigido e ajustado por concurso'),
    )
    linhas = [
        '# Relatório de evolução',
        '',
        f'{len(consolidado)} questões de {consolidado["concurso"].nunique()} concursos. Os percentuais são '
        'ajustados ao acaso, e a evolução se lê pelo z-score.',
        '',
        respostas_em_markdown(achados),
        '',
        '## Sensibilidade: sem o nível médio',
        '',
        sensibilidade_em_markdown(consolidado, achados),
        '',
        '## Nota final pela regra do edital',
        '',
        notas_finais_em_markdown(consolidado),
        '',
        '## Figuras',
        '',
        *(f'![{legenda}]({nome})\n' for nome, legenda in figuras),
    ]
    relatorio = pasta / ARQUIVO_RELATORIO
    relatorio.write_text('\n'.join(linhas), encoding='utf-8')
    return relatorio


def notas_finais_em_markdown(consolidado: pd.DataFrame) -> str:
    """Só os concursos em que a nota difere da contagem de acertos (desconto por erro ou pesos)."""
    meta = comparar_com_meta(consolidado)
    com_regra = meta[meta['modelo_correcao'] != ModeloCorrecao.BRUTA]
    if com_regra.empty:
        return 'Nenhum concurso com desconto por erro ou pesos.'
    return '\n'.join(
        f'- {rotulo_com_variante(linha.concurso, linha.variante)}: '
        f'{NotaFinal(linha.nota, linha.nota_maxima, _ou_none(linha.nota_corte)).texto}.'
        for linha in com_regra.itertuples()
    )


def descrever_simulacao(simulacao: pd.DataFrame, disciplina: str, pontos_percentuais: float) -> str:
    """O texto de `simular_cenario`: sempre estimativa de cenário, sem colocação e sem linguagem de
    previsão."""
    cabecalho = (
        f'**Estimativa de cenário** (+{pontos_percentuais:g} p.p. em {disciplina}): não é previsão de '
        'resultado nem estima colocação, porque o projeto não tem as notas dos outros candidatos.'
    )
    if simulacao.empty:
        return f'{cabecalho}\n\nNenhum concurso com {disciplina} e cortes do edital.'
    partes = [cabecalho]
    for (concurso, variante), linhas in simulacao.groupby(['concurso', 'variante'], dropna=False, sort=False):
        primeira = linhas.iloc[0]
        cortes = '; '.join(
            f'{_escopo_do_corte(linha)}: nota {linha.nota_atual:g} → {linha.nota_estimada:g}, '
            f'gap {linha.gap_atual:+g} → {linha.gap_estimado:+g} {linha.unidade}'
            for linha in linhas.itertuples()
        )
        partes.append(
            f'- {rotulo_com_variante(concurso, variante)}: '
            f'{_contagem(primeira.itens_convertidos, "item vira", "itens viram")} acerto '
            f'({_contagem(primeira.erros_convertidos, "erro", "erros")} e '
            f'{_contagem(primeira.brancos_convertidos, "branco", "brancos")}). {cortes}. '
            'Todos os cortes satisfeitos no cenário: '
            f'{"sim" if primeira.atingido_estimado else "não"}.'
        )
    return '\n\n'.join(partes)


def _contagem(n: int, singular: str, plural: str) -> str:
    return f'{n} {singular if n == 1 else plural}'


def _escopo_do_corte(linha) -> str:
    return linha.escopo if pd.isna(linha.disciplina) else f'{linha.escopo} {linha.disciplina}'


def destaque_do_ranking(ranking: pd.DataFrame) -> str:
    """O destaque em markdown de `ranking_concursos_por_metrica`: quem sobe e quem cai em cada métrica."""
    frases = []
    for metrica in METRICAS_DO_RANKING[1:]:
        mudancas = ranking[ranking[f'deslocamento_{metrica}'] != 0].sort_values(
            [f'deslocamento_{metrica}', 'concurso'], ascending=[False, True]
        )
        if mudancas.empty:
            continue
        partes = '; '.join(
            f'{rotulo_com_variante(linha["concurso"], linha["variante"])} {"sobe" if linha[f"deslocamento_{metrica}"] > 0 else "cai"} '
            f'{_contagem(abs(linha[f"deslocamento_{metrica}"]), "posição", "posições")}'
            for _, linha in mudancas.iterrows()
        )
        frases.append(f'No {metrica}: {partes}.')
    if not frases:
        return 'O ranking é o mesmo no bruto, no corrigido e no ponderado.'
    return '> **O ranking muda entre as métricas.** ' + ' '.join(frases)


def peculiaridades_do_edital(regras: Mapping[str, dict], concurso_alvo: str | None = None) -> pd.DataFrame:
    """As regras que surpreendem: as descobertas de alto impacto encontradas e os cortes em acertos e da
    discursiva, com o trecho do edital."""
    alto_impacto = {
        c.chave: c for c in CANDIDATOS if c.impacto is Impacto.ALTO and c.chave not in _FORA_DO_PAINEL
    }
    linhas = []
    for concurso, dados in regras.items():
        if concurso_alvo is not None and concurso != concurso_alvo:
            continue
        for metadado in dados.get('metadados', []):
            candidato = alto_impacto.get(metadado['chave'])
            if candidato is None or metadado['status'] != StatusExtracao.ENCONTRADO:
                continue
            linhas.append(
                {
                    'concurso': concurso,
                    'peculiaridade': candidato.informacao,
                    'valor': texto_do_valor(metadado['valor']),
                    'uso': candidato.uso,
                    'trecho': metadado['trecho_origem'],
                }
            )
        for corte in dados.get('cortes', []):
            if corte['escopo'] == EscopoCorte.DISCURSIVA:
                peculiaridade, valor = 'Corte da discursiva', f'{corte["valor"]:g} {corte["unidade"]}'
                uso = 'Registrado e exibido, fora do "atingido"'
            elif not UnidadeCorte(corte['unidade']).calculavel:
                peculiaridade = 'Corte não calculável'
                valor = NAO_CALCULAVEIS[corte['unidade']]
                if corte['valor'] is not None:
                    valor += f' (mínimo {corte["valor"]:g})'
                uso = 'Depende das notas dos outros candidatos: registrado com aviso, fora do "atingido"'
            elif corte['unidade'] == UnidadeCorte.ACERTOS:
                peculiaridade = 'Corte em acertos'
                acertos = 'acerto' if corte['valor'] == 1 else 'acertos'
                valor = f'{corte["valor"]:g} {acertos} {_ALVO_DO_CORTE[corte["escopo"]]}'
                if corte['escopo'] == EscopoCorte.DISCIPLINA and corte.get('bloco'):
                    valor += f' {_DO_BLOCO[corte["bloco"]]}'
                uso = 'O gap desse corte conta acertos, com a anulada valendo acerto'
            else:
                continue
            linhas.append(
                {
                    'concurso': concurso,
                    'peculiaridade': peculiaridade,
                    'valor': valor,
                    'uso': uso,
                    'trecho': corte.get('trecho_origem'),
                }
            )
    return pd.DataFrame(linhas, columns=['concurso', 'peculiaridade', 'valor', 'uso', 'trecho'])


def desempate_por_concurso(regras: Mapping[str, dict], concurso_alvo: str | None = None) -> pd.DataFrame:
    """Os critérios de desempate de cada concurso na ordem do edital, sem cálculo."""
    linhas = [
        {'concurso': concurso, 'prioridade': prioridade, 'criterio': criterio}
        for concurso, dados in regras.items()
        if concurso_alvo is None or concurso == concurso_alvo
        for metadado in dados.get('metadados', [])
        if metadado['chave'] == 'desempate' and isinstance(metadado['valor'], list)
        for prioridade, criterio in enumerate(metadado['valor'], 1)
    ]
    return pd.DataFrame(linhas, columns=['concurso', 'prioridade', 'criterio'])


def _ou_none(valor: float) -> float | None:
    return None if pd.isna(valor) else float(valor)


def _resposta_melhoras(achados: Achados) -> str:
    contexto = f'{len(achados.com_tendencia)} de {len(achados.tendencias)} séries de disciplina têm {_SERIE_SUFICIENTE}.'
    if achados.melhoras.empty:
        partes = [f'Nenhuma disciplina melhorou de forma significativa ({_P}). {contexto}']
        mais_fortes = achados.nao_significativas.head(TENDENCIAS_LISTADAS)
        if not mais_fortes.empty:
            partes += ['As tendências de menor p, ainda não significativas:', _itens(mais_fortes, _tendencia)]
    else:
        partes = [
            f'Melhoraram de forma significativa ({_P}). {contexto}',
            _itens(achados.melhoras, _tendencia),
        ]
    if not achados.pioras.empty:
        partes += [f'Pioraram de forma significativa ({_P}):', _itens(achados.pioras, _tendencia)]
    return '\n\n'.join(partes)


def _resposta_fracos(achados: Achados) -> str:
    criterio = (
        f'abaixo de {_numero(100 * achados.limiar, 0)}% (ajustado) em {MINIMO_CONCURSOS} concursos ou mais, '
        f'com n somado ≥ {N_MINIMO_TOPICO}'
    )
    if achados.fracos.empty:
        return f'Nenhum tópico fica {criterio}.'
    return '\n\n'.join(
        [
            f'{len(achados.fracos)} tópicos ficam {criterio}, do mais fraco para o mais forte:',
            _itens(achados.fracos, _fraco),
        ]
    )


def _resposta_correlacao(achados: Achados) -> str:
    partes = [
        'A média dos z-scores de um concurso fica perto de 0 por construção, então ela não mede tendência. A '
        'medida geral é a correlação entre a ordem e o percentual ajustado de cada concurso: '
        f'{_correlacao(achados.correlacao_geral)}.'
    ]
    por_disciplina = achados.correlacoes.dropna(subset=['rho'])
    if not por_disciplina.empty:
        partes.append(
            f'Por disciplina (Spearman entre a ordem e o z-score), {(por_disciplina["rho"] > 0).sum()} de '
            f'{len(por_disciplina)} séries têm ρ positivo e {(por_disciplina["rho"] < 0).sum()}, negativo; '
            f'{(por_disciplina["p_valor"] < P_SIGNIFICATIVO).sum()} com {_P}.'
        )
    return ' '.join(partes)


def _resposta_ranking(achados: Achados) -> str:
    mudancas = achados.mudancas_de_posicao
    total = len(achados.ranking)
    if mudancas.empty:
        return f'O ranking não muda entre bruto, corrigido e ajustado ({total} linhas).'
    maior = int(mudancas[['deslocamento_corrigida', 'deslocamento_ajustada']].abs().to_numpy().max())
    return '\n\n'.join(
        [
            f'O ranking muda: {len(mudancas)} de {total} linhas mudam de posição, até {maior} posições.',
            _itens(mudancas, _posicao),
        ]
    )


def _comparar_ranking(com: pd.DataFrame, sem: pd.DataFrame) -> str:
    juntos = com.merge(sem, on=['concurso', 'variante'], suffixes=('_com', '_sem'))
    mudou = juntos[juntos['deslocamento_ajustada_com'] != juntos['deslocamento_ajustada_sem']]
    if mudou.empty:
        return 'Ranking: o deslocamento entre bruto e ajustado de cada concurso é o mesmo sem o nível médio.'
    descricoes = [
        f'{rotulo_com_variante(linha["concurso"], linha["variante"])} ({_numero(linha["deslocamento_ajustada_com"], 0, sinal=True)} → '
        f'{_numero(linha["deslocamento_ajustada_sem"], 0, sinal=True)})'
        for _, linha in mudou.iterrows()
    ]
    return f'Ranking: sem o nível médio, muda o deslocamento entre bruto e ajustado de {_lista(descricoes)}.'


def _tendencia(linha: pd.Series) -> str:
    return (
        f'**{linha["disciplina"]}** ({linha["bloco"]}): slope {_numero(linha["slope"], 2, sinal=True)} z por '
        f'concurso, p = {_numero(linha["p_valor"], 3)}, n = {linha["n"]}, {linha["pontos"]} concursos'
    )


def _fraco(linha: pd.Series) -> str:
    abaixo = linha['concursos_abaixo']
    return (
        f'**{linha["topico"]}** ({linha["disciplina"]}): {_numero(linha["percentual"], 0)}% em '
        f'n = {linha["n"]}, abaixo em {len(abaixo)} de {linha["concursos"]} concursos ({", ".join(abaixo)})'
    )


def _posicao(linha: pd.Series) -> str:
    return (
        f'{rotulo_com_variante(linha["concurso"], linha["variante"])}: {linha["posicao_bruta"]}º no bruto, {linha["posicao_corrigida"]}º no corrigido, '
        f'{linha["posicao_ajustada"]}º no ajustado'
    )


def _correlacao(correlacao: Correlacao) -> str:
    if pd.isna(correlacao.rho):
        return f'sem correlação (menos de {MINIMO_PONTOS_TENDENCIA} pontos distintos ao longo da ordem)'
    return (
        f'ρ = {_numero(correlacao.rho, 2, sinal=True)}, p = {_numero(correlacao.p_valor, 3)}, '
        f'{correlacao.pontos} concursos'
    )


def _comparar(rotulo: str, com: list[str], sem: list[str]) -> str:
    if set(com) == set(sem):
        return f'{rotulo}: {_lista(com) if com else "nenhum caso"}, com ou sem o nível médio.'
    mudancas = [
        f'{verbo} {_lista(nomes)}'
        for verbo, nomes in (
            ('saem', [nome for nome in com if nome not in sem]),
            ('entram', [nome for nome in sem if nome not in com]),
        )
        if nomes
    ]
    return f'{rotulo}: sem o nível médio, {"; ".join(mudancas)}.'


def _disciplinas(tabela: pd.DataFrame) -> list[str]:
    return [
        f'{disciplina} ({bloco})'
        for disciplina, bloco in zip(tabela['disciplina'], tabela['bloco'], strict=True)
    ]


def _itens(tabela: pd.DataFrame, descrever: Callable[[pd.Series], str]) -> str:
    return '\n'.join(f'- {descrever(linha)}.' for _, linha in tabela.iterrows())


def _lista(nomes: list[str]) -> str:
    return nomes[0] if len(nomes) == 1 else f'{", ".join(nomes[:-1])} e {nomes[-1]}'


def _numero(valor: float, casas: int, sinal: bool = False) -> str:
    return f'{valor:{"+" if sinal else ""}.{casas}f}'.replace('.', ',')
