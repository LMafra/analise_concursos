from dataclasses import dataclass
from pathlib import Path

import tomli_w

from concursos.analytics.dashboard_fontes import MetasDashboard, metas_do_toml, metas_padrao
from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.config.contexto import Contexto, gravar_secao, ler_toml
from concursos.configuracao import validar_analise
from concursos.erros import ErroDoUsuario
from concursos.modelo import TemaGui

SECAO_GUI = 'gui'
SECAO_DASHBOARD = 'dashboard'


@dataclass(frozen=True)
class PreferenciasAnalise:
    limiar_confianca: float = 0.75
    limiar_topico_baixo: float = 0.6
    concurso_alvo: str | None = None


def ler_analise(contexto: Contexto) -> PreferenciasAnalise:
    try:
        configuracao = validar_analise(
            ler_toml(contexto.config_projeto).get('analise', {}), contexto.config_projeto
        )
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(
            'Não consegui ler as preferências da análise deste projeto.',
            'salve as preferências de novo em Configurações.',
            f'{erro} (seção [analise] de {contexto.config_projeto})',
        ) from erro
    return PreferenciasAnalise(
        configuracao.limiar_confianca, configuracao.limiar_topico_baixo, configuracao.concurso_alvo
    )


def gravar_analise(contexto: Contexto, preferencias: PreferenciasAnalise) -> None:
    """Grava os três campos em `[analise]` do projeto; as outras chaves e seções ficam como estavam.

    O TOML não tem nulo: sem concurso-alvo, a chave sai do arquivo.
    """
    dados = ler_toml(contexto.config_projeto)
    analise = {
        **dados.get('analise', {}),
        'limiar_confianca': preferencias.limiar_confianca,
        'limiar_topico_baixo': preferencias.limiar_topico_baixo,
        'concurso_alvo': preferencias.concurso_alvo,
    }
    if analise['concurso_alvo'] is None:
        del analise['concurso_alvo']
    try:
        validar_analise(analise, contexto.config_projeto)
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(
            'Alguma preferência ficou fora do esperado; nada foi gravado.',
            'use valores entre 0 e 1 e escolha um concurso já cadastrado.',
            str(erro),
        ) from erro
    dados['analise'] = analise
    contexto.config_projeto.parent.mkdir(parents=True, exist_ok=True)
    contexto.config_projeto.write_text(tomli_w.dumps(dados), encoding='utf-8')


def ultimo_projeto(config_global: Path) -> Path | None:
    valor = ler_toml(config_global).get(SECAO_GUI, {}).get('ultimo_projeto')
    return Path(valor) if isinstance(valor, str) and valor else None


def lembrar_projeto(config_global: Path, projeto: Path) -> None:
    if ultimo_projeto(config_global) != projeto:
        gravar_secao(config_global, SECAO_GUI, {'ultimo_projeto': projeto.as_posix()})


def aviso_webview2_dispensado(config_global: Path) -> bool:
    return ler_toml(config_global).get(SECAO_GUI, {}).get('aviso_webview2_dispensado') is True


def dispensar_aviso_webview2(config_global: Path) -> None:
    gravar_secao(config_global, SECAO_GUI, {'aviso_webview2_dispensado': True})


def tema_da_gui(config_global: Path) -> TemaGui:
    try:
        return TemaGui(ler_toml(config_global).get(SECAO_GUI, {}).get('tema', TemaGui.SISTEMA.value))
    except ValueError:
        return TemaGui.SISTEMA


def gravar_tema_da_gui(config_global: Path, tema: TemaGui) -> None:
    gravar_secao(config_global, SECAO_GUI, {'tema': tema.value})


def ler_dashboard(contexto: Contexto) -> MetasDashboard:
    if not contexto.config_projeto.is_file():
        return metas_padrao()
    return metas_do_toml(ler_toml(contexto.config_projeto))


def gravar_dashboard(contexto: Contexto, metas: MetasDashboard) -> None:
    """Grava `[dashboard]` (metas de selo + banca alvo); demais seções intactas."""
    if not (0 < metas.tec_media <= metas.tec_alta <= 1):
        raise ErroDoUsuario(
            'As metas do TEC precisam estar entre 0 e 1, com a alta ≥ média.',
            'ajuste os controles em Configurações.',
        )
    if not (0 < metas.simulado_media <= metas.simulado_alta <= 1):
        raise ErroDoUsuario(
            'As metas de simulado precisam estar entre 0 e 1, com a alta ≥ média.',
            'ajuste os controles em Configurações.',
        )
    if metas.amostra_minima < 1:
        raise ErroDoUsuario(
            'A amostra mínima por assunto precisa ser pelo menos 1.',
            'use um número inteiro positivo.',
        )
    dados = ler_toml(contexto.config_projeto) if contexto.config_projeto.is_file() else {}
    dados[SECAO_DASHBOARD] = {
        'tec_meta_alta': metas.tec_alta,
        'tec_meta_media': metas.tec_media,
        'simulado_meta_alta': metas.simulado_alta,
        'simulado_meta_media': metas.simulado_media,
        'amostra_minima_assunto': metas.amostra_minima,
        'banca_alvo': metas.banca_alvo,
    }
    if not metas.banca_alvo:
        del dados[SECAO_DASHBOARD]['banca_alvo']
    contexto.config_projeto.parent.mkdir(parents=True, exist_ok=True)
    contexto.config_projeto.write_text(tomli_w.dumps(dados), encoding='utf-8')
