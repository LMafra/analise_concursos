import csv
import json
from pathlib import Path

import pytest
import yaml

from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.modelo import ModoCaderno, OrigemErroTec
from concursos.pratica_tec import (
    ARQUIVO_CADERNOS,
    ARQUIVO_DESEMPENHO,
    ARQUIVO_ERROS,
    ARQUIVO_ESTADO,
    ARQUIVO_RESUMO,
    ARQUIVO_REVISAO,
    FORA_DO_EDITAL,
    PASTA_PRATICA,
    Escolhas,
    ExportacaoInvalidaError,
    disciplina_da_materia,
    importar_pratica,
    impressao_digital,
    ler_configuracao,
    ler_entrada,
    ler_escolhas,
    ler_exportacao,
    mesclar_cadernos,
    mesclar_erros,
    textos_do_caderno,
    textos_para_normas,
)
from concursos.topicos import NAO_MAPEADO


def erro(id_='q1', **campos):
    base = {
        'id': id_,
        'fp': 'texto da questao',
        'd': '2026-11-02',
        't': 1,
        'v': 1,
        'ds': ['2026-11-02T10:00:00-03:00'],
        'dev': 'd1',
        'origem': 'tempo_real',
        'mat': 'Direito Tributário',
        'ass': 'Simples Nacional',
        'enun': 'Texto da questão',
    }
    return {**base, **campos}


def caderno(id_='c1', **campos):
    base = {
        'id': id_,
        'cad': 'Caderno 1',
        'mat': 'Direito Tributário',
        'tot': 100,
        'res': 10,
        'ac': 6,
        'er': 4,
        't': 1,
    }
    return {**base, **campos}


def exportacao(erros=(), cads=(), dev='d1', **extra):
    return {
        'app': 'tec-erros',
        'v': 1,
        'em': '2026-11-02T10:00:00-03:00',
        'dev': dev,
        'erros': list(erros),
        'cads': list(cads),
        **extra,
    }


def gravar_json(caminho: Path, dados) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding='utf-8')
    return caminho


def ler_csv(caminho: Path) -> list[dict]:
    with caminho.open(encoding='utf-8', newline='') as arquivo:
        return list(csv.DictReader(arquivo))


TAXONOMIA = {'Legislação Tributária': {'bloco': 'especifico', 'nomes': ['Direito Tributário']}}

EDITAL = {
    'fonte': 'edital.pdf',
    'cargo': None,
    'conhecimentos': [
        {
            'nome': 'Conhecimentos específicos',
            'disciplinas': [
                {
                    'nome': 'Legislação Tributária',
                    'topicos': [
                        {
                            'numero': '1',
                            'nome': 'Simples Nacional',
                            'descricao': 'Simples Nacional: regime único',
                        },
                        {'numero': '2', 'nome': 'ICMS', 'descricao': 'ICMS: fato gerador e base de cálculo'},
                    ],
                }
            ],
        }
    ],
}


@pytest.fixture
def projeto(tmp_path):
    (tmp_path / '.concurso').mkdir()
    (tmp_path / '.concurso' / 'taxonomia.yaml').write_text(
        yaml.safe_dump(TAXONOMIA, allow_unicode=True), encoding='utf-8'
    )
    gravar_json(tmp_path / 'analises' / 'ana' / 'alvo' / 'edital_estruturado.json', EDITAL)
    (tmp_path / 'tec').mkdir()
    return tmp_path


def importar(projeto: Path, interacao=None, concurso_alvo='alvo'):
    from concursos.analytics.taxonomia import carregar_taxonomia

    return importar_pratica(
        projeto / 'tec',
        projeto / 'analises' / 'ana',
        projeto / '.concurso' / 'pratica_tec.yaml',
        carregar_taxonomia(projeto / '.concurso' / 'taxonomia.yaml'),
        concurso_alvo,
        interacao,
    )


class Respostas:
    def __init__(self, *escolhas):
        self.escolhas = list(escolhas)
        self.perguntas = []

    def escolher(self, pergunta, opcoes, sugestao=None):
        self.perguntas.append((pergunta, opcoes, sugestao))
        resposta = self.escolhas.pop(0)
        return sugestao if resposta is None else resposta

    def mostrar(self, texto):
        pass


