import shutil
from pathlib import Path

from concursos import exemplo
from concursos.aplicacao import analise
from concursos.aplicacao.opcoes import Opcoes
from concursos.config.contexto import PASTA_ANALISES, PASTA_PROJETO, PASTA_PROVAS, Contexto
from concursos.erros import ErroDoAmbiente
from concursos.relatorio_html import ARQUIVO_INDICE

PASTA = 'exemplo'


def analisar_exemplo(home: Path) -> Path:
    """Recria `<home>/exemplo/`, analisa o concurso de exemplo sem OCR, IA nem rede e devolve o `index.html`.

    A análise grava caminhos relativos à pasta atual; por isso a raiz do contexto é ela, e as pastas do
    exemplo ficam absolutas fora do projeto do usuário."""
    pasta = home / PASTA
    shutil.rmtree(pasta, ignore_errors=True)
    exemplo.criar_exemplo(pasta)
    contexto = Contexto(
        raiz=Path.cwd().resolve(),
        home=home,
        projeto=pasta / PASTA_PROJETO,
        provas=pasta / PASTA_PROVAS,
        analises=pasta / PASTA_ANALISES,
        candidato=exemplo.CANDIDATO,
    )
    opcoes = Opcoes(contexto, sim=True, forcar=True, abrir=False, llm=False, rede=False)
    if analise.analisar(opcoes) != 0:
        raise ErroDoAmbiente(
            'Não consegui analisar o concurso de exemplo.',
            'veja o que aconteceu no registro em ~/.concurso/logs/.',
        )
    return contexto.analises / exemplo.CANDIDATO / ARQUIVO_INDICE
