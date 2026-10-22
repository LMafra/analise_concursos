import json
import logging
import re
from dataclasses import replace
from datetime import date

from concursos.analytics.regras_edital import (
    Campo,
    FonteRegra,
    RegrasEdital,
    confianca_do_edital,
)
from concursos.deteccao import normalizar
from concursos.llm import ClienteLlm, LlmIndisponivelError
from concursos.modelo import Formato

logger = logging.getLogger(__name__)

CONFIANCA_LLM = 0.6
MAXIMO_CARACTERES = 40_000
_FONTES_SUBSTITUIVEIS = frozenset({FonteRegra.PERFIL, FonteRegra.DEFAULT})
_PALAVRAS_CHAVE = re.compile(
    r'alternativ|opç|opco|resposta|ponto|nota|anulad|errad|desconta|data|realizad|cronograma|objetiva',
    re.IGNORECASE,
)
_SISTEMA = (
    'Você extrai regras de editais de concurso público brasileiros. Responda só com um objeto JSON. Para '
    'cada campo pedido, devolva {"valor": ..., "trecho_origem": "..."} ou null se o edital não disser. O '
    'trecho_origem é uma cópia literal, de até 300 caracteres, do texto do edital que sustenta o valor.'
)
_CAMPOS = {
    'alternativas': 'número de alternativas por questão da prova objetiva (inteiro)',
    'penalidade': (
        'fração de uma questão certa descontada por questão errada (0 se o erro não desconta; 1 se uma '
        'errada anula uma certa)'
    ),
    'data_prova': 'data da prova objetiva no formato AAAA-MM-DD',
}


def completar_com_llm(
    regras: RegrasEdital, documentos: dict[str, list[str]], cliente: ClienteLlm
) -> RegrasEdital:
    """Preenche, com fonte `llm`, os campos que o texto do edital não resolveu e que cairiam no perfil ou no
    padrão. Só o texto do edital e dos anexos vai para o provedor; um valor sem trecho literal é descartado."""
    pedidos = _pedidos(regras)
    if not pedidos:
        return regras
    texto = _texto_enviado(documentos)
    usuario = (
        'Campos pedidos:\n'
        + '\n'.join(f'- {campo}: {_CAMPOS[campo]}' for campo in pedidos)
        + f'\n\nTexto do edital:\n<<<\n{texto}\n>>>'
    )
    try:
        resposta = _json(cliente.completar(_SISTEMA, usuario))
    except LlmIndisponivelError as erro:
        logger.warning('LLM %s indisponível; seguindo sem ele: %s', cliente.provedor, erro)
        return regras
    preenchidos = {}
    for campo in pedidos:
        if (achado := _campo(campo, resposta.get(campo), documentos, cliente.provedor)) is not None:
            preenchidos[campo] = achado
    if not preenchidos:
        return regras
    for campo, achado in preenchidos.items():
        logger.warning(
            '%s veio do LLM %s: %s (trecho "%s", %s, página %s); confira no PDF',
            campo,
            cliente.provedor,
            achado.valor,
            achado.trecho_origem,
            achado.documento_origem,
            achado.pagina_origem,
        )
    prova = regras.prova
    if 'alternativas' in preenchidos:
        prova = replace(prova, alternativas=preenchidos['alternativas'])
    if 'penalidade' in preenchidos:
        prova = replace(prova, penalidade=preenchidos['penalidade'])
    cronograma = regras.cronograma
    if 'data_prova' in preenchidos:
        cronograma = replace(cronograma, objetiva=preenchidos['data_prova'])
    completas = replace(regras, prova=prova, cronograma=cronograma)
    return replace(completas, confianca_edital=confianca_do_edital(completas))


def _pedidos(regras: RegrasEdital) -> list[str]:
    pedidos = []
    if (
        regras.prova.formato.valor == Formato.MULTIPLA_ESCOLHA
        and regras.prova.alternativas.fonte in _FONTES_SUBSTITUIVEIS
    ):
        pedidos.append('alternativas')
    if regras.prova.penalidade.fonte in _FONTES_SUBSTITUIVEIS:
        pedidos.append('penalidade')
    if regras.cronograma.objetiva.fonte in _FONTES_SUBSTITUIVEIS:
        pedidos.append('data_prova')
    return pedidos


def _texto_enviado(documentos: dict[str, list[str]]) -> str:
    """As páginas com palavras das regras pedidas, até o limite; cada uma com o documento e a página."""
    partes, tamanho = [], 0
    for documento, paginas in documentos.items():
        for numero, pagina in enumerate(paginas, start=1):
            if not _PALAVRAS_CHAVE.search(pagina):
                continue
            parte = f'[{documento}, página {numero}]\n{pagina.strip()}'
            if tamanho + len(parte) > MAXIMO_CARACTERES:
                return '\n\n'.join(partes)
            partes.append(parte)
            tamanho += len(parte)
    return '\n\n'.join(partes)


def _json(texto: str) -> dict:
    inicio, fim = texto.find('{'), texto.rfind('}')
    if inicio < 0 or fim < inicio:
        raise LlmIndisponivelError('resposta sem objeto JSON')
    try:
        dados = json.loads(texto[inicio : fim + 1])
    except json.JSONDecodeError as erro:
        raise LlmIndisponivelError(f'JSON inválido na resposta: {erro}') from erro
    if not isinstance(dados, dict):
        raise LlmIndisponivelError('resposta sem objeto JSON')
    return dados


def _campo(campo: str, resposta: object, documentos: dict[str, list[str]], provedor: str) -> Campo | None:
    if not isinstance(resposta, dict) or resposta.get('valor') is None:
        return None
    trecho = resposta.get('trecho_origem')
    origem = _localizar(trecho, documentos) if isinstance(trecho, str) and trecho.strip() else None
    if origem is None:
        logger.info('LLM %s: %s descartado, sem trecho literal conferível no edital', provedor, campo)
        return None
    valor = _valor(campo, resposta['valor'])
    if valor is None:
        logger.info('LLM %s: %s descartado, valor inválido %r', provedor, campo, resposta['valor'])
        return None
    documento, pagina = origem
    return Campo(valor, FonteRegra.LLM, trecho.strip(), documento, pagina, CONFIANCA_LLM)


def _valor(campo: str, valor: object) -> object | None:
    try:
        if campo == 'alternativas':
            numero = int(valor)
            return numero if 2 <= numero <= 10 else None
        if campo == 'penalidade':
            fator = float(str(valor).replace(',', '.'))
            return fator if 0 <= fator <= 1 else None
        return date.fromisoformat(str(valor))
    except (TypeError, ValueError):
        return None


def _localizar(trecho: str, documentos: dict[str, list[str]]) -> tuple[str, int] | None:
    procurado = _compacto(trecho)
    if not procurado:
        return None
    for documento, paginas in documentos.items():
        for numero, pagina in enumerate(paginas, start=1):
            if procurado in _compacto(pagina):
                return documento, numero
    return None


def _compacto(texto: str) -> str:
    return normalizar(texto)
