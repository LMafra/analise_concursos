"""Retratos do texto que o usuário lê: cada seção do `index.html`, as mensagens da CLI e as da janela. Uma mudança
de redação aparece no diff do retrato; atualize com `uv run pytest --snapshot-update` depois de conferir."""

import re
from pathlib import Path

import pytest
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode
from test_cli_relatorio_html import concurso, indice, projeto, respostas  # noqa: F401

from concursos.cli import main
from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.erros import ErroDoAmbiente, ErroDoUsuario


class SecaoHtml(SingleFileSnapshotExtension):
    file_extension = 'html'
    _write_mode = WriteMode.TEXT


def mascarar(texto: str, raiz: Path) -> str:
    for pasta in {str(raiz.parent.resolve()), str(raiz.parent)}:
        texto = texto.replace(pasta, '<TMP>')
    texto = re.sub(r'<TMP>[^\s)]*', lambda caminho: caminho.group(0).replace('\\', '/'), texto)
    texto = re.sub(r'concurso-analise \d[\w.+]*', 'concurso-analise <VERSAO>', texto)
    return re.sub(r'\d{2}/\d{2}/\d{4}( \d{2}:\d{2})?(?= a partir|</p>)', '<DATA>', texto)


def secoes_do_indice(html: str) -> dict[str, str]:
    corpo = html.split('<body>', 1)[1].split('</body>', 1)[0]
    principal, tecnico = corpo.split('<details id="detalhes-tecnicos">', 1)
    partes = re.split(r'(?=<h2 id=")', principal)
    secoes = {'cabecalho': partes[0]}
    secoes.update({re.match(r'<h2 id="([^"]+)"', parte).group(1): parte for parte in partes[1:]})
    secoes['detalhes-tecnicos'] = '<details id="detalhes-tecnicos">' + tecnico
    return secoes


@pytest.fixture
def analisado(projeto: Path, capsys: pytest.CaptureFixture[str]) -> tuple[Path, str]:  # noqa: F811
    concurso(projeto, 'beta', '2025-09-01')
    respostas(projeto, 'beta', '1 A\n2 B\n3 D\n4 E\n')
    concurso(projeto, 'gama', '2026-02-01')
    respostas(projeto, 'gama', '1 A\n2 C\n3 D\n4 -\n')
    assert main(['--candidate', 'alice', '--no-open']) == 0
    saida = capsys.readouterr()
    return projeto, saida.out + saida.err


def test_secoes_do_indice(analisado, snapshot):
    raiz, _ = analisado
    html = mascarar(indice(raiz).read_text(encoding='utf-8'), raiz)

    secoes = secoes_do_indice(html)

    assert list(secoes) == [
        'cabecalho',
        'como-estou-saindo',
        'pontos-fortes',
        'pontos-a-melhorar',
        'evolucao',
        'o-que-fazer',
        'detalhes-tecnicos',
    ]
    for nome, conteudo in secoes.items():
        assert conteudo == snapshot(name=nome, extension_class=SecaoHtml)


def test_avisos_da_analise_na_cli(analisado, snapshot):
    raiz, saida = analisado

    avisos = [
        linha
        for linha in mascarar(saida, raiz).splitlines()
        if linha.lstrip().startswith(('aviso:', 'dica:', 'detalhe:'))
    ]

    assert avisos == snapshot


def test_erro_sem_pasta_de_provas_na_cli(tmp_path, monkeypatch, capsys, snapshot):
    monkeypatch.chdir(tmp_path)

    assert main(['--yes', '--no-open', 'analyze']) == 1

    assert mascarar(capsys.readouterr().err, tmp_path / 'x') == snapshot


def test_erros_na_janela(snapshot):
    pytest.importorskip('nicegui')
    from concursos.gui.textos import erro_da_tela, linhas_do_erro

    erros = [
        ErroDoUsuario('Falta o seu nome.', 'escreva o seu nome para continuar.'),
        ErroDoAmbiente(
            'Não consegui falar com o open-notebook.',
            'ligue o seu open-notebook e confira o endereço em Configurações > Avançado.',
            'URLError: [Errno 111] Connection refused',
        ),
        ConfiguracaoInvalidaError('[analise] limiar_confianca: 1.5 fora de [0, 1]'),
    ]

    assert [(*linhas_do_erro(erro), erro_da_tela(erro).detalhe) for erro in erros] == snapshot


def test_rotulos_da_janela(snapshot):
    pytest.importorskip('nicegui')
    from concursos.gui.paginas.novo_concurso import AVISO_SEM_OCR
    from concursos.gui.paginas.resultados import DESCRICAO_DOS_FORMATOS

    assert {
        'formatos': {str(formato): texto for formato, texto in DESCRICAO_DOS_FORMATOS.items()},
        'sem_leitura_de_imagem': AVISO_SEM_OCR,
    } == snapshot
