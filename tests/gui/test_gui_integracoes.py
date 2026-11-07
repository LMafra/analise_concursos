from dataclasses import replace
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing.user import User

from concursos.aplicacao import cadastro, captura_tec, integracoes, simulados
from concursos.config.contexto import ler_toml
from concursos.gui.estado import ESTADO
from concursos.gui.paginas import tec as pagina_tec
from concursos.integracoes.pci_mcp import ConcursoPci, DatasInscricao, ProvaAnteriorPci
from concursos.integracoes.sincronizacao_pci import Interesses

ENTRADA = Path(__file__).parents[1] / 'contrato_tec' / 'entrada'

SEFAZ = ConcursoPci(
    id=101,
    titulo='SEFAZ-DF abre 50 vagas',
    uf='DF',
    cargos=('Auditor',),
    cargos_resumo='Auditor',
    vagas_salario='50 vagas até R$ 20.000',
    formacao='superior',
    regiao='centro-oeste',
    datas=DatasInscricao(fim='20/11/2026', dias_ate_fim=15),
    link='https://www.pciconcursos.com.br/noticias/sefaz-df',
    data_referencia='2026-11-05',
)
PROVA = ProvaAnteriorPci(
    id=7,
    descricao='Auditor Fiscal',
    orgao='SEFAZ-DF',
    ano=2020,
    organizadora='Cebraspe',
    link='https://www.pciconcursos.com.br/provas/auditor-sefaz-df',
)


def ligar_pci() -> None:
    integracoes.ligar_pci(ESTADO.contexto(), 'https://pci.exemplo/mcp')


def proibido(*_args, **_kwargs):
    raise AssertionError('desligada, a integração não pode ser chamada')


ENDERECOS = {
    'Encontrar concursos': '/?aba=encontrar',
    'Provas anteriores': '/?aba=provas',
    'open-notebook': '/configuracoes?secao=avancado',
    'Prática no TEC': '/tec',
}


async def abrir_aba(user: User, aba: str) -> None:
    await user.open(ENDERECOS[aba])


async def test_pci_desligado_mostra_o_aviso_e_nao_consulta(user: User, projeto, monkeypatch):
    monkeypatch.setattr(integracoes, 'descobrir', proibido)

    await abrir_aba(user, 'Encontrar concursos')

    await user.should_see(marker='aviso-pci')
    await user.should_see('só termos de busca')
    await user.should_not_see(marker='buscar-pci')


async def test_ligar_pci_grava_enabled(user: User, projeto):
    await abrir_aba(user, 'Encontrar concursos')
    user.find(marker='ligar-pci').click()

    await user.should_see(marker='buscar-pci')
    assert ler_toml(ESTADO.contexto().config_global)['pci_mcp']['enabled'] is True


def elemento(user: User, marca: str):
    (achado,) = user.find(marker=marca).elements
    return achado


def busca_falsa(monkeypatch, resultado=(SEFAZ,)) -> list[dict]:
    filtros: list[dict] = []

    def descobrir_falso(opcoes, cargos=None, uf=None, cidade=None, regiao=None, termo=None, refresh=False):
        filtros.append({'cargos': cargos, 'uf': uf, 'cidade': cidade, 'regiao': regiao, 'refresh': refresh})
        return list(resultado)

    monkeypatch.setattr(integracoes, 'descobrir', descobrir_falso)
    return filtros


async def test_encontrar_mostra_regiao_prazo_e_acompanhar_registra_no_radar(user: User, projeto, monkeypatch):
    ligar_pci()
    filtros = busca_falsa(monkeypatch)
    await abrir_aba(user, 'Encontrar concursos')
    user.find(marker='filtro-cargo').type('Auditor, Analista')
    elemento(user, 'filtro-uf').value = 'DF'
    elemento(user, 'filtro-cidade').value = 'Brasília'
    user.find(marker='buscar-pci').click()

    await user.should_see('SEFAZ-DF abre 50 vagas')
    await user.should_see('Centro-Oeste · DF · Auditor')
    await user.should_see('20/11/2026 (15 dias)')
    assert filtros == [
        {
            'cargos': ['Auditor', 'Analista'],
            'uf': 'DF',
            'cidade': 'Brasília',
            'regiao': None,
            'refresh': False,
        }
    ]
    user.find(marker='acompanhar-101').click()

    await user.should_see(marker='interesse-101')
    assert Interesses.do_projeto(ESTADO.contexto().projeto).obter(101)['titulo'] == SEFAZ.titulo


