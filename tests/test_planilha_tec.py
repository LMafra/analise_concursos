import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from openpyxl import Workbook

from concursos import planilha_tec
from concursos.aplicacao import pratica
from concursos.aplicacao.opcoes import Opcoes
from concursos.config.contexto import ler_toml, resolver_contexto
from concursos.erros import ErroDoUsuario
from concursos.pratica_tec import ARQUIVO_ESCOLHAS, ler_entrada, ler_escolhas, ler_exportacao

ENTRADA = Path(__file__).parent / 'contrato_tec' / 'entrada'
AGORA = datetime(2026, 11, 6, 10, 0, tzinfo=timezone(timedelta(hours=-3)))
ENUNCIADO = 'Julgue o item: a autarquia é pessoa jurídica de direito público.'
LINHAS = [
    ['Disciplina', 'Assunto', 'Questão', 'Resultado', 'Data', 'Banca'],
    ['Direito Administrativo', 'Autarquias', ENUNCIADO, 'Errado', '03/11/2026', 'CEBRASPE'],
    ['Direito Administrativo', 'Autarquias', '#123456', 'E', '04/11/2026', 'CEBRASPE'],
    ['Português', 'Crase', 'Outra questão qualquer', 'Certo', '2026-11-02', 'FGV'],
    ['', 'Sem disciplina', 'Linha incompleta', 'Errado', '', ''],
    ['Português', 'Crase', 'Resultado estranho', 'talvez', '', ''],
]


def csv(caminho: Path, linhas: list[list[str]], separador: str = ';', codificacao: str = 'utf-8') -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes('\n'.join(separador.join(linha) for linha in linhas).encode(codificacao))
    return caminho


def xlsx(caminho: Path, linhas: list[list]) -> Path:
    livro = Workbook()
    for linha in linhas:
        livro.active.append(linha)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    livro.save(caminho)
    return caminho


@pytest.fixture
def contexto(tmp_path: Path):
    return resolver_contexto(cwd=tmp_path, data_dir=tmp_path / '.concurso')


@pytest.mark.parametrize('separador', [';', ',', '\t'])
def test_le_csv_pelo_separador_da_primeira_linha(tmp_path, separador):
    linhas = [[c.replace(',', '') for c in linha] for linha in LINHAS]
    planilha = planilha_tec.ler_planilha(csv(tmp_path / 'tec.csv', linhas, separador))

    assert planilha.cabecalho == LINHAS[0]
    assert planilha.linhas[0]['Disciplina'] == 'Direito Administrativo'
    assert len(planilha.linhas) == 5


def test_le_csv_em_latin1(tmp_path):
    planilha = planilha_tec.ler_planilha(csv(tmp_path / 'tec.csv', LINHAS, codificacao='latin-1'))

    assert planilha.linhas[2]['Disciplina'] == 'Português'


def test_le_xlsx_com_data_e_numero(tmp_path):
    linhas = [LINHAS[0], ['Português', 'Crase', 98765.0, 'Errado', datetime(2026, 11, 3), 'FGV']]

    planilha = planilha_tec.ler_planilha(xlsx(tmp_path / 'tec.xlsx', linhas))

    assert planilha.linhas == [
        {
            'Disciplina': 'Português',
            'Assunto': 'Crase',
            'Questão': '98765',
            'Resultado': 'Errado',
            'Data': '2026-11-03',
            'Banca': 'FGV',
        }
    ]


def test_extensao_desconhecida_e_planilha_vazia_sao_invalidas(tmp_path):
    with pytest.raises(planilha_tec.PlanilhaInvalidaError):
        planilha_tec.ler_planilha(csv(tmp_path / 'tec.ods', LINHAS))
    with pytest.raises(planilha_tec.PlanilhaInvalidaError):
        planilha_tec.ler_planilha(csv(tmp_path / 'vazia.csv', [['', '']]))


