FORA_DO_EDITAL = 'fora_do_edital'
NAO_MAPEADO = 'nao_mapeado'


def linhas_topico(topico: str) -> list[str]:
    if topico in (NAO_MAPEADO, FORA_DO_EDITAL):
        return []
    return [f'Tópico do edital: {topico}', '']


def linhas_enunciado(e: dict) -> list[str]:
    if not e.get('enun'):
        return []
    return [str(e['enun']), '']


def linhas_alternativas(e: dict) -> list[str]:
    alternativas = [a for a in e.get('alts') or [] if isinstance(a, dict)]
    if not alternativas:
        return []
    return [*(f'- {a.get("l", "")}) {a.get("t", "")}' for a in alternativas), '']


def linhas_resposta(e: dict) -> list[str]:
    if not (e.get('marc') or e.get('gab')):
        return []
    return [f'Sua resposta: {e.get("marc") or "—"}. Gabarito: {e.get("gab") or "—"}.', '']


def linhas_comentario(e: dict) -> list[str]:
    if not e.get('com'):
        return []
    autor = f' ({e["prof"]})' if e.get('prof') else ''
    return [f'Comentário{autor}: {e["com"]}', '']


def linhas_url(e: dict) -> list[str]:
    if not e.get('url'):
        return []
    return [f'Questão: {e["url"]}', '']


def questao_markdown(
    e: dict,
    aliases: dict[str, str | None],
    *,
    topico_do_erro,
    plural,
) -> list[str]:
    vezes = e.get('v') or 1
    linhas = [f'## {e.get("ass") or "Sem assunto"} — errada {plural(vezes, "vez", "vezes")}', '']
    if origem := ' · '.join(str(e[c]) for c in ('banca', 'orgao', 'ano', 'cad') if e.get(c)):
        linhas += [origem, '']
    topico = topico_do_erro(e.get('ass'), aliases)
    linhas += linhas_topico(topico)
    linhas += linhas_enunciado(e)
    linhas += linhas_alternativas(e)
    linhas += linhas_resposta(e)
    linhas += linhas_comentario(e)
    linhas += linhas_url(e)
    return linhas