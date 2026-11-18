from pathlib import Path

from concursos.aplicacao.resultados import relatorios_disponiveis
from concursos.config.contexto import Contexto
from concursos.relatorio_html import ARQUIVO_INDICE, ARQUIVO_RELATORIO_HTML


def test_relatorios_disponiveis_lista_visao_geral_e_concursos(tmp_path: Path) -> None:
    analises = tmp_path / 'analises' / 'alice'
    analises.mkdir(parents=True)
    (analises / ARQUIVO_INDICE).write_text('<html></html>', encoding='utf-8')
    for nome in ('beta', 'alfa'):
        pasta = analises / nome
        pasta.mkdir()
        (pasta / ARQUIVO_RELATORIO_HTML).write_text('<html></html>', encoding='utf-8')
    (analises / 'sem_relatorio').mkdir()

    contexto = Contexto(
        raiz=tmp_path,
        home=tmp_path / 'home',
        projeto=tmp_path,
        provas=tmp_path / 'provas',
        analises=tmp_path / 'analises',
        candidato='alice',
    )
    opcoes = relatorios_disponiveis(contexto)

    assert [o.rotulo for o in opcoes] == ['Visão geral', 'alfa', 'beta']
    assert opcoes[0].caminho.name == ARQUIVO_INDICE
    assert opcoes[1].caminho.name == ARQUIVO_RELATORIO_HTML
