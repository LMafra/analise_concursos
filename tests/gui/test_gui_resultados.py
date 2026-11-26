from pathlib import Path

from nicegui.testing.user import User

from concursos.aplicacao import analise, estudo
from concursos.exportacao import FormatoExportacao
from concursos.relatorio_html import ARQUIVO_CONCURSOS, ARQUIVO_INDICE, ARQUIVO_SIMULADOS, ARQUIVO_TEC


def com_relatorio(projeto: Path) -> Path:
    (projeto / 'provas').mkdir(exist_ok=True)
    pasta = projeto / 'analises'
    pasta.mkdir(exist_ok=True)
    (pasta / ARQUIVO_INDICE).write_text('<html><body>painel</body></html>', encoding='utf-8')
    (pasta / ARQUIVO_CONCURSOS).write_text('<html><body>concursos</body></html>', encoding='utf-8')
    (pasta / ARQUIVO_TEC).write_text('<html><body>tec</body></html>', encoding='utf-8')
    (pasta / ARQUIVO_SIMULADOS).write_text('<html><body>simulados</body></html>', encoding='utf-8')
    return pasta


async def test_sem_relatorio_explica_como_gerar(user: User, projeto):
    (projeto / 'provas').mkdir()

    await user.open('/resultados')

    await user.should_see(marker='sem-concursos')
    await user.should_see('Analisar')


async def test_relatorio_vai_num_iframe_servido_so_por_endereco_proprio(user: User, projeto):
    com_relatorio(projeto)

    await user.open('/resultados')

    await user.should_see(marker='relatorio-concursos')
    iframe = next(iter(user.find(marker='relatorio-concursos').elements))
    assert iframe.tag == 'iframe'
    assert iframe.props['src'].startswith('/_analises/')
    assert '/concursos.html?v=' in iframe.props['src']
    assert str(projeto) not in iframe.props['src']


async def test_abrir_no_navegador_abre_o_index(user: User, projeto, navegador):
    pasta = com_relatorio(projeto)

    await user.open('/resultados')
    user.find(marker='abrir-navegador').click()

    assert navegador == [pasta / ARQUIVO_CONCURSOS]


async def test_aba_tec_troca_o_iframe(user: User, projeto):
    com_relatorio(projeto)

    await user.open('/resultados')
    user.find(marker='aba-resultado-tec').click()

    await user.should_see(marker='relatorio-tec')
    iframe = next(iter(user.find(marker='relatorio-tec').elements))
    assert '/tec.html?v=' in iframe.props['src']


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

    await user.should_see(marker='nada-encontrado', retries=60)
    assert perguntas == ['crase']


async def test_filtro_de_concurso_escolhe_o_diagnostico(user: User, projeto, monkeypatch):
    from concursos.aplicacao import nomes
    from concursos.aplicacao import resultados as resultados_mod
    from concursos.aplicacao.resultados import PontoDeNota, ResumoVisual

    com_relatorio(projeto)
    resumo = ResumoVisual(
        pontos=(
            PontoDeNota('alfa-2024', 1, 60.0, 70.0, False),
            PontoDeNota('beta-2025', 2, 80.0, 70.0, True),
        )
    )
    monkeypatch.setattr(resultados_mod, 'resumo_visual', lambda contexto: resumo)
    monkeypatch.setattr(
        nomes,
        'opcoes_de_concurso',
        lambda contexto: {
            'alfa-2024': 'Alfa 2024 — Analista',
            'beta-2025': 'Beta 2025 — Auditor',
        },
    )

    await user.open('/resultados')

    await user.should_see(marker='concurso-resultados')
    await user.should_see('Concurso selecionado')
    select = user.find(marker='concurso-resultados').elements.pop()
    assert 'ca-seletor' in select._classes
    assert any(
        'ca-rotulo-campo' in elemento._classes for elemento in user.find('Concurso selecionado').elements
    )
    assert select.value == 'beta-2025'
    await user.should_see('beta-2025 — 10,0 pontos percentuais acima do corte')

    await user.open('/resultados?concurso=alfa-2024')

    select = user.find(marker='concurso-resultados').elements.pop()
    assert select.value == 'alfa-2024'
    await user.should_see('alfa-2024 — 10,0 pontos percentuais abaixo do corte')


async def test_aba_simulados_mostra_o_html(user: User, projeto):
    com_relatorio(projeto)

    await user.open('/resultados')
    user.find(marker='aba-resultado-simulados').click()

    await user.should_see(marker='relatorio-simulados')
    iframe = next(iter(user.find(marker='relatorio-simulados').elements))
    assert '/simulados.html?v=' in iframe.props['src']
