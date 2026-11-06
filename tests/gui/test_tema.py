import re
from pathlib import Path

import pytest

from concursos.gui import tema
from concursos.gui.tema import CLARO, ESCURO, Paleta, Tom

PASTA_GUI = Path(tema.__file__).parent
PALETAS = {'claro': CLARO, 'escuro': ESCURO}

CORES_QUASAR = (
    'red|pink|purple|deep-purple|indigo|blue|light-blue|cyan|teal|green|light-green|lime|yellow|amber|'
    'orange|deep-orange|brown|grey|blue-grey|white|black|primary|secondary|accent|positive|negative|info|'
    'warning|dark'
)
PROIBIDOS = {
    'hex': re.compile(r'#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?\b'),
    'gap-*': re.compile(r'\bgap-[\w\[]'),
    'classe de cor': re.compile(rf'\b(?:text|bg|border)-(?:{CORES_QUASAR})(?:-\d+)?\b'),
    'color=': re.compile(r'\bcolor\s*=\s*[\'"]?\w'),
}


def luminancia(cor: str) -> float:
    canais = [int(cor[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lineares = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * lineares[0] + 0.7152 * lineares[1] + 0.0722 * lineares[2]


def contraste(a: str, b: str) -> float:
    clara, escura = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (clara + 0.05) / (escura + 0.05)


def pares_de_texto(p: Paleta) -> list[tuple[str, str, str]]:
    pares = [
        ('texto', p.texto, p.fundo),
        ('texto', p.texto, p.superficie),
        ('texto suave', p.texto_suave, p.fundo),
        ('texto suave', p.texto_suave, p.superficie),
        ('link', p.primaria_texto, p.fundo),
        ('link', p.primaria_texto, p.superficie),
        ('botão', p.sobre_primaria, p.primaria),
    ]
    for tom in Tom:
        fundo = getattr(p, f'{tom}_fundo')
        pares += [
            (f'{tom} texto', getattr(p, f'{tom}_texto'), fundo),
            (f'{tom} texto na superfície', getattr(p, f'{tom}_texto'), p.superficie),
            (f'texto no aviso {tom}', p.texto, fundo),
            (f'texto suave no aviso {tom}', p.texto_suave, fundo),
        ]
    return pares


@pytest.mark.parametrize('nome', PALETAS)
def test_texto_tem_contraste_aa(nome):
    falhas = [
        f'{rotulo}: {frente} sobre {fundo} = {contraste(frente, fundo):.2f}'
        for rotulo, frente, fundo in pares_de_texto(PALETAS[nome])
        if contraste(frente, fundo) < 4.5
    ]
    assert not falhas


@pytest.mark.parametrize('nome', PALETAS)
def test_icones_e_foco_tem_contraste_de_componente(nome):
    p = PALETAS[nome]
    pares = [('foco', p.foco, p.superficie), ('foco', p.foco, p.fundo)]
    for tom in Tom:
        icone = getattr(p, f'{tom}_icone')
        pares += [(f'{tom} ícone', icone, getattr(p, f'{tom}_fundo')), (f'{tom} ícone', icone, p.superficie)]
    falhas = [f'{r}: {a} sobre {b} = {contraste(a, b):.2f}' for r, a, b in pares if contraste(a, b) < 3]
    assert not falhas


def test_notificacoes_do_quasar_tem_contraste_aa():
    cores = tema.CORES_DO_QUASAR
    for nome in ('positive', 'negative', 'info'):
        assert contraste(cores[nome], '#FFFFFF') >= 4.5, nome
    assert contraste(cores['warning'], '#1D1D1D') >= 4.5


def test_nenhuma_cor_ou_gap_fora_do_tema():
    achados = []
    for arquivo in sorted(PASTA_GUI.rglob('*.py')):
        if arquivo.name == 'tema.py':
            continue
        for numero, linha in enumerate(arquivo.read_text(encoding='utf-8').splitlines(), 1):
            for nome, padrao in PROIBIDOS.items():
                if padrao.search(linha):
                    achados.append(f'{arquivo.relative_to(PASTA_GUI)}:{numero} ({nome}): {linha.strip()}')
    assert not achados


def test_gap_vira_style():
    assert tema.gap('sm') == 'gap: 8px'
    assert tema.gap('xs', 'lg') == 'row-gap: 4px; column-gap: 24px'


def test_css_tem_as_duas_paletas():
    assert f'--ca-texto: {CLARO.texto};' in tema.CSS
    assert f'--ca-texto: {ESCURO.texto};' in tema.CSS
    assert 'body.body--dark' in tema.CSS


def test_notificacao_tem_botao_na_cor_do_texto_e_a_dica_em_outra_linha():
    """O Quasar pinta as ações da notificação com a primária: azul sobre o vermelho do erro."""
    assert '.q-notification__actions { color: inherit; }' in tema.CSS
    assert '.q-notification__message { white-space: pre-line; }' in tema.CSS


def test_important_so_na_camada_de_overrides():
    """O NiceGUI põe o `!important` do Quasar numa camada, que vence qualquer `!important` sem camada."""
    camada = re.search(r'@layer overrides \{(.*?)\n\}', tema.CSS, re.DOTALL)
    assert camada is not None
    assert '!important' in camada.group(1)
    assert '!important' not in tema.CSS.replace(camada.group(0), '')
