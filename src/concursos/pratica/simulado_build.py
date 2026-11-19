import html


def origem_questao(e: dict) -> str:
    return ' · '.join(str(e[c]) for c in ('mat', 'ass', 'banca', 'orgao', 'ano') if e.get(c))


def secao_questao(numero: int, e: dict) -> str:
    origem = origem_questao(e)
    partes = [f'<h2>Questão {numero}</h2>', f'<p class="origem">{html.escape(origem)}</p>']
    if e.get('enun'):
        partes.append(f'<p>{html.escape(str(e["enun"]))}</p>')
    if alternativas := [a for a in e.get('alts') or [] if isinstance(a, dict)]:
        itens = ''.join(
            f'<li>{html.escape(str(a.get("l", "")))}) {html.escape(str(a.get("t", "")))}</li>'
            for a in alternativas
        )
        partes.append(f'<ul>{itens}</ul>')
    if e.get('url'):
        partes.append(f'<p><a href="{html.escape(str(e["url"]))}">abrir no TEC</a></p>')
    return f'<section>{"".join(partes)}</section>'


def gabarito_html(questoes: list[dict]) -> str:
    return ''.join(
        f'<li>Questão {numero}: {html.escape(str(e.get("gab") or "—"))}'
        + (f' (você marcou {html.escape(str(e["marc"]))})' if e.get('marc') else '')
        + '</li>'
        for numero, e in enumerate(questoes, start=1)
    )


def pagina_simulado(questoes: list[dict], explicacao: str) -> str:
    corpo = [secao_questao(numero, e) for numero, e in enumerate(questoes, start=1)]
    gabarito = gabarito_html(questoes)
    return (
        '<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
        '<title>Simulado com os meus erros</title>\n'
        '<style>body{font-family:sans-serif;max-width:48rem;margin:2rem auto;line-height:1.5}'
        '.origem{font-size:.9rem;opacity:.75}section{margin-bottom:2rem}</style>\n</head>\n<body>\n'
        f'<h1>Simulado com os meus erros</h1>\n<p>{html.escape(explicacao)}</p>\n'
        + '\n'.join(corpo)
        + f'\n<h2>Gabarito</h2>\n<ol class="gabarito">{gabarito}</ol>\n</body>\n</html>\n'
    )