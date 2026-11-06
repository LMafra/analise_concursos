from dataclasses import replace
from pathlib import Path

from concursos import relatorio_html
from concursos.analytics.consolidado import concursos_analisados
from concursos.analytics.taxonomia import carregar_taxonomia
from concursos.aplicacao.integracoes import radar_pci, sincronizar_depois_da_analise
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.pratica import (
    copiar_exportacao,
    exigir_configuracao_pratica,
    fontes_de_estudo,
    praticar,
    recomendar_estudo,
)
from concursos.aplicacao.projeto import (
    candidatos_da_execucao,
    curto,
    escolher_candidato,
    exigir_provas,
    lembrar_candidato,
    migrar,
    pasta_do_candidato,
)
from concursos.candidatos import completar_perfis, gravar_revisao
from concursos.candidatos import pasta_do_candidato as pasta_de_respostas
from concursos.config.contexto import Contexto
from concursos.configuracao import configuracao_do_projeto
from concursos.consolidado import comparar_candidatos
from concursos.erros import ErroDoUsuario
from concursos.exportacao import FormatoExportacao, exportar_consolidado
from concursos.llm import ClienteComMemoria, ClienteLlm, cliente_configurado
from concursos.manifesto import ARQUIVO_MANIFESTO
from concursos.modelo import Etapa
from concursos.pipeline import ARQUIVO_RESPOSTAS, analisar_todos, planejar
from concursos.pratica_tec import textos_para_normas
from concursos.respostas import RespostasInvalidasError
from concursos.status import StatusConcurso, avaliar, listar_concursos

TEXTO_DA_ETAPA = {
    Etapa.LENDO_ARQUIVOS: 'Lendo os arquivos…',
    Etapa.LENDO_FOLHA: 'Lendo a folha…',
    Etapa.CORRIGINDO: 'Corrigindo…',
    Etapa.CLASSIFICANDO: 'Classificando tópicos…',
    Etapa.GERANDO_RELATORIOS: 'Gerando os relatórios…',
    Etapa.CONSOLIDANDO: 'Juntando os concursos…',
}


def analisar(opcoes: Opcoes, concurso: str | None = None, reaproveitar: bool = False) -> int:
    """A análise completa de uma execução; devolve o código de saída (0 ou 1)."""
    exigir_provas(opcoes.contexto.provas)
    opcoes = migrar(opcoes)
    contexto = opcoes.contexto
    if reaproveitar:
        reaproveitar_csv(opcoes, concurso)
    if not opcoes.todos:
        candidato = escolher_candidato(contexto)
        sucesso = analisar_candidato(opcoes, cliente_llm(opcoes), candidato, concurso)
        sincronizar_depois_da_analise(opcoes, [candidato])
        return 0 if sucesso else 1
    candidatos = candidatos_da_execucao(contexto, todos=True)
    cliente = cliente_llm(opcoes)
    sucessos = [analisar_candidato(opcoes, cliente, candidato, concurso) for candidato in candidatos]
    if not opcoes.dry_run:
        comparar_candidatos(contexto.analises, candidatos)
    sincronizar_depois_da_analise(opcoes, candidatos)
    return 0 if all(sucessos) else 1


def cliente_llm(opcoes: Opcoes) -> ClienteLlm | None:
    if opcoes.dry_run:
        return None
    cliente = cliente_configurado(opcoes.contexto.home, opcoes.contexto.config_global, opcoes.llm)
    return ClienteComMemoria(cliente) if cliente else None


def analisar_candidato(
    opcoes: Opcoes, cliente: ClienteLlm | None, candidato: str | None, concurso: str | None
) -> bool:
    contexto = opcoes.contexto
    provas, analises = curto(contexto.provas, contexto.raiz), curto(contexto.analises, contexto.raiz)
    destino = analises / candidato if candidato else analises
    if opcoes.dry_run:
        prefixo = f'{candidato}/' if candidato else ''
        for nome, acao in planejar(provas, destino, opcoes.forcar, concurso, candidato):
            opcoes.saida(f'{prefixo}{nome}: {acao}')
        praticar(opcoes, candidato, destino, None)
        return True
    if candidato:
        completar_perfis(contexto.provas, candidato)
        if not opcoes.todos:
            lembrar_candidato(contexto, candidato)
    configuracao = replace(configuracao_do_projeto(contexto), cliente_llm=cliente)
    taxonomia = carregar_taxonomia(contexto.taxonomia) if contexto.taxonomia.exists() else None
    fontes = fontes_de_estudo(contexto)
    antes = manifestos(destino)
    sucesso = analisar_todos(
        provas,
        destino,
        opcoes.forcar,
        concurso,
        configuracao,
        taxonomia,
        candidato,
        opcoes.ao_progresso,
        opcoes.ao_etapa,
    )
    pratica = praticar(opcoes, candidato, destino, configuracao)
    textos = textos_para_normas(pratica) if pratica is not None else []
    recomendacoes = recomendar_estudo(
        opcoes, fontes, provas, destino, configuracao.limiar_topico_baixo, textos
    )
    radar = radar_pci(opcoes, candidato, destino)
    indice = destino / relatorio_html.ARQUIVO_INDICE
    mudou_pratica = pratica is not None and pratica.mudou
    if recomendacoes or mudou_pratica or radar or manifestos(destino) != antes or not indice.exists():
        relatorio_html.gerar_relatorio_html(
            provas, destino, contexto.taxonomia, configuracao.limiar_topico_baixo
        )
        if opcoes.abrir:
            relatorio_html.abrir_no_navegador(contexto.raiz / indice)
    opcoes.saida(f'relatório: {contexto.raiz / indice}')
    return sucesso


