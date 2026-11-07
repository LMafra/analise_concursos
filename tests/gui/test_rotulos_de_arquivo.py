"""Todo nome de arquivo ou pasta que a janela mostra vem com o rótulo de `linguagem.rotulo_do_arquivo`."""

import ast
import re
from pathlib import Path

import concursos
from concursos.linguagem import ROTULOS_DE_ARQUIVO

PACOTE = Path(concursos.__file__).parent
CHAMADAS_DA_TELA = {'label', 'markdown', 'html', 'notify', 'aviso', 'situacao'}
CONHECIDOS = re.compile(
    '|'.join(
        rf'(?<![\w.]){re.escape(nome)}/' if '.' not in nome.lstrip('.') else rf'(?<![\w.]){re.escape(nome)}\b'
        for nome in ROTULOS_DE_ARQUIVO
    )
)


def _nome_da_chamada(chamada: ast.Call) -> str | None:
    if isinstance(chamada.func, ast.Attribute):
        return chamada.func.attr
    if isinstance(chamada.func, ast.Name):
        return chamada.func.id
    return None


def nomes_sem_rotulo(codigo: str) -> list[int]:
    arvore = ast.parse(codigo)
    rotulados = {
        id(filho)
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and _nome_da_chamada(no) == 'rotulo_do_arquivo'
        for filho in ast.walk(no)
    }
    achados = []
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Call) and _nome_da_chamada(no) in CHAMADAS_DA_TELA and no.args):
            continue
        for filho in ast.walk(no.args[0]):
            if id(filho) in rotulados:
                continue
            nome_de_arquivo = isinstance(filho, ast.Attribute) and filho.attr == 'name'
            literal = isinstance(filho, ast.Constant) and isinstance(filho.value, str)
            if nome_de_arquivo or (literal and CONHECIDOS.search(filho.value)):
                achados.append(filho.lineno)
    return sorted(achados)


def test_o_detector_acha_nome_de_arquivo_sem_rotulo():
    codigo = (
        'ui.label(caminho.name)\n'
        "ui.label('As provas ficam em provas/ e o resto em analises/.')\n"
        "ui.label(f'Abra o {pasta}/respostas_extraidas.csv')\n"
        'ui.label(rotulo_do_arquivo(caminho.name))\n'
        'ui.label(f\'Ficam em {rotulo_do_arquivo("provas/")}.\')\n'
        "ui.button('Abrir').mark(f'linha-{caminho.name}')\n"
    )

    assert nomes_sem_rotulo(codigo) == [1, 2, 3]


def test_a_janela_mostra_todo_nome_de_arquivo_com_rotulo():
    achados = [
        f'{arquivo.relative_to(PACOTE)}:{linha}'
        for arquivo in sorted((PACOTE / 'gui').rglob('*.py'))
        for linha in nomes_sem_rotulo(arquivo.read_text(encoding='utf-8'))
    ]

    assert achados == []
