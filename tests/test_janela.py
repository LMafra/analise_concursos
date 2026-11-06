from pathlib import Path

import pytest

from concursos import janela
from concursos.modelo import DecisaoJanela


def registro(**valores: str):
    """Leitor de registro falso: `valores` vai de `raiz:chave` para o `pv`."""

    def ler(raiz: str, chave: str) -> str | None:
        return valores.get(f'{raiz}:{chave}')

    return ler


def sem_loader() -> str | None:
    return None


@pytest.mark.parametrize('chave', janela.CHAVES_WEBVIEW2)
def test_pv_valido_em_qualquer_chave_abre_a_janela(chave):
    ler = registro(**{f'{chave[0]}:{chave[1]}': '130.0.2849.56'})

    decisao = janela.decidir_janela('win32', ler_registro=ler, versao_pelo_loader=sem_loader)

    assert decisao is DecisaoJanela.NATIVA


@pytest.mark.parametrize('pv', ['0.0.0.0', '', None])
def test_pv_vazio_zerado_ou_ausente_cai_no_navegador_com_motivo(pv):
    raiz, chave = janela.CHAVES_WEBVIEW2[0]
    ler = registro(**({f'{raiz}:{chave}': pv} if pv is not None else {}))

    decisao = janela.decidir_janela('win32', ler_registro=ler, versao_pelo_loader=sem_loader)

    assert decisao is DecisaoJanela.NAVEGADOR_SEM_WEBVIEW2


def test_sem_registro_mas_o_loader_acha_o_runtime_abre_a_janela():
    decisao = janela.decidir_janela('win32', ler_registro=registro(), versao_pelo_loader=lambda: '131.0.1.0')

    assert decisao is DecisaoJanela.NATIVA


def test_loader_que_quebra_conta_como_sem_webview2():
    def quebra() -> str | None:
        raise OSError('WebView2Loader.dll não carregou')

    decisao = janela.decidir_janela('win32', ler_registro=registro(), versao_pelo_loader=quebra)

    assert decisao is DecisaoJanela.NAVEGADOR_SEM_WEBVIEW2


def test_linux_e_navegador_sem_consultar_o_registro():
    def proibido(raiz: str, chave: str) -> str | None:
        raise AssertionError('no Linux não há registro')

    assert janela.decidir_janela('linux', ler_registro=proibido) is DecisaoJanela.NAVEGADOR_LINUX


def test_browser_vence_em_qualquer_sistema():
    for sistema in ('win32', 'darwin', 'linux'):
        assert janela.decidir_janela(sistema, navegador=True) is DecisaoJanela.NAVEGADOR_PEDIDO


def test_macos_continua_na_janela():
    assert janela.decidir_janela('darwin') is DecisaoJanela.NATIVA


@pytest.mark.parametrize(
    ('decisao', 'dispensado', 'falhou', 'mostra'),
    [
        (DecisaoJanela.NAVEGADOR_SEM_WEBVIEW2, False, False, True),
        (DecisaoJanela.NAVEGADOR_SEM_WEBVIEW2, True, False, False),
        (DecisaoJanela.NAVEGADOR_PEDIDO, False, True, True),
        (DecisaoJanela.NAVEGADOR_PEDIDO, True, True, True),
        (DecisaoJanela.NAVEGADOR_PEDIDO, False, False, False),
        (DecisaoJanela.NAVEGADOR_LINUX, False, False, False),
        (DecisaoJanela.NATIVA, False, False, False),
    ],
)
def test_aviso_so_quando_a_janela_era_esperada(decisao, dispensado, falhou, mostra):
    assert janela.mostrar_aviso(decisao, dispensado=dispensado, janela_falhou=falhou) is mostra


def test_reabrir_no_navegador_no_executavel_usa_o_proprio_exe(tmp_path):
    exe = tmp_path / 'concurso-analise.exe'

    comando = janela.comando_para_reabrir(congelado=True, executavel=str(exe), projeto=tmp_path / 'p')

    assert comando == [str(exe), 'gui', '--browser', '--project', str(tmp_path / 'p')]


def test_reabrir_no_navegador_fora_do_executavel_chama_a_cli_pelo_python():
    comando = janela.comando_para_reabrir(congelado=False, executavel='/usr/bin/python3', projeto=None)

    assert comando[0] == '/usr/bin/python3'
    assert comando[1] == '-c'
    assert comando[-2:] == ['gui', '--browser']


def test_loader_fica_no_pacote_do_pywebview():
    caminho = janela.caminho_do_loader()

    if caminho is not None:
        assert caminho.name == 'WebView2Loader.dll'
        assert Path('runtimes') in caminho.parents or 'runtimes' in caminho.parts