def test_impressao_digital_igual_a_do_javascript():
    assert impressao_digital('  Ação   É\nFÁCIL ') == 'acao e facil'
    assert len(impressao_digital('x' * 400)) == 300


def test_exportacao_de_outro_app_ou_versao_e_recusada(tmp_path):
    with pytest.raises(ExportacaoInvalidaError, match='app'):
        ler_exportacao(gravar_json(tmp_path / 'a.json', {'app': 'outro', 'v': 1}))
    with pytest.raises(ExportacaoInvalidaError, match='versão'):
        ler_exportacao(gravar_json(tmp_path / 'b.json', {'app': 'tec-erros', 'v': 2}))


def test_campo_desconhecido_vira_aviso(tmp_path):
    dados, avisos = ler_exportacao(gravar_json(tmp_path / 'a.json', exportacao([erro()], novo=1)))
    assert len(dados['erros']) == 1
    assert avisos == [f'{tmp_path / "a.json"}: campo desconhecido ignorado: novo']


def test_dois_aparelhos_no_mesmo_dia_contam_dois_erros():
    pc = erro(ds=['2026-11-02T10:00:00-03:00'], dev='pc')
    tablet = erro(ds=['2026-11-02T21:00:00-03:00'], dev='tablet', t=5)
    (fundido,) = mesclar_erros([pc], [tablet])
    assert fundido['v'] == 2
    assert fundido['ds'] == ['2026-11-02T10:00:00-03:00', '2026-11-02T21:00:00-03:00']
    assert fundido['dev'] == 'pc'
    assert fundido['t'] == 5


def test_casa_pela_impressao_digital_quando_o_id_difere():
    (fundido,) = mesclar_erros(
        [erro('q1')], [erro('habc', ds=['2026-11-03T08:00:00-03:00'], banca='CEBRASPE')]
    )
    assert fundido['id'] == 'q1'
    assert fundido['v'] == 2
    assert fundido['banca'] == 'CEBRASPE'


def test_historico_nao_soma_ao_tempo_real():
    historico = erro(ds=[], v=1, origem='historico', d='2026-10-01')
    (fundido,) = mesclar_erros([historico], [erro()])
    assert fundido['v'] == 1
    assert fundido['origem'] == OrigemErroTec.TEMPO_REAL
    assert fundido['d'] == '2026-10-01'


def test_comentario_mais_longo_vence_e_nada_e_apagado():
    curto = erro(com='curto', prof='A', gab='C')
    longo = erro(com='comentário bem mais longo', prof='B', gab='')
    (fundido,) = mesclar_erros([curto], [longo])
    assert (fundido['com'], fundido['prof'], fundido['gab']) == ('comentário bem mais longo', 'B', 'C')


def test_caderno_fica_com_o_maior_progresso():
    cads = mesclar_cadernos([caderno(res=10, t=9)], [caderno(res=8, t=10), caderno('c2')])
    assert {c['id']: c['res'] for c in cads} == {'c1': 10, 'c2': 10}


def test_disciplina_pela_taxonomia_ignorando_acento_e_caixa():
    from concursos.analytics.taxonomia import DisciplinaCanonica
    from concursos.modelo import Bloco

    taxonomia = {'Direito Tributário': DisciplinaCanonica('Legislação Tributária', Bloco.ESPECIFICO)}
    assert disciplina_da_materia('direito tributario', taxonomia, {}) == 'Legislação Tributária'
    assert disciplina_da_materia('Português', taxonomia, {}) is None
    assert (
        disciplina_da_materia('Português', taxonomia, {'Português': 'Língua Portuguesa'})
        == 'Língua Portuguesa'
    )


def test_sem_secao_pratica_nada_muda(tmp_path):
    (tmp_path / 'config.toml').write_text('[analise]\nlimiar_topico_baixo = 0.5\n', encoding='utf-8')
    assert ler_configuracao(tmp_path / 'config.toml', tmp_path) is None


def test_secao_pratica_com_caminho_relativo_a_raiz(tmp_path):
    (tmp_path / 'config.toml').write_text('[pratica]\nentrada_tec = "tec"\n', encoding='utf-8')
    configuracao = ler_configuracao(tmp_path / 'config.toml', tmp_path)
    assert configuracao.entrada == tmp_path / 'tec'
    assert configuracao.candidato is None
    assert configuracao.open_notebook is False


