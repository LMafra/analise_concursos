import json
from pathlib import Path

from concursos.analytics.taxonomia import DisciplinaCanonica
from concursos.edital import ARQUIVO_EDITAL_ESTRUTURADO, Conhecimento, Disciplina, Edital, Topico
from concursos.topicos import chave_de_palavras


def disciplina_da_materia(
    materia: str | None, taxonomia: dict[str, DisciplinaCanonica], materias: dict[str, str]
) -> str | None:
    """A disciplina canônica da matéria do TEC: um nome da taxonomia (sem diferença de acento e caixa) ou a
    escolha gravada em `materias`."""
    if not materia:
        return None
    if materia in materias:
        return materias[materia]
    if materia in taxonomia:
        return taxonomia[materia].nome
    chave = chave_de_palavras(materia)
    return next((d.nome for nome, d in taxonomia.items() if chave_de_palavras(nome) == chave), None)


def carregar_edital(pasta_concurso: Path) -> Edital | None:
    caminho = pasta_concurso / ARQUIVO_EDITAL_ESTRUTURADO
    if not caminho.exists():
        return None
    dados = json.loads(caminho.read_text(encoding='utf-8'))
    return Edital(
        dados.get('fonte', ''),
        dados.get('cargo'),
        tuple(
            Conhecimento(
                c['nome'],
                tuple(
                    Disciplina(
                        d['nome'],
                        tuple(
                            Topico(t.get('numero', ''), t['nome'], t.get('descricao') or t['nome'])
                            for t in d.get('topicos', [])
                        ),
                    )
                    for d in c.get('disciplinas', [])
                ),
            )
            for c in dados.get('conhecimentos', [])
        ),
    )