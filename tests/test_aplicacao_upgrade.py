import pytest

from concursos.aplicacao import atualizador as aplicacao
from concursos.aplicacao.opcoes import Opcoes
from concursos.atualizador import Artefato
from concursos.config.contexto import resolver_contexto
from concursos.erros import ErroDoUsuario
from concursos.modelo import CanalAtualizacao

NOVIDADE = aplicacao.Novidade(
    versao='0.6.0',
    canal=CanalAtualizacao.STABLE,
    notas='https://github.com/LMafra/analise_concursos/releases/tag/v0.6.0',
    plataforma='linux-x86_64',
    artefato=Artefato('concurso-analise-0.6.0-linux-x86_64.AppImage', 'a' * 64, 250_000_000),
    url='https://github.com/LMafra/analise_concursos/releases/download/v0.6.0/x',
)


class Confirma:
    def __init__(self, resposta: bool) -> None:
        self.resposta = resposta
        self.perguntas: list[str] = []

    def confirmar(self, pergunta: str, padrao: bool = False) -> bool:
        self.perguntas.append(pergunta)
        return self.resposta


@pytest.fixture
def opcoes(tmp_path, home_isolada):
    def montar(**campos) -> tuple[Opcoes, list[str]]:
        mensagens: list[str] = []
        return Opcoes(resolver_contexto(cwd=tmp_path), saida=mensagens.append, **campos), mensagens

    return montar


@pytest.fixture
def sem_rede(monkeypatch):
    def proibido(*args, **kwargs):
        raise AssertionError('consultou a rede')

    monkeypatch.setattr(aplicacao, 'verificar', proibido)


def test_dry_run_nao_consulta(opcoes, sem_rede):
    o, mensagens = opcoes(dry_run=True)

    assert aplicacao.atualizar_executavel(o) == 0
    assert 'dry-run' in mensagens[0]


def test_offline_e_erro_com_dica(opcoes, sem_rede):
    o, _ = opcoes(rede=False)

    with pytest.raises(ErroDoUsuario, match='offline'):
        aplicacao.atualizar_executavel(o)


def test_sem_run_so_mostra_a_versao_nova(opcoes, monkeypatch):
    monkeypatch.setattr(aplicacao, 'verificar', lambda canal, **kwargs: NOVIDADE)
    o, mensagens = opcoes()

    assert aplicacao.atualizar_executavel(o, instalar_com=pytest.fail) == 0
    assert 'versão nova: 0.6.0' in mensagens[0]
    assert 'upgrade --run' in mensagens[1]


def test_canal_padrao_vem_da_configuracao(opcoes, monkeypatch, home_isolada):
    canais = []
    monkeypatch.setattr(aplicacao, 'verificar', lambda canal, **kwargs: canais.append(canal))
    o, _ = opcoes()
    aplicacao.gravar_preferencias(o.contexto.config_global, aplicacao.Preferencias(CanalAtualizacao.BETA))

    aplicacao.atualizar_executavel(o)

    assert canais == [CanalAtualizacao.BETA]


def test_run_pergunta_antes_e_respeita_o_nao(opcoes, monkeypatch):
    monkeypatch.setattr(aplicacao, 'verificar', lambda canal, **kwargs: NOVIDADE)
    interacao = Confirma(False)
    o, mensagens = opcoes(interacao=interacao)

    assert aplicacao.atualizar_executavel(o, executar=True, instalar_com=pytest.fail) == 0
    assert '250 MB' in interacao.perguntas[0]
    assert mensagens[-1] == 'atualização cancelada'


def test_run_confirmado_instala(opcoes, monkeypatch, tmp_path):
    monkeypatch.setattr(aplicacao, 'verificar', lambda canal, **kwargs: NOVIDADE)
    o, mensagens = opcoes(interacao=Confirma(True))
    instalados = []

    def instalar(novidade, **kwargs):
        instalados.append(novidade)
        return aplicacao.Instalacao('0.6.0', tmp_path / 'x.AppImage', setup_em_andamento=False)

    assert aplicacao.atualizar_executavel(o, executar=True, instalar_com=instalar) == 0
    assert instalados == [NOVIDADE]
    assert 'atualizado para 0.6.0' in mensagens[-1]


def test_sem_novidade_diz_que_esta_na_mais_nova(opcoes, monkeypatch):
    monkeypatch.setattr(aplicacao, 'verificar', lambda canal, **kwargs: None)
    o, mensagens = opcoes()

    aplicacao.atualizar_executavel(o)

    assert 'mais nova do canal stable' in mensagens[0]
