import csv
from pathlib import Path
from typing import TYPE_CHECKING

from concursos.assistente import Interacao
from concursos.edital import Edital
from concursos.modelo import ModoCaderno
from concursos.pratica.interno import TOTAIS
from concursos.pratica.tipos import Escolhas, Pendencia
from concursos.topicos import NAO_MAPEADO, SCORE_BAIXO, chave_de_palavras, palavras_chave, sugerir_topicos

if TYPE_CHECKING:
    from concursos.analytics.dicionario_topicos import Dicionario

NENHUM = 'nenhum'
OPCAO_NENHUM = 'não pertence a nenhum tópico'
OPCAO_DEPOIS = 'decidir depois'
OPCOES_MODO = {'registrar tudo': ModoCaderno.TUDO, 'só acompanhar daqui': ModoCaderno.DAQUI}
MAXIMO_OPCOES = 30


def _topicos(edital: Edital) -> list[tuple[str, str]]:
    return [(d.nome, t.nome) for c in edital.conhecimentos for d in c.disciplinas for t in d.topicos]


def _da_disciplina(edital: Edital, disciplina: str | None) -> list[str]:
    todos = _topicos(edital)
    if disciplina:
        chave = palavras_chave(disciplina)
        mesmos = [t for d, t in todos if (p := palavras_chave(d)) and chave and (p <= chave or chave <= p)]
        if mesmos:
            return list(dict.fromkeys(mesmos))
    return list(dict.fromkeys(t for _, t in todos)) if len(todos) <= MAXIMO_OPCOES else []


def _aliases_exatos(edital: Edital, abertos: list[str], escolhas: Escolhas) -> list[str]:
    exatos = {chave_de_palavras(t): t for _, t in _topicos(edital)}
    restantes = list(abertos)
    for assunto in list(restantes):
        if (topico := exatos.get(chave_de_palavras(assunto))) is not None:
            escolhas.aliases[assunto] = topico
            restantes.remove(assunto)
    return restantes


def _sugestoes_calculadas(
    edital: Edital,
    abertos: list[str],
    assuntos: dict[str, str | None],
    dicionario: 'Dicionario | None',
):
    textos_abertos = dict(enumerate(abertos))
    disciplinas_abertas = {i: assuntos[a] for i, a in enumerate(abertos) if assuntos[a]}
    if dicionario is not None:
        from concursos.analytics.dicionario_topicos import sugerir_com_dicionario

        return sugerir_com_dicionario(
            edital, textos_abertos, disciplinas_abertas, dicionario, sugerir_topicos
        )
    return sugerir_topicos(edital, textos_abertos, disciplinas_abertas)


def _sugestao_assunto(
    assunto: str,
    indice: int,
    sugeridos: dict,
    calculadas,
) -> tuple[str | None, float]:
    if assunto in sugeridos:
        return sugeridos[assunto], 1.0
    calculada = calculadas[indice]
    valida = calculada.topico != NAO_MAPEADO and calculada.score >= SCORE_BAIXO
    return (calculada.topico if valida else None), calculada.score


def _opcoes_assunto(edital: Edital, disciplina: str | None, sugeridos: dict, assunto: str, sugestao):
    opcao_sugerida = OPCAO_NENHUM if assunto in sugeridos and sugestao is None else sugestao
    return list(
        dict.fromkeys(
            [
                *filter(None, [opcao_sugerida]),
                *_da_disciplina(edital, disciplina),
                OPCAO_NENHUM,
                OPCAO_DEPOIS,
            ]
        )
    )


def _opcao_padrao_assunto(assunto: str, sugeridos: dict, sugestao) -> str:
    opcao_sugerida = OPCAO_NENHUM if assunto in sugeridos and sugestao is None else sugestao
    return opcao_sugerida or OPCAO_DEPOIS


