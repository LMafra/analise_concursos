from pathlib import Path

import pandas as pd

from concursos.analytics.regras_edital import Campo, Distribuicao, FonteRegra, RegrasEdital
from concursos.analytics.taxonomia import DisciplinaCanonica
from concursos.analytics.validacao_edital import validar_edital
from concursos.concurso_config import validar_dados
from concursos.modelo import Bloco

RACIOCINIO = DisciplinaCanonica('Raciocínio Lógico', Bloco.GERAL)
TAXONOMIA = {
    'Língua Portuguesa': DisciplinaCanonica('Língua Portuguesa', Bloco.GERAL),
    'Raciocínio Lógico': RACIOCINIO,
    'Raciocínio Lógico e Matemático': RACIOCINIO,
    'Raciocínio Lógico Matemático': RACIOCINIO,
    'Banco de Dados': DisciplinaCanonica('Banco de Dados', Bloco.ESPECIFICO),
}


def config(provas: dict):
    return validar_dados(Path('sintetico'), {'banca': 'fgv', 'formato': 'multipla_escolha', 'provas': provas})


def questoes(*faixas: tuple[str, str, int]) -> pd.DataFrame:
    linhas = [(prova, disciplina) for prova, disciplina, n in faixas for _ in range(n)]
    tabela = pd.DataFrame(linhas, columns=['prova', 'disciplina'])
    return tabela.assign(questao=range(1, len(tabela) + 1))


def edital(total=None, geral=None, especifico=None, por_disciplina=None) -> RegrasEdital:
    def campo(valor):
        return Campo(valor, FonteRegra.EDITAL) if valor is not None else Campo()

    distribuicao = Distribuicao(campo(total), campo(geral), campo(especifico), campo(por_disciplina))
    return RegrasEdital(distribuicao=distribuicao)


def linhas(tabela: pd.DataFrame) -> dict[str, dict]:
    return {linha['item']: linha for linha in tabela.to_dict('records')}


def test_total_e_bloco_divergentes_por_prova_sao_error():
    cfg = config(
        {'cb': {'gabarito': 'g.txt', 'itens': [1, 4]}, 'ce': {'gabarito': 'h.txt', 'itens': [5, 10]}}
    )
    prova = questoes(('cb', 'Língua Portuguesa', 4), ('ce', 'Banco de Dados', 6))

    tabela = linhas(validar_edital(cfg, edital(total=12, geral=6, especifico=6), prova))

    assert set(tabela) == {'total de itens', 'itens de conhecimentos gerais'}
    total = tabela['total de itens']
    assert (total['esperado_edital'], total['observado_prova'], total['diferenca']) == ('12', '10', -2)
    assert total['severidade'] == 'error'
    assert tabela['itens de conhecimentos gerais']['diferenca'] == -2


def test_na_prova_unica_o_bloco_vem_da_taxonomia_e_a_disciplina_casa_pela_canonica():
    cfg = config({'unica': {'gabarito': 'g.txt', 'itens': [1, 9]}})
    prova = questoes(
        ('unica', 'Língua Portuguesa', 2),
        ('unica', 'Raciocínio Lógico Matemático', 3),
        ('unica', 'Banco de Dados', 4),
    )
    regras = edital(
        total=9,
        geral=5,
        especifico=4,
        por_disciplina={'Língua Portuguesa': 3, 'Raciocínio Lógico e Matemático': 3},
    )

    tabela = linhas(validar_edital(cfg, regras, prova, TAXONOMIA))

    assert set(tabela) == {'disciplina: Língua Portuguesa'}
    portugues = tabela['disciplina: Língua Portuguesa']
    assert (portugues['severidade'], portugues['esperado_edital'], portugues['observado_prova']) == (
        'warn',
        '3',
        '2',
    )


def test_sem_bloco_conhecido_nao_compara_blocos_e_sem_quadro_nao_compara_disciplinas():
    cfg = config({'unica': {'gabarito': 'g.txt', 'itens': [1, 4]}})
    prova = questoes(('unica', 'nao_mapeado', 4))

    assert validar_edital(cfg, edital(total=4, geral=1, especifico=3), prova, TAXONOMIA).empty