def test_secao_pratica_invalida(tmp_path):
    (tmp_path / 'config.toml').write_text('[pratica]\nentradas = "tec"\n', encoding='utf-8')
    with pytest.raises(ConfiguracaoInvalidaError, match='entrada_tec'):
        ler_configuracao(tmp_path / 'config.toml', tmp_path)


def test_le_varios_arquivos_e_o_estado_do_caderno(tmp_path):
    gravar_json(tmp_path / 'tec-erros-pc-2026-11-02.json', exportacao([erro()], [caderno()]))
    gravar_json(
        tmp_path / 'tec-erros-tab-2026-11-02.json',
        exportacao(
            [erro(ds=['2026-11-02T22:00:00-03:00'], dev='tab'), erro('q2', fp='outra', enun='Outra')],
            dev='tab',
        ),
    )
    gravar_json(
        tmp_path / ARQUIVO_ESTADO,
        {'app': 'tec-erros-caderno', 'v': 1, 'removidos': ['q2'], 'aliases': {'X': None}},
    )
    gravar_json(tmp_path / 'qualquer.json', {'app': 'outro', 'v': 1})
    pratica, avisos = ler_entrada(tmp_path)
    assert [(e['id'], e['v']) for e in pratica.erros] == [('q1', 2)]
    assert pratica.estado['aliases'] == {'X': None}
    assert len(pratica.cadernos) == 1
    assert any('qualquer.json' in aviso for aviso in avisos)


def test_importa_e_grava_tabelas_com_alias_exato(projeto):
    gravar_json(
        projeto / 'tec' / 'a.json',
        exportacao(
            [
                erro(),
                erro('q2', fp='b', enun='B', ds=['2026-11-01T09:00:00-03:00', '2026-11-04T09:00:00-03:00']),
            ],
            [caderno()],
        ),
    )
    resultado = importar(projeto)
    assert resultado.mudou
    pasta = projeto / 'analises' / 'ana' / PASTA_PRATICA
    erros = ler_csv(pasta / ARQUIVO_ERROS)
    assert [(e['id'], e['v'], e['disciplina'], e['topico']) for e in erros] == [
        ('q2', '2', 'Legislação Tributária', 'Simples Nacional'),
        ('q1', '1', 'Legislação Tributária', 'Simples Nacional'),
    ]
    assert erros[0]['primeira_data'] == '2026-11-01'
    assert erros[0]['ultima_data'] == '2026-11-04'
    (cad,) = ler_csv(pasta / ARQUIVO_CADERNOS)
    assert (cad['modo'], cad['resolvidas'], cad['acertos']) == ('tudo', '10', '6')
    (disciplina,) = ler_csv(pasta / ARQUIVO_DESEMPENHO)
    assert disciplina['disciplina'] == 'Legislação Tributária'
    assert (disciplina['n'], disciplina['percentual'], disciplina['repetidos']) == ('10', '60.0', '1')
    assert ler_escolhas(projeto / '.concurso' / 'pratica_tec.yaml').aliases == {
        'Simples Nacional': 'Simples Nacional'
    }


def test_reimportar_sem_mudanca_nao_altera_mtime(projeto):
    gravar_json(projeto / 'tec' / 'a.json', exportacao([erro()], [caderno()]))
    importar(projeto)
    pasta = projeto / 'analises' / 'ana' / PASTA_PRATICA
    antes = {p.name: p.stat().st_mtime_ns for p in pasta.iterdir()}
    assert not importar(projeto).mudou
    assert {p.name: p.stat().st_mtime_ns for p in pasta.iterdir()} == antes


