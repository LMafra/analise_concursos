from pathlib import Path

import pytest
from conftest import criar_concurso
from test_pci_simulado import ALVO, ARQUIVOS_ALVO

from concursos.aplicacao import integracoes
from concursos.aplicacao.opcoes import Opcoes
from concursos.config.contexto import resolver_contexto
from concursos.erros import ErroDoAmbiente, ErroDoUsuario
from concursos.integracoes.pci_mcp import ProvaAnteriorPci
from concursos.integracoes.simulado_pci import nome_da_pasta

PROVAS = [
    ProvaAnteriorPci(
        id=i, descricao='Auditor', orgao=f'Órgão {i}', ano=2020 + i, organizadora='FGV', link=f'l{i}'
    )
    for i in (1, 2, 3)
]


@pytest.fixture
def contexto(tmp_path: Path):
    (tmp_path / 'provas').mkdir()
    return resolver_contexto(cwd=tmp_path, data_dir=tmp_path / '.concurso')


def roteiro(monkeypatch, efeitos: dict) -> list[int]:
    tentadas: list[int] = []

    def importar(opcoes, provas, identificador, alvo, esperar=None):
        tentadas.append(identificador)
        efeito = efeitos.get(identificador, 0)
        if isinstance(efeito, BaseException):
            raise efeito
        return efeito

    monkeypatch.setattr(integracoes, 'importar_simulado', importar)
    return tentadas


def test_lote_segue_depois_de_uma_falha_no_meio(contexto, monkeypatch):
    tentadas = roteiro(monkeypatch, {2: ErroDoAmbiente('a página não abriu', 'tente de novo')})
    mensagens: list[str] = []

    lote = integracoes.importar_simulados(Opcoes(contexto, saida=mensagens.append), PROVAS, [1, 2, 3], None)

    assert tentadas == [1, 2, 3]
    assert (lote.importadas, lote.falhas, lote.cancelado) == ([1, 3], {2: 'a página não abriu'}, False)
    assert mensagens[0].startswith('Passo 1 de 3: o navegador vai abrir a página da prova Órgão 1 2021')
    assert mensagens[-1] == 'provas anteriores: 2 importada(s); 1 com falha'


def test_cancelar_encerra_o_lote_e_lista_as_que_faltaram(contexto, monkeypatch):
    tentadas = roteiro(monkeypatch, {2: integracoes.ImportacaoCanceladaError()})

    lote = integracoes.importar_simulados(Opcoes(contexto), PROVAS, [1, 2, 3], None)

    assert tentadas == [1, 2]
    assert (lote.importadas, lote.nao_tentadas, lote.cancelado) == ([1], [2, 3], True)


def test_prova_ja_importada_nao_abre_de_novo_e_cadastro_incompleto_e_falha(contexto, monkeypatch):
    pasta = contexto.provas / nome_da_pasta(PROVAS[0])
    pasta.mkdir()
    (pasta / 'concurso.yaml').write_text('nome: x\nprovas: {unica: {gabarito: g.txt}}\n', encoding='utf-8')
    tentadas = roteiro(monkeypatch, {3: 1})

    lote = integracoes.importar_simulados(Opcoes(contexto), PROVAS, [1, 2, 3], None)

    assert tentadas == [2, 3]
    assert (lote.ja_importadas, lote.importadas, lote.falhas) == ([1], [2], {3: 'o cadastro não terminou'})


def test_erro_do_usuario_numa_prova_tambem_nao_para_o_lote(contexto, monkeypatch):
    roteiro(monkeypatch, {1: ErroDoUsuario('nenhum arquivo apareceu', 'salve os PDFs')})

    lote = integracoes.importar_simulados(Opcoes(contexto), PROVAS, [1, 2], None)

    assert (lote.importadas, list(lote.falhas)) == ([2], [1])


def test_termos_previstos_mostram_o_que_a_busca_usara(contexto):
    criar_concurso(contexto.provas, 'alvo', ALVO, ARQUIVOS_ALVO)

    assert integracoes.termos_previstos(contexto, 'alvo') == ['analista ti cebraspe', 'analista ti']
    assert integracoes.termos_previstos(contexto, None) == []
    assert integracoes.termos_previstos(contexto, 'nao_existe') == []
