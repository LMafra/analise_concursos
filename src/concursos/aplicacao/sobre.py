"""O resumo da tela Sobre: versão, sistema, leitor de folhas e biblioteca, sem projeto aberto e sem rede."""

import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

from concursos.aplicacao import atualizador as atualizacao
from concursos.empacotado import embutido
from concursos.erros import ErroDoUsuario
from concursos.estudo import instalacao
from concursos.estudo.instalacao import Pastas


@dataclass(frozen=True)
class ResumoDoApp:
    versao: str
    sistema: str
    leitor_de_folhas: str
    leitor_pronto: bool
    biblioteca: str
    biblioteca_pronta: bool


def leitor_de_folhas() -> tuple[str, bool]:
    tesseract = shutil.which('tesseract')
    if tesseract is None:
        return (
            'não encontrado: provas escaneadas não são lidas, e as respostas podem ser digitadas se a folha '
            'não for lida',
            False,
        )
    return ('pronto' if embutido(tesseract) else f'pronto ({tesseract})', True)


def biblioteca(home: Path) -> tuple[str, bool]:
    try:
        instalacao.plataforma()
    except ErroDoUsuario:
        return 'não disponível neste sistema', False
    pastas = Pastas.do_home(home)
    if instalacao.instalado(pastas) is None:
        return 'não preparada (prepare em Estudar)', False
    return f'pronta (open-notebook {instalacao.ler_estado(pastas).atual})', True


def resumo_do_app(home: Path) -> ResumoDoApp:
    texto_do_leitor, leitor_pronto = leitor_de_folhas()
    texto_da_biblioteca, biblioteca_pronta = biblioteca(home)
    return ResumoDoApp(
        atualizacao.versao_instalada(),
        f'{platform.system()} {platform.release()}'.strip(),
        texto_do_leitor,
        leitor_pronto,
        texto_da_biblioteca,
        biblioteca_pronta,
    )
