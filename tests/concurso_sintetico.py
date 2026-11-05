from pathlib import Path

import yaml

EDITAL_MINIMO = 'conhecimentos: []\n'


def com_edital_minimo(pasta: Path, config: dict) -> dict:
    """Concurso sem edital fica incompleto; o manual mínimo não traz regra nem tópico."""
    if 'edital' in config:
        return config
    (pasta / 'edital_manual.yaml').write_text(EDITAL_MINIMO, encoding='utf-8')
    return {**config, 'edital': {'manual': 'edital_manual.yaml'}}


def criar_concurso(provas: Path, nome: str, config: dict, arquivos: dict[str, str]) -> Path:
    pasta = provas / nome
    pasta.mkdir(parents=True, exist_ok=True)
    config = com_edital_minimo(pasta, config)
    (pasta / 'concurso.yaml').write_text(yaml.safe_dump(config, allow_unicode=True), encoding='utf-8')
    for nome_arquivo, conteudo in arquivos.items():
        (pasta / nome_arquivo).write_text(conteudo, encoding='utf-8')
    return pasta


ARQUIVOS_SIMPLES = {'gabarito.txt': '1 A\n2 B\n', 'respostas.txt': '1 A\n2 C\n'}


def config_simples(nome: str) -> dict:
    """Múltipla escolha de dois itens, com gabarito e respostas em texto: analisa sem OCR."""
    return {
        'nome': nome,
        'banca': 'fgv',
        'formato': 'multipla_escolha',
        'pontuacao': 'simples',
        'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 2]}},
        'respostas': {'arquivo': 'respostas.txt'},
    }