async def test_cidade_so_fica_ativa_com_uf_e_mostra_os_municipios_dela(user: User, projeto):
    ligar_pci()
    await abrir_aba(user, 'Encontrar concursos')
    cidade = elemento(user, 'filtro-cidade')
    assert not cidade.enabled

    elemento(user, 'filtro-uf').value = 'MG'
    assert cidade.enabled and 'Belo Horizonte' in cidade.options and 'Brasília' not in cidade.options
    cidade.value = 'Belo Horizonte'
    elemento(user, 'filtro-uf').value = 'SP'
    assert cidade.value is None and 'Campinas' in cidade.options


async def test_nacional_aparece_como_todas_as_regioes(user: User, projeto, monkeypatch):
    ligar_pci()
    nacional = replace(SEFAZ, id=102, titulo='INB abre vagas', uf='BR', cargos_resumo='Vários cargos')
    busca_falsa(monkeypatch, (nacional,))
    await abrir_aba(user, 'Encontrar concursos')
    user.find(marker='buscar-pci').click()

    await user.should_see('Nacional — todas as regiões · Vários cargos')


async def test_lembrar_os_filtros_grava_e_preenche_na_volta(user: User, projeto, monkeypatch):
    ligar_pci()
    busca_falsa(monkeypatch)
    await abrir_aba(user, 'Encontrar concursos')
    user.find(marker='filtro-cargo').type('Auditor')
    elemento(user, 'filtro-uf').value = 'MG'
    elemento(user, 'filtro-cidade').value = 'Belo Horizonte'
    elemento(user, 'lembrar-filtros').value = True
    user.find(marker='buscar-pci').click()
    await user.should_see('SEFAZ-DF abre 50 vagas')

    secao = ler_toml(ESTADO.contexto().config_global)['pci_mcp']
    assert (secao['cargos'], secao['uf'], secao['cidade']) == (['Auditor'], 'mg', 'Belo Horizonte')
    await abrir_aba(user, 'Encontrar concursos')
    assert elemento(user, 'filtro-uf').value == 'MG'
    assert elemento(user, 'filtro-cidade').value == 'Belo Horizonte'
    assert elemento(user, 'filtro-cargo').value == 'Auditor'


async def test_situacao_do_cache_e_atualizar_agora(user: User, projeto, monkeypatch):
    ligar_pci()
    filtros = busca_falsa(monkeypatch)
    monkeypatch.setattr(integracoes, 'situacao_do_cache', lambda contexto: 'Atualizado há 3 horas')
    await abrir_aba(user, 'Encontrar concursos')

    await user.should_see('Atualizado há 3 horas')
    user.find(marker='atualizar-pci').click()
    await user.should_see('SEFAZ-DF abre 50 vagas')
    assert filtros[-1]['refresh'] is True


async def test_adicionar_ao_projeto_cria_o_concurso_incompleto_na_lista(user: User, projeto, monkeypatch):
    ligar_pci()
    busca_falsa(monkeypatch)
    await abrir_aba(user, 'Encontrar concursos')
    user.find(marker='buscar-pci').click()
    await user.should_see('SEFAZ-DF abre 50 vagas')
    user.find(marker='adicionar-101').click()

    await user.should_see('SEFAZ-DF abre 50 vagas')
    await user.should_see('a confirmar')
    await user.should_see('Adicionar o edital e a prova')
    (pasta,) = [p for p in ESTADO.contexto().provas.iterdir() if p.is_dir()]
    assert pasta.name.startswith('sefaz_df')


async def test_importar_simulado_pode_ser_cancelado(user: User, projeto, monkeypatch, tmp_path):
    ligar_pci()
    monkeypatch.setattr(
        integracoes,
        'provas_anteriores',
        lambda opcoes, concurso=None, termos=None: integracoes.ProvasAnteriores(None, 'auditor', [PROVA]),
    )

    def importar_falso(opcoes, provas, identificador, alvo, esperar=None):
        esperar(tmp_path, ['prova.pdf'], 0.0, 30.0)
        raise AssertionError('a espera devia ter sido cancelada')

    monkeypatch.setattr(integracoes, 'importar_simulado', importar_falso)
    await abrir_aba(user, 'Provas anteriores')
    user.find(marker='termo-provas').type('auditor sefaz')
    user.find(marker='buscar-provas').click()
    await user.should_see('Auditor Fiscal')
    user.find(marker='importar-7').click()
    await user.should_see(marker='cancelar-importacao')
    user.find(marker='cancelar-importacao').click()

    await user.should_see('Importação cancelada')


SEGUNDA = ProvaAnteriorPci(
    id=8, descricao='Auditor', orgao='SEFAZ-DF', ano=2015, organizadora='Cebraspe', link='l8'
)


def busca_de_provas(monkeypatch) -> None:
    monkeypatch.setattr(
        integracoes,
        'provas_anteriores',
        lambda opcoes, concurso=None, termos=None: integracoes.ProvasAnteriores(
            None, 'auditor sefaz', [PROVA, SEGUNDA]
        ),
    )


