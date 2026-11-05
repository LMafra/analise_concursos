from pathlib import Path

import pytest
from nicegui import ui
from nicegui.testing.user import User

from concursos.aplicacao import captura_tec, integracoes
from concursos.config.contexto import ler_toml
from concursos.gui.estado import ESTADO
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


async def abrir_aba(user: User, aba: str) -> None:
    await user.open('/integracoes')
    user.find(aba).click()


async def test_pci_desligado_mostra_o_aviso_e_nao_consulta(user: User, projeto, monkeypatch):
    monkeypatch.setattr(integracoes, 'descobrir', proibido)

    await abrir_aba(user, 'Descobrir concursos')

    await user.should_see(marker='aviso-pci')
    await user.should_see('só termos de busca')
    await user.should_not_see(marker='buscar-pci')


async def test_ligar_pci_grava_enabled(user: User, projeto):
    await abrir_aba(user, 'Descobrir concursos')
    user.find(marker='ligar-pci').click()

    await user.should_see(marker='buscar-pci')
    assert ler_toml(ESTADO.contexto().config_global)['pci_mcp']['enabled'] is True


async def test_descobrir_mostra_prazo_e_link_e_acompanhar_registra_no_radar(user: User, projeto, monkeypatch):
    ligar_pci()
    filtros: list[dict] = []

    def descobrir_falso(opcoes, cargos=None, uf=None, cidade=None, regiao=None, termo=None):
        filtros.append({'cargos': cargos, 'uf': uf, 'cidade': cidade, 'regiao': regiao})
        return [SEFAZ]

    monkeypatch.setattr(integracoes, 'descobrir', descobrir_falso)
    await abrir_aba(user, 'Descobrir concursos')
    user.find(marker='filtro-cargo').type('Auditor, Analista')
    user.find(marker='filtro-uf').type('df')
    user.find(marker='buscar-pci').click()

    await user.should_see('SEFAZ-DF abre 50 vagas')
    await user.should_see('20/11/2026 (15 dias)')
    assert filtros == [{'cargos': ['Auditor', 'Analista'], 'uf': 'df', 'cidade': None, 'regiao': None}]
    user.find(marker='acompanhar-101').click()

    await user.should_see(marker='interesse-101')
    assert Interesses.do_projeto(ESTADO.contexto().projeto).obter(101)['titulo'] == SEFAZ.titulo


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
