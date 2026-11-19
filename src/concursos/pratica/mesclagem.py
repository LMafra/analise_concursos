from concursos.modelo import OrigemErroTec
from concursos.pratica.erros import CompletudeInvalidaError
from concursos.pratica.interno import CAMPOS_TEXTO


def vazio(valor) -> bool:
    return valor is None or valor == '' or (isinstance(valor, list) and not valor)


def contagem(ds: list[str]) -> int:
    return len(ds) or 1


def _preencher_campo(r: dict, b: dict, campo: str) -> None:
    if vazio(r.get(campo)) and not vazio(b.get(campo)):
        r[campo] = b[campo]


def _mesclar_campos_texto(r: dict, b: dict) -> None:
    for campo in (*CAMPOS_TEXTO, 'alts', 'fp'):
        _preencher_campo(r, b, campo)


def _mesclar_comentario(r: dict, b: dict) -> None:
    if not vazio(b.get('com')) and len(str(b['com'])) > len(str(r.get('com') or '')):
        r['com'] = b['com']
        if not vazio(b.get('prof')):
            r['prof'] = b['prof']


def _mesclar_ds_e_origem(r: dict, a: dict, b: dict) -> None:
    r['ds'] = sorted({d for d in [*(a.get('ds') or []), *(b.get('ds') or [])] if d})
    r['v'] = contagem(r['ds'])
    tempo_real = OrigemErroTec.TEMPO_REAL.value
    r['origem'] = (
        tempo_real
        if tempo_real in (a.get('origem'), b.get('origem')) or r['ds']
        else OrigemErroTec.HISTORICO.value
    )


def _mesclar_data_e_dev(r: dict, a: dict, b: dict) -> None:
    primeira_ds = r['ds'][0][:10] if r['ds'] else ''
    if datas := sorted(d for d in (a.get('d'), b.get('d'), primeira_ds) if d):
        r['d'] = datas[0]
    if b.get('dev') and (not a.get('dev') or (b.get('d') and a.get('d') and b['d'] < a['d'])):
        r['dev'] = b['dev']


def fundir(a: dict, b: dict) -> dict:
    r = dict(a)
    _mesclar_campos_texto(r, b)
    _mesclar_comentario(r, b)
    _mesclar_ds_e_origem(r, a, b)
    _mesclar_data_e_dev(r, a, b)
    if {**r, 't': a.get('t')} == {**a, 't': a.get('t')}:
        return a
    r['t'] = max(a.get('t') or 0, b.get('t') or 0)
    return r


def mesclar_erros(base: list[dict], novos: list[dict], *, impressao_digital) -> list[dict]:
    """Casa por `id` e, sem ele, pela impressão digital; a ordem é a da primeira vez em que cada erro apareceu."""
    lista = list(base)
    por_id = {r['id']: i for i, r in enumerate(lista)}
    por_digital = {r['fp']: i for i, r in enumerate(lista) if r.get('fp')}
    for original in novos:
        r = {'ds': [], **original}
        if not r.get('fp') and r.get('enun'):
            r['fp'] = impressao_digital(r['enun'])
        if not isinstance(r['ds'], list):
            r['ds'] = []
        i = por_id.get(r.get('id'), por_digital.get(r['fp']) if r.get('fp') else None)
        if i is None:
            r['v'] = contagem(r['ds'])
            lista.append(r)
            i = len(lista) - 1
        else:
            lista[i] = fundir(lista[i], r)
        por_id[r.get('id')] = i
        if r.get('fp'):
            por_digital[r['fp']] = i
    return lista


def _somar_cads(cads: list[dict], campo: str) -> int:
    return sum(int(c.get(campo) or 0) for c in cads)


def _avisos_completude(n: int, total_er: int, total_res: int, total_tot: int) -> list[str]:
    if total_er and n == total_er:
        return ['prática: exportação só de erros (len == cads.er)']
    if total_tot and n == total_tot:
        return ['prática: exportação completa (len == cads.tot, com brancos)']
    if total_res and n == total_res:
        return ['prática: exportação completa (len == cads.res)']
    if total_er and n < total_er:
        return ['prática: exportação parcial (len < cads.er)']
    return []


def verificar_completude(itens: list[dict], cads: list[dict]) -> list[str]:
    """Compara len(itens) com totais de `cads`; sem cadernos, não avisa.

    Brancos não entram em `res` do TEC: `len` pode ser `tot` (> `res`). Só `len > tot` é erro."""
    if not cads:
        return []
    total_er = _somar_cads(cads, 'er')
    total_res = _somar_cads(cads, 'res')
    total_tot = _somar_cads(cads, 'tot')
    n = len(itens)
    if total_tot and n > total_tot:
        raise CompletudeInvalidaError(
            f'mais questões do que o caderno ({n} no arquivo, {total_tot} no total em cads)'
        )
    return _avisos_completude(n, total_er, total_res, total_tot)