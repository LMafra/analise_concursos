import os
from dataclasses import replace
from pathlib import Path

from concursos import doctor as diagnostico
from concursos import onboarding
from concursos.aplicacao.analise import analisar
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.projeto import diagnosticar, exigir_provas, migrar
from concursos.calibracao import Calibracao, CalibracaoError, calibrar, gravar_calibracao
from concursos.config.contexto import Contexto
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
    opcoes = configurar(opcoes, respostas)
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


def configurar(opcoes: Opcoes, respostas: onboarding.Respostas) -> Opcoes:
    """Grava as respostas do onboarding (as mesmas do `init`) e migra o layout antigo, se houver."""
    contexto = opcoes.contexto
    if respostas.calibracao is not None:
        opcoes = replace(opcoes, forcar=True)
    opcoes = replace(opcoes, contexto=onboarding.aplicar(contexto, respostas))
    if opcoes.contexto.provas.is_dir():
        opcoes = migrar(opcoes)
    onboarding.gravar(contexto, respostas)
    return opcoes


def respostas_atuais(contexto: Contexto) -> onboarding.Respostas:
    """Os padrões do `init` para este projeto, como ponto de partida do formulário."""
    return onboarding.perguntar(contexto, set(), None, {})


def pasta_no_formulario(pasta: Path, raiz: Path) -> str:
    return pasta.relative_to(raiz).as_posix() if pasta.is_relative_to(raiz) else str(pasta)


def respostas_do_formulario(
    contexto: Contexto,
    nome: str,
    provas: str,
    analises: str,
    doctor: bool,
    calibracao: Calibracao | None = None,
) -> onboarding.Respostas:
    """As respostas do formulário; pastas relativas são relativas à pasta do projeto."""
    nome = validar_nome(nome)

    def na_raiz(texto: str, padrao: Path) -> Path:
        if not texto.strip():
            return padrao
        caminho = Path(texto.strip()).expanduser()
        return caminho if caminho.is_absolute() else contexto.raiz / caminho

    return onboarding.Respostas(
        nome=nome,
        provas=na_raiz(provas, contexto.provas),
        analises=na_raiz(analises, contexto.analises),
        doctor=doctor,
        calibracao=calibracao,
    )


def validar_nome(nome: str) -> str:
    if not nome.strip():
        raise ErroDoUsuario('falta o seu nome', 'escreva o nome que vai aparecer nos relatórios')
    return nome.strip()


def calibrar_folha(folha: Path, digitadas: str) -> Calibracao:
    try:
        return calibrar(folha, digitadas)
    except CalibracaoError as erro:
        raise ErroDoUsuario(f'calibração reprovada: {erro.causa}', erro.dica) from erro


def concluir_onboarding(opcoes: Opcoes, respostas: onboarding.Respostas) -> Opcoes:
    """O onboarding do formulário: cria a pasta de provas com o LEIA-ME, se faltar, e grava."""
    if not respostas.provas.is_dir():
        onboarding.criar_pasta_de_provas(respostas.provas)
    return configurar(opcoes, respostas)


def salvar_calibracao(contexto: Contexto, folha: Path, digitadas: str) -> Path:
    """Calibra pela folha e grava o perfil no projeto; as folhas já lidas só mudam se forem relidas."""
    return gravar_calibracao(contexto.projeto, calibrar_folha(folha, digitadas))
