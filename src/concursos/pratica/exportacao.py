import json
from pathlib import Path

from concursos.pratica.erros import ExportacaoInvalidaError
from concursos.pratica.interno import CAMPOS_EXPORTACAO
from concursos.pratica.nomes import APP, VERSAO


def ler_exportacao(caminho: Path) -> tuple[dict, list[str]]:
    try:
        dados = json.loads(caminho.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ExportacaoInvalidaError(f'{caminho}: não é um JSON legível ({erro})') from erro
    if not isinstance(dados, dict) or dados.get('app') != APP:
        raise ExportacaoInvalidaError(f'{caminho}: não é um arquivo do tec-erros (campo app)')
    if dados.get('v') != VERSAO:
        raise ExportacaoInvalidaError(f'{caminho}: versão {dados.get("v")} do arquivo; esperada {VERSAO}')
    avisos = [
        f'{caminho}: campo desconhecido ignorado: {campo}'
        for campo in sorted(set(dados) - CAMPOS_EXPORTACAO)
    ]
    itens = dados.get('erros') if dados.get('erros') is not None else dados.get('respostas')
    if itens is None:
        itens = []
    avisos_ext = dados.get('avisos_extensao') or []
    if isinstance(avisos_ext, list):
        avisos.extend(f'{caminho}: {a}' for a in avisos_ext if a)
    return {
        'erros': itens,
        'cads': dados.get('cads') or [],
        'dev': dados.get('dev'),
        'avisos_extensao': avisos_ext if isinstance(avisos_ext, list) else [],
    }, avisos