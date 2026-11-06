import re

ISO = re.compile(r'^(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?$')


def data_br(texto: str | None) -> str:
    """'2026-11-06' (ou com hora) vira '06/11/2026'; o que não é data ISO volta como veio."""
    if not texto:
        return ''
    encontrada = ISO.match(str(texto).strip())
    if encontrada is None:
        return str(texto)
    ano, mes, dia = encontrada.groups()
    return f'{dia}/{mes}/{ano}'