def test_assunto_sem_terminal_vai_para_revisao_e_volta_corrigido(projeto):
    gravar_json(projeto / 'tec' / 'a.json', exportacao([erro(ass='Fato gerador do ICMS')]))
    resultado = importar(projeto)
    pasta = projeto / 'analises' / 'ana' / PASTA_PRATICA
    (pendente,) = ler_csv(pasta / ARQUIVO_REVISAO)
    assert pendente['assunto'] == 'Fato gerador do ICMS'
    assert pendente['sugestao'] == 'ICMS'
    assert pendente['topico'] == ''
    assert ler_csv(pasta / ARQUIVO_ERROS)[0]['topico'] == NAO_MAPEADO
    assert any('revisao_aliases.csv' in aviso for aviso in resultado.avisos)

    pendente['topico'] = 'ICMS'
    with (pasta / ARQUIVO_REVISAO).open('w', encoding='utf-8', newline='') as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(pendente))
        escritor.writeheader()
        escritor.writerow(pendente)
    importar(projeto)
    assert ler_csv(pasta / ARQUIVO_ERROS)[0]['topico'] == 'ICMS'
    assert ler_csv(pasta / ARQUIVO_REVISAO) == []
    assert ler_escolhas(projeto / '.concurso' / 'pratica_tec.yaml').aliases == {
        'Fato gerador do ICMS': 'ICMS'
    }


def test_terminal_pergunta_uma_vez_e_aplica_a_todos(projeto):
    gravar_json(
        projeto / 'tec' / 'a.json',
        exportacao(
            [erro(ass='Fato gerador do ICMS'), erro('q2', fp='b', enun='B', ass='Fato gerador do ICMS')]
        ),
    )
    respostas = Respostas(None)
    importar(projeto, respostas)
    assert len(respostas.perguntas) == 1
    _, opcoes, sugestao = respostas.perguntas[0]
    assert sugestao == 'ICMS'
    assert 'Simples Nacional' in opcoes
    erros = ler_csv(projeto / 'analises' / 'ana' / PASTA_PRATICA / ARQUIVO_ERROS)
    assert {e['topico'] for e in erros} == {'ICMS'}
    importar(projeto, Respostas())


def test_assunto_fora_do_edital(projeto):
    gravar_json(projeto / 'tec' / 'a.json', exportacao([erro(ass='Assunto alheio')]))
    gravar_json(
        projeto / 'tec' / ARQUIVO_ESTADO,
        {'app': 'tec-erros-caderno', 'v': 1, 'aliases': {'Assunto alheio': None}},
    )
    respostas = Respostas('não pertence a nenhum tópico')
    importar(projeto, respostas)
    assert respostas.perguntas[0][2] == 'não pertence a nenhum tópico'
    assert (
        ler_csv(projeto / 'analises' / 'ana' / PASTA_PRATICA / ARQUIVO_ERROS)[0]['topico'] == FORA_DO_EDITAL
    )
    assert ler_escolhas(projeto / '.concurso' / 'pratica_tec.yaml').aliases == {'Assunto alheio': None}


def test_materia_desconhecida_vira_pendencia(projeto):
    gravar_json(projeto / 'tec' / 'a.json', exportacao([erro(mat='Astrologia', ass='Mapa astral')]))
    resultado = importar(projeto)
    (linha,) = ler_csv(projeto / 'analises' / 'ana' / PASTA_PRATICA / ARQUIVO_ERROS)
    assert linha['disciplina'] == ''
    assert any('Astrologia' in aviso and 'taxonomia.yaml' in aviso for aviso in resultado.avisos)


def test_caderno_so_daqui_desconta_a_base(projeto):
    gravar_json(projeto / 'tec' / 'a.json', exportacao(cads=[caderno(res=10, ac=6, er=4)]))
    importar(projeto, Respostas('só acompanhar daqui'))
    escolhas = ler_escolhas(projeto / '.concurso' / 'pratica_tec.yaml')
    assert escolhas.cadernos['c1'] == {'modo': ModoCaderno.DAQUI.value, 'base': {'res': 10, 'ac': 6, 'er': 4}}

    gravar_json(projeto / 'tec' / 'b.json', exportacao(cads=[caderno(res=15, ac=9, er=6, t=2)]))
    importar(projeto, Respostas())
    (cad,) = ler_csv(projeto / 'analises' / 'ana' / PASTA_PRATICA / ARQUIVO_CADERNOS)
    assert (cad['modo'], cad['resolvidas'], cad['acertos'], cad['erros']) == ('daqui', '5', '3', '2')


