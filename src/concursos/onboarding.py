import logging
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path

from concursos.assistente import InteracaoConsole
from concursos.calibracao import QUESTOES_CALIBRACAO, Calibracao, CalibracaoError, calibrar, gravar_calibracao
from concursos.candidatos import PASTA_PERFIS_GLOBAIS, candidatos_existentes, gravar_perfil_global, slug
from concursos.config.contexto import Contexto, gravar_secao, ler_toml
from concursos.erros import linhas_do_erro
from concursos.llm import (
    ARQUIVO_ENV,
    NENHUM,
    PROVEDORES,
    gravar_configuracao,
    guardar_chave,
    ler_configuracao,
    obter_chave,
)
from concursos.migracao import candidato_padrao

logger = logging.getLogger(__name__)

VARIAVEL_DOCTOR = 'CONCURSO_DOCTOR'
VARIAVEL_LLM = 'CONCURSO_LLM'
VARIAVEL_CALIBRAR_FOLHA = 'CONCURSO_CALIBRAR_FOLHA'
VARIAVEL_CALIBRAR_RESPOSTAS = 'CONCURSO_CALIBRAR_RESPOSTAS'
ARQUIVO_LEIA_ME = 'LEIA-ME.txt'
TOTAL_PERGUNTAS = 6
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


class ProvedorInvalidoError(ValueError):
    pass


@dataclass(frozen=True)
class Respostas:
    nome: str | None
    provas: Path
    analises: Path
    doctor: bool
    calibracao: Calibracao | None = None
    llm: str | None = None


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
    folha, digitadas = ambiente.get(VARIAVEL_CALIBRAR_FOLHA), ambiente.get(VARIAVEL_CALIBRAR_RESPOSTAS)
    if folha and digitadas:
        padrao = replace(padrao, calibracao=calibrar(_absoluto(folha, contexto.raiz), digitadas))
        fornecidos = {*fornecidos, 'calibracao'}
    if provedor := ambiente.get(VARIAVEL_LLM):
        padrao = replace(padrao, llm=_provedor_valido(provedor))
        fornecidos = {*fornecidos, 'llm'}
        if padrao.llm != NENHUM:
            logger.warning('%s: %s', VARIAVEL_LLM, o_que_vai_para(padrao.llm))
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
    if 'calibracao' not in fornecidos:
        respostas = replace(respostas, calibracao=_perguntar_calibracao(interacao, contexto.raiz))
    if 'llm' not in fornecidos:
        respostas = replace(respostas, llm=_perguntar_llm(interacao, contexto))
    if 'doctor' not in fornecidos:
        resposta = _texto(interacao, 6, 'Conferir o ambiente com o doctor no fim? (s/n)', 's')
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
    if respostas.calibracao is not None:
        gravar_calibracao(contexto.projeto, respostas.calibracao)
    if respostas.llm is not None and _mudou_o_llm(contexto, respostas.llm):
        gravar_configuracao(contexto.config_global, respostas.llm)
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


def _perguntar_calibracao(interacao: InteracaoConsole, raiz: Path) -> Calibracao | None:
    while True:
        folha = interacao.perguntar(
            f'[4/{TOTAL_PERGUNTAS}] Folha preenchida para calibrar a leitura (Enter para pular)'
        )
        if not folha:
            return None
        caminho = _absoluto(folha, raiz)
        if not caminho.is_file():
            interacao.mostrar(f'erro: {caminho} não encontrado')
            continue
        digitadas = interacao.perguntar(
            f'      Respostas das {QUESTOES_CALIBRACAO} primeiras questões (ex.: ABCD-, com - para branco)'
        )
        try:
            calibracao = calibrar(caminho, digitadas or '')
        except CalibracaoError as erro:
            interacao.mostrar('\n'.join(linhas_do_erro(erro)))
            continue
        interacao.mostrar(
            f'Calibração aprovada: alternativas {calibracao.perfil.alternativas}, '
            f'limiar de marcação {calibracao.perfil.limiar_marcada}'
        )
        return calibracao


def _perguntar_llm(interacao: InteracaoConsole, contexto: Contexto) -> str:
    atual = ler_configuracao(contexto.config_global)
    opcoes = '/'.join([NENHUM, *PROVEDORES])
    while True:
        escolha = interacao.perguntar(
            f'[5/{TOTAL_PERGUNTAS}] LLM para ler editais de bancas desconhecidas ({opcoes})',
            atual.provedor if atual else NENHUM,
        )
        escolha = (escolha or NENHUM).strip().lower()
        if escolha == NENHUM or escolha in PROVEDORES:
            break
        interacao.mostrar(f'Opção inválida: use {opcoes}.')
    if escolha == NENHUM:
        return NENHUM
    if not (atual and atual.provedor == escolha and atual.consentimento):
        interacao.mostrar(o_que_vai_para(escolha))
        if not interacao.confirmar('Concorda?'):
            return NENHUM
    provedor = PROVEDORES[escolha]
    if provedor.variavel_chave is None:
        return escolha
    configuracao = ler_configuracao(contexto.config_global)
    variavel = provedor.variavel_chave
    encontrada = (
        obter_chave(configuracao, contexto.home)
        if configuracao and configuracao.provedor == escolha
        else None
    )
    encontrada = encontrada or (os.environ.get(variavel) and (os.environ[variavel], f'variável {variavel}'))
    if not encontrada:
        interacao.mostrar(
            f'Defina a variável {variavel} antes de analisar (export {variavel}=...); sem ela, o LLM fica desligado.'
        )
    elif encontrada[1] == f'variável {variavel}' and interacao.confirmar(
        f'Guardar a chave de {variavel} no keyring, para não depender da variável? Sem keyring, ela fica '
        f'em texto plano em {contexto.home / ARQUIVO_ENV} (permissão 600)'
    ):
        interacao.mostrar(f'Chave guardada em {guardar_chave(variavel, encontrada[0], contexto.home)}.')
    return escolha


def o_que_vai_para(provedor: str) -> str:
    return (
        f'Só o texto do edital e dos anexos vai para {provedor}; respostas, folhas, notas e inscrição não '
        'saem do computador. Sem a IA, a leitura do edital continua só no computador.'
    )


def _provedor_valido(provedor: str) -> str:
    provedor = provedor.strip().lower()
    if provedor != NENHUM and provedor not in PROVEDORES:
        raise ProvedorInvalidoError(
            f'{VARIAVEL_LLM}: provedor {provedor!r} inválido (use {", ".join([NENHUM, *PROVEDORES])})'
        )
    return provedor


def _mudou_o_llm(contexto: Contexto, provedor: str) -> bool:
    atual = ler_configuracao(contexto.config_global)
    if atual is None:
        return provedor != NENHUM
    return not (atual.provedor == provedor and atual.consentimento)


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
            f'  LLM: {respostas.llm or "como está"}',
            f'  leitura da folha: {"calibrada" if respostas.calibracao else "detecção automática ou perfil da banca"}',
            f'  em {contexto.config_projeto} e {contexto.config_global}',
        ]
    )


def _relativo(pasta: Path, raiz: Path) -> str:
    return pasta.relative_to(raiz).as_posix() if pasta.is_relative_to(raiz) else str(pasta)


def _absoluto(texto: str, raiz: Path) -> Path:
    caminho = Path(texto).expanduser()
    return caminho if caminho.is_absolute() else raiz / caminho
