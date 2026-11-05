import os
from dataclasses import dataclass
from pathlib import Path

from concursos.aplicacao.preferencias import lembrar_projeto, ultimo_projeto
from concursos.candidatos import candidatos_existentes
from concursos.config.contexto import PASTA_PROJETO, PASTA_PROVAS, Contexto, resolver_contexto, resolver_home
from concursos.erros import ErroDoUsuario
from concursos.modelo import DecisaoJanela

NOME_PASTA_PADRAO = 'Concursos'


@dataclass
class Estado:
    """O que a janela lembra entre uma tela e outra; a GUI é de um usuário só, na máquina dele."""

    projeto: Path | None = None
    candidato: str | None = None
    todos: bool = False
    ocupado: bool = False
    pedir_analise: bool = False
    no_navegador: bool = False
    decisao_janela: DecisaoJanela | None = None
    janela_falhou: bool = False
    cliente_conectou: bool = False
    janela_reaberta: bool = False

    def contexto(self) -> Contexto:
        if self.projeto is None:
            raise ErroDoUsuario('nenhuma pasta de projeto escolhida', 'escolha a pasta em "Projeto"')
        return resolver_contexto(
            cwd=self.projeto, data_dir=self.projeto / PASTA_PROJETO, candidato=self.candidato
        )

    def abrir_projeto(self, pasta: Path) -> None:
        """Muda a pasta atual do processo: partes do pipeline resolvem caminhos a partir dela."""
        pasta = pasta.expanduser().resolve()
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except OSError as erro:
            raise ErroDoUsuario(
                f'não foi possível usar a pasta {pasta} ({erro})', 'escolha outra pasta'
            ) from erro
        os.chdir(pasta)
        self.projeto = pasta
        self.candidato = None
        self.todos = False
        lembrar_projeto(resolver_home() / 'config.toml', pasta)

    def candidatos(self) -> list[str]:
        if self.projeto is None:
            return []
        provas = self.contexto().provas
        return candidatos_existentes(provas) if provas.is_dir() else []


def pasta_padrao(home: Path | None = None) -> Path:
    """`Documentos/Concursos` (ou `Documents/Concursos`, se for a pasta que existe)."""
    home = home or Path.home()
    for nome in ('Documentos', 'Documents'):
        if (home / nome).is_dir():
            return home / nome / NOME_PASTA_PADRAO
    return home / 'Documentos' / NOME_PASTA_PADRAO


def parece_projeto(pasta: Path) -> bool:
    return (pasta / PASTA_PROJETO).is_dir() or (pasta / PASTA_PROVAS).is_dir()


def projeto_inicial(cwd: Path, config_global: Path) -> Path | None:
    """A pasta atual, se já é um projeto; senão a última usada na GUI, se ainda existe."""
    if parece_projeto(cwd) and cwd.resolve() != resolver_home().resolve().parent:
        return cwd.resolve()
    ultimo = ultimo_projeto(config_global)
    return ultimo if ultimo is not None and ultimo.is_dir() else None


ESTADO = Estado()
