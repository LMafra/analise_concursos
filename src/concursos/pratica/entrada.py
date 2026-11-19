import json
from pathlib import Path

from concursos.pratica.erros import CompletudeInvalidaError, ExportacaoInvalidaError
from concursos.pratica.exportacao import ler_exportacao
from concursos.pratica.mesclagem import mesclar_erros, verificar_completude
from concursos.pratica.nomes import APP_ESTADO, ARQUIVO_ESTADO
from concursos.pratica.tipos import Pratica


def mesclar_cadernos(base: list[dict], novos: list[dict]) -> list[dict]:
    """O progresso fica na conta do TEC e não diminui: vence o de maior `res` e, no empate, o mais recente."""
    por_id = {c['id']: c for c in base}
    for c in novos:
        atual = por_id.get(c['id'])
        if (
            atual is None
            or c.get('res', 0) > atual.get('res', 0)
            or (c.get('res', 0) == atual.get('res', 0) and (c.get('t') or 0) > (atual.get('t') or 0))
        ):
            por_id[c['id']] = {**(atual or {}), **c}
    return list(por_id.values())


def _ler_estado(caminho: Path) -> tuple[dict, list[str]]:
    try:
        dados = json.loads(caminho.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erro:
        return {}, [f'prática: {caminho} ilegível ({erro}); as escolhas do caderno.html ficaram de fora']
    if not isinstance(dados, dict) or dados.get('app') != APP_ESTADO:
        return {}, [f'prática: {caminho} não é um estado do caderno.html (campo app)']
    return dados, []


def _itens_e_cadernos(dados: dict) -> tuple[list[dict], list[dict]]:
    itens = [e for e in dados['erros'] if isinstance(e, dict) and e.get('id')]
    cads = [c for c in dados['cads'] if isinstance(c, dict) and c.get('id')]
    return itens, cads


def _incorporar_arquivo(pratica: Pratica, dados: dict, aviso: list[str], *, impressao_digital) -> list[str]:
    itens, cads = _itens_e_cadernos(dados)
    avisos = list(verificar_completude(itens, cads)) + list(aviso)
    pratica.erros = mesclar_erros(pratica.erros, itens, impressao_digital=impressao_digital)
    pratica.cadernos = mesclar_cadernos(pratica.cadernos, cads)
    return avisos


def _filtrar_removidos(erros: list[dict], estado: dict) -> list[dict]:
    removidos = set(estado.get('removidos') or [])
    return [
        e for e in erros if e['id'] not in removidos and f'fp:{e.get("fp")}' not in removidos
    ]


def _avisos_arquivo_invalido(caminho: Path, erro: Exception) -> str:
    if isinstance(erro, CompletudeInvalidaError):
        return f'prática: {caminho}: {erro}; arquivo ignorado'
    return f'prática: {erro}; arquivo ignorado'


def ler_entrada(pasta: Path, *, impressao_digital) -> tuple[Pratica, list[str]]:
    """Todas as exportações da pasta, mescladas, e o `caderno-estado.json` (sugestões do `caderno.html`).

    Um arquivo inválido vira aviso e os outros seguem. Completude `len > cads.res` aborta o arquivo."""
    pratica, avisos = Pratica(), []
    for caminho in sorted(pasta.glob('*.json')) if pasta.is_dir() else []:
        if caminho.name == ARQUIVO_ESTADO:
            pratica.estado, aviso = _ler_estado(caminho)
            avisos += aviso
            continue
        try:
            dados, aviso = ler_exportacao(caminho)
            avisos += _incorporar_arquivo(pratica, dados, aviso, impressao_digital=impressao_digital)
        except (CompletudeInvalidaError, ExportacaoInvalidaError) as erro:
            avisos.append(_avisos_arquivo_invalido(caminho, erro))
            continue
    pratica.erros = _filtrar_removidos(pratica.erros, pratica.estado)
    return pratica, avisos