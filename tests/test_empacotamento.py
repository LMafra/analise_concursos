import http.server
import io
import os
import sys
import threading
from pathlib import Path

import pytest

from concursos import doctor, empacotado

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def executavel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um `_MEIPASS` falso com o Tesseract embutido, como o PyInstaller monta."""
    base = tmp_path / 'pacote'
    (base / 'tesseract' / 'bin').mkdir(parents=True)
    (base / 'tesseract' / 'tessdata').mkdir()
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(base), raising=False)
    monkeypatch.setenv('PATH', '/usr/bin')
    for variavel in ('TESSDATA_PREFIX', 'LD_LIBRARY_PATH', 'LD_LIBRARY_PATH_ORIG'):
        monkeypatch.delenv(variavel, raising=False)
    return base


def test_preparar_ambiente_poe_o_tesseract_embutido_na_frente(executavel):
    empacotado.preparar_ambiente(executavel)

    assert os.environ['PATH'].split(os.pathsep)[0] == str(executavel / 'tesseract' / 'bin')
    assert os.environ['TESSDATA_PREFIX'] == str(executavel / 'tesseract' / 'tessdata')


def test_preparar_ambiente_sem_tesseract_nao_mexe_no_path(tmp_path, monkeypatch):
    monkeypatch.setenv('PATH', '/usr/bin')
    for variavel in ('TESSDATA_PREFIX', 'LD_LIBRARY_PATH', 'LD_LIBRARY_PATH_ORIG'):
        monkeypatch.delenv(variavel, raising=False)

    empacotado.preparar_ambiente(tmp_path)

    assert os.environ['PATH'] == '/usr/bin'
    assert 'TESSDATA_PREFIX' not in os.environ


def test_no_linux_os_programas_do_sistema_voltam_as_bibliotecas_originais(executavel, monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setenv('LD_LIBRARY_PATH', str(executavel))
    monkeypatch.setenv('LD_LIBRARY_PATH_ORIG', '/opt/sistema/lib')

    empacotado.preparar_ambiente(executavel)

    assert os.environ['LD_LIBRARY_PATH'] == '/opt/sistema/lib'
    assert 'LD_LIBRARY_PATH_ORIG' not in os.environ


def test_no_linux_sem_original_o_ld_library_path_sai(executavel, monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setenv('LD_LIBRARY_PATH', str(executavel))
    monkeypatch.delenv('LD_LIBRARY_PATH_ORIG', raising=False)

    empacotado.preparar_ambiente(executavel)

    assert 'LD_LIBRARY_PATH' not in os.environ


def test_smoke_recusa_o_tesseract_do_sistema_quando_o_pacote_traz_o_seu(executavel, tmp_path, monkeypatch):
    do_sistema = tmp_path / 'sistema' / 'tesseract'
    monkeypatch.setattr(empacotado.shutil, 'which', lambda nome: str(do_sistema))

    class Saida:
        stdout = 'List of available languages (2):\neng\npor\n'

    monkeypatch.setattr(empacotado.subprocess, 'run', lambda *a, **k: Saida())

    with pytest.raises(empacotado.SmokeError, match='veio na frente'):
        empacotado.conferir_tesseract()


def test_janela_sem_console_ganha_saidas_vazias(monkeypatch):
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)

    empacotado.garantir_saidas()

    sys.stdout.write('nada')
    sys.stderr.write('nada')


def test_saida_redirecionada_no_windows_escreve_utf8(monkeypatch):
    saida = io.BytesIO()
    monkeypatch.setattr(sys, 'stdout', io.TextIOWrapper(saida, encoding='cp1252'))

    empacotado.garantir_saidas()
    sys.stdout.write('✓ legislação')
    sys.stdout.flush()

    assert saida.getvalue().decode('utf-8') == '✓ legislação'


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    chamadas: list[list[str]] = []
    monkeypatch.setattr('concursos.cli.main', lambda argv: chamadas.append(argv) or 0)
    return chamadas


def test_sem_argumentos_abre_a_gui(cli):
    assert empacotado.principal([]) == 0
    assert cli == [['gui']]


def test_com_argumentos_e_a_cli(cli):
    empacotado.principal(['doctor'])

    assert cli == [['doctor']]


def test_smoke_nao_passa_pela_cli(cli, monkeypatch):
    monkeypatch.setattr(empacotado, 'conferir_pacote', lambda: 0)

    assert empacotado.principal(['--smoke']) == 0
    assert cli == []


def test_versao_e_perfis_carregam():
    assert empacotado.conferir_versao().startswith(tuple('0123456789'))
    assert 'generic' in empacotado.conferir_perfis()


def test_smoke_exige_o_tesseract_com_portugues(monkeypatch):
    monkeypatch.setattr(empacotado.shutil, 'which', lambda nome: None)
    monkeypatch.delenv(empacotado.VARIAVEL_SEM_OCR, raising=False)

    with pytest.raises(empacotado.SmokeError, match='Tesseract'):
        empacotado.conferir_tesseract()


def test_smoke_pode_dispensar_o_tesseract_num_build_de_desenvolvimento(monkeypatch):
    monkeypatch.setattr(empacotado.shutil, 'which', lambda nome: None)
    monkeypatch.setenv(empacotado.VARIAVEL_SEM_OCR, '1')

    assert 'dispensado' in empacotado.conferir_tesseract()


TESSERACT_LOCAL = RAIZ / 'empacotamento' / 'construcao' / 'tesseract'


def test_segundos_desde_o_inicio_do_processo_e_positivo_e_cresce():
    primeiro = empacotado.segundos_desde_o_inicio()
    segundo = empacotado.segundos_desde_o_inicio()

    assert 0 < primeiro <= segundo < 3600


def test_partida_acima_do_limite_falha(monkeypatch):
    monkeypatch.setenv(empacotado.VARIAVEL_LIMITE_PARTIDA, '3')

    with pytest.raises(empacotado.SmokeError, match='partida de 4,2 s passou do limite de 3 s'):
        empacotado.conferir_partida(4.2)


def test_partida_dentro_do_limite_ou_sem_limite_passa(monkeypatch):
    monkeypatch.setenv(empacotado.VARIAVEL_LIMITE_PARTIDA, '10')
    assert empacotado.conferir_partida(2.6) == 'partida: 2,6 s (limite 10 s)'

    monkeypatch.delenv(empacotado.VARIAVEL_LIMITE_PARTIDA)
    assert empacotado.conferir_partida(2.6) == 'partida: 2,6 s'


def test_limite_de_partida_invalido_e_erro(monkeypatch):
    monkeypatch.setenv(empacotado.VARIAVEL_LIMITE_PARTIDA, 'rapido')

    with pytest.raises(empacotado.SmokeError, match=empacotado.VARIAVEL_LIMITE_PARTIDA):
        empacotado.conferir_partida(1.0)


def test_ocr_recusa_tesseract_que_nao_le_a_imagem(monkeypatch, tmp_path):
    class Saida:
        returncode = 0
        stdout = 'texto qualquer\n'
        stderr = ''

    monkeypatch.setattr(empacotado.subprocess, 'run', lambda *a, **k: Saida())

    with pytest.raises(empacotado.SmokeError, match='não leu'):
        empacotado.conferir_ocr(str(tmp_path / 'tesseract'))


def test_ocr_aceita_quando_o_texto_aparece(monkeypatch, tmp_path):
    comandos: list[list[str]] = []

    class Saida:
        returncode = 0
        stdout = 'CONCURSO 2026\n'
        stderr = ''

    def rodar(comando, **_):
        comandos.append(comando)
        assert Path(comando[1]).is_file()
        return Saida()

    monkeypatch.setattr(empacotado.subprocess, 'run', rodar)

    assert 'OCR' in empacotado.conferir_ocr(str(tmp_path / 'tesseract'))
    assert comandos[0][2:] == ['stdout', '-l', 'por']


@pytest.mark.skipif(
    not (TESSERACT_LOCAL / 'bin' / 'tesseract').is_file() or sys.platform != 'linux',
    reason='sem o Tesseract extraído por empacotamento/tesseract/obter_linux.sh',
)
def test_ocr_de_verdade_com_o_tesseract_do_empacotamento(monkeypatch):
    monkeypatch.setenv('TESSDATA_PREFIX', str(TESSERACT_LOCAL / 'tessdata'))

    assert 'OCR' in empacotado.conferir_ocr(str(TESSERACT_LOCAL / 'bin' / 'tesseract'))


def test_responde_espera_o_servidor_subir():
    servidor = http.server.HTTPServer(('127.0.0.1', 0), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        assert empacotado.responde(f'http://127.0.0.1:{servidor.server_port}/', timeout=10)
    finally:
        servidor.shutdown()


def test_responde_desiste_no_timeout():
    assert not empacotado.responde('http://127.0.0.1:9/', timeout=0.3, intervalo=0.1)


def test_doctor_no_executavel_mostra_o_tesseract_embutido(executavel, monkeypatch):
    tesseract = executavel / 'tesseract' / 'bin' / 'tesseract'
    monkeypatch.setattr(doctor.shutil, 'which', lambda nome: str(tesseract) if nome == 'tesseract' else None)
    monkeypatch.setattr(doctor, '_idiomas_do_tesseract', lambda caminho: ['eng', 'por'])

    itens = {item.nome: item for item in doctor.diagnosticar([executavel], executavel)}

    assert itens['uv'].situacao is doctor.Situacao.OK
    assert 'não necessário' in itens['uv'].detalhe
    assert 'embutido' in itens['Python'].detalhe
    assert itens['Tesseract'].situacao is doctor.Situacao.OK
    assert 'embutido' in itens['Tesseract'].detalhe


def test_fora_do_executavel_nada_e_embutido(monkeypatch):
    monkeypatch.delattr(sys, 'frozen', raising=False)

    assert empacotado.pasta_embutida() is None
    assert not empacotado.embutido('/qualquer/tesseract')


def test_arquivos_do_empacotamento_existem():
    pasta = RAIZ / 'empacotamento'
    for relativo in (
        'launcher.py',
        'concurso-analise.spec',
        'hooks/hook-concursos.py',
        'coletar_licencas.py',
        'tesseract/obter_windows.ps1',
        'inno/concurso-analise.iss',
        'windows/versao.py',
        'windows/obter_webview2.ps1',
        'linux/verificar_bibliotecas.sh',
        'linux/bibliotecas_do_sistema.txt',
        'icones/concurso-analise-256.png',
        'LICENSES/LEIA-ME.md',
    ):
        assert (pasta / relativo).is_file(), relativo
    assert (RAIZ / 'scripts' / 'smoke_maquina_limpa.ps1').is_file()
    assert (RAIZ / '.github' / 'workflows' / 'release.yml').is_file()


def test_launcher_chama_freeze_support_antes_de_tudo():
    texto = (RAIZ / 'empacotamento' / 'launcher.py').read_text(encoding='utf-8')
    guarda = texto.split("if __name__ == '__main__':", 1)[1].strip().splitlines()

    assert guarda[0].strip() == 'multiprocessing.freeze_support()'


def test_instalador_por_usuario_com_versao_no_nome():
    texto = (RAIZ / 'empacotamento' / 'inno' / 'concurso-analise.iss').read_text(encoding='utf-8-sig')

    assert 'PrivilegesRequired=lowest' in texto
    assert 'OutputBaseFilename=concurso-analise-{#Versao}-windows-x64-setup' in texto
    assert 'BrazilianPortuguese.isl' in texto
    assert 'VersionInfoProductName={#Nome}' in texto
    assert 'VersionInfoVersion={#VersaoNumerica}' in texto


def modulo_versao():
    import importlib.util

    caminho = RAIZ / 'empacotamento' / 'windows' / 'versao.py'
    especificacao = importlib.util.spec_from_file_location('versao_windows', caminho)
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize(
    ('versao', 'numerica'),
    [
        ('0.6.0', (0, 6, 0, 0)),
        ('0.6.0b1', (0, 6, 0, 0)),
        ('1.2', (1, 2, 0, 0)),
        ('0.6.0.post1', (0, 6, 0, 1)),
    ],
)
def test_versao_numerica_do_windows_tem_quatro_partes(versao, numerica):
    assert modulo_versao().versao_numerica(versao) == numerica


def test_recurso_de_versao_identifica_o_produto_e_o_editor(tmp_path):
    versao = modulo_versao()

    texto = versao.recurso_de_versao('0.6.0b1', 'concurso-analise-cli', 'concurso-analise (linha de comando)')

    assert 'filevers=(0, 6, 0, 0)' in texto
    assert "StringStruct('ProductName', 'concurso-analise')" in texto
    assert "StringStruct('ProductVersion', '0.6.0b1')" in texto
    assert "StringStruct('OriginalFilename', 'concurso-analise-cli.exe')" in texto
    assert "StringStruct('CompanyName', 'LMafra')" in texto
    assert 'VarStruct' in texto


def test_spec_usa_o_recurso_de_versao_nos_dois_executaveis():
    texto = (RAIZ / 'empacotamento' / 'concurso-analise.spec').read_text(encoding='utf-8')

    assert texto.count('version=recurso(') == 2


def test_lista_de_bibliotecas_do_sistema_e_so_a_glibc():
    linhas = (
        (RAIZ / 'empacotamento' / 'linux' / 'bibliotecas_do_sistema.txt')
        .read_text(encoding='utf-8')
        .splitlines()
    )
    permitidas = {linha for linha in linhas if linha and not linha.startswith('#')}

    assert {'libc.so.6', 'ld-linux-x86-64.so.2', 'libm.so.6'} <= permitidas
    assert not {
        nome for nome in permitidas if nome.startswith(('libstdc++', 'libgcc_s', 'libz.', 'libtesseract'))
    }


def test_appdir_tem_desktop_valido_icone_e_versao():
    montar = (RAIZ / 'empacotamento' / 'linux' / 'montar_appimage.sh').read_text(encoding='utf-8')
    desktop = (RAIZ / 'empacotamento' / 'linux' / 'concurso-analise.desktop').read_text(encoding='utf-8')

    assert 'verificar_bibliotecas.sh' in montar
    assert '.DirIcon' in montar
    assert 'hicolor/256x256/apps' in montar
    assert 'X-AppImage-Version=$VERSAO' in montar
    assert 'Icon=concurso-analise' in desktop
    assert 'Categories=Education;' in desktop
