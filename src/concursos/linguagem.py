"""Vocabulário leigo comum aos relatórios, à GUI e às mensagens: selos de status, rótulos de arquivo e os
termos técnicos que não aparecem na parte principal. O mapa completo está em `docs/spec-linguagem.md`."""

import re
from dataclasses import dataclass
from pathlib import PurePath


@dataclass(frozen=True)
class Selo:
    rotulo: str
    icone: str
    classe: str


SELOS = {
    'acima': Selo('Acima do corte', '✓', 'selo-acima'),
    'limite': Selo('No limite', '!', 'selo-limite'),
    'abaixo': Selo('Abaixo do corte', '✗', 'selo-abaixo'),
    'sem_corte': Selo('Sem corte no edital', '–', 'selo-neutro'),
    'nao_calculavel': Selo('Corte não calculável', '–', 'selo-neutro'),
}

ROTULOS_DE_ARQUIVO = {
    'provas': 'Suas provas',
    'analises': 'Suas análises',
    'respostas.txt': 'Suas respostas',
    'respostas.csv': 'Suas respostas (planilha)',
    'respostas_extraidas.csv': 'Respostas lidas da folha',
    'questoes.csv': 'Questões da prova',
    'edital_estruturado.json': 'O que o app leu do edital',
    'discrepancias_edital.csv': 'O que o app conferiu no edital',
    'catalogo_edital.md': 'Descobertas no edital',
    'diff_gabarito.csv': 'Mudanças do gabarito preliminar para o definitivo',
    'depuracao': 'Arquivos para investigar problemas',
    'relatorio.md': 'Relatório do concurso (texto)',
    'desempenho_por_disciplina.csv': 'Desempenho por disciplina',
    'desempenho_por_topico.csv': 'Desempenho por tópico',
    'edital_a_confirmar.yaml': 'Dados do edital a confirmar',
    'desempenho_geral.csv': 'Desempenho geral',
    'comparativo_concursos.md': 'Comparação entre os concursos',
    'relatorio_evolucao.md': 'Relatório de evolução (técnico)',
}

TIPOS_DE_PROVA = {'certo_errado': 'certo ou errado', 'multipla_escolha': 'múltipla escolha'}
CALCULO_DA_NOTA = {
    'cebraspe': 'uma errada anula uma certa',
    'simples': 'cada acerto vale um ponto, sem desconto',
}
SITUACAO_DO_GABARITO = {'preliminar': 'preliminar (provisório)', 'definitivo': 'definitivo'}

TERMOS_TECNICOS_DO_RELATORIO = (
    'p <',
    'p =',
    'slope',
    'z-score',
    'Spearman',
    'ρ',
    'MCP',
    'embedding',
    'TF-IDF',
    'ajustado ao acaso',
    'score',
    'similaridade',
    'fator',
)
TERMOS_TECNICOS_DA_MENSAGEM = (
    'YAML',
    'yaml',
    'MCP',
    'cache',
    'OCR',
    'Tesseract',
    'SHA-256',
    'manifesto',
    'perfil da banca',
    'fator',
    'CSV',
    'PATH',
    'modo mínimo',
    'nao_mapeado',
    'endpoint',
    'LLM',
)


def rotulo_do_arquivo(nome: str | PurePath) -> str:
    """ "Rótulo (nome real)" para um arquivo ou pasta conhecido; o nome sozinho para os outros."""
    texto = str(nome)
    chave = PurePath(texto.rstrip('/')).name
    rotulo = ROTULOS_DE_ARQUIVO.get(chave)
    return f'{rotulo} ({texto})' if rotulo else texto


def percentual(valor: float, casas: int = 1) -> str:
    return f'{valor:.{casas}f}'.replace('.', ',') + '%'


def numero(valor: float, casas: int = 1) -> str:
    return f'{valor:.{casas}f}'.replace('.', ',')


def plural(quantidade: int, singular: str, plural_: str | None = None) -> str:
    return f'{quantidade} {singular if quantidade == 1 else plural_ or singular + "s"}'


_MENCAO_NO_EDITAL = re.compile(r', embora o edital mencione (?P<gatilhos>.+); confira à mão$')
_TRADUCOES_DE_AVISO = (
    (
        re.compile(r"^cargo '(?P<cargo>.*)' do concurso\.yaml não casa com nenhum cargo do edital"),
        'o cargo “{cargo}” do cadastro não aparece no edital; li as regras do edital inteiro, sem separar '
        'por cargo.',
    ),
    (
        re.compile(r'^pesos não encontrados no edital$'),
        'não encontrei no edital o peso de cada parte da prova.',
    ),
    (
        re.compile(r'^número de questões não encontrado no edital$'),
        'não encontrei no edital quantas questões cada disciplina tem.',
    ),
    (
        re.compile(r'^nenhuma nota de corte no edital nem no concurso\.yaml$'),
        'nem o edital nem o cadastro trazem nota de corte; sem ela, não dá para dizer se você passou do corte.',
    ),
    (
        re.compile(
            r'^nota de corte do concurso\.yaml \((?P<cadastro>[^)]*)\) difere da do edital \((?P<edital>[^)]*)\)'
        ),
        'a nota de corte do cadastro ({cadastro}) é diferente da do edital ({edital}); vale a do edital.',
    ),
    (
        re.compile(r'^corte por (?P<tipo>.+) não calculável localmente'),
        'o edital define um corte por {tipo}, que não dá para calcular só com a sua prova; ele fica de fora na '
        'comparação com o corte.',
    ),
    (
        re.compile(r'^cronograma do edital sem data de (?P<datas>.+); ficam vazias$'),
        'o edital não traz a data de {datas}.',
    ),
)


def traduzir_aviso(aviso: str) -> str | None:
    """O aviso gravado no `edital_estruturado.json` (sem o prefixo do concurso) em linguagem leiga; None
    quando nenhum padrão o reconhece."""
    texto, mencao = aviso, ''
    if achado := _MENCAO_NO_EDITAL.search(texto):
        texto = texto[: achado.start()]
        mencao = f' O edital fala em {achado["gatilhos"]}; vale conferir no PDF.'
    for padrao, modelo in _TRADUCOES_DE_AVISO:
        if achado := padrao.search(texto):
            return modelo.format(**achado.groupdict()) + mencao
    return None