def test_modo_do_caderno_vem_do_estado_do_caderno_html(projeto):
    gravar_json(projeto / 'tec' / 'a.json', exportacao(cads=[caderno(res=12, ac=8, er=4)]))
    gravar_json(
        projeto / 'tec' / ARQUIVO_ESTADO,
        {
            'app': 'tec-erros-caderno',
            'v': 1,
            'cadernos': {'c1': {'modo': 'daqui', 'base': {'res': 2, 'ac': 1, 'er': 1}}},
        },
    )
    importar(projeto)
    (cad,) = ler_csv(projeto / 'analises' / 'ana' / PASTA_PRATICA / ARQUIVO_CADERNOS)
    assert (cad['resolvidas'], cad['acertos']) == ('10', '7')


def test_sem_concurso_alvo_os_topicos_ficam_nao_mapeados(projeto):
    gravar_json(projeto / 'tec' / 'a.json', exportacao([erro()]))
    resultado = importar(projeto, concurso_alvo=None)
    assert ler_csv(projeto / 'analises' / 'ana' / PASTA_PRATICA / ARQUIVO_ERROS)[0]['topico'] == NAO_MAPEADO
    assert any('concurso_alvo' in aviso for aviso in resultado.avisos)
    assert not (projeto / 'analises' / 'ana' / PASTA_PRATICA / ARQUIVO_REVISAO).exists()


def test_resumo_cruza_topico_fraco_da_prova_com_erro_repetido(projeto):
    import pandas as pd

    repetido = erro(ds=['2026-11-01T09:00:00-03:00', '2026-11-04T09:00:00-03:00'])
    gravar_json(
        projeto / 'tec' / 'a.json',
        exportacao([repetido, erro('q2', fp='b', enun='B', ass='ICMS')], [caderno(res=3, ac=1, er=2)]),
    )
    fracos = pd.DataFrame(
        [
            {
                'disciplina': 'Legislação Tributária',
                'topico': 'simples nacional',
                'n': 8,
                'percentual': 25.0,
                'concursos_abaixo': ['a', 'b'],
            }
        ]
    )
    resultado = importar_pratica(
        projeto / 'tec',
        projeto / 'analises' / 'ana',
        projeto / '.concurso' / 'pratica_tec.yaml',
        {},
        'alvo',
        None,
        fracos,
    )
    resumo = (projeto / 'analises' / 'ana' / PASTA_PRATICA / ARQUIVO_RESUMO).read_text(encoding='utf-8')
    assert resumo.startswith('# Prática no TEC')
    assert '2 erros registrados (1 repetido, errado 2 vezes ou mais)' in resumo
    prioridade = resumo.split('## O que revisar primeiro')[1].split('##')[0]
    assert '| Simples Nacional | 25,0% de 8 questões | 1 |' in prioridade
    assert 'ICMS' not in prioridade
    assert '| 2 | Simples Nacional | Simples Nacional | 2026-11-04 |' in resumo
    assert 'poucas questões para avaliar (3)' in resumo
    assert resultado.mudou


def test_textos_do_caderno_por_disciplina_e_para_as_normas(projeto):
    gravar_json(
        projeto / 'tec' / 'a.json',
        exportacao(
            [
                erro(
                    alts=[{'l': 'A', 't': 'certo'}, {'l': 'B', 't': 'errado'}],
                    marc='B',
                    gab='A',
                    com='Ver Lei 9.784/99.',
                    prof='Prof X',
                ),
                erro('q2', fp='b', enun='Outro enunciado', mat='Astrologia'),
            ]
        ),
    )
    resultado = importar(projeto)
    textos = textos_do_caderno(resultado)
    assert set(textos) == {'Legislação Tributária', 'Sem disciplina'}
    tributaria = textos['Legislação Tributária']
    assert tributaria.startswith('# Caderno de erros — Legislação Tributária')
    assert 'A) certo' in tributaria and 'Sua resposta: B. Gabarito: A.' in tributaria
    assert 'Comentário (Prof X): Ver Lei 9.784/99.' in tributaria
    assert textos_para_normas(resultado) == ['Texto da questão\nVer Lei 9.784/99.', 'Outro enunciado']


def test_escolhas_vazias_quando_o_arquivo_nao_existe(tmp_path):
    assert ler_escolhas(tmp_path / 'nada.yaml') == Escolhas()
