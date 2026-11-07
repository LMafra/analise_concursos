from pathlib import Path

import pandas as pd
import yaml
from conftest import criar_concurso
from test_pci_simulado import ALVO, ARQUIVOS_ALVO, ARQUIVOS_SIMULADO, SIMULADO

from concursos import simulado_focado
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.simulados import gerar_simulado_focado
from concursos.cli import main
from concursos.config.contexto import resolver_contexto
from concursos.topicos import ARQUIVO_REVISAO, COLUNAS_REVISAO

FRACOS = pd.DataFrame(
    [
        {'disciplina': 'Direito Administrativo', 'topico': 'Licitações', 'n': 12, 'percentual': 35.0},
        {'disciplina': 'Português', 'topico': 'Crase', 'n': 8, 'percentual': 45.0},
    ]
)


def simulado(
    raiz_provas: Path, pasta: str, linhas: list[dict], nome: str = 'TCU 2019 (simulado PCI 1)'
) -> Path:
    destino = raiz_provas / pasta
    (destino / 'revisao').mkdir(parents=True)
    (destino / 'concurso.yaml').write_text(
        yaml.safe_dump({'nome': nome, 'simulado': {'fonte': 'pci', 'id_pci': 1}}), encoding='utf-8'
    )
    completas = [{coluna: '' for coluna in COLUNAS_REVISAO} | {'prova': 'unica'} | linha for linha in linhas]
    pd.DataFrame(completas, columns=COLUNAS_REVISAO).to_csv(destino / ARQUIVO_REVISAO, index=False)
    return destino


def questao(numero: int, disciplina_sugerida: str, topico_sugerido: str, **outros) -> dict:
    return {
        'questao': numero,
        'disciplina_sugerida': disciplina_sugerida,
        'topico_sugerido': topico_sugerido,
        'enunciado': f'Enunciado da questão {numero}',
    } | outros


def test_escolhe_na_ordem_dos_fracos_com_teto_por_topico(tmp_path: Path):
    provas = tmp_path / 'provas'
    simulado(
        provas,
        'tcu_2019_pci1',
        [questao(n, 'Direito Administrativo', 'Licitações') for n in range(1, 8)]
        + [questao(8, 'Português', 'Crase'), questao(9, 'Português', 'nao_mapeado')],
    )

    resultado = simulado_focado.montar(provas, tmp_path / 'analises', FRACOS)

    [(primeiro, licitacoes), (segundo, crase)] = resultado.questoes
    assert (primeiro['topico'], len(licitacoes)) == ('Licitações', simulado_focado.MAXIMO_POR_TOPICO)
    assert (segundo['topico'], [q.questao for q in crase]) == ('Crase', [8])
    assert resultado.total == simulado_focado.MAXIMO_POR_TOPICO + 1


def test_revisao_manual_vence_e_acertadas_ficam_fora(tmp_path: Path):
    provas, analises = tmp_path / 'provas', tmp_path / 'analises'
    simulado(
        provas,
        'tcu_2019_pci1',
        [
            questao(1, 'Português', 'Pontuação', disciplina='Português', topico='Crase'),
            questao(2, 'Português', 'Crase'),
        ],
    )
    (analises / 'tcu_2019_pci1').mkdir(parents=True)
    pd.DataFrame([{'prova': 'unica', 'questao': 2, 'resultado': 'acerto'}]).to_csv(
        analises / 'tcu_2019_pci1' / 'questoes.csv', index=False
    )

    [(_, crase)] = simulado_focado.montar(provas, analises, FRACOS).questoes

    assert [q.questao for q in crase] == [1]