def _perguntar_assunto(
    interacao: Interacao,
    assunto: str,
    disciplina: str | None,
    opcoes: list[str],
    padrao: str,
) -> str:
    de = f' ({disciplina})' if disciplina else ''
    return interacao.escolher(
        f'Assunto do TEC "{assunto}"{de}: qual tópico do edital?',
        opcoes,
        padrao,
    )


def _gravar_escolha_assunto(escolhas: Escolhas, assunto: str, escolha: str) -> bool:
    if escolha == OPCAO_DEPOIS:
        return False
    escolhas.aliases[assunto] = None if escolha == OPCAO_NENHUM else escolha
    return True


def resolver_assuntos(
    assuntos: dict[str, str | None],
    edital: Edital,
    escolhas: Escolhas,
    sugeridos: dict,
    revisados: dict[str, str | None],
    interacao: Interacao | None,
    dicionario: 'Dicionario | None' = None,
) -> list[Pendencia]:
    """Grava em `escolhas.aliases` cada assunto decidido; devolve os que ficaram para a revisão."""
    escolhas.aliases.update(revisados)
    abertos = _aliases_exatos(edital, [a for a in assuntos if a not in escolhas.aliases], escolhas)
    calculadas = _sugestoes_calculadas(edital, abertos, assuntos, dicionario)
    pendentes = []
    for i, assunto in enumerate(abertos):
        sugestao, score = _sugestao_assunto(assunto, i, sugeridos, calculadas)
        if interacao is not None:
            opcoes = _opcoes_assunto(edital, assuntos[assunto], sugeridos, assunto, sugestao)
            padrao = _opcao_padrao_assunto(assunto, sugeridos, sugestao)
            escolha = _perguntar_assunto(interacao, assunto, assuntos[assunto], opcoes, padrao)
            if _gravar_escolha_assunto(escolhas, assunto, escolha):
                continue
        pendentes.append(Pendencia(assunto, assuntos[assunto], sugestao, round(score, 3)))
    return pendentes


def ler_revisao(caminho: Path) -> dict[str, str | None]:
    if not caminho.exists():
        return {}
    with caminho.open(encoding='utf-8', newline='') as arquivo:
        linhas = list(csv.DictReader(arquivo))
    return {
        linha['assunto']: None if linha['topico'].strip() == NENHUM else linha['topico'].strip()
        for linha in linhas
        if (linha.get('topico') or '').strip()
    }


def _modo_caderno(c: dict, sugerido: dict, interacao: Interacao | None) -> ModoCaderno:
    if sugerido.get('modo') in {m.value for m in ModoCaderno}:
        return ModoCaderno(sugerido['modo'])
    if interacao is None:
        return ModoCaderno.TUDO
    totais = ', '.join(f'{c.get(t, 0)} {t}' for t in TOTAIS)
    nome = next(k for k, v in OPCOES_MODO.items() if v == ModoCaderno.TUDO)
    return OPCOES_MODO[
        interacao.escolher(
            f'Caderno do TEC "{c.get("cad") or c["id"]}" ({totais}): registrar tudo ou só daqui em diante?',
            list(OPCOES_MODO),
            nome,
        )
    ]


def _base_caderno(modo: ModoCaderno, sugerido: dict, c: dict) -> dict:
    if modo == ModoCaderno.TUDO:
        return dict.fromkeys(TOTAIS, 0)
    return {t: int((sugerido.get('base') or c).get(t, 0) or 0) for t in TOTAIS}


def resolver_cadernos(
    cadernos: list[dict], escolhas: Escolhas, estado: dict, interacao: Interacao | None
) -> None:
    do_estado = estado.get('cadernos') or {}
    for c in cadernos:
        if c['id'] in escolhas.cadernos:
            continue
        sugerido = do_estado.get(c['id']) or {}
        modo = _modo_caderno(c, sugerido, interacao)
        escolhas.cadernos[c['id']] = {'modo': modo.value, 'base': _base_caderno(modo, sugerido, c)}