def test_detecta_colunas_por_sinonimo_e_prefixo():
    cabecalho = [
        'Matéria',
        'Tópico',
        'Texto da questão',
        'Acertou?',
        'Resolvida em',
        'Órgão',
        'Gabarito oficial',
    ]

    assert planilha_tec.detectar_colunas(cabecalho) == {
        'materia': 'Matéria',
        'assunto': 'Tópico',
        'enunciado': 'Texto da questão',
        'resultado': 'Acertou?',
        'data': 'Resolvida em',
        'banca': None,
        'orgao': 'Órgão',
        'ano': None,
        'gabarito': 'Gabarito oficial',
        'marcada': None,
    }


def test_sem_disciplina_ou_resultado_falta_o_obrigatorio():
    mapeamento = planilha_tec.detectar_colunas(['Assunto', 'Questão'])

    assert planilha_tec.faltando(mapeamento) == ['materia', 'resultado']


def test_assinatura_ignora_acento_e_caixa():
    assert planilha_tec.assinatura(['Matéria', 'Resultado']) == planilha_tec.assinatura(
        ['materia', 'RESULTADO']
    )
    assert planilha_tec.assinatura(['Matéria']) != planilha_tec.assinatura(['Matéria', 'Resultado'])


def test_fnv1a_e_o_mesmo_do_nucleo_js():
    assert planilha_tec.fnv1a(ENUNCIADO) == '2636d69c'


@pytest.mark.parametrize(
    ('valor', 'esperado'),
    [
        ('Certo', True),
        ('C', True),
        ('sim', True),
        ('1', True),
        ('Errado', False),
        ('E', False),
        ('não', False),
    ],
)
def test_resultado_reconhecido(valor, esperado):
    assert planilha_tec.acertou(valor) is esperado


def test_resultado_desconhecido_fica_sem_valor():
    assert planilha_tec.acertou('talvez') is None


def test_converte_erros_e_cadernos_no_contrato_v1(tmp_path):
    planilha = planilha_tec.ler_planilha(csv(tmp_path / 'tec.csv', LINHAS))

    conversao = planilha_tec.converter(
        planilha, planilha_tec.detectar_colunas(planilha.cabecalho), 'tec.csv', AGORA
    )

    assert (conversao.linhas, conversao.erradas, conversao.ignoradas) == (5, 2, 2)
    texto, codigo = conversao.exportacao['erros']
    assert texto['id'] == 'h2636d69c'
    assert texto['enun'] == ENUNCIADO and texto['fp'].startswith('julgue o item')
    assert (texto['d'], texto['origem'], texto['dev'], texto['ass'], texto['banca']) == (
        '2026-11-03',
        'historico',
        'planilha',
        'Autarquias',
        'CEBRASPE',
    )
    assert codigo['id'] == 'q123456' and 'enun' not in codigo
    assert conversao.exportacao['cads'] == [
        {
            'id': 'planilha:tec.csv:direito-administrativo',
            'cad': 'planilha:tec.csv',
            'mat': 'Direito Administrativo',
            'tot': 2,
            'res': 2,
            'ac': 0,
            'er': 2,
            'd': '2026-11-04',
            't': 0,
            'dev': 'planilha',
        },
        {
            'id': 'planilha:tec.csv:portugues',
            'cad': 'planilha:tec.csv',
            'mat': 'Português',
            'tot': 1,
            'res': 1,
            'ac': 1,
            'er': 0,
            'd': '2026-11-02',
            't': 0,
            'dev': 'planilha',
        },
    ]


def test_importar_planilha_grava_exportacao_que_se_mescla_com_a_captura(contexto, tmp_path):
    arquivo = csv(tmp_path / 'baixados' / 'Meu histórico.csv', LINHAS)
    (tmp_path / 'tec').mkdir()
    for nome in ('tec-erros-computador-2026-11-03.json', 'tec-erros-tablet-2026-11-04.json'):
        shutil.copy2(ENTRADA / nome, tmp_path / 'tec' / nome)

    destino = pratica.importar_planilha(Opcoes(contexto), arquivo, agora=AGORA)

    assert destino == tmp_path / 'tec' / 'tec-erros-planilha-meu-historico-2026-11-06.json'
    assert ler_toml(contexto.config_projeto)['pratica'] == {'entrada_tec': 'tec'}
    dados, avisos = ler_exportacao(destino)
    assert avisos == [] and len(dados['erros']) == 2
    mesclada, _ = ler_entrada(tmp_path / 'tec')
    ids = {e['id'] for e in mesclada.erros}
    assert {'h2636d69c', 'q123456'} <= ids
    assert len(ids) == len(mesclada.erros)


