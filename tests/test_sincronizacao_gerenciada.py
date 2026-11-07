import pytest
from servidor_open_notebook import ServidorOpenNotebook

from concursos.aplicacao import estudo, integracoes
from concursos.aplicacao.opcoes import Opcoes
from concursos.config.contexto import Contexto
from concursos.integracoes.open_notebook import ClienteOpenNotebook
from concursos.integracoes.sincronizacao_notebook import Documento, EstadoSincronizacao, Sincronizador


@pytest.fixture
def servidor():
    servidor = ServidorOpenNotebook(senha='s')
    yield servidor
    servidor.desligar()


def sincronizador(servidor, tmp_path):
    return Sincronizador(
        ClienteOpenNotebook(servidor.url, 's'),
        EstadoSincronizacao.ler(tmp_path / 'open_notebook.json'),
        instancia='gerenciada',
        por_nome=False,
        prefixo_nome='Meus concursos · ',
    )


def test_notebook_do_projeto_so_pelo_id_e_com_o_nome_da_pasta(servidor, tmp_path):
    servidor.criar_notebook('Meus concursos · tcu — candidato 1')
    sinc = sincronizador(servidor, tmp_path)

    notebook_id = sinc.notebook('tcu', 'tcu — candidato 1', [Documento('a', 't', 'x')], [])

    assert servidor.notebooks[notebook_id]['name'] == 'Meus concursos · tcu — candidato 1'
    assert len(servidor.notebooks) == 2
    assert sinc.estado.dados['instancias']['gerenciada']['notebooks']['tcu']['id'] == notebook_id
    assert sinc.notebook('tcu', 'tcu — candidato 1', [], []) == notebook_id


def test_notebook_compartilhado_reusa_pelo_nome(servidor, tmp_path):
    existente = servidor.criar_notebook('Legislação')

    notebook_id = sincronizador(servidor, tmp_path).notebook(
        '_legislacao', 'Legislação', [], [], compartilhado=True
    )

    assert notebook_id == existente['id']


def test_depois_da_analise_usa_a_instancia_gerenciada_quando_preparada(tmp_path, monkeypatch):
    contexto = Contexto(
        tmp_path, tmp_path / 'home', tmp_path / '.concurso', tmp_path / 'provas', tmp_path / 'a'
    )
    chamadas = []
    monkeypatch.setattr(
        estudo, 'situacao_do_estudo', lambda c: estudo.SituacaoEstudo(True, '1.15.1-1', False, False, '')
    )
    monkeypatch.setattr(
        integracoes,
        'sincronizar_gerenciada',
        lambda c, cand, conc: chamadas.append(cand) or integracoes.RelatorioSincronizacao(),
    )

    integracoes.sincronizar_depois_da_analise(Opcoes(contexto), [None])

    assert chamadas == [[None]]


def test_sem_preparar_nada_e_sincronizado(tmp_path, monkeypatch):
    contexto = Contexto(
        tmp_path, tmp_path / 'home', tmp_path / '.concurso', tmp_path / 'provas', tmp_path / 'a'
    )
    monkeypatch.setattr(
        integracoes, 'sincronizar_gerenciada', lambda *a: pytest.fail('não devia sincronizar')
    )

    integracoes.sincronizar_depois_da_analise(Opcoes(contexto), [None])


def test_falha_do_open_notebook_do_app_nao_manda_configurar_o_endereco(tmp_path, monkeypatch, caplog):
    contexto = Contexto(
        tmp_path, tmp_path / 'home', tmp_path / '.concurso', tmp_path / 'provas', tmp_path / 'a'
    )
    monkeypatch.setattr(
        estudo, 'situacao_do_estudo', lambda c: estudo.SituacaoEstudo(True, '1.15.1-1', False, False, '')
    )

    def fora_do_ar(*_args):
        ClienteOpenNotebook('http://127.0.0.1:1', timeout=2).saude()

    monkeypatch.setattr(integracoes, 'sincronizar_gerenciada', fora_do_ar)

    integracoes.sincronizar_depois_da_analise(Opcoes(contexto), [None])

    [registro] = [r for r in caplog.records if r.levelname == 'WARNING']
    assert 'Estudar' in registro.dica and 'Avançado' not in registro.dica
