from concursos.pratica.questao_md import questao_markdown
from concursos.pratica.tabelas import topico_do_erro
from concursos.pratica.tipos import ResultadoPratica

SEM_DISCIPLINA = 'Sem disciplina'


def _plural(n: int, singular: str, plural: str) -> str:
    return f'{n} {singular if n == 1 else plural}'


def textos_do_caderno(resultado: ResultadoPratica) -> dict[str, str]:
    """Disciplina → markdown dos erros dela, para o notebook "Caderno de erros" do open-notebook."""
    por_disciplina: dict[str, list[dict]] = {}
    for e in resultado.pratica.erros:
        disciplina = resultado.disciplinas.get(e.get('mat') or '') or SEM_DISCIPLINA
        por_disciplina.setdefault(disciplina, []).append(e)
    textos = {}
    for disciplina, erros in sorted(por_disciplina.items()):
        linhas = [
            f'# Caderno de erros — {disciplina}',
            '',
            f'{_plural(len(erros), "questão errada", "questões erradas")} no TEC, das mais repetidas para as menos.',
            '',
        ]
        for e in sorted(erros, key=lambda e: (-(e.get('v') or 1), e['id'])):
            linhas += questao_markdown(
                e, resultado.escolhas.aliases, topico_do_erro=topico_do_erro, plural=_plural
            )
        textos[disciplina] = '\n'.join(linhas).rstrip() + '\n'
    return textos


def textos_para_normas(resultado: ResultadoPratica) -> list[str]:
    """Enunciado e comentário de cada erro, onde `legislacao.extrair_citacoes` procura as normas citadas."""
    return ['\n'.join(str(e[c]) for c in ('enun', 'com') if e.get(c)) for e in resultado.pratica.erros]