async def test_termo_explicado_e_termo_automatico_no_campo(user: User, projeto, monkeypatch):
    ligar_pci()
    monkeypatch.setattr(integracoes, 'termos_previstos', lambda contexto, alvo: ['auditor controle cebraspe'])
    monkeypatch.setattr(
        'concursos.gui.paginas.encontrar.opcoes_de_concurso', lambda contexto: {'tcu_2025': 'TCU 2025'}
    )
    await abrir_aba(user, 'Provas anteriores')

    await user.should_see('só aparecem as provas que têm todas elas')
    elemento(user, 'alvo-provas').value = 'tcu_2025'
    assert elemento(user, 'termo-provas').props['placeholder'] == 'auditor controle cebraspe'


async def test_importar_todas_em_lote_e_mostrar_o_simulado_focado(user: User, projeto, monkeypatch):
    ligar_pci()
    busca_de_provas(monkeypatch)
    tentadas: list[int] = []
    monkeypatch.setattr(
        integracoes,
        'importar_simulado',
        lambda opcoes, provas, identificador, alvo, esperar=None: tentadas.append(identificador) or 0,
    )
    focado = type('Focado', (), {'total': 14})()
    monkeypatch.setattr(simulados, 'simulado_focado_do_projeto', lambda opcoes: focado)
    monkeypatch.setattr(
        simulados, 'texto_do_simulado_focado', lambda contexto: '# Simulado focado\n\n- TCU 2019'
    )
    await abrir_aba(user, 'Provas anteriores')
    user.find(marker='termo-provas').type('auditor sefaz')
    user.find(marker='buscar-provas').click()
    await user.should_see('Busca: auditor sefaz')
    user.find(marker='importar-todas').click()

    await user.should_see(marker='simulado-importado')
    assert tentadas == [7, 8]
    await user.should_see('Simulado focado: 14 questões das provas anteriores nos seus tópicos mais fracos')
    user.find(marker='ver-simulado-focado').click()
    await user.should_see('TCU 2019')


async def test_importar_selecionadas_so_as_marcadas(user: User, projeto, monkeypatch):
    ligar_pci()
    busca_de_provas(monkeypatch)
    tentadas: list[int] = []
    monkeypatch.setattr(
        integracoes,
        'importar_simulado',
        lambda opcoes, provas, identificador, alvo, esperar=None: tentadas.append(identificador) or 0,
    )
    monkeypatch.setattr(simulados, 'simulado_focado_do_projeto', lambda opcoes: None)
    await abrir_aba(user, 'Provas anteriores')
    user.find(marker='termo-provas').type('auditor sefaz')
    user.find(marker='buscar-provas').click()
    await user.should_see('Busca: auditor sefaz')
    elemento(user, 'selecionar-8').value = True
    user.find(marker='importar-selecionadas').click()

    await user.should_see(marker='simulado-importado')
    assert tentadas == [8]


async def test_importar_simulado_concluido(user: User, projeto, monkeypatch):
    ligar_pci()
    monkeypatch.setattr(
        integracoes,
        'provas_anteriores',
        lambda opcoes, concurso=None, termos=None: integracoes.ProvasAnteriores(None, 'auditor', [PROVA]),
    )
    monkeypatch.setattr(integracoes, 'importar_simulado', lambda *a, **k: 0)
    await abrir_aba(user, 'Provas anteriores')
    user.find(marker='termo-provas').type('auditor sefaz')
    user.find(marker='buscar-provas').click()
    await user.should_see('Auditor Fiscal')
    user.find(marker='importar-7').click()

    await user.should_see(marker='simulado-importado')


async def test_open_notebook_desligado_mostra_o_que_e_enviado(user: User, projeto, monkeypatch):
    monkeypatch.setattr(integracoes, 'sincronizar', proibido)

    await abrir_aba(user, 'open-notebook')

    await user.should_see(marker='aviso-notebook')
    await user.should_see('pseudônimo')
    await user.should_not_see(marker='sincronizar-notebook')


async def test_ligar_e_sincronizar_open_notebook(user: User, projeto, monkeypatch):
    class Relatorio:
        def formatar(self) -> str:
            return 'notebooks: 1 criados, 0 reusados'

    monkeypatch.setattr(integracoes, 'sincronizar', lambda opcoes, todos=False: Relatorio())
    await abrir_aba(user, 'open-notebook')
    user.find(marker='ligar-notebook').click()
    await user.should_see(marker='sincronizar-notebook')
    configuracao = ler_toml(ESTADO.contexto().config_global)['open_notebook']
    assert configuracao['enabled'] is True
    assert configuracao['consentimento'] is True
    user.find(marker='sincronizar-notebook').click()

    await user.should_see('notebooks: 1 criados, 0 reusados')


