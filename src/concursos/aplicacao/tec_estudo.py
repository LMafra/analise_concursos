"""Explicação e questões similares dos erros do TEC via open-notebook (`/api/search/ask/simple`)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from concursos.aplicacao import pratica as pratica_app
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.projeto import pasta_do_candidato
from concursos.erros import ErroDoUsuario, avisar
from concursos.integracoes.open_notebook import (
    ClienteOpenNotebook,
    OpenNotebookIndisponivelError,
    ler_configuracao,
)
from concursos.pratica_tec import RESULTADO_ACERTO, RESULTADO_ERRO, ler_entrada, tipo_questao

logger = logging.getLogger(__name__)

BLOCO_ALTERNATIVAS = (
    'Explique por que cada alternativa errada está errada, uma por uma.'
)
PROMPT_CE = """Você explica questões de concurso (Certo/Errado).
Enunciado:
{enun}

Gabarito: {gab}
Resposta marcada: {marc}
Comentário do professor (pode estar vazio): {com}
Assunto: {ass}

Explique por que a marcada está errada (se estiver) e por que a correta está certa.
Ligue a resposta ao assunto e sugira o que revisar.
"""

PROMPT_ME = """Você explica questões de concurso (múltipla escolha).
Enunciado:
{enun}

Alternativas:
{alts}

Gabarito: {gab}
Resposta marcada: {marc}
Comentário do professor (pode estar vazio): {com}
Assunto: {ass}

{bloco}

A note deve ter uma seção por alternativa. Cubra:
1) por que a marcada está errada;
2) por que a correta está certa;
3) por que cada uma das outras alternativas está errada, com motivo específico;
4) conexão com o assunto e sugestão de revisão.
"""

PROMPT_SIMILARES = """Com base neste erro de concurso, crie 2 ou 3 questões similares no estilo da banca {banca}.
Assunto: {ass}
Matéria: {mat}
Enunciado original:
{enun}
Gabarito original: {gab}

