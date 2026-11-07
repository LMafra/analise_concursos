import io
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_estudo_instalacao import Transporte, chave, publicar  # noqa: F401

from concursos.aplicacao import estudo
from concursos.aplicacao.opcoes import Opcoes
from concursos.config.contexto import Contexto
from concursos.erros import ErroDoAmbiente, ErroDoUsuario
from concursos.estudo import instalacao


@pytest.fixture
def contexto(tmp_path) -> Contexto:
    return Contexto(
        raiz=tmp_path,
        home=tmp_path / 'home',
        projeto=tmp_path / '.concurso',
        provas=tmp_path / 'provas',
        analises=tmp_path / 'analises',
    )


def pacote(tmp_path: Path, versao='1.15.1-1') -> Path:
    arquivo = tmp_path / f'estudo-{versao}-linux-x86_64.tar.xz'
    with tarfile.open(arquivo, 'w:xz') as tar:
        info = tarfile.TarInfo(f'estudo-{versao}/estudo.toml')
        info.size = 0
        tar.addfile(info, io.BytesIO(b''))
    return arquivo


def test_antes_de_preparar_explica_o_download(contexto):
    situacao = estudo.situacao_do_estudo(contexto, 'linux')

    assert not situacao.preparado
    assert 'open-notebook' in situacao.mensagem and 'não saem do computador' in situacao.mensagem


@pytest.mark.parametrize(('sistema', 'tamanho'), [('linux', 'cerca de 360 MB'), ('win32', 'cerca de 420 MB')])
def test_o_tamanho_do_download_e_o_do_sistema(contexto, sistema, tamanho):
    assert tamanho in estudo.situacao_do_estudo(contexto, sistema).mensagem


def test_macos_diz_que_ainda_nao_esta_disponivel(contexto):
    situacao = estudo.situacao_do_estudo(contexto, 'darwin')

    assert not situacao.disponivel_no_sistema
    assert 'ainda não está disponível' in situacao.mensagem


def test_preparar_de_um_arquivo_local(contexto, tmp_path):
    versao = estudo.preparar_estudo(Opcoes(contexto), consentiu=False, arquivo=pacote(tmp_path))

    assert versao == '1.15.1-1'
    assert estudo.situacao_do_estudo(contexto, 'linux').versao == '1.15.1-1'


def test_baixar_exige_consentimento_e_rede(contexto):
    with pytest.raises(ErroDoUsuario, match='concordar'):
        estudo.preparar_estudo(Opcoes(contexto), consentiu=False)
    with pytest.raises(ErroDoUsuario, match='Sem internet'):
        estudo.preparar_estudo(Opcoes(contexto, rede=False), consentiu=True)


@pytest.fixture
def no_linux(monkeypatch):
    monkeypatch.setattr('sys.platform', 'linux')


def _com_app(monkeypatch, versao):
    monkeypatch.setattr(estudo.atualizacao, 'versao_instalada', lambda: versao)


def test_app_de_teste_acha_a_biblioteca_de_teste_no_stable(contexto, chave, tmp_path, monkeypatch, no_linux):  # noqa: F811
    transporte = Transporte()
    publicar(transporte, chave, tmp_path, '1.15.1-1', app_minimo='0.7.0b1', prerelease=True)
    _com_app(monkeypatch, '0.7.0b1')

    disponivel = estudo.procurar_pacote(Opcoes(contexto), transporte)

    assert disponivel.manifesto.versao == '1.15.1-1'


def test_app_antigo_diz_a_versao_exigida_e_a_instalada(contexto, chave, tmp_path, monkeypatch, no_linux):  # noqa: F811
    transporte = Transporte()
    publicar(transporte, chave, tmp_path, '1.15.1-1', app_minimo='0.7.0b1', prerelease=True)
    _com_app(monkeypatch, '0.6.0b3')

    with pytest.raises(ErroDoAmbiente) as erro:
        estudo.preparar_estudo(Opcoes(contexto), consentiu=True, transporte=transporte)

    assert '0.7.0b1' in erro.value.causa and '0.6.0b3' in erro.value.causa
    assert 'Sobre' in erro.value.dica


def test_so_biblioteca_de_teste_sugere_o_canal_beta(contexto, chave, tmp_path, monkeypatch, no_linux):  # noqa: F811
    transporte = Transporte()
    publicar(transporte, chave, tmp_path, '1.16.0-1', app_minimo='0.7.0b1', prerelease=True)
    _com_app(monkeypatch, '0.7.0')

    with pytest.raises(ErroDoAmbiente) as erro:
        estudo.preparar_estudo(Opcoes(contexto), consentiu=True, transporte=transporte)

    assert 'versão de teste' in erro.value.causa
    assert 'beta' in erro.value.dica and 'Configurações > Avançado' in erro.value.dica


def test_sem_nenhuma_biblioteca_publicada(contexto, monkeypatch, no_linux):
    transporte = Transporte()
    transporte.urls[instalacao.URL_RELEASES] = b'[]'
    _com_app(monkeypatch, '0.7.0')

    with pytest.raises(ErroDoAmbiente, match='Ainda não há uma biblioteca'):
        estudo.preparar_estudo(Opcoes(contexto), consentiu=True, transporte=transporte)


def test_dry_run_nao_grava(contexto, tmp_path):
    estudo.preparar_estudo(Opcoes(contexto, dry_run=True), consentiu=True, arquivo=pacote(tmp_path))

    assert not estudo.pastas(contexto).base.exists()


