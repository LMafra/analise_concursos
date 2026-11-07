import io
import logging

import pytest

from concursos.cli import main
from concursos.cli.erros import ARQUIVO_LOG, FormatoDoConsole, configurar_log
from concursos.erros import ErroDoUsuario, avisar
from concursos.gui.progresso import Andamento, HandlerDoPainel


@pytest.fixture
def tela():
    saida = io.StringIO()
    handler = logging.StreamHandler(saida)
    handler.setFormatter(FormatoDoConsole())
    logger = logging.getLogger('teste_mensagens')
    logger.handlers, logger.propagate = [handler], False
    logger.setLevel(logging.DEBUG)
    handler.setLevel(logging.INFO)
    yield logger, handler, saida
    logger.handlers = []


def test_aviso_em_tres_linhas(tela):
    logger, _, saida = tela

    avisar(logger, 'alfa: não encontrei a regra de correção no edital.', 'confira em Concursos.', 'fator 0')

    assert saida.getvalue() == (
        'aviso: alfa: não encontrei a regra de correção no edital.\ndica: confira em Concursos.\ndetalhe: fator 0\n'
    )


def test_aviso_sem_dica_nem_detalhe_nao_imprime_none(tela):
    logger, _, saida = tela

    avisar(logger, 'só o texto, com 100% de certeza')
    logger.warning('aviso antigo, sem extra')

    assert saida.getvalue() == 'aviso: só o texto, com 100% de certeza\naviso: aviso antigo, sem extra\n'


def test_info_sai_sem_prefixo_e_erro_com_prefixo(tela):
    logger, _, saida = tela

    logger.info('Analisando alfa')
    logger.error('não deu')

    assert saida.getvalue() == 'Analisando alfa\nerro: não deu\n'


def test_quiet_mostra_o_aviso_inteiro_e_esconde_o_info(tela):
    logger, handler, saida = tela
    handler.setLevel(logging.WARNING)

    logger.info('Analisando alfa')
    avisar(logger, 'faltou algo', detalhe='campo x')

    assert saida.getvalue() == 'aviso: faltou algo\ndetalhe: campo x\n'


def test_verbose_marca_o_debug(tela):
    logger, handler, saida = tela
    handler.setLevel(logging.DEBUG)

    logger.debug('passo interno')

    assert saida.getvalue() == 'debug: passo interno\n'


def test_arquivo_de_log_guarda_dica_e_detalhe(tmp_path):
    arquivo = configurar_log(tmp_path)

    avisar(logging.getLogger('concursos.teste'), 'faltou algo', 'faça x', 'campo y')

    texto = arquivo.read_text(encoding='utf-8')
    assert arquivo.name == ARQUIVO_LOG
    assert 'faltou algo\n    dica: faça x\n    detalhe: campo y' in texto


def test_log_do_painel_da_gui_mostra_dica_e_detalhe(tela):
    logger, _, _ = tela
    andamento = Andamento()
    logger.addHandler(HandlerDoPainel(andamento))

    avisar(logger, 'faltou algo', 'faça x', 'campo y')

    [linha] = andamento.retirar_linhas()
    assert linha.endswith('WARNING faltou algo\n    dica: faça x\n    detalhe: campo y')


def test_erro_do_usuario_com_detalhe(monkeypatch, capsys):
    def falha(*_args, **_kwargs):
        raise ErroDoUsuario(
            'Não consegui ler os dados do concurso.', 'confira na tela Concursos.', 'YAML inválido'
        )

    monkeypatch.setattr('concursos.cli.app', falha)

    assert main(['status']) == 1
    assert capsys.readouterr().err.endswith(
        'erro: Não consegui ler os dados do concurso.\ndica: confira na tela Concursos.\ndetalhe: YAML inválido\n'
    )
