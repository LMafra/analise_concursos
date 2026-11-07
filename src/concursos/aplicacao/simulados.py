"""As provas anteriores importadas como simulados: a revisão de tópicos antes das respostas e o simulado focado."""

import logging
from dataclasses import replace
from pathlib import Path

from concursos import simulado_focado
from concursos.analytics.taxonomia import carregar_taxonomia
from concursos.aplicacao.dicionario import dicionario_do_projeto
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.projeto import pasta_do_candidato
from concursos.biblioteca import topicos_fracos
from concursos.concurso_config import ConfiguracaoInvalidaError, carregar_concurso
from concursos.config.contexto import Contexto
from concursos.configuracao import ConfiguracaoGlobal, configuracao_do_projeto
from concursos.pipeline import preparar_revisao
from concursos.topicos import ARQUIVO_REVISAO

logger = logging.getLogger('concursos')


def _configuracao(contexto: Contexto) -> ConfiguracaoGlobal:
    return replace(configuracao_do_projeto(contexto), dicionario=dicionario_do_projeto(contexto))


def revisar_simulado(contexto: Contexto, pasta: Path, configuracao: ConfiguracaoGlobal | None = None) -> bool:
    """Classifica as questões do simulado recém-importado; a falha vira aviso, e o simulado fica sem tópicos
    até a próxima análise."""
    try:
        config = carregar_concurso(pasta)
        taxonomia = carregar_taxonomia(contexto.taxonomia) if contexto.taxonomia.exists() else None
        preparar_revisao(config, configuracao or _configuracao(contexto), taxonomia)
    except (ConfiguracaoInvalidaError, FileNotFoundError, ValueError) as erro:
        logger.warning('%s: tópicos das questões não classificados (%s)', pasta.name, erro)
        return False
    return True


def gerar_simulado_focado(
    opcoes: Opcoes,
    raiz_provas: Path,
    destino: Path,
    limiar: float,
    configuracao: ConfiguracaoGlobal | None = None,
) -> simulado_focado.SimuladoFocado | None:
    """Sem provas anteriores importadas, nada é gravado. Os simulados importados antes da revisão automática
    são classificados aqui, uma vez."""
    contexto = opcoes.contexto
    pastas = simulado_focado.pastas_de_simulado(raiz_provas)
    if not pastas or opcoes.dry_run:
        return None
    for pasta in pastas:
        if not (pasta / ARQUIVO_REVISAO).exists():
            revisar_simulado(contexto, pasta, configuracao)
    fracos, avisos = topicos_fracos(raiz_provas, destino, contexto.taxonomia, limiar)
    for aviso in avisos:
        logger.warning('simulado focado: %s', aviso)
    resultado = simulado_focado.montar(raiz_provas, destino, fracos)
    simulado_focado.gravar(destino, simulado_focado.formatar(resultado, limiar))
    return resultado


def simulado_focado_do_projeto(opcoes: Opcoes) -> simulado_focado.SimuladoFocado | None:
    """O da GUI, depois de importar provas anteriores: o candidato da execução e o limiar do projeto."""
    contexto = opcoes.contexto
    configuracao = _configuracao(contexto)
    return gerar_simulado_focado(
        opcoes, contexto.provas, pasta_do_candidato(contexto), configuracao.limiar_topico_baixo, configuracao
    )


def texto_do_simulado_focado(contexto: Contexto) -> str | None:
    caminho = pasta_do_candidato(contexto) / simulado_focado.ARQUIVO_SIMULADO_FOCADO
    return caminho.read_text(encoding='utf-8') if caminho.exists() else None
