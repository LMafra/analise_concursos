from pathlib import Path

from concursos.aplicacao.resultados import resultados
from concursos.config.contexto import resolver_contexto


def test_sem_analise_nada_existe_ainda(tmp_path: Path):
    (tmp_path / 'provas').mkdir()

    achados = resultados(resolver_contexto(cwd=tmp_path, data_dir=tmp_path / '.concurso'))

    assert achados.pasta == tmp_path / 'analises'
    assert achados.indice is None
    assert achados.recomendacoes is None
    assert achados.pratica is None
    assert achados.tabelas_pratica == {}


def test_acha_relatorio_recomendacoes_e_pratica_do_candidato(tmp_path: Path):
    (tmp_path / 'provas').mkdir()
    pasta = tmp_path / 'analises' / 'ana_teste'
    (pasta / 'consolidado').mkdir(parents=True)
    (pasta / 'pratica').mkdir()
    (pasta / 'index.html').write_text('<html></html>', encoding='utf-8')
    (pasta / 'consolidado' / 'recomendacoes_estudo.md').write_text('# Estudar crase', encoding='utf-8')
    (pasta / 'pratica' / 'resumo_pratica.md').write_text('# Prática', encoding='utf-8')
    (pasta / 'pratica' / 'erros_tec.csv').write_text('id\n1\n', encoding='utf-8')

    achados = resultados(
        resolver_contexto(cwd=tmp_path, data_dir=tmp_path / '.concurso', candidato='ana_teste')
    )

    assert achados.indice == pasta / 'index.html'
    assert achados.recomendacoes == '# Estudar crase'
    assert achados.pratica == '# Prática'
    assert achados.tabelas_pratica == {'Erros': pasta / 'pratica' / 'erros_tec.csv'}
