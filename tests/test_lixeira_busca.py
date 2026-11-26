"""Lixeira, busca e exclusão de concurso."""

from pathlib import Path

import yaml

from concursos.aplicacao import busca, exclusao, lixeira
from concursos.config.contexto import Contexto


def _contexto(tmp_path: Path) -> Contexto:
    projeto = tmp_path / '.gabarito-vivo'
    projeto.mkdir()
    provas = tmp_path / 'provas'
    analises = tmp_path / 'analises'
    provas.mkdir()
    analises.mkdir()
    return Contexto(tmp_path, tmp_path / 'home', projeto, provas, analises)


def test_mover_e_restaurar(tmp_path: Path) -> None:
    origem = tmp_path / 'arquivo.txt'
    origem.write_text('x', encoding='utf-8')
    item = lixeira.mover_para_lixeira(tmp_path, origem, tipo='teste')
    assert item is not None
    assert not origem.exists()
    assert lixeira.restaurar(tmp_path, item.id) == origem
    assert origem.read_text(encoding='utf-8') == 'x'


def test_esvaziar(tmp_path: Path) -> None:
    origem = tmp_path / 'a.txt'
    origem.write_text('1', encoding='utf-8')
    lixeira.mover_para_lixeira(tmp_path, origem, tipo='t')
    lixeira.esvaziar(tmp_path)
    assert not (tmp_path / 'lixeira').exists()


def test_excluir_concurso(tmp_path: Path) -> None:
    ctx = _contexto(tmp_path)
    pasta = ctx.provas / 'alfa'
    pasta.mkdir()
    (pasta / 'concurso.yaml').write_text('nome: alfa\n', encoding='utf-8')
    (ctx.analises / 'ana' / 'alfa').mkdir(parents=True)
    (ctx.analises / 'ana' / 'alfa' / 'relatorio.md').write_text('ok', encoding='utf-8')
    interesses = ctx.projeto / 'interesses_pci.yaml'
    interesses.write_text(
        yaml.safe_dump({'interesses': [{'id': '1', 'concurso': 'alfa'}, {'id': '2', 'concurso': 'beta'}]}),
        encoding='utf-8',
    )
    itens = exclusao.excluir_concurso(ctx, 'alfa')
    assert not pasta.exists()
    assert not (ctx.analises / 'ana' / 'alfa').exists()
    dados = yaml.safe_load(interesses.read_text(encoding='utf-8'))
    assert len(dados['interesses']) == 1
    exclusao.desfazer_exclusao(ctx, itens)
    assert pasta.exists()


def test_busca_concurso(tmp_path: Path) -> None:
    ctx = _contexto(tmp_path)
    (ctx.provas / 'tcu_25').mkdir()
    (ctx.provas / 'fgv_24').mkdir()
    achados = busca.procurar(ctx, 'tcu')
    assert [a for a in achados if a.rotulo == 'tcu_25'] == [
        busca.ResultadoBusca('Concurso', 'tcu_25', '/resultados?aba=concursos&concurso=tcu_25')
    ]


def test_busca_de_topico_abre_o_simulado(tmp_path: Path, monkeypatch) -> None:
    from concursos.aplicacao.resultados import ResumoVisual, TopicoParaAgir

    ctx = _contexto(tmp_path)
    monkeypatch.setattr(
        'concursos.aplicacao.resultados.resumo_visual',
        lambda contexto: ResumoVisual(fracos=(TopicoParaAgir('Português', 'Crase', 20.0),)),
    )
    assert busca.procurar(ctx, 'crase') == [
        busca.ResultadoBusca('Tópico fraco', 'Crase', '/estudar?aba=simulado&topico=Crase')
    ]


def test_busca_ignora_topico_acima_do_limiar(tmp_path: Path, monkeypatch) -> None:
    from concursos.aplicacao.resultados import ResumoVisual, TopicoParaAgir

    ctx = _contexto(tmp_path)
    monkeypatch.setattr(
        'concursos.aplicacao.resultados.resumo_visual',
        lambda contexto: ResumoVisual(fracos=(TopicoParaAgir('Português', 'Crase', 80.0),)),
    )
    assert busca.procurar(ctx, 'crase') == []
