"""Caminhos de explicar_erros_tec com cliente falso."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import tomli_w

from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.tec_estudo import ResultadoExplicacao, explicar_erros_tec
from concursos.config.contexto import Contexto
from concursos.erros import ErroDoUsuario
from concursos.integracoes.open_notebook import OpenNotebookIndisponivelError


def _opcoes(tmp_path: Path) -> Opcoes:
    home = tmp_path / 'home'
    home.mkdir()
    projeto = tmp_path / 'projeto' / '.gabarito-vivo'
    projeto.mkdir(parents=True)
    (projeto / 'config.toml').write_text(
        tomli_w.dumps({'pratica': {'entrada_tec': str(tmp_path / 'tec'), 'candidato': 'ana'}}),
        encoding='utf-8',
    )
    (tmp_path / 'tec').mkdir()
    return Opcoes(
        Contexto(
            raiz=tmp_path / 'projeto',
            home=home,
            projeto=projeto,
            provas=tmp_path / 'projeto' / 'provas',
            analises=tmp_path / 'projeto' / 'analises',
            candidato='ana',
        ),
        saida=lambda _: None,
    )


def test_explicar_sem_open_notebook_ligado(tmp_path: Path) -> None:
    opcoes = _opcoes(tmp_path)
    (opcoes.contexto.config_global).write_text(
        tomli_w.dumps({'open_notebook': {'enabled': False}}), encoding='utf-8'
    )
    with pytest.raises(ErroDoUsuario, match='não está ligado'):
        explicar_erros_tec(opcoes)


def test_explicar_instancia_fora_do_ar(tmp_path: Path) -> None:
    opcoes = _opcoes(tmp_path)
    (opcoes.contexto.config_global).write_text(
        tomli_w.dumps(
            {
                'open_notebook': {
                    'enabled': True,
                    'consentimento': True,
                    'url': 'http://127.0.0.1:9',
                }
            }
        ),
        encoding='utf-8',
    )
    with (
        patch(
            'concursos.aplicacao.tec_estudo._cliente',
            side_effect=ErroDoUsuario(
                'Não consegui falar com o open-notebook.',
                'confira se ele está aberto neste computador.',
                str(OpenNotebookIndisponivelError('fora')),
            ),
        ),
        pytest.raises(ErroDoUsuario, match='Não consegui falar'),
    ):
        explicar_erros_tec(opcoes)


def test_explicar_sucesso_parcial(tmp_path: Path) -> None:
    opcoes = _opcoes(tmp_path)
    cliente = MagicMock()
    cliente.buscar_notebook_por_nome.return_value = {'id': 'nb1'}
    cliente.listar_notas.return_value = []
    cliente.adicionar_source_texto.return_value = {'id': 's1'}
    cliente.criar_nota.return_value = {'id': 'n1'}
    cliente.perguntar.return_value = {'answer': 'explicação'}
    pratica = MagicMock()
    pratica.erros = [
        {
            'id': '1',
            'enun': 'e',
            'gab': 'A',
            'marc': 'B',
            'com': '',
            'ass': 'ass',
            'mat': 'mat',
            'banca': 'fgv',
            'alts': [],
        }
    ]
    with (
        patch('concursos.aplicacao.tec_estudo._cliente', return_value=(cliente, 'modelo')),
        patch('concursos.aplicacao.tec_estudo.ler_entrada', return_value=(pratica, [])),
        patch('concursos.aplicacao.tec_estudo.pratica_app.exigir_configuracao_pratica') as exigir,
        patch('concursos.aplicacao.tec_estudo.pasta_do_candidato', return_value=tmp_path),
        patch('concursos.aplicacao.tec_estudo._gerar_similares'),
        patch('concursos.aplicacao.tec_estudo._persistir_resumo'),
        patch('concursos.aplicacao.tec_estudo.tipo_questao', return_value='certo_errado'),
        patch('concursos.aplicacao.tec_estudo.resultado_questao', return_value='erro'),
    ):
        exigir.return_value = MagicMock(entrada=tmp_path / 'tec', candidato='ana')
        resultado = explicar_erros_tec(opcoes)
    assert isinstance(resultado, ResultadoExplicacao)
    assert resultado.explicadas == 1
