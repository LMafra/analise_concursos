from concursos.analytics.consolidado import N_MINIMO_TOPICO
from concursos.pratica.interno import TOTAIS
from concursos.pratica.mesclagem import contagem
from concursos.pratica.tipos import Escolhas, Pratica

FORA_DO_EDITAL = 'fora_do_edital'
NAO_MAPEADO = 'nao_mapeado'


def percentual(acertos: int, n: int) -> float | None:
    return round(100 * acertos / n, 1) if n else None


def topico_do_erro(assunto: str | None, aliases: dict[str, str | None]) -> str:
    if not assunto or assunto not in aliases:
        return NAO_MAPEADO
    return aliases[assunto] or FORA_DO_EDITAL


def linha_de_erro(e: dict, datas: list[str], escolhas: Escolhas, disciplinas: dict[str, str | None]) -> dict:
    return {
        'id': e['id'],
        'v': e.get('v') or contagem(e.get('ds') or []),
        'primeira_data': datas[0],
        'ultima_data': datas[-1],
        'origem': e.get('origem', ''),
        'materia_tec': e.get('mat', ''),
        'disciplina': disciplinas.get(e.get('mat') or ''),
        'assunto': e.get('ass', ''),
        'topico': topico_do_erro(e.get('ass'), escolhas.aliases),
        'banca': e.get('banca', ''),
        'orgao': e.get('orgao', ''),
        'ano': e.get('ano', ''),
        'caderno': e.get('cad', ''),
    }


def linhas_de_erros(pratica: Pratica, escolhas: Escolhas, disciplinas: dict[str, str | None]) -> list[dict]:
    linhas = []
    for e in pratica.erros:
        datas = sorted({d[:10] for d in e.get('ds') or [] if d} | ({e['d']} if e.get('d') else set())) or ['']
        linhas.append(linha_de_erro(e, datas, escolhas, disciplinas))
    return sorted(linhas, key=lambda linha: (-linha['v'], linha['primeira_data'], linha['id']))


def linhas_de_cadernos(
    pratica: Pratica, escolhas: Escolhas, disciplinas: dict[str, str | None]
) -> list[dict]:
    linhas = []
    for c in sorted(pratica.cadernos, key=lambda c: c['id']):
        escolha = escolhas.cadernos[c['id']]
        res, ac, er = (max(0, int(c.get(t) or 0) - int(escolha['base'].get(t, 0))) for t in TOTAIS)
        linhas.append(
            {
                'id': c['id'],
                'caderno': c.get('cad', ''),
                'materia_tec': c.get('mat', ''),
                'disciplina': disciplinas.get(c.get('mat') or ''),
                'modo': escolha['modo'],
                'total': c.get('tot'),
                'resolvidas': res,
                'acertos': ac,
                'erros': er,
                'percentual': percentual(ac, res),
                'amostra_insuficiente': res < N_MINIMO_TOPICO,
            }
        )
    return linhas


def _linha_de_desempenho(disciplina: str) -> dict:
    return {
        'disciplina': disciplina,
        'n': 0,
        'acertos': 0,
        'erros': 0,
        'cadernos': 0,
        'erros_registrados': 0,
        'repetidos': 0,
    }


def linhas_de_desempenho(erros: list[dict], cadernos: list[dict]) -> list[dict]:
    por_disciplina: dict[str, dict] = {}
    for c in cadernos:
        if not c['disciplina']:
            continue
        linha = por_disciplina.setdefault(c['disciplina'], _linha_de_desempenho(c['disciplina']))
        linha['n'] += c['resolvidas']
        linha['acertos'] += c['acertos']
        linha['erros'] += c['erros']
        linha['cadernos'] += 1
    for e in erros:
        if not e['disciplina']:
            continue
        linha = por_disciplina.setdefault(e['disciplina'], _linha_de_desempenho(e['disciplina']))
        linha['erros_registrados'] += 1
        linha['repetidos'] += e['v'] >= 2
    for linha in por_disciplina.values():
        linha['percentual'] = percentual(linha['acertos'], linha['n'])
        linha['amostra_insuficiente'] = linha['n'] < N_MINIMO_TOPICO
    return sorted(por_disciplina.values(), key=lambda linha: linha['disciplina'])
