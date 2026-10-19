import pandas as pd

from concursos.concurso_config import ConcursoConfig
from concursos.modelo import ItemGabarito, RespostaMarcada, Resultado

TOPICO_NAO_MAPEADO = 'nao_mapeado'


def corrigir(
    config: ConcursoConfig,
    gabaritos: dict[str, list[ItemGabarito]],
    respostas: list[RespostaMarcada],
) -> pd.DataFrame:
    """Uma linha por questão com gabarito, resposta e resultado (acerto/erro/branco)."""
    por_questao = {r.questao: r for r in respostas}
    linhas = []
    for prova in config.provas:
        for item in gabaritos[prova.chave]:
            resposta = por_questao.get(item.questao)
            marcada = resposta.alternativa if resposta else None
            linhas.append(
                {
                    'concurso': config.nome,
                    'prova': prova.chave,
                    'questao': item.questao,
                    'disciplina': prova.disciplina_de(item.questao),
                    'topico': TOPICO_NAO_MAPEADO,
                    'gabarito': item.resposta,
                    'resposta': marcada,
                    'anulada': item.anulada,
                    'resultado': _resultado(item, marcada).value,
                }
            )
    return pd.DataFrame(linhas)


def _resultado(item: ItemGabarito, marcada: str | None) -> Resultado:
    if marcada is None:
        return Resultado.BRANCO
    return Resultado.ACERTO if marcada == item.resposta else Resultado.ERRO
