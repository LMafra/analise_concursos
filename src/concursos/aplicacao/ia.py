from dataclasses import dataclass

from concursos.config.contexto import Contexto
from concursos.erros import ErroDoUsuario
from concursos.llm import (
    NENHUM,
    PROVEDORES,
    gravar_configuracao,
    guardar_chave,
    ler_configuracao,
    obter_chave,
)
from concursos.onboarding import o_que_vai_para


@dataclass(frozen=True)
class EstadoIa:
    """A camada de IA da leitura de editais; `chave_em` diz onde a chave está, nunca a chave."""

    ligada: bool
    provedor: str | None = None
    variavel_chave: str | None = None
    chave_em: str | None = None


def provedores() -> list[str]:
    return list(PROVEDORES)


def aviso(provedor: str) -> str:
    return o_que_vai_para(provedor)


def estado_da_ia(contexto: Contexto) -> EstadoIa:
    configuracao = ler_configuracao(contexto.config_global)
    if configuracao is None or not configuracao.consentimento:
        return EstadoIa(ligada=False)
    encontrada = obter_chave(configuracao, contexto.home)
    return EstadoIa(
        ligada=True,
        provedor=configuracao.provedor,
        variavel_chave=configuracao.variavel_chave,
        chave_em=encontrada[1] if encontrada else None,
    )


def ligar_ia(contexto: Contexto, provedor: str, chave: str | None) -> str | None:
    """Grava o provedor com o consentimento; a chave vai para o keyring (ou o `.env` 600), nunca para TOML.

    Devolve onde a chave ficou, quando uma chave foi dada."""
    if provedor not in PROVEDORES:
        raise ErroDoUsuario(
            f'Não conheço o serviço de inteligência artificial “{provedor}”.',
            f'use um destes: {", ".join(PROVEDORES)}.',
        )
    gravar_configuracao(contexto.config_global, provedor)
    variavel = PROVEDORES[provedor].variavel_chave
    if variavel is None or not (chave or '').strip():
        return None
    return guardar_chave(variavel, chave.strip(), contexto.home)


def desligar_ia(contexto: Contexto) -> None:
    gravar_configuracao(contexto.config_global, NENHUM)