def test_importar_planilha_lembra_o_mapeamento_pelos_cabecalhos(contexto, tmp_path):
    linhas = [['Área', 'Status', 'Enunciado'], ['Português', 'Errado', 'Questão sobre crase']]
    arquivo = csv(tmp_path / 'tec.csv', linhas)
    previsao = pratica.prever_planilha(contexto, arquivo)
    assert previsao.faltando == ['materia', 'resultado'] and not previsao.lembrado

    mapeamento = {**previsao.mapeamento, 'materia': 'Área', 'resultado': 'Status'}
    pratica.importar_planilha(Opcoes(contexto), arquivo, mapeamento, agora=AGORA)

    escolhas = ler_escolhas(contexto.projeto / ARQUIVO_ESCOLHAS)
    assert list(escolhas.planilhas.values()) == [
        {'materia': 'Área', 'resultado': 'Status', 'enunciado': 'Enunciado'}
    ]
    de_novo = pratica.prever_planilha(contexto, csv(tmp_path / 'outra.csv', linhas))
    assert de_novo.lembrado and de_novo.faltando == []
    assert de_novo.amostra == [{'Área': 'Português', 'Status': 'Errado', 'Enunciado': 'Questão sobre crase'}]


def test_importar_planilha_sem_colunas_obrigatorias_explica(contexto, tmp_path):
    arquivo = csv(tmp_path / 'tec.csv', [['Área', 'Status'], ['Português', 'Errado']])

    with pytest.raises(ErroDoUsuario) as erro:
        pratica.importar_planilha(Opcoes(contexto), arquivo)

    assert 'Disciplina, Resultado' in erro.value.causa
    assert 'Importar do TEC' in erro.value.dica
    assert not (tmp_path / 'tec').exists()


def test_importar_planilha_sem_linha_reconhecida_nao_grava(contexto, tmp_path):
    arquivo = csv(tmp_path / 'tec.csv', [['Disciplina', 'Resultado'], ['Português', 'talvez']])

    with pytest.raises(ErroDoUsuario) as erro:
        pratica.importar_planilha(Opcoes(contexto), arquivo)

    assert 'nenhuma linha' in erro.value.causa
    assert not (tmp_path / 'tec').exists()


def test_importar_planilha_em_dry_run_nao_grava(contexto, tmp_path):
    mensagens = []
    arquivo = csv(tmp_path / 'tec.csv', LINHAS)

    pratica.importar_planilha(Opcoes(contexto, saida=mensagens.append, dry_run=True), arquivo, agora=AGORA)

    assert not (tmp_path / 'tec').exists()
    assert not contexto.config_projeto.exists()
    assert '2 erro(s) em 3 questão(ões)' in mensagens[0]


def test_planilha_convertida_e_json_valido(contexto, tmp_path):
    destino = pratica.importar_planilha(Opcoes(contexto), csv(tmp_path / 'tec.csv', LINHAS), agora=AGORA)

    assert json.loads(destino.read_text(encoding='utf-8'))['em'] == '2026-11-06T10:00:00-03:00'


def test_saidas_da_pratica_so_com_a_analise_feita(contexto):
    assert pratica.saidas_da_pratica(contexto) == pratica.SaidasDaPratica(None, None)

    pasta = contexto.analises / 'pratica'
    pasta.mkdir(parents=True)
    (pasta / 'resumo_pratica.md').write_text('# Prioridades', encoding='utf-8')
    (pasta / 'simulado_tec.html').write_text('<html></html>', encoding='utf-8')

    assert pratica.saidas_da_pratica(contexto) == pratica.SaidasDaPratica(
        '# Prioridades', pasta / 'simulado_tec.html'
    )