async def soltar_tec(user: User, *arquivos: tuple[str, bytes]) -> None:
    upload = next(iter(user.find(marker='soltar-tec').elements))
    await upload.handle_uploads(
        [ui.upload.SmallFileUpload(nome, 'application/json', conteudo) for nome, conteudo in arquivos]
    )


async def test_soltar_exportacao_valida_copia_para_a_entrada(user: User, projeto):
    nome = 'tec-erros-computador-2026-11-03.json'
    await abrir_aba(user, 'Prática no TEC')

    await soltar_tec(user, (nome, (ENTRADA / nome).read_bytes()))

    await user.should_see(marker='tec-importado')
    assert (projeto / 'tec' / nome).is_file()
    user.find('Analisar agora').click()
    assert ESTADO.pedir_analise is True


async def test_soltar_exportacao_invalida_mostra_erro_e_nao_copia(user: User, projeto):
    await abrir_aba(user, 'Prática no TEC')

    await soltar_tec(user, ('tec-erros-quebrado.json', b'{"app": "outro"}'))

    await user.should_see('erro:')
    await user.should_see('dica:')
    assert not (projeto / 'tec').exists()


async def test_soltar_planilha_confere_as_colunas_importa_e_analisa(user: User, projeto, monkeypatch):
    monkeypatch.setattr(pagina_tec, 'analisar', lambda: ui.notify('análise pedida'))
    await abrir_aba(user, 'Prática no TEC')
    await user.should_see(marker='como-conseguir')
    planilha = 'Área;Assunto;Status\nPortuguês;Crase;Errado\nPortuguês;Crase;Certo\n'.encode()

    await soltar_tec(user, ('historico.csv', planilha))

    await user.should_see(marker='conferir-colunas')
    assert elemento(user, 'coluna-assunto').value == 'Assunto'
    assert elemento(user, 'coluna-materia').value == ''
    elemento(user, 'coluna-materia').value = 'Área'
    elemento(user, 'coluna-resultado').value = 'Status'
    user.find(marker='importar-planilha').click()

    await user.should_see('análise pedida')
    (exportacao,) = (projeto / 'tec').iterdir()
    assert exportacao.name.startswith('tec-erros-planilha-historico-')
    assert not any((projeto / '.concurso' / cadastro.PASTA_ENVIOS).iterdir())


async def test_planilha_sem_coluna_obrigatoria_mostra_erro_e_mantem_a_conferencia(user: User, projeto):
    await abrir_aba(user, 'Prática no TEC')
    await soltar_tec(user, ('historico.csv', 'Área;Status\nPortuguês;Errado\n'.encode()))
    await user.should_see(marker='conferir-colunas')

    user.find(marker='importar-planilha').click()

    await user.should_see('erro:')
    await user.should_see(marker='conferir-colunas')
    assert not (projeto / 'tec').exists()
    assert ESTADO.pedir_analise is False


async def test_com_a_pratica_analisada_mostra_prioridades_e_simulado(user: User, projeto, navegador):
    pasta = projeto / 'analises' / 'pratica'
    pasta.mkdir(parents=True)
    (pasta / 'resumo_pratica.md').write_text('# Prioridades da semana', encoding='utf-8')
    (pasta / 'simulado_tec.html').write_text('<html></html>', encoding='utf-8')
    await abrir_aba(user, 'Prática no TEC')

    user.find(marker='ver-prioridades').click()
    await user.should_see('Prioridades da semana')
    user.find(marker='ver-simulado-tec').click()

    assert navegador == [pasta / 'simulado_tec.html']


@pytest.fixture
def captura(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / 'captura'
    (pasta / 'extensao-chrome').mkdir(parents=True)
    (pasta / 'caderno.html').write_text('<html></html>', encoding='utf-8')
    (pasta / 'tec-erros.user.js').write_text('//', encoding='utf-8')
    monkeypatch.setattr(captura_tec, 'candidatas', lambda: [pasta])
    return pasta


async def test_instalar_captura_mostra_os_passos_e_abre_os_arquivos(user: User, projeto, captura, navegador):
    await abrir_aba(user, 'Prática no TEC')

    await user.should_see(marker='captura-tec')
    await user.should_see('Carregar sem compactação')
    await user.should_see('Violentmonkey')
    user.find(marker='abrir-extensao').click()
    user.find(marker='abrir-caderno').click()

    assert navegador == [captura / 'extensao-chrome', captura / 'caderno.html']


async def test_sem_captura_aponta_para_as_instrucoes(user: User, projeto, monkeypatch):
    monkeypatch.setattr(captura_tec, 'candidatas', lambda: [])

    await abrir_aba(user, 'Prática no TEC')

    await user.should_see(marker='sem-captura')
