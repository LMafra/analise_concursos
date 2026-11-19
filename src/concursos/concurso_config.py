import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from concursos.modelo import (
    LETRAS,
    Escolaridade,
    Formato,
    ModeloCorrecao,
    Nivel,
    Pontuacao,
    StatusGabarito,
)
from concursos.perfis import ids_de_banca, perfil_da_banca

ARQUIVO_CONFIG = 'concurso.yaml'
ARQUIVO_CONFIRMACAO = 'edital_a_confirmar.yaml'
CAMPOS_CONFIRMAVEIS = ('data_prova', 'alternativas', 'fator_penalidade', 'nota_corte')
_CAMPOS_DE_CORRECAO = ('fator_penalidade', 'nota_corte')


from concursos.concurso_config_modelos import *  # noqa: F403
from concursos.concurso_config_modelos import (  # noqa: F401
    _CarregadorSemDatas,
    ArquivoAusenteError,
    ConfiguracaoInvalidaError,
    ConcursoConfig,
    peso_da_questao,
    pesos_variam,
)


def carregar_concurso(pasta: Path) -> ConcursoConfig:
    caminho = pasta / ARQUIVO_CONFIG
    if not caminho.exists():
        raise ArquivoAusenteError(f'{caminho}: arquivo de configuração ausente')
    dados = _ler_yaml(caminho)
    confirmados = _ler_confirmacao(pasta / ARQUIVO_CONFIRMACAO)
    if not confirmados:
        return validar_dados(pasta, dados)
    try:
        return _montar(pasta, _com_confirmados(dados, confirmados))
    except (KeyError, TypeError, ValueError) as erro:
        validar_dados(pasta, dados)
        raise ConfiguracaoInvalidaError(f'{pasta / ARQUIVO_CONFIRMACAO}: {erro}') from erro


def ler_dados(pasta: Path) -> dict:
    """O `concurso.yaml` cru, para regravar; vazio se ausente ou ilegível."""
    caminho = pasta / ARQUIVO_CONFIG
    if not caminho.exists():
        return {}
    try:
        return yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError:
        return {}


def _bloco_sem_provas(pasta: Path, bloco: str) -> dict | None:
    try:
        dados = ler_dados(pasta)
    except ValueError:
        return None
    if not isinstance(dados, dict) or dados.get('provas') or not isinstance(dados.get(bloco), dict):
        return None
    return dados[bloco]


def vinculo_sem_provas(pasta: Path) -> dict | None:
    """O bloco `pci` da pasta criada por "Adicionar ao meu projeto", enquanto ela não tem os arquivos da prova."""
    return _bloco_sem_provas(pasta, 'pci')


def simulado_sem_provas(pasta: Path) -> dict | None:
    """O bloco `simulado` da prova anterior do PCI cujos PDFs ainda não foram baixados."""
    return _bloco_sem_provas(pasta, 'simulado')


def gravar_dados(pasta: Path, dados: dict) -> None:
    texto = yaml.safe_dump(dados, allow_unicode=True, sort_keys=False)
    (pasta / ARQUIVO_CONFIG).write_text(texto, encoding='utf-8')


def com_gabarito_definitivo(dados: dict, prova: str, anterior: str, novo: str, data: str) -> dict:
    """Cópia dos dados com o gabarito definitivo na prova, o anterior ignorado e o evento no histórico."""
    provas = {**dados['provas']}
    provas[prova] = {
        **provas[prova],
        'gabarito': {'arquivo': novo, 'status': StatusGabarito.DEFINITIVO.value},
    }
    alterado = {**dados, 'provas': provas}
    if anterior != novo:
        alterado['ignorar'] = [*(dados.get('ignorar') or []), anterior]
    evento = {'data': data, 'tipo': 'gabarito_definitivo', 'prova': prova, 'anterior': anterior, 'novo': novo}
    alterado['historico'] = [*(dados.get('historico') or []), evento]
    return alterado


def _ler_yaml(caminho: Path) -> dict:
    try:
        dados = yaml.load(caminho.read_text(encoding='utf-8'), Loader=_CarregadorSemDatas) or {}
    except yaml.YAMLError as erro:
        raise ConfiguracaoInvalidaError(f'{caminho}: {erro}') from erro
    if not isinstance(dados, dict):
        raise ConfiguracaoInvalidaError(f'{caminho}: esperado um mapa de campo para valor')
    return dados


def _ler_confirmacao(caminho: Path) -> dict:
    """Os campos preenchidos do `edital_a_confirmar.yaml`; os vazios ficam de fora."""
    if not caminho.exists():
        return {}
    dados = _ler_yaml(caminho)
    if desconhecidos := sorted(set(dados) - set(CAMPOS_CONFIRMAVEIS)):
        raise ConfiguracaoInvalidaError(
            f"{caminho}: campo desconhecido '{desconhecidos[0]}' (use {', '.join(CAMPOS_CONFIRMAVEIS)})"
        )
    return {campo: valor for campo, valor in dados.items() if valor is not None}


def _com_confirmados(dados: dict, confirmados: dict) -> dict:
    """O que o `concurso.yaml` declara vence o que foi confirmado."""
    dados = dict(dados)
    for campo, valor in confirmados.items():
        if campo in _CAMPOS_DE_CORRECAO:
            correcao = dict(dados.get('correcao') or {})
            if correcao.get(campo) is None:
                correcao[campo] = valor
            dados['correcao'] = correcao
        elif dados.get(campo) is None:
            dados[campo] = valor
    return dados


def validar_dados(pasta: Path, dados: dict) -> ConcursoConfig:
    try:
        return _montar(pasta, dados)
    except (KeyError, TypeError, ValueError) as erro:
        raise ConfiguracaoInvalidaError(f'{pasta / ARQUIVO_CONFIG}: {erro}') from erro


from concursos.concurso_config_montagem import (  # noqa: E402
    _alternativas,
    _campos_obrigatorios_concurso,
    _campos_opcionais_concurso,
    _data_opcional,
    _enum,
    _montar,
    _montar_correcao,
    _montar_edital,
    _montar_folha,
    _montar_pesos,
    _montar_prova,
    _montar_resultado,
    _montar_simulado,
    _montar_variantes,
    _numero_opcional,
    _obrigatorio,
    _opcao,
    _respostas_do_yaml,
    _texto_opcional,
    _validar_faixas_disjuntas,
)
