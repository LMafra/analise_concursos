import pytest

from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.configuracao import carregar_configuracao_global


def test_concurso_alvo_e_opcional_e_comeca_vazio(tmp_path):
    assert carregar_configuracao_global(tmp_path / 'config.yaml').concurso_alvo is None


def test_concurso_alvo_aceita_o_nome_da_pasta_do_concurso(tmp_path):
    caminho = tmp_path / 'config.yaml'
    caminho.write_text('concurso_alvo: tcu_25\nlimiar_topico_baixo: 0.5\n', encoding='utf-8')

    configuracao = carregar_configuracao_global(caminho)

    assert (configuracao.concurso_alvo, configuracao.limiar_topico_baixo) == ('tcu_25', 0.5)


@pytest.mark.parametrize('valor', ['0.5', "''", '[tcu_25]'])
def test_concurso_alvo_que_nao_e_nome_aponta_o_campo(tmp_path, valor):
    caminho = tmp_path / 'config.yaml'
    caminho.write_text(f'concurso_alvo: {valor}\n', encoding='utf-8')

    with pytest.raises(ConfiguracaoInvalidaError, match='concurso_alvo'):
        carregar_configuracao_global(caminho)
