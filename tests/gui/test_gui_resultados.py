from pathlib import Path

from nicegui.testing.user import User

from concursos.aplicacao import analise
from concursos.exportacao import FormatoExportacao


def com_relatorio(projeto: Path) -> Path:
    (projeto / 'provas').mkdir(exist_ok=True)
    pasta = projeto / 'analises'
    pasta.mkdir(exist_ok=True)
    (pasta / 'index.html').write_text('<html><body>relatório</body></html>', encoding='utf-8')
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

    assert navegador == [pasta / 'index.html']


async def test_recomendacoes_e_pratica_explicam_quando_ainda_nao_existem(user: User, projeto):
    com_relatorio(projeto)

    await user.open('/resultados')
    user.find('Tópicos para estudar').click()
    await user.should_see(marker='sem-recomendacoes')
    user.find('Prática no TEC').click()
    await user.should_see(marker='sem-pratica')


async def test_recomendacoes_e_pratica_mostram_o_markdown(user: User, projeto):
    pasta = com_relatorio(projeto)
    (pasta / 'consolidado').mkdir()
    (pasta / 'consolidado' / 'recomendacoes_estudo.md').write_text('Revisar crase', encoding='utf-8')
    (pasta / 'pratica').mkdir()
    (pasta / 'pratica' / 'resumo_pratica.md').write_text('Prática da semana', encoding='utf-8')

    await user.open('/resultados')
    user.find('Tópicos para estudar').click()
    await user.should_see(marker='recomendacoes')
    user.find('Prática no TEC').click()
    await user.should_see(marker='pratica')


async def test_exportar_mostra_onde_gravou(user: User, projeto, monkeypatch):
    com_relatorio(projeto)
    pedidos: list[FormatoExportacao] = []

    def exportar_falso(contexto, formato):
        pedidos.append(formato)
        return contexto.analises / 'export' / f'consolidado.{formato}'

    monkeypatch.setattr(analise, 'exportar', exportar_falso)

    await user.open('/resultados')
    user.find('Exportar').click()
    user.find(marker='exportar-csv').click()

    await user.should_see(marker='exportado', retries=60)
    assert pedidos == [FormatoExportacao.CSV]


async def test_topico_fraco_abre_a_pergunta_nos_livros(user: User, projeto, monkeypatch):
    from concursos.aplicacao import estudo

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
    user.find('Tópicos para estudar').click()
    await user.should_see(marker='procurar-nos-livros')
    user.find(marker='procurar-nos-livros').click()

    await user.should_see(marker='nada-encontrado')
    assert perguntas == ['crase']


async def test_simulado_focado_explica_e_depois_mostra_os_dois(user: User, projeto, navegador):
    pasta = com_relatorio(projeto)
    await user.open('/resultados')
    user.find('Simulado focado').click()
    await user.should_see(marker='sem-simulado')

    (pasta / 'consolidado').mkdir()
    (pasta / 'consolidado' / 'simulado_focado.md').write_text(
        '# 12 questões nos tópicos fracos', encoding='utf-8'
    )
    (pasta / 'pratica').mkdir()
    (pasta / 'pratica' / 'simulado_tec.html').write_text('<html></html>', encoding='utf-8')
    await user.open('/resultados')
    user.find('Simulado focado').click()

    await user.should_see('12 questões nos tópicos fracos')
    user.find(marker='abrir-simulado-tec').click()
    assert navegador == [pasta / 'pratica' / 'simulado_tec.html']
