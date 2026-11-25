import ast
import re
from pathlib import Path

import pytest
from test_cli_relatorio_html import concurso, concursos_html, indice, projeto, respostas  # noqa: F401

from concursos.cli import main
from concursos.linguagem import SELOS, TERMOS_TECNICOS_DA_MENSAGEM, TERMOS_TECNICOS_DO_RELATORIO
from concursos.relatorio_html import _CSS

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


TERMOS_TECNICOS_DO_RELATORIO_DO_CONCURSO = (
    'score',
    'similaridade',
    'TF-IDF',
    'confianca_ocr',
    'nota_liquida',
)


def _parte_principal(html: str, marcador: str) -> str:
    """O que o leitor vê antes do apêndice: sem o CSS e sem os endereços de arquivos e links."""
    principal = re.sub(r'<style>.*?</style>', '', html.split(marcador, 1)[0], flags=re.DOTALL)
    return re.sub(r'(src|href)="[^"]*"', '', principal)


@pytest.fixture
def analisado(projeto: Path) -> Path:  # noqa: F811
    concurso(projeto, 'beta', '2025-09-01')
    respostas(projeto, 'beta', '1 A\n2 B\n3 D\n4 E\n')
    concurso(projeto, 'gama', '2026-02-01')
    respostas(projeto, 'gama', '1 A\n2 C\n3 D\n4 -\n')
    assert main(['--candidate', 'alice']) == 0
    return projeto


def test_parte_principal_do_indice_sem_jargao(analisado):
    painel = indice(analisado).read_text(encoding='utf-8')
    assert [termo for termo in TERMOS_TECNICOS_DO_RELATORIO if termo in painel] == []

    html = concursos_html(analisado).read_text(encoding='utf-8')
    principal = _parte_principal(html, '<details id="detalhes-tecnicos">')
    assert [termo for termo in TERMOS_TECNICOS_DO_RELATORIO if termo in principal] == []


def test_parte_principal_do_relatorio_do_concurso_sem_jargao(analisado):
    html = (analisado / 'analises' / 'alice' / 'alfa' / 'relatorio.html').read_text(encoding='utf-8')

    principal = _parte_principal(html, '<details>')

    assert [termo for termo in TERMOS_TECNICOS_DO_RELATORIO_DO_CONCURSO if termo in principal] == []


def test_indice_tem_tres_cards_e_um_selo_por_prova(analisado):
    html = concursos_html(analisado).read_text(encoding='utf-8')

    secao = html.split('id="como-estou-saindo"', 1)[1].split('</table>', 1)[0]
    assert html.count('<div class="card">') == 3
    assert secao.count('<tr><td>') == 3
    assert len(re.findall(r'class="selo selo-\w+" role="status"', secao)) == 3


def _luminancia(cor: str) -> float:
    canais = [int(cor[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lineares = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * lineares[0] + 0.7152 * lineares[1] + 0.0722 * lineares[2]


def _cor_do_selo(classe: str) -> tuple[str, str]:
    """Resolve `var(--token)` dos selos para o hex em `TOKENS_RELATORIO`."""
    from concursos.design_tokens import TOKENS_RELATORIO

    regra = re.search(
        rf'\.{classe} {{ background: (#[0-9a-fA-F]{{6}}|var\(--[\w-]+\)); color: (#[0-9a-fA-F]{{6}}|var\(--[\w-]+\));',
        _CSS,
    )
    assert regra is not None

    def resolver(valor: str) -> str:
        if valor.startswith('#'):
            return valor.lower()
        nome = re.fullmatch(r'var\((--[\w-]+)\)', valor)
        assert nome is not None and nome.group(1) in TOKENS_RELATORIO
        return TOKENS_RELATORIO[nome.group(1)].lower()

    return resolver(regra.group(1)), resolver(regra.group(2))


@pytest.mark.parametrize('classe', sorted({selo.classe for selo in SELOS.values()}))
def test_selo_tem_contraste_aa(classe):
    fundo, texto = _cor_do_selo(classe)
    clara, escura = sorted((_luminancia(fundo), _luminancia(texto)), reverse=True)

    assert (clara + 0.05) / (escura + 0.05) >= 4.5
