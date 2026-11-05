import sys
import tomllib

import pytest
from concurso_sintetico import ARQUIVOS_SIMPLES, config_simples, criar_concurso
from nicegui.testing.user import User

from concursos.aplicacao.preferencias import ler_analise
from concursos.gui.estado import ESTADO


def elemento(user: User, marca: str):
    return next(iter(user.find(marker=marca).elements))


async def test_limiares_e_concurso_alvo_gravam_analise_para_a_proxima_analise(user: User, projeto):
    criar_concurso(projeto / 'provas', 'alfa', config_simples('alfa'), ARQUIVOS_SIMPLES)

    await user.open('/configuracoes')
    elemento(user, 'limiar-confianca').value = 0.8
    elemento(user, 'limiar-topico').value = 0.5
    elemento(user, 'concurso-alvo').value = 'alfa'
    user.find(marker='salvar-analise').click()

    await user.should_see('Configurações gravadas; valem na próxima análise.')
    preferencias = ler_analise(ESTADO.contexto())
    assert (preferencias.limiar_confianca, preferencias.limiar_topico_baixo) == (0.8, 0.5)
    assert preferencias.concurso_alvo == 'alfa'


async def test_ia_comeca_desmarcada_e_sem_formulario(user: User, projeto):
    await user.open('/configuracoes')

    assert elemento(user, 'usar-ia').value is False
    await user.should_not_see(marker='chave-ia')


async def test_ligar_ia_mostra_o_que_vai_e_guarda_a_chave_fora_do_toml(
    user: User, projeto, home_isolada, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setitem(sys.modules, 'keyring', None)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)

    await user.open('/configuracoes')
    user.find(marker='usar-ia').click()
    await user.should_see(marker='aviso-ia')
    await user.should_see('Só o texto do edital')
    elemento(user, 'provedor-ia').value = 'openai'
    user.find(marker='chave-ia').type('sk-segredo-de-teste')
    user.find(marker='ligar-ia').click()

    await user.should_see('IA ligada.')
    config = (home_isolada / 'config.toml').read_text(encoding='utf-8')
    assert tomllib.loads(config)['llm']['provedor'] == 'openai'
    assert 'sk-segredo-de-teste' not in config
    assert 'sk-segredo-de-teste' in (home_isolada / '.env').read_text(encoding='utf-8')


async def test_desmarcar_desliga_a_ia(user: User, projeto, home_isolada):
    await user.open('/configuracoes')
    user.find(marker='usar-ia').click()
    elemento(user, 'provedor-ia').value = 'ollama'
    user.find(marker='ligar-ia').click()
    await user.should_see('IA ligada.')

    user.find(marker='usar-ia').click()

    await user.should_see('Desligada: a leitura do edital é só local.')
    llm = tomllib.loads((home_isolada / 'config.toml').read_text(encoding='utf-8'))['llm']
    assert llm['provedor'] == 'nenhum'
