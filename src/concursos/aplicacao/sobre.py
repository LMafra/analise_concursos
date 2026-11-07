"""A tela Sobre: o resumo do app (sem rede) e a atualização da biblioteca, sem projeto aberto."""

import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

from concursos.aplicacao import atualizador as atualizacao
from concursos.aplicacao import estudo
from concursos.aplicacao.opcoes import Opcoes
from concursos.config.contexto import Contexto
from concursos.empacotado import embutido
from concursos.erros import ErroDoUsuario
from concursos.estudo import instalacao
from concursos.estudo.instalacao import PacoteDisponivel, Pastas


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


def _so_global(home: Path) -> Opcoes:
    """A biblioteca mora na pasta global; nenhum caminho de projeto é usado."""
    return Opcoes(Contexto(raiz=home, home=home, projeto=home, provas=home, analises=home))


def biblioteca_nova(home: Path, transporte=None) -> PacoteDisponivel | None:  # noqa: ANN001
    return estudo.atualizacao_da_biblioteca(_so_global(home), transporte)


def atualizar_biblioteca(
    home: Path,
    progresso: estudo.ProgressoEstudo | None = None,
    transporte=None,  # noqa: ANN001
) -> str:
    return estudo.atualizar_biblioteca(
        _so_global(home), consentiu=True, progresso=progresso, transporte=transporte
    )
