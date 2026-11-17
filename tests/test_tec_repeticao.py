"""Repetição local das questões erradas do TEC."""

import csv
from pathlib import Path
from types import SimpleNamespace

from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.tec_repeticao import listar_erros, registrar_tentativa
from concursos.pratica_tec import ARQUIVO_RESPOSTAS, ARQUIVO_TENTATIVAS, PASTA_PRATICA, ConfiguracaoPratica


def _opcoes(tmp_path: Path, monkeypatch) -> Opcoes:
    from concursos.aplicacao import tec_repeticao

    monkeypatch.setattr(
        tec_repeticao.pratica_app,
        'exigir_configuracao_pratica',
        lambda _c: ConfiguracaoPratica(entrada=tmp_path / 'tec', candidato='ana'),
    )
    monkeypatch.setattr(
        tec_repeticao,
        'pasta_do_candidato',
        lambda _c, _n: tmp_path / 'analises' / 'ana',
    )
    return Opcoes(contexto=SimpleNamespace(raiz=tmp_path), saida=lambda _t: None)


def test_registrar_tentativa_acerto_e_erro(tmp_path: Path, monkeypatch):
    pasta = tmp_path / 'analises' / 'ana' / PASTA_PRATICA
    pasta.mkdir(parents=True)
    with (pasta / ARQUIVO_RESPOSTAS).open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                'id',
                'tipo_questao',
                'mat',
                'ass',
                'banca',
                'ano',
                'gab',
                'marc',
                'resultado',
                'tem_comentario',
            ],
        )
        w.writeheader()
        w.writerow(
            {
                'id': 'q1',
                'tipo_questao': 'multipla_escolha',
                'mat': 'X',
                'ass': 'Y',
                'banca': 'FGV',
                'ano': '2020',
                'gab': 'B',
                'marc': 'A',
                'resultado': 'erro',
                'tem_comentario': 'nao',
            }
        )

    opcoes = _opcoes(tmp_path, monkeypatch)
    assert registrar_tentativa(opcoes, 'q1', 'B', 'B', 'multipla_escolha') == 'acerto'
    assert registrar_tentativa(opcoes, 'q1', 'A', 'B', 'multipla_escolha') == 'erro'
    with (pasta / ARQUIVO_TENTATIVAS).open(encoding='utf-8', newline='') as f:
        linhas = list(csv.DictReader(f))
    assert len(linhas) == 2
    assert linhas[0]['resultado'] == 'acerto'
    assert linhas[1]['resultado'] == 'erro'


def test_listar_erros_filtra_assunto(tmp_path: Path, monkeypatch):
    pasta = tmp_path / 'analises' / 'ana' / PASTA_PRATICA
    pasta.mkdir(parents=True)
    with (pasta / ARQUIVO_RESPOSTAS).open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                'id',
                'tipo_questao',
                'mat',
                'ass',
                'banca',
                'ano',
                'gab',
                'marc',
                'resultado',
                'tem_comentario',
            ],
        )
        w.writeheader()
        for id_, ass in (('q1', 'Neurais'), ('q2', 'Outro')):
            w.writerow(
                {
                    'id': id_,
                    'tipo_questao': 'multipla_escolha',
                    'mat': 'X',
                    'ass': ass,
                    'banca': '',
                    'ano': '',
                    'gab': 'B',
                    'marc': 'A',
                    'resultado': 'erro',
                    'tem_comentario': 'nao',
                }
            )

    opcoes = _opcoes(tmp_path, monkeypatch)
    qs = listar_erros(opcoes, assunto='Neurais')
    assert [q.id for q in qs] == ['q1']
