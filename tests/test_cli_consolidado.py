import re
from pathlib import Path

import pandas as pd
import yaml
from conftest import analisar, criar_concurso, ler_csv

EDITAL_MANUAL = {
    'conhecimentos': [
        {
            'nome': 'Conhecimentos Gerais',
            'disciplinas': [{'nome': 'Língua Portuguesa', 'topicos': ['Crase', 'Concordância']}],
        }
    ]
}


def criar(
    provas: Path,
    nome: str,
    gabarito: str,
    respostas: str | None,
    topicos: dict[int, str],
    status: str = 'definitivo',
):
    config = {
        'nome': nome,
        'banca': 'fgv',
        'formato': 'multipla_escolha',
        'pontuacao': 'simples',
        'edital': {'manual': 'edital_manual.yaml'},
        'provas': {'unica': {'gabarito': {'arquivo': 'gabarito.txt', 'status': status}, 'itens': [1, 4]}},
    }
    arquivos = {
        'gabarito.txt': gabarito,
        'edital_manual.yaml': yaml.safe_dump(EDITAL_MANUAL, allow_unicode=True),
    }
    if respostas is not None:
        config['respostas'] = {'arquivo': 'respostas.txt'}
        arquivos['respostas.txt'] = respostas
    pasta = criar_concurso(provas, nome, config, arquivos)
    revisao = pd.DataFrame(
        [
            {'questao': q, 'prova': 'unica', 'disciplina': 'Língua Portuguesa', 'topico': t}
            for q, t in topicos.items()
        ]
    )
    (pasta / 'revisao').mkdir()
    revisao.to_csv(pasta / 'revisao' / 'questoes_revisado.csv', index=False)
    return pasta


def tres_concursos(provas: Path) -> None:
    gabarito = '1 A\n2 B\n3 C\n4 D\n'
    criar(
        provas,
        'a',
        gabarito,
        '1 B\n2 C\n3 C\n4 D\n',
        {1: 'Crase', 2: 'Crase', 3: 'Concordância'},
        status='preliminar',
    )
    criar(
        provas,
        'b',
        gabarito,
        '1 B\n2 B\n3 C\n4 D\n',
        {1: 'CRASE', 2: 'CRASE', 3: 'Concordância', 4: 'Concordância'},
    )
    criar(
        provas,
        'c',
        gabarito,
        '1 A\n2 B\n3 C\n4 A\n',
        {1: 'Crase', 2: 'Crase', 3: 'Concordância', 4: 'Concordância'},
    )
    criar(provas, 'd', gabarito, None, {})


def secao(texto: str, titulo: str) -> str:
    return texto.split(f'## {titulo}', 1)[1].split('\n## ', 1)[0]


def test_comparativo_lista_topico_fraco_em_dois_concursos(raizes):
    provas, analises = raizes
    tres_concursos(provas)

    assert analisar(provas, analises) == 0

    comparativo = (analises / 'consolidado' / 'comparativo_concursos.md').read_text(encoding='utf-8')
    baixos = secao(comparativo, 'Tópicos consistentemente baixos')
    assert 'Crase' in baixos
    assert 'a (0%)' in baixos and 'b (50%)' in baixos
    assert 'c (' not in baixos
    assert 'Concordância' not in baixos


def test_consolidado_inclui_incompletos_e_status_do_gabarito(raizes):
    provas, analises = raizes
    tres_concursos(provas)

    analisar(provas, analises)

    comparativo = (analises / 'consolidado' / 'comparativo_concursos.md').read_text(encoding='utf-8')
    pendentes = secao(comparativo, 'Concursos incompletos ou desatualizados')
    assert '| d | incompleto |' in pendentes and 'respostas não configuradas' in pendentes
    por_concurso = secao(comparativo, 'Desempenho por concurso')
    assert '| a | preliminar |' in por_concurso
    assert '| b | definitivo |' in por_concurso
    assert '| d |' not in por_concurso


def test_relatorio_referencia_graficos_existentes_e_questoes_para_revisar(raizes):
    provas, analises = raizes
    tres_concursos(provas)

    analisar(provas, analises)

    destino = analises / 'a'
    relatorio = (destino / 'relatorio.md').read_text(encoding='utf-8')
    imagens = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', relatorio)
    assert {'graficos/desempenho_por_disciplina.png', 'graficos/desempenho_por_topico.png'} <= set(imagens)
    assert all((destino / imagem).stat().st_size > 0 for imagem in imagens)
    revisar = secao(relatorio, 'Questões para revisar')
    assert '| 4 |' in revisar
    assert '- Gabarito: preliminar' in relatorio


def test_desempenho_geral_soma_os_desempenhos_por_concurso(raizes):
    provas, analises = raizes
    tres_concursos(provas)

    analisar(provas, analises)

    geral = ler_csv(analises / 'consolidado' / 'desempenho_geral.csv')
    assert list(geral.columns[:8]) == [
        'concurso',
        'prova',
        'disciplina',
        'topico',
        'total',
        'acertos',
        'erros',
        'percentual',
    ]
    somas = geral.groupby('concurso')[['total', 'acertos', 'erros']].sum()
    assert sorted(somas.index) == ['a', 'b', 'c']
    for concurso in somas.index:
        por_disciplina = ler_csv(analises / concurso / 'desempenho_por_disciplina.csv')
        assert somas.loc[concurso].tolist() == por_disciplina[['total', 'acertos', 'erros']].sum().tolist()
