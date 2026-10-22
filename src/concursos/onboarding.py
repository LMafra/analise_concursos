import logging
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path

from concursos.assistente import InteracaoConsole
from concursos.candidatos import PASTA_PERFIS_GLOBAIS, candidatos_existentes, gravar_perfil_global, slug
from concursos.config.contexto import Contexto, gravar_secao, ler_toml
from concursos.migracao import candidato_padrao

logger = logging.getLogger(__name__)

VARIAVEL_DOCTOR = 'CONCURSO_DOCTOR'
ARQUIVO_LEIA_ME = 'LEIA-ME.txt'
TOTAL_PERGUNTAS = 4
_SIM = {'s', 'sim', 'y', 'yes', '1', 'true'}
_LEIA_ME = """\
Coloque aqui uma pasta por concurso, por exemplo provas/meu_concurso/, com:

- o gabarito oficial (PDF ou texto);
- o caderno de prova (PDF), se quiser os tópicos por questão;
- o edital (PDF), para as regras de correção, os cortes e o conteúdo programático;
- as suas respostas em candidatos/<seu_nome>/: respostas.txt, respostas.csv
  (colunas questao,alternativa) ou a foto/PDF da folha de respostas.

Depois rode `concurso-analise add provas/meu_concurso` para gerar o concurso.yaml
e `concurso-analise` para analisar.
"""


class OnboardingCanceladoError(Exception):
    pass


@dataclass(frozen=True)
class Respostas:
    nome: str | None
    provas: Path
    analises: Path
    doctor: bool


def precisa_de_onboarding(contexto: Contexto) -> bool:
    return not contexto.config_projeto.exists()


def interativo(sim: bool) -> bool:
    return not sim and not os.environ.get('CI') and sys.stdin.isatty()


def perguntar(
    contexto: Contexto, fornecidos: set[str], interacao: InteracaoConsole | None, ambiente=os.environ
) -> Respostas:
    """Pergunta só o que não veio por flag ou variável; sem `interacao`, fica com os padrões."""
    padrao = Respostas(
        nome=_nome_atual(contexto) if 'nome' not in fornecidos else contexto.candidato,
        provas=contexto.provas,
        analises=contexto.analises,
        doctor=ambiente.get(VARIAVEL_DOCTOR, 's').strip().lower() in _SIM,
    )
    if 'doctor' not in fornecidos and VARIAVEL_DOCTOR in ambiente:
        fornecidos = {*fornecidos, 'doctor'}
    if interacao is None:
        logger.info(
            'onboarding sem terminal: usando os padrões (nome %s, provas %s, análises %s, doctor %s)',
            padrao.nome or '(nenhum)',
            padrao.provas,
            padrao.analises,
            'sim' if padrao.doctor else 'não',
        )
        return padrao
    respostas = padrao
    if 'nome' not in fornecidos:
        respostas = replace(respostas, nome=_texto(interacao, 1, 'Seu nome', padrao.nome))
    if 'provas' not in fornecidos:
        provas = _texto(interacao, 2, 'Pasta de provas', _relativo(padrao.provas, contexto.raiz))
        respostas = replace(respostas, provas=_absoluto(provas, contexto.raiz))
    if not respostas.provas.is_dir() and interacao.confirmar(
        f'A pasta {respostas.provas} não existe. Criar com um {ARQUIVO_LEIA_ME} explicando o que pôr nela?',
        padrao=True,
    ):
        criar_pasta_de_provas(respostas.provas)
        interacao.mostrar(f'Criada {respostas.provas}; leia o {ARQUIVO_LEIA_ME} dentro dela.')
    if 'analises' not in fornecidos:
        analises = _texto(interacao, 3, 'Pasta de análises', _relativo(padrao.analises, contexto.raiz))
        respostas = replace(respostas, analises=_absoluto(analises, contexto.raiz))
    if 'doctor' not in fornecidos:
        resposta = _texto(interacao, 4, 'Conferir o ambiente com o doctor no fim? (s/n)', 's')
        respostas = replace(respostas, doctor=resposta.lower() in _SIM)
    interacao.mostrar(_resumo(contexto, respostas))
    if not interacao.confirmar('Gravar?', padrao=True):
        raise OnboardingCanceladoError
    return respostas


def aplicar(contexto: Contexto, respostas: Respostas) -> Contexto:
    return replace(
        contexto,
        provas=respostas.provas,
        analises=respostas.analises,
        candidato=slug(respostas.nome) if respostas.nome else None,
    )


def gravar(contexto: Contexto, respostas: Respostas) -> None:
    """Configuração global, perfil do candidato e configuração do projeto."""
    pastas = {
        'provas': _relativo(respostas.provas, contexto.raiz),
        'analises': _relativo(respostas.analises, contexto.raiz),
    }
    gravar_secao(contexto.config_projeto, 'pastas', pastas)
    if respostas.nome:
        candidato = slug(respostas.nome)
        gravar_perfil_global(contexto.home, respostas.nome, atualizar=True)
        conhecidos = ler_toml(contexto.config_global).get('candidatos', {}).get('conhecidos', [])
        gravar_secao(contexto.config_global, 'candidatos', {'conhecidos': sorted({*conhecidos, candidato})})
        gravar_secao(contexto.config_projeto, 'candidato', {'ultimo': candidato})


def criar_pasta_de_provas(pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / ARQUIVO_LEIA_ME).write_text(_LEIA_ME, encoding='utf-8')


def _nome_atual(contexto: Contexto) -> str | None:
    """O nome do candidato atual; sem ele, o único candidato das provas ou, sem nenhum, o login."""
    candidato = contexto.candidato
    if candidato is None:
        existentes = candidatos_existentes(contexto.provas) if contexto.provas.is_dir() else []
        if len(existentes) > 1:
            return None
        candidato = existentes[0] if existentes else candidato_padrao()
    perfil = ler_toml(contexto.home / PASTA_PERFIS_GLOBAIS / f'{candidato}.toml')
    return perfil.get('nome') or candidato


def _texto(interacao: InteracaoConsole, numero: int, pergunta: str, padrao: str | None) -> str:
    while not (resposta := interacao.perguntar(f'[{numero}/{TOTAL_PERGUNTAS}] {pergunta}', padrao)):
        interacao.mostrar('Resposta obrigatória.')
    return resposta


def _resumo(contexto: Contexto, respostas: Respostas) -> str:
    return '\n'.join(
        [
            'Vou gravar:',
            f'  candidato: {respostas.nome or "(escolhido a cada análise)"}',
            f'  pasta de provas: {respostas.provas}',
            f'  pasta de análises: {respostas.analises}',
            f'  em {contexto.config_projeto} e {contexto.config_global}',
        ]
    )


def _relativo(pasta: Path, raiz: Path) -> str:
    return pasta.relative_to(raiz).as_posix() if pasta.is_relative_to(raiz) else str(pasta)


def _absoluto(texto: str, raiz: Path) -> Path:
    caminho = Path(texto).expanduser()
    return caminho if caminho.is_absolute() else raiz / caminho
