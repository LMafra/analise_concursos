import os
from dataclasses import replace

from concursos import doctor as diagnostico
from concursos import onboarding
from concursos.aplicacao.analise import analisar
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.projeto import diagnosticar, exigir_provas, migrar
from concursos.calibracao import CalibracaoError
from concursos.erros import ErroDoUsuario
from concursos.status import listar_concursos


def executar_onboarding(
    opcoes: Opcoes, doctor: bool | None = None, extras: dict[str, str] | None = None
) -> int:
    """As perguntas do onboarding (por `opcoes.interacao`, ou os padrões sem ela), a gravação e a análise."""
    contexto = opcoes.contexto
    if opcoes.interacao is None:
        exigir_provas(contexto.provas)
    ambiente = {**os.environ, **(extras or {})}
    if doctor is not None:
        ambiente[onboarding.VARIAVEL_DOCTOR] = 's' if doctor else 'n'
    try:
        respostas = onboarding.perguntar(contexto, set(opcoes.fornecidos), opcoes.interacao, ambiente)
    except onboarding.OnboardingCanceladoError:
        raise ErroDoUsuario(
            'onboarding cancelado; nada foi gravado', 'rode `concurso-analise init` quando quiser'
        ) from None
    except CalibracaoError as erro:
        raise ErroDoUsuario(f'calibração reprovada, nada foi gravado: {erro.causa}', erro.dica) from erro
    except onboarding.ProvedorInvalidoError as erro:
        raise ErroDoUsuario(
            f'{erro}; nada foi gravado', f'corrija {onboarding.VARIAVEL_LLM} ou apague a variável'
        ) from erro
    if respostas.calibracao is not None:
        opcoes = replace(opcoes, forcar=True)
    opcoes = replace(opcoes, contexto=onboarding.aplicar(contexto, respostas))
    if opcoes.contexto.provas.is_dir():
        opcoes = migrar(opcoes)
    onboarding.gravar(contexto, respostas)
    contexto = opcoes.contexto
    if respostas.doctor:
        opcoes.saida(diagnostico.formatar(diagnosticar(contexto)))
    if contexto.provas.is_dir() and not listar_concursos(contexto.provas):
        opcoes.saida(
            f'nenhum concurso em {contexto.provas} ainda; siga o {onboarding.ARQUIVO_LEIA_ME} '
            'e rode `concurso-analise` de novo'
        )
        return 0
    return analisar(opcoes)
