"""O leigo nunca lê termos técnicos: as strings da GUI e as mensagens do estudo, das integrações e da planilha do
TEC passam por esta lista. Só o Avançado ("Usar um open-notebook que já tenho") pode usá-los."""

import ast
import re
from pathlib import Path

import concursos

PACOTE = Path(concursos.__file__).parent
PROIBIDOS = re.compile(
    r'\blocalhost\b|\bportas?\b|\bservidor(es)?\b|\bdocker\b|(?-i:\bAPI\b)|\bsources?\b|(?<!open-)\bnotebooks?\b'
    r'|sincroniz|\bsync\b|embedding|\bterminal\b',
    re.IGNORECASE,
)
ARQUIVOS = [
    *sorted((PACOTE / 'gui').rglob('*.py')),
    PACOTE / 'aplicacao' / 'estudo.py',
    PACOTE / 'aplicacao' / 'integracoes.py',
    PACOTE / 'planilha_tec.py',
]
# Chamadas cujos argumentos não chegam à tela: marcas de teste, classes e estilos, log, rotas e expressões regulares.
CHAMADAS_INVISIVEIS = {
    'mark',
    'classes',
    'props',
    'style',
    'debug',
    'info',
    'warning',
    'error',
    'exception',
    'getLogger',
    'to',
    'compile',
    'sub',
    'match',
    'search',
    'fullmatch',
    'startswith',
    'endswith',
    'split',
    'get',
}
ARGUMENTOS_INVISIVEIS = {'icon', 'icone', 'icone_da_acao', 'type', 'marca', 'tom', 'name'}
# O segundo argumento destas é o identificador do aviso, não texto.
IDENTIFICADOR_NO_SEGUNDO = {'texto_do_aviso', 'consentimento'}
COMANDOS = re.compile(r'`[^`]*`')
AVANCADO = {
    ('gui/paginas/configuracoes.py', 'OpenNotebookProprio'),
    ('aplicacao/integracoes.py', 'aviso_open_notebook'),
}


def _ignorar(no: ast.AST, ignorados: set[int]) -> None:
    ignorados.update(id(filho) for filho in ast.walk(no))


def _nome_da_chamada(chamada: ast.Call) -> str | None:
    if isinstance(chamada.func, ast.Attribute):
        return chamada.func.attr
    if isinstance(chamada.func, ast.Name):
        return chamada.func.id
    return None


def termos_proibidos(codigo: str, relativo: str = '') -> list[tuple[int, str]]:
    arvore = ast.parse(codigo)
    ignorados: set[int] = set()
    for no in ast.walk(arvore):
        corpo = getattr(no, 'body', None)
        if isinstance(no, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if (relativo, getattr(no, 'name', '')) in AVANCADO:
                _ignorar(no, ignorados)
            if corpo and isinstance(corpo[0], ast.Expr) and isinstance(corpo[0].value, ast.Constant):
                ignorados.add(id(corpo[0].value))
        if isinstance(no, ast.Dict):
            for chave in no.keys:
                if chave is not None:
                    _ignorar(chave, ignorados)
        if isinstance(no, ast.Call):
            nome = _nome_da_chamada(no)
            if nome in CHAMADAS_INVISIVEIS:
                for argumento in [*no.args, *(k.value for k in no.keywords)]:
                    _ignorar(argumento, ignorados)
            if nome in IDENTIFICADOR_NO_SEGUNDO:
                for argumento in no.args[1:]:
                    _ignorar(argumento, ignorados)
            for argumento in no.keywords:
                if argumento.arg in ARGUMENTOS_INVISIVEIS:
                    _ignorar(argumento.value, ignorados)
    return sorted(
        (no.lineno, no.value)
        for no in ast.walk(arvore)
        if isinstance(no, ast.Constant)
        and isinstance(no.value, str)
        and id(no) not in ignorados
        and PROIBIDOS.search(COMANDOS.sub('', no.value))
    )


def test_o_detector_acha_termo_proibido_em_texto_da_tela():
    codigo = (
        "ui.button('Sincronizar agora').mark('sincronizar')\n"
        "ui.label(f'Servidor em localhost:{porta}')\n"
        "ui.label('Envie para o open-notebook')\n"
        "logger.debug('notebook sync falhou')\n"
    )

    assert [linha for linha, _ in termos_proibidos(codigo)] == [1, 2]


def test_nenhum_termo_tecnico_fora_do_avancado():
    achados = [
        f'{arquivo.relative_to(PACOTE)}:{linha}: {texto!r}'
        for arquivo in ARQUIVOS
        for linha, texto in termos_proibidos(
            arquivo.read_text(encoding='utf-8'), arquivo.relative_to(PACOTE).as_posix()
        )
    ]

    assert achados == []
