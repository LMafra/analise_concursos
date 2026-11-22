import unicodedata

from concursos.pratica.constantes import RESULTADO_ACERTO, RESULTADO_BRANCO, RESULTADO_ERRO

TIPO_CERTO_ERRADO = 'certo_errado'
TIPO_MULTIPLA = 'multipla_escolha'
TAMANHO_DIGITAL = 300


def normalizar(texto) -> str:
    decomposto = unicodedata.normalize('NFD', str(texto or ''))
    sem_acento = ''.join(c for c in decomposto if not 0x300 <= ord(c) <= 0x36F)
    return ' '.join(sem_acento.lower().split())


def impressao_digital(enunciado) -> str:
    return normalizar(enunciado)[:TAMANHO_DIGITAL]


def tipo_questao(alts) -> str:
    """Certo/Errado se há exatamente duas alternativas com textos Certo e Errado; senão múltipla escolha."""
    if not isinstance(alts, list) or len(alts) != 2:
        return TIPO_MULTIPLA
    textos = sorted(normalizar((a or {}).get('t')) for a in alts)
    if textos == ['certo', 'errado']:
        return TIPO_CERTO_ERRADO
    return TIPO_MULTIPLA


def _normalizar_marc_gab(valor, tipo: str) -> str:
    bruto = str(valor if valor is not None else '').strip()
    if not bruto:
        return ''
    if tipo == TIPO_CERTO_ERRADO:
        n = normalizar(bruto)
        if n in {'c', 'certo'}:
            return 'certo'
        if n in {'e', 'errado'}:
            return 'errado'
        return n
    return bruto.upper()


def resultado_questao(gab, marc, tipo: str | None = None) -> str:
    """Recalcula acerto/erro/branco a partir de gab e marc; `resultado` do JSON é só auditoria."""
    tipo_efetivo = tipo or TIPO_MULTIPLA
    if marc is None or str(marc).strip() == '':
        return RESULTADO_BRANCO
    g = _normalizar_marc_gab(gab, tipo_efetivo)
    m = _normalizar_marc_gab(marc, tipo_efetivo)
    if not g or not m:
        return RESULTADO_BRANCO
    return RESULTADO_ACERTO if g == m else RESULTADO_ERRO


def linha_de_resposta(item: dict) -> dict:
    tipo = tipo_questao(item.get('alts'))
    marc = item.get('marc')
    return {
        'id': item.get('id') or '',
        'tipo_questao': tipo,
        'mat': item.get('mat') or '',
        'ass': item.get('ass') or '',
        'banca': item.get('banca') or '',
        'ano': item.get('ano') or '',
        'gab': item.get('gab') or '',
        'marc': '' if marc is None else str(marc),
        'resultado': resultado_questao(item.get('gab'), marc, tipo),
        'tem_comentario': 'sim' if (item.get('com') or '').strip() else 'nao',
    }


def so_erros(itens: list[dict]) -> list[dict]:
    """Itens com resultado erro; sem gab/marc (export antigo) entram como erro."""
    filtrados = []
    for item in itens:
        if 'gab' not in item and 'marc' not in item:
            filtrados.append(item)
            continue
        tipo = tipo_questao(item.get('alts'))
        if resultado_questao(item.get('gab'), item.get('marc'), tipo) == RESULTADO_ERRO:
            filtrados.append(item)
    return filtrados
