import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

from concursos.erros import ErroDoAmbiente
from concursos.estudo import instalacao, supervisor
from concursos.estudo.instalacao import Pastas
from concursos.estudo.supervisor import Processo, Supervisor

FALSO = Path(__file__).with_name('estudo_falso.py')


def pacote(versao='1.15.1-1') -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:xz') as tar:
        info = tarfile.TarInfo(f'estudo-{versao}/estudo.toml')
        info.size = 0
        tar.addfile(info, io.BytesIO(b''))
    return buffer.getvalue()


@pytest.fixture
def pastas(tmp_path):
    pastas = Pastas(tmp_path / 'on')
    arquivo = tmp_path / 'p.tar.xz'
    arquivo.write_bytes(pacote())
    instalacao.instalar_arquivo(pastas, arquivo, '1.15.1-1')
    return pastas


def montador(registro: Path, falhar: set[str] | None = None):
    falhar = falhar or set()

    def montar(raiz, pastas, sessao, segredos, ambiente_ia):
        def proc(nome, porta, saude, extra=None):
            argv = [sys.executable, str(FALSO), str(porta) if porta else '-', str(registro)]
            if nome in falhar:
                argv.append('--falhar')
            ambiente = supervisor.ambiente_limpo({'PATH': '', 'OPENAI_API_KEY': 'do-usuario'}) | (extra or {})
            return Processo(nome, argv, pastas.base, ambiente, saude)

        return [
            proc('surreal', sessao.porta_surreal, f'http://127.0.0.1:{sessao.porta_surreal}/health'),
            proc('embeddings', sessao.porta_embeddings, f'http://127.0.0.1:{sessao.porta_embeddings}/health'),
            proc(
                'api',
                sessao.porta_api,
                f'{sessao.url}/health',
                {'OPEN_NOTEBOOK_PASSWORD': segredos.senha_api, **ambiente_ia},
            ),
            proc('worker', None, None),
        ]

    return montar


def registros(caminho: Path) -> list[dict]:
    return [json.loads(linha) for linha in caminho.read_text().splitlines()] if caminho.exists() else []


def novo(pastas, tmp_path, **kwargs) -> Supervisor:
    kwargs.setdefault('montar', montador(tmp_path / 'registro.jsonl'))
    return Supervisor(pastas, tmp_path / 'logs', chave_cifra=lambda: 'cifra', timeout_partida=20, **kwargs)


def test_sobe_os_quatro_em_127_0_0_1_com_senha_por_sessao(pastas, tmp_path):
    sup = novo(pastas, tmp_path, ambiente_ia=lambda: {'OPENAI_API_KEY': 'da-ia'})
    try:
        sessao = sup.garantir()
        vistos = registros(tmp_path / 'registro.jsonl')

        assert [v['porta'] for v in vistos[:3]] == [
            str(sessao.porta_surreal),
            str(sessao.porta_embeddings),
            str(sessao.porta_api),
        ]
        assert {v['host'] for v in vistos if v['host']} == {'127.0.0.1'}
        assert sessao.url.startswith('http://127.0.0.1:')
        assert len(sessao.senha) >= 32
        api = vistos[2]['env']
        assert api['OPEN_NOTEBOOK_PASSWORD'] == sessao.senha
        assert api['OPENAI_API_KEY'] == 'da-ia'
        assert 'OPENAI_API_KEY' not in vistos[0]['env']
        assert sup.garantir() is sessao
        assert not Path(f'{tmp_path / "registro.jsonl"}.config').exists()
    finally:
        sup.parar()
    assert sup.sessao is None


def test_processo_que_cai_sobe_de_novo(pastas, tmp_path):
    sup = novo(pastas, tmp_path)
    try:
        primeira = sup.garantir()
        sup._rodando[1].popen.kill()
        sup._rodando[1].popen.wait()

        segunda = sup.garantir()

        assert segunda.senha != primeira.senha
        assert sup.sessao is segunda
    finally:
        sup.parar()


def test_tres_falhas_seguidas_deixam_indisponivel(pastas, tmp_path):
    sup = novo(pastas, tmp_path, montar=montador(tmp_path / 'r.jsonl', {'api'}))
    for _ in range(3):
        with pytest.raises(ErroDoAmbiente):
            sup.garantir()

    assert sup.indisponivel
    with pytest.raises(ErroDoAmbiente, match='não conseguiu abrir'):
        sup.garantir()
    assert sup._rodando == []


def test_para_depois_da_ociosidade(pastas, tmp_path):
    agora = [1000.0]
    sup = novo(pastas, tmp_path, relogio=lambda: agora[0], ociosidade=600)
    try:
        sup.garantir()
        agora[0] += 599
        assert not sup.parar_se_ocioso()
        agora[0] += 2
        assert sup.parar_se_ocioso()
        assert sup.sessao is None
    finally:
        sup.parar()


def test_trava_unica_entre_duas_instancias(pastas, tmp_path):
    primeiro = novo(pastas, tmp_path)
    segundo = novo(pastas, tmp_path)
    try:
        primeiro.garantir()
        with pytest.raises(ErroDoAmbiente, match='outra janela'):
            segundo.garantir()
    finally:
        primeiro.parar()
    try:
        segundo.garantir()
    finally:
        segundo.parar()


def test_sem_pacote_pede_para_preparar(tmp_path):
    sup = novo(Pastas(tmp_path / 'vazio'), tmp_path)

    with pytest.raises(ErroDoAmbiente, match='ainda não foi preparada') as erro:
        sup.garantir()
    assert 'Preparar agora' in erro.value.dica


def test_versao_nova_faz_backup_e_volta_ao_anterior_se_nao_abre(pastas, tmp_path):
    pastas.banco.mkdir(parents=True)
    (pastas.banco / 'x').write_bytes(b'banco')
    instalacao.registrar_partida(pastas)
    arquivo = tmp_path / 'novo.tar.xz'
    arquivo.write_bytes(pacote('1.15.1-2'))
    instalacao.instalar_arquivo(pastas, arquivo, '1.15.1-2')
    tentativas = []
    bom = montador(tmp_path / 'r.jsonl')
    ruim = montador(tmp_path / 'r.jsonl', {'api'})

    def montar(raiz, *args):
        tentativas.append(raiz.name)
        return (ruim if raiz.name.endswith('-2') else bom)(raiz, *args)

    sup = novo(pastas, tmp_path, montar=montar)
    try:
        sup.garantir()
    finally:
        sup.parar()

    assert tentativas == ['estudo-1.15.1-2', 'estudo-1.15.1-1']
    assert instalacao.ler_estado(pastas).atual == '1.15.1-1'
    assert len(list(pastas.backups.iterdir())) == 1


def test_ganchos_rodam_depois_de_subir(pastas, tmp_path):
    vistos = []
    sup = novo(pastas, tmp_path, ao_subir=[vistos.append])
    try:
        sessao = sup.garantir()
    finally:
        sup.parar()

    assert vistos == [sessao]


def test_mudar_a_ia_sobe_de_novo_com_o_ambiente_novo(pastas, tmp_path):
    ia = {}
    sup = novo(pastas, tmp_path, ambiente_ia=lambda: dict(ia))
    try:
        primeira = sup.garantir()
        assert sup.garantir() is primeira
        ia['ANTHROPIC_API_KEY'] = 'nova'
        segunda = sup.garantir()
    finally:
        sup.parar()

    assert segunda is not primeira


def test_ambiente_limpo_tira_chaves_e_variaveis_do_open_notebook():
    limpo = supervisor.ambiente_limpo(
        {
            'PATH': '/bin',
            'OPENAI_API_KEY': 'x',
            'OPEN_NOTEBOOK_PASSWORD': 'y',
            'SURREAL_URL': 'z',
            'HOME': '/h',
        }
    )

    assert limpo == {'PATH': '/bin', 'HOME': '/h'}


def test_processos_do_pacote_so_em_127_0_0_1_e_sem_api_config(tmp_path):
    raiz = tmp_path / 'estudo-1.15.1-1'
    (raiz / 'open-notebook' / 'open_notebook' / 'database' / 'migrations').mkdir(parents=True)
    (raiz / 'open-notebook' / 'open_notebook' / 'database' / 'migrations' / '1.surrealql').write_text('x')
    pastas = Pastas(tmp_path / 'on')
    sessao = supervisor.Sessao('http://127.0.0.1:3', 's', 1, 2, 3, 't')
    segredos = supervisor.Segredos('s', 'b', 't', 'c')

    processos = supervisor.processos_do_pacote(raiz, pastas, sessao, segredos, {})

    assert [p.nome for p in processos] == ['surreal', 'embeddings', 'api', 'worker']
    texto = json.dumps([p.argv for p in processos])
    assert '0.0.0.0' not in texto and 'localhost' not in texto
    assert '127.0.0.1:1' in texto
    api = processos[2]
    assert api.ambiente['SURREAL_NAMESPACE'] == api.ambiente['SURREAL_DATABASE'] == 'open_notebook'
    assert api.ambiente['OPENAI_COMPATIBLE_BASE_URL_EMBEDDING'] == 'http://127.0.0.1:2/v1'
    assert (pastas.dados / 'open_notebook' / 'database' / 'migrations' / '1.surrealql').exists()
    assert '/api/config' not in json.dumps([p.saude for p in processos])


def test_senha_do_banco_e_a_mesma_a_cada_partida():
    assert supervisor.senha_do_banco('cifra') == supervisor.senha_do_banco('cifra')
    assert supervisor.senha_do_banco('cifra') != supervisor.senha_do_banco('outra')