def test_markdown_cita_o_limiar_o_n_e_os_simulados_sem_revisao(tmp_path: Path):
    provas = tmp_path / 'provas'
    simulado(provas, 'tcu_2019_pci1', [questao(1, 'Português', 'Crase')])
    (provas / 'sem_revisao').mkdir()
    (provas / 'sem_revisao' / 'concurso.yaml').write_text(
        'nome: x\nsimulado: {fonte: pci}\n', encoding='utf-8'
    )

    texto = simulado_focado.formatar(simulado_focado.montar(provas, tmp_path / 'a', FRACOS), 0.6)

    assert '1 questão de provas anteriores' in texto and 'abaixo de 60%' in texto
    assert '## Português: Crase (45% descontado o chute, em 8 questões)' in texto
    assert '- TCU 2019 (simulado PCI 1), questão 1 (prova unica): Enunciado da questão 1' in texto
    assert 'sem_revisao' in texto


def test_sem_provas_anteriores_nada_e_gravado(tmp_path: Path):
    (tmp_path / 'provas').mkdir()
    contexto = resolver_contexto(cwd=tmp_path, data_dir=tmp_path / '.concurso')

    assert gerar_simulado_focado(Opcoes(contexto), tmp_path / 'provas', tmp_path / 'analises', 0.6) is None
    assert not (tmp_path / 'analises' / simulado_focado.ARQUIVO_SIMULADO_FOCADO).exists()


def test_simulado_sem_respostas_ganha_a_revisao_e_o_arquivo_na_analise(
    tmp_path: Path, monkeypatch, home_isolada
):
    raiz = tmp_path / 'projeto'
    provas, analises = raiz / 'provas', raiz / 'analises'
    provas.mkdir(parents=True)
    (raiz / '.concurso').mkdir()
    monkeypatch.chdir(raiz)
    criar_concurso(provas, 'alvo', ALVO, ARQUIVOS_ALVO)
    sem_respostas = {chave: valor for chave, valor in SIMULADO.items() if chave != 'respostas'}
    criar_concurso(provas, 'simulado', sem_respostas, {'gabarito.txt': ARQUIVOS_SIMULADO['gabarito.txt']})

    assert main(['--yes', '--no-open', '--offline']) == 0

    revisao = pd.read_csv(provas / 'simulado' / ARQUIVO_REVISAO)
    assert sorted(revisao['questao']) == [1, 2, 3, 4]
    [arquivo] = analises.glob(f'*/{simulado_focado.ARQUIVO_SIMULADO_FOCADO}')
    assert '# Simulado focado' in arquivo.read_text(encoding='utf-8')
    assert 'Simulado focado' in (arquivo.parents[1] / 'index.html').read_text(encoding='utf-8')
    mtime = arquivo.stat().st_mtime_ns
    assert main(['--yes', '--no-open', '--offline']) == 0
    assert arquivo.stat().st_mtime_ns == mtime


def test_simulado_ainda_sem_os_arquivos_da_prova_avisa_uma_vez_com_o_link(
    tmp_path: Path, monkeypatch, home_isolada, caplog
):
    raiz = tmp_path / 'projeto'
    provas = raiz / 'provas'
    provas.mkdir(parents=True)
    (raiz / '.concurso').mkdir()
    monkeypatch.chdir(raiz)
    criar_concurso(provas, 'alvo', ALVO, ARQUIVOS_ALVO)
    pasta = provas / 'orgao_2002_pci1'
    pasta.mkdir()
    link = 'https://www.pciconcursos.com.br/provas/download/orgao-2002'
    (pasta / 'concurso.yaml').write_text(
        yaml.safe_dump(
            {'nome': 'Órgão 2002 (simulado PCI 1)', 'banca': 'generic', 'simulado': {'link': link}}
        ),
        encoding='utf-8',
    )

    assert main(['--yes', '--no-open', '--offline']) == 0

    avisos = [r for r in caplog.records if r.levelname == 'WARNING' and 'orgao_2002_pci1' in r.getMessage()]
    assert len(avisos) == 1
    texto = f'{avisos[0].getMessage()} {avisos[0].dica} {avisos[0].detalhe}'
    assert link in texto and 'campo obrigatório' not in texto
