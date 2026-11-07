import ast
from pathlib import Path

import pytest

from concursos.linguagem import TERMOS_TECNICOS_DA_MENSAGEM

PACOTE = Path(__file__).parent.parent / 'src' / 'concursos'
FORA = {'cli/legado.py'}


def _texto_literal(no: ast.expr) -> str:
    """Só as partes literais: numa f-string, o que fica fora das chaves."""
    if isinstance(no, ast.Constant) and isinstance(no.value, str):
        return no.value
    if isinstance(no, ast.JoinedStr):
        return ''.join(_texto_literal(parte) for parte in no.values if isinstance(parte, ast.Constant))
    if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add):
        return _texto_literal(no.left) + _texto_literal(no.right)
    return ''


def _mensagem(chamada: ast.Call) -> ast.expr | None:
    """O texto mostrado na tela: a causa do erro, o texto do `avisar` ou a mensagem do `logger`."""
    funcao = chamada.func
    nome = (
        funcao.id
        if isinstance(funcao, ast.Name)
        else funcao.attr
        if isinstance(funcao, ast.Attribute)
        else ''
    )
    argumentos = {palavra.arg: palavra.value for palavra in chamada.keywords}
    if nome in {'ErroDoUsuario', 'ErroDoAmbiente'}:
        return chamada.args[0] if chamada.args else argumentos.get('causa')
    if nome == 'avisar':
        return chamada.args[1] if len(chamada.args) > 1 else argumentos.get('texto')
    if nome in {'warning', 'error'} and isinstance(funcao.value, ast.Name) and funcao.value.id == 'logger':
        return chamada.args[0] if chamada.args else None
    return None


def mensagens_com_jargao(arquivo: Path) -> list[str]:
    achados = []
    for no in ast.walk(ast.parse(arquivo.read_text(encoding='utf-8'))):
        if isinstance(no, ast.Call) and (mensagem := _mensagem(no)) is not None:
            texto = _texto_literal(mensagem)
            termos = [termo for termo in TERMOS_TECNICOS_DA_MENSAGEM if termo in texto]
            if termos:
                achados.append(f'{no.lineno}: {termos} em {texto!r}')
    return achados


def _arquivos() -> list[str]:
    return sorted(str(p.relative_to(PACOTE)) for p in PACOTE.rglob('*.py'))


@pytest.mark.parametrize('relativo', [a for a in _arquivos() if a not in FORA])
def test_mensagens_na_tela_sem_jargao(relativo):
    """O técnico vai para o `detalhe` (ou `dica`), nunca para a causa ou o texto do aviso."""
    assert mensagens_com_jargao(PACOTE / relativo) == []