def manifestos(destino: Path) -> dict[str, int]:
    """Quando cada concurso foi analisado pela última vez; o manifesto só é regravado numa análise."""
    return {p.parent.name: p.stat().st_mtime_ns for p in destino.glob(f'*/{ARQUIVO_MANIFESTO}')}


def reaproveitar_csv(opcoes: Opcoes, concurso: str | None) -> None:
    contexto = opcoes.contexto
    if concurso is None or opcoes.todos:
        raise ErroDoUsuario(
            '--reuse-csv vale para um concurso e um candidato por vez',
            'rode `concurso-analise analyze <concurso> --reuse-csv --candidate <nome>`',
        )
    candidato = escolher_candidato(contexto)
    if candidato is None:
        raise ErroDoUsuario(
            '--reuse-csv precisa de um candidato, e este projeto não tem nenhum',
            'acrescente as respostas com `concurso-analise add <folha> --candidate <nome> --concurso <pasta>`',
        )
    csv = contexto.analises / candidato / concurso / ARQUIVO_RESPOSTAS
    if not csv.exists():
        raise ErroDoUsuario(
            f'{csv}: CSV de leitura da folha não encontrado',
            f'rode `concurso-analise analyze {concurso}` para ler a folha, corrija o CSV e rode de novo '
            'com --reuse-csv',
        )
    status = avaliar(contexto.provas / concurso, candidato)
    if status.config is None:
        raise ErroDoUsuario(
            f'{concurso}: {"; ".join(status.motivos)}', 'corrija o concurso.yaml e rode de novo'
        )
    if opcoes.dry_run:
        opcoes.saida(f'copiaria {csv} para {pasta_de_respostas(contexto.provas / concurso, candidato)}')
        return
    try:
        destino = gravar_revisao(status.config, candidato, csv)
    except RespostasInvalidasError as erro:
        raise ErroDoUsuario(str(erro), f'corrija o {csv} e rode de novo com --reuse-csv') from erro
    opcoes.saida(f'revisão copiada para {destino}; ela vence a folha a partir de agora')


def importar_pratica_e_analisar(opcoes: Opcoes, arquivo: Path | None = None) -> int:
    configuracao = exigir_configuracao_pratica(opcoes.contexto)
    if arquivo is not None:
        copiar_exportacao(opcoes, arquivo, configuracao.entrada)
    return analisar(opcoes)


def situacoes(raiz_provas: Path, candidato: str | None = None) -> list[StatusConcurso]:
    exigir_provas(raiz_provas)
    return [avaliar(pasta, candidato) for pasta in listar_concursos(raiz_provas)]


def relatorio(contexto: Contexto) -> Path:
    """O `index.html` do candidato; erro quando ainda não foi gerado."""
    indice = pasta_do_candidato(contexto) / relatorio_html.ARQUIVO_INDICE
    if not indice.exists():
        raise ErroDoUsuario(
            f'{indice}: relatório ainda não gerado',
            'rode `concurso-analise` para analisar e gerar o relatório',
        )
    return indice


def exportar(contexto: Contexto, formato: FormatoExportacao) -> Path:
    exigir_provas(contexto.provas)
    pasta = pasta_do_candidato(contexto)
    if not concursos_analisados(contexto.provas, pasta):
        raise ErroDoUsuario(
            f'{pasta}: nenhum concurso analisado para exportar', 'rode `concurso-analise` antes do export'
        )
    return exportar_consolidado(contexto.provas, pasta, contexto.taxonomia, formato)
