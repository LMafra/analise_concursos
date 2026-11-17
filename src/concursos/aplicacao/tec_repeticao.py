"""Repetição local das questões erradas do TEC (gabarito oculto até responder)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from concursos.aplicacao import pratica as pratica_app
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.projeto import pasta_do_candidato
from concursos.arquivos import gravar_se_mudou
from concursos.erros import ErroDoUsuario
from concursos.pratica_tec import (
    ARQUIVO_RESPOSTAS,
    ARQUIVO_TENTATIVAS,
    COLUNAS_TENTATIVAS,
    PASTA_PRATICA,
    RESULTADO_ERRO,
    resultado_questao,
    tipo_questao,
)


@dataclass(frozen=True)
class QuestaoParaRepetir:
    id: str
    enun: str
    alts: list[dict]
    gab: str
    marc: str
    mat: str
    ass: str
    tipo: str


def _pasta_pratica(opcoes: Opcoes, candidato: str | None = None) -> Path:
    configuracao = pratica_app.exigir_configuracao_pratica(opcoes.contexto)
    nome = candidato or configuracao.candidato
    if not nome:
        raise ErroDoUsuario(
            'Não sei qual candidato usar na prática.',
            'indique o candidato ou configure [pratica] candidato.',
        )
    return pasta_do_candidato(opcoes.contexto, nome) / PASTA_PRATICA


def _ler_itens_completos(pasta: Path) -> list[dict]:
    """Reconstrói enunciado/alts a partir do último import mesclado: usa erros_tec só para ids e
    busca o JSON de entrada quando possível; fallback: só ids de tec_respostas.csv."""
    respostas = pasta / ARQUIVO_RESPOSTAS
    if not respostas.is_file():
        raise ErroDoUsuario(
            'Ainda não há respostas importadas do TEC.',
            'importe o JSON da captura (Exportar todas as respostas ou apenas erros) e rode a análise.',
        )
    with respostas.open(encoding='utf-8', newline='') as arquivo:
        return list(csv.DictReader(arquivo))


def listar_erros(
    opcoes: Opcoes,
    assunto: str | None = None,
    itens_completos: list[dict] | None = None,
) -> list[QuestaoParaRepetir]:
    """Lista questões com resultado=erro. `itens_completos` traz enun/alts (da prática mesclada)."""
    pasta = _pasta_pratica(opcoes)
    linhas = _ler_itens_completos(pasta)
    erros = [l for l in linhas if l.get('resultado') == RESULTADO_ERRO]
    if assunto:
        erros = [l for l in erros if (l.get('ass') or '') == assunto]
    por_id = {i.get('id'): i for i in (itens_completos or []) if i.get('id')}
    saida: list[QuestaoParaRepetir] = []
    for linha in erros:
        completo = por_id.get(linha['id'], {})
        alts = completo.get('alts') or []
        tipo = linha.get('tipo_questao') or tipo_questao(alts)
        saida.append(
            QuestaoParaRepetir(
                id=linha['id'],
                enun=completo.get('enun') or '(enunciado só no JSON importado; reimporte a captura)',
                alts=alts if isinstance(alts, list) else [],
                gab=linha.get('gab') or completo.get('gab') or '',
                marc=linha.get('marc') or '',
                mat=linha.get('mat') or '',
                ass=linha.get('ass') or '',
                tipo=tipo,
            )
        )
    return saida


def carregar_erros_da_pratica(opcoes: Opcoes, assunto: str | None = None) -> list[QuestaoParaRepetir]:
    """Carrega erros com enunciado/alts a partir da pasta de entrada do TEC (última mescla)."""
    from concursos.pratica_tec import ler_entrada

    configuracao = pratica_app.exigir_configuracao_pratica(opcoes.contexto)
    pratica, _avisos = ler_entrada(configuracao.entrada)
    return listar_erros(opcoes, assunto, pratica.erros)


def registrar_tentativa(
    opcoes: Opcoes, id_questao: str, resposta: str, gab: str, tipo: str | None = None
) -> str:
    """Compara a resposta com o gabarito e acrescenta uma linha em tec_tentativas.csv."""
    pasta = _pasta_pratica(opcoes)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / ARQUIVO_TENTATIVAS
    resultado = resultado_questao(gab, resposta, tipo or tipo_questao(None))
    linhas: list[dict] = []
    if caminho.is_file():
        with caminho.open(encoding='utf-8', newline='') as arquivo:
            linhas = list(csv.DictReader(arquivo))
    linhas.append(
        {
            'id': id_questao,
            'data': datetime.now().astimezone().isoformat(timespec='seconds'),
            'resposta': resposta,
            'resultado': resultado,
        }
    )
    buf = __import__('io').StringIO()
    escritor = csv.DictWriter(buf, fieldnames=COLUNAS_TENTATIVAS, lineterminator='\n')
    escritor.writeheader()
    escritor.writerows(linhas)
    gravar_se_mudou(caminho, buf.getvalue())
    return resultado


def repetir_interativo(opcoes: Opcoes, assunto: str | None = None) -> int:
    """CLI: pergunta cada erro, compara e grava tentativas. Sem TTY, só lista."""
    questoes = carregar_erros_da_pratica(opcoes, assunto)
    if not questoes:
        opcoes.saida(
            'Nenhuma questão errada para repetir' + (f' no assunto {assunto}.' if assunto else '.')
        )
        return 0
    interacao = opcoes.interacao
    acertos = erros = 0
    for q in questoes:
        opcoes.saida(f'\n[{q.id}] {q.mat} — {q.ass}\n{q.enun}')
        for alt in q.alts:
            opcoes.saida(f'  {alt.get("l", "?")}) {alt.get("t", "")}')
        if interacao is None:
            continue
        resposta = interacao.perguntar('Sua resposta (letra ou Certo/Errado)', sugestao='')
        if resposta is None:
            continue
        resultado = registrar_tentativa(opcoes, q.id, resposta, q.gab, q.tipo)
        if resultado == 'acerto':
            acertos += 1
            opcoes.saida('acertou')
        else:
            erros += 1
            opcoes.saida(f'errou (gabarito: {q.gab})')
    opcoes.saida(f'\nRepetição: {acertos} acerto(s), {erros} erro(s).')
    return 0