def test_chave_de_cifra_gerada_uma_vez(contexto, monkeypatch):
    guardadas = {}
    monkeypatch.setattr(
        estudo, 'obter_chave_da_variavel', lambda v, h: (guardadas[v], 'x') if v in guardadas else None
    )
    monkeypatch.setattr(estudo, 'guardar_chave', lambda v, c, h: guardadas.__setitem__(v, c))

    primeira = estudo.chave_de_cifra(contexto.home)

    assert estudo.chave_de_cifra(contexto.home) == primeira
    assert len(primeira) >= 32


def test_adicionar_livros_le_em_segundo_plano(contexto, tmp_path):
    livro = tmp_path / 'Apostila.txt'
    livro.write_text('crase\fregência', encoding='utf-8')
    invalido = tmp_path / 'foto.png'
    invalido.write_bytes(b'png')
    avisos = []

    resultados = estudo.adicionar_livros(
        Opcoes(contexto), [livro, invalido], disciplina='Português', ao_mudar=lambda: avisos.append(1)
    )
    estudo.esperar_trabalho(contexto, timeout=60)

    assert [r.novo for r in resultados] == [True, False]
    assert 'formato não aceito' in resultados[1].erro
    (lido,) = estudo.listar_livros(contexto)
    assert estudo.situacao_do_livro(lido, preparado=False) == 'Pronto para buscar'
    assert avisos


def test_remover_livro_sem_open_notebook(contexto, tmp_path):
    livro = tmp_path / 'Apostila.txt'
    livro.write_text('crase', encoding='utf-8')
    estudo.adicionar_livros(Opcoes(contexto), [livro])
    estudo.esperar_trabalho(contexto, timeout=60)
    (lido,) = estudo.listar_livros(contexto)

    estudo.remover_livro(contexto, lido.sha)

    assert estudo.listar_livros(contexto) == []


def test_cli_livros_add_list_remove(tmp_path, monkeypatch, capsys):
    from concursos.cli import main

    monkeypatch.chdir(tmp_path)
    (tmp_path / 'livros').mkdir()
    (tmp_path / 'livros' / 'a.txt').write_text('crase', encoding='utf-8')
    (tmp_path / 'livros' / 'nota.md').write_text('fora', encoding='utf-8')

    assert main(['livros', 'add', 'livros', '--disciplina', 'Português']) == 0
    assert main(['livros', 'list']) == 0
    saida = capsys.readouterr().out
    assert 'Português  a: Pronto para buscar' in saida
    assert main(['livros', 'ask', 'crase']) == 0
    assert 'a, p. 1: «crase»' in capsys.readouterr().out
    codigo = saida.strip().splitlines()[-1].split()[0]
    assert main(['livros', 'remove', codigo]) == 0
    main(['livros', 'list'])
    assert 'vazia' in capsys.readouterr().out


def test_opcoes_de_concurso_e_disciplina(contexto):
    (contexto.provas / 'sefaz-df-2026').mkdir(parents=True)
    (contexto.provas / '.oculta').mkdir()
    contexto.taxonomia.parent.mkdir(parents=True, exist_ok=True)
    contexto.taxonomia.write_text(
        'Direito Constitucional:\n  bloco: especifico\n  nomes: [Constitucional]\n', encoding='utf-8'
    )

    assert estudo.concursos_do_projeto(contexto) == ['sefaz-df-2026']
    assert estudo.disciplinas_sugeridas(contexto) == ['Geral', 'Direito Constitucional']


def _disponivel(versao: str):
    return SimpleNamespace(manifesto=SimpleNamespace(versao=versao, open_notebook=versao.split('-')[0]))


def test_atualizacao_da_biblioteca_nao_consulta_sem_biblioteca(contexto, monkeypatch):
    def nao_consulta(*_args, **_kwargs):
        raise AssertionError('consultou sem biblioteca preparada')

    monkeypatch.setattr(estudo, 'procurar_pacote', nao_consulta)

    assert estudo.atualizacao_da_biblioteca(Opcoes(contexto)) is None


def test_atualizacao_da_biblioteca_so_com_versao_mais_nova(contexto, tmp_path, monkeypatch):
    estudo.preparar_estudo(Opcoes(contexto), consentiu=False, arquivo=pacote(tmp_path))

    monkeypatch.setattr(estudo, 'procurar_pacote', lambda *_a, **_k: _disponivel('1.15.1-1'))
    assert estudo.atualizacao_da_biblioteca(Opcoes(contexto)) is None
    monkeypatch.setattr(estudo, 'procurar_pacote', lambda *_a, **_k: _disponivel('1.15.1-2'))
    assert estudo.atualizacao_da_biblioteca(Opcoes(contexto)).manifesto.versao == '1.15.1-2'


def test_atualizar_biblioteca_para_o_open_notebook_em_uso(contexto, monkeypatch):
    parados = []
    monkeypatch.setattr(estudo, 'preparar_estudo', lambda *_a, **_k: '1.15.1-2')
    monkeypatch.setitem(estudo._supervisores, contexto.home, SimpleNamespace(parar=lambda: parados.append(1)))

    assert estudo.atualizar_biblioteca(Opcoes(contexto), consentiu=True) == '1.15.1-2'
    assert parados == [1]


def test_upgrade_avisa_da_biblioteca_nova(contexto, tmp_path, monkeypatch):
    estudo.preparar_estudo(Opcoes(contexto), consentiu=False, arquivo=pacote(tmp_path))
    monkeypatch.setattr(estudo, 'procurar_pacote', lambda *_a, **_k: _disponivel('1.15.1-2'))
    saida: list[str] = []

    estudo.avisar_atualizacao_da_biblioteca(Opcoes(contexto, rede=False, saida=saida.append))
    assert saida == []
    estudo.avisar_atualizacao_da_biblioteca(Opcoes(contexto, saida=saida.append))
    assert len(saida) == 1 and '1.15.1-2' in saida[0] and 'estudo preparar' in saida[0]
