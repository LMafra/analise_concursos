from pathlib import Path

from nicegui.testing.user import User

from concursos.aplicacao import analise, estudo
from concursos.exportacao import FormatoExportacao
from concursos.relatorio_html import ARQUIVO_INDICE, ARQUIVO_RELATORIO_HTML


def com_relatorio(projeto: Path) -> Path:
    (projeto / 'provas').mkdir(exist_ok=True)
    pasta = projeto / 'analises'
    pasta.mkdir(exist_ok=True)
    (pasta / ARQUIVO_INDICE).write_text('<html><body>relatório</body></html>', encoding='utf-8')
    return pasta


async def test_sem_relatorio_explica_como_gerar(user: User, projeto):
    (projeto / 'provas').mkdir()

    await user.open('/resultados')

    await user.should_see(marker='sem-relatorio')
    await user.should_see('Analisar')


async def test_relatorio_vai_num_iframe_servido_so_por_endereco_proprio(user: User, projeto):
    com_relatorio(projeto)

    await user.open('/resultados')

    await user.should_see(marker='relatorio')
    iframe = next(iter(user.find(marker='relatorio').elements))
    assert iframe.tag == 'iframe'
    assert iframe.props['src'].startswith('/_analises/')
    assert '/index.html?v=' in iframe.props['src']
    assert str(projeto) not in iframe.props['src']


async def test_abrir_no_navegador_abre_o_index(user: User, projeto, navegador):
    pasta = com_relatorio(projeto)

    await user.open('/resultados')
    user.find(marker='abrir-navegador').click()

    assert navegador == [pasta / ARQUIVO_INDICE]


async def test_seletor_troca_o_iframe_para_o_concurso(user: User, projeto):
    pasta = com_relatorio(projeto)
    concurso = pasta / 'alfa'
    concurso.mkdir()
    (concurso / ARQUIVO_RELATORIO_HTML).write_text('<html><body>alfa</body></html>', encoding='utf-8')

    await user.open('/resultados')
    await user.should_see(marker='seletor-concurso-relatorio')
    seletor = next(iter(user.find(marker='seletor-concurso-relatorio').elements))
    seletor.set_value('alfa')

    iframe = next(iter(user.find(marker='relatorio').elements))
    assert '/alfa/relatorio.html?v=' in iframe.props['src']


async def test_recomendacoes_explicam_quando_ainda_nao_existem(user: User, projeto):
    com_relatorio(projeto)

    await user.open('/resultados')
    user.find('Tópicos').click()
    await user.should_see(marker='sem-recomendacoes')


async def test_recomendacoes_mostram_o_markdown(user: User, projeto):
    pasta = com_relatorio(projeto)
    (pasta / 'consolidado').mkdir()
    (pasta / 'consolidado' / 'recomendacoes_estudo.md').write_text('Revisar crase', encoding='utf-8')

    await user.open('/resultados')
    user.find('Tópicos').click()
    await user.should_see(marker='recomendacoes')


async def test_exportar_mostra_onde_gravou(user: User, projeto, monkeypatch):
    com_relatorio(projeto)
    pedidos: list[FormatoExportacao] = []

    def exportar_falso(contexto, formato):
        pedidos.append(formato)
        return contexto.analises / 'export' / f'consolidado.{formato}'

    monkeypatch.setattr(analise, 'exportar', exportar_falso)

    await user.open('/resultados')
    user.find(marker='exportar').click()
    user.find(marker='exportar-csv').click()

    await user.should_see(marker='exportado', retries=60)
    assert pedidos == [FormatoExportacao.CSV]


async def test_topico_fraco_abre_a_pergunta_nos_livros(user: User, projeto, monkeypatch):
    com_relatorio(projeto)
    monkeypatch.setattr(
        estudo, 'sugestoes_de_pergunta', lambda contexto: [estudo.Sugestao('Revisar crase', 'crase')]
    )
    monkeypatch.setattr(estudo, 'listar_livros', lambda contexto: [])
    monkeypatch.setattr(estudo, 'iniciar_trabalho', lambda contexto, ao_mudar=None: None)
    perguntas = []
    monkeypatch.setattr(
        estudo,
        'perguntar',
        lambda opcoes, pergunta, **kw: (
            perguntas.append(pergunta) or estudo.Resposta([], avisos=(estudo.TEXTO_NADA,))
        ),
    )

    await user.open('/resultados')
    user.find('Tópicos').click()
    await user.should_see(marker='procurar-nos-livros')
    user.find(marker='procurar-nos-livros').click()

    await user.should_see(marker='nada-encontrado')
    assert perguntas == ['crase']


async def test_simulado_e_pratica_leva_para_estudar(user: User, projeto, monkeypatch):
    com_relatorio(projeto)
    monkeypatch.setattr(estudo, 'listar_livros', lambda contexto: [])
    monkeypatch.setattr(estudo, 'iniciar_trabalho', lambda contexto, ao_mudar=None: None)
    monkeypatch.setattr(estudo, 'sugestoes_de_pergunta', lambda contexto: [])

    await user.open('/resultados')
    user.find(marker='ir-estudar-simulado').click()

    await user.should_see(marker='aba-simulado')