Para múltipla escolha: 4 ou 5 alternativas e justificativa de cada uma.
Para Certo/Errado: enunciado + gabarito + justificativa.
Não substitua a repetição da original; são só para treino.
"""

PROMPT_CONFIRMACAO = """Resuma em 2–3 frases por que a resposta {gab} está correta para:
{enun}
Assunto: {ass}
"""


@dataclass
class ResultadoExplicacao:
    explicadas: int
    similares: int
    confirmacoes: int
    avisos: list[str]


def _cliente(opcoes: Opcoes) -> tuple[ClienteOpenNotebook, str]:
    cfg = ler_configuracao(opcoes.contexto.config_global)
    if not cfg.ativa:
        raise ErroDoUsuario(
            'O open-notebook não está ligado.',
            'ligue o open-notebook nas Configurações (com o consentimento) e tente de novo.',
        )
    cliente = ClienteOpenNotebook(cfg)
    try:
        modelos = cliente.listar_modelos(tipo='language')
    except OpenNotebookIndisponivelError as erro:
        raise ErroDoUsuario(
            'Não consegui falar com o open-notebook.',
            'confira se ele está aberto neste computador.',
            str(erro),
        ) from erro
    if not modelos:
        raise ErroDoUsuario(
            'Não há modelo de linguagem no open-notebook.',
            'configure um modelo na seção Avançado das Configurações.',
        )
    return cliente, str(modelos[0].get('id') or modelos[0].get('name') or '')


def _texto_alts(alts: list) -> str:
    linhas = []
    for a in alts or []:
        linhas.append(f'- {a.get("l", "?")}: {a.get("t", "")}')
    return '\n'.join(linhas) or '(sem alternativas)'


def _notebook(cliente: ClienteOpenNotebook, nome: str, descricao: str) -> dict:
    existente = cliente.buscar_notebook_por_nome(nome)
    if existente:
        return existente
    return cliente.criar_notebook(nome, descricao)


def _ja_tem_nota(cliente: ClienteOpenNotebook, notebook_id: str, titulo: str) -> bool:
    for nota in cliente.listar_notas(notebook_id):
        if (nota.get('title') or '') == titulo:
            return True
    return False


def explicar_erros_tec(opcoes: Opcoes, incluir_acertos: bool = True) -> ResultadoExplicacao:
    """Cria sources/notes de explicação e similares; exige opt-in e ação explícita (quem chama o botão)."""
    configuracao = pratica_app.exigir_configuracao_pratica(opcoes.contexto)
    pratica, avisos_entrada = ler_entrada(configuracao.entrada)
    cliente, modelo_id = _cliente(opcoes)
    candidato = configuracao.candidato or 'candidato'
    nb = _notebook(cliente, f'TEC — {candidato}', 'Erros e revisões do TEC')
    notebook_id = str(nb.get('id'))
    explicadas = similares = confirmacoes = 0
    avisos = list(avisos_entrada)
    assuntos_erro: set[str] = set()

    for item in pratica.erros:
        tipo = tipo_questao(item.get('alts'))
        from concursos.pratica_tec import resultado_questao

        resultado = resultado_questao(item.get('gab'), item.get('marc'), tipo)
        qid = item.get('id') or '?'
        ass = item.get('ass') or 'sem assunto'

        if resultado == RESULTADO_ERRO:
            titulo_source = f'Erro TEC — {qid} — {ass}'
            alts = item.get('alts') or []
            corpo = (
                f'Enunciado:\n{item.get("enun") or ""}\n\n'
                f'Alternativas:\n{_texto_alts(alts)}\n\n'
                f'Gabarito: {item.get("gab")}\nMarcada: {item.get("marc")}\n'
                f'Comentário: {item.get("com") or ""}\n'
            )
            cliente.adicionar_source_texto(notebook_id, titulo_source, corpo, embed=False)
            if tipo == 'certo_errado':
                pergunta = PROMPT_CE.format(
                    enun=item.get('enun') or '',
                    gab=item.get('gab') or '',
                    marc=item.get('marc') or '',
                    com=item.get('com') or '',
                    ass=ass,
                )
            else:
                pergunta = PROMPT_ME.format(
                    enun=item.get('enun') or '',
                    alts=_texto_alts(alts),
                    gab=item.get('gab') or '',
                    marc=item.get('marc') or '',
                    com=item.get('com') or '',
                    ass=ass,
                    bloco=BLOCO_ALTERNATIVAS,
                )
            titulo_nota = f'Explicação — {qid} — {ass}'
            if not _ja_tem_nota(cliente, notebook_id, titulo_nota):
                try:
                    resposta = cliente.perguntar(pergunta, modelo_id)
                    cliente.criar_nota(notebook_id, titulo_nota, resposta.get('answer') or '')
                    explicadas += 1
                except OpenNotebookIndisponivelError as erro:
                    avisos.append(str(erro))
                    avisar(logger, 'Não consegui gerar a explicação desta questão.', detalhe=str(erro))
            assuntos_erro.add(ass)

        elif resultado == RESULTADO_ACERTO and incluir_acertos:
            titulo = f'Confirmação — {qid} — {ass}'
            if not _ja_tem_nota(cliente, notebook_id, titulo):
                try:
                    resposta = cliente.perguntar(
                        PROMPT_CONFIRMACAO.format(
                            gab=item.get('gab') or '', enun=item.get('enun') or '', ass=ass
                        ),
                        modelo_id,
                    )
                    cliente.criar_nota(notebook_id, titulo, resposta.get('answer') or '')
                    confirmacoes += 1
                except OpenNotebookIndisponivelError as erro:
                    avisos.append(str(erro))

    for ass in sorted(assuntos_erro):
        titulo = f'Similares — {ass}'
        if _ja_tem_nota(cliente, notebook_id, titulo):
            continue
        amostra = next((i for i in pratica.erros if (i.get('ass') or '') == ass), None)
        if not amostra:
            continue
        pergunta = PROMPT_SIMILARES.format(
            banca=amostra.get('banca') or 'da banca',
            ass=ass,
            mat=amostra.get('mat') or '',
            enun=amostra.get('enun') or '',
            gab=amostra.get('gab') or '',
        )
        try:
            resposta = cliente.perguntar(pergunta, modelo_id)
            cliente.criar_nota(notebook_id, titulo, resposta.get('answer') or '')
            similares += 1
        except OpenNotebookIndisponivelError as erro:
            avisos.append(str(erro))

    from concursos.analytics.tec_estatisticas import markdown_resumo

    pasta_cand = pasta_do_candidato(opcoes.contexto, candidato)
    resumo_md = markdown_resumo(pasta_cand)
    titulo_resumo = f'Resumo prática TEC — {candidato}'
    if not _ja_tem_nota(cliente, notebook_id, titulo_resumo):
        cliente.criar_nota(notebook_id, titulo_resumo, resumo_md)
    else:
        for nota in cliente.listar_notas(notebook_id):
            if (nota.get('title') or '') == titulo_resumo and nota.get('id'):
                cliente.atualizar_nota(str(nota['id']), resumo_md)
                break

    opcoes.saida(
        f'Explicações: {explicadas}; similares: {similares}; confirmações: {confirmacoes}.'
    )
    return ResultadoExplicacao(explicadas, similares, confirmacoes, avisos)
