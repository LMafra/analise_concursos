import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from concursos import relatorio_html
from concursos.analytics.consolidado import concursos_analisados
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.pratica import caderno_de_erros, fontes_de_estudo
from concursos.aplicacao.projeto import (
    candidatos_da_execucao,
    concurso_alvo,
    escolher_candidato,
    exigir_provas,
    pasta_do_candidato,
)
from concursos.cadastro import cadastrar
from concursos.candidatos import alvos_pci
from concursos.concurso_config import ConcursoConfig, ConfiguracaoInvalidaError
from concursos.config.contexto import Contexto
from concursos.configuracao import configuracao_do_projeto
from concursos.erros import ErroDoAmbiente, ErroDoUsuario
from concursos.integracoes import download_assistido, pci_mcp
from concursos.integracoes.open_notebook import (
    DICA_INSTANCIA,
    ClienteOpenNotebook,
    ConfiguracaoOpenNotebook,
    OpenNotebookIndisponivelError,
    gravar_configuracao,
    ler_configuracao,
)
from concursos.integracoes.pagina_pci import baixar_pagina, ler_arquivos, validar_link
from concursos.integracoes.pci_mcp import (
    REGIOES,
    ClientePciMcp,
    ConcursoPci,
    ConfiguracaoPciMcp,
    PciMcpErro,
    PciMcpParametroError,
    ProvaAnteriorPci,
    validar_uf,
)
from concursos.integracoes.radar_pci import gravar_radar, ler_radar, montar_radar, resumo_radar
from concursos.integracoes.simulado_pci import (
    gravar_provas_anteriores,
    nome_da_pasta,
    preparar_pasta,
    termos_automaticos,
)
from concursos.integracoes.sincronizacao_notebook import (
    ARQUIVO_ESTADO,
    ARTEFATOS_DO_CONCURSO,
    ARTEFATOS_DO_CONSOLIDADO,
    EstadoSincronizacao,
    RelatorioSincronizacao,
    Sincronizador,
    sincronizar_candidato,
)
from concursos.integracoes.sincronizacao_pci import Interesses, sessao_pci

logger = logging.getLogger(__name__)


# open-notebook


@dataclass(frozen=True)
class EstadoOpenNotebook:
    ligado: bool
    url: str
    ultima_sincronizacao: datetime | None


def configuracao_open_notebook(contexto: Contexto) -> ConfiguracaoOpenNotebook:
    try:
        return ler_configuracao(contexto.config_global)
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(
            str(erro), f'corrija a seção [open_notebook] de {contexto.config_global}'
        ) from erro


def aviso_open_notebook(url: str, configuracao: ConfiguracaoOpenNotebook) -> str:
    rotulo = (
        'o nome (slug) do candidato'
        if configuracao.incluir_nome
        else 'um pseudônimo (candidato 1, candidato 2…)'
    )
    return '\n'.join(
        [
            f'O open-notebook em {url} vai receber, a cada análise:',
            f'- por concurso: {", ".join(ARTEFATOS_DO_CONCURSO)} e uma nota de resumo;',
            f'- no consolidado: {", ".join(Path(a).name for a in ARTEFATOS_DO_CONSOLIDADO)} e uma nota de resumo.',
            f'O candidato aparece como {rotulo}; CPF e inscrição não são enviados.',
            'Se a instância usa um provedor de IA externo, o chat dela manda esse conteúdo para ele.',
            f'A senha, se houver, vem da variável {configuracao.variavel_chave}, nunca do config.toml.',
        ]
    )


def ligar_open_notebook(contexto: Contexto, url: str) -> None:
    gravar_configuracao(contexto.config_global, enabled=True, consentimento=True, url=url)


def desligar_open_notebook(contexto: Contexto) -> None:
    gravar_configuracao(contexto.config_global, enabled=False)


def estado_open_notebook(contexto: Contexto) -> EstadoOpenNotebook:
    """A última sincronização é a última gravação do estado local; o servidor não é consultado."""
    configuracao = configuracao_open_notebook(contexto)
    arquivo = contexto.projeto / ARQUIVO_ESTADO
    ultima = datetime.fromtimestamp(arquivo.stat().st_mtime) if arquivo.exists() else None
    return EstadoOpenNotebook(configuracao.ativa, configuracao.url, ultima)


def sincronizar(
    opcoes: Opcoes, concurso: str | None = None, todos: bool = False
) -> RelatorioSincronizacao | None:
    """Num comando explícito; devolve None no `--dry-run`, depois de listar o que iria."""
    contexto = opcoes.contexto
    exigir_provas(contexto.provas)
    configuracao = configuracao_open_notebook(contexto)
    if not configuracao.ativa:
        raise ErroDoUsuario(
            'a sincronização com o open-notebook está desligada',
            'ligue com `concurso-analise notebook enable`',
        )
    if not opcoes.rede:
        raise ErroDoUsuario('notebook sync usa a rede e foi pedido --offline', 'rode de novo sem --offline')
    candidatos = candidatos_da_execucao(contexto, todos or opcoes.todos)
    if opcoes.dry_run:
        for nome_candidato in candidatos:
            pasta = contexto.analises / nome_candidato if nome_candidato else contexto.analises
            prefixo = f'{nome_candidato}/' if nome_candidato else ''
            for nome in concursos_analisados(contexto.provas, pasta):
                if concurso in (None, nome):
                    opcoes.saida(f'{prefixo}{nome}: sincronizaria com {configuracao.url}')
        return None
    try:
        return sincronizar_notebooks(contexto, configuracao, candidatos, concurso)
    except OpenNotebookIndisponivelError as erro:
        if erro.status in (401, 403):
            raise ErroDoUsuario(erro.causa, erro.dica) from erro
        raise ErroDoAmbiente(erro.causa, erro.dica or DICA_INSTANCIA) from erro


def sincronizar_notebooks(
    contexto: Contexto,
    configuracao: ConfiguracaoOpenNotebook,
    candidatos: list[str | None],
    concurso: str | None,
) -> RelatorioSincronizacao:
    cliente = ClienteOpenNotebook.da_configuracao(configuracao, contexto.home)
    cliente.saude()
    cliente.listar_notebooks()
    sincronizador = Sincronizador(
        cliente, EstadoSincronizacao.ler(contexto.projeto / ARQUIVO_ESTADO), embed=configuracao.embed
    )
    limiar = configuracao_do_projeto(contexto).limiar_topico_baixo
    fontes = fontes_de_estudo(contexto)
    caderno = caderno_de_erros(contexto, candidatos)
    try:
        for candidato in candidatos:
            sincronizar_candidato(
                sincronizador,
                contexto.provas,
                contexto.analises / candidato if candidato else contexto.analises,
                candidato,
                limiar=limiar,
                arquivo_taxonomia=contexto.taxonomia,
                incluir_nome=configuracao.incluir_nome,
                concurso=concurso,
                fontes=fontes,
                caderno_de_erros=caderno.get(candidato),
            )
    finally:
        sincronizador.gravar_estado()
    return sincronizador.relatorio


def sincronizar_depois_da_analise(opcoes: Opcoes, candidatos: list[str | None]) -> None:
    """Uma falha aqui vira aviso: a análise já terminou e o código de saída é dela."""
    if opcoes.dry_run or not opcoes.rede:
        return
    contexto = opcoes.contexto
    try:
        configuracao = ler_configuracao(contexto.config_global)
    except ConfiguracaoInvalidaError as erro:
        logger.warning('open-notebook: %s; a sincronização foi pulada', erro)
        return
    if not configuracao.ativa:
        return
    try:
        relatorio = sincronizar_notebooks(contexto, configuracao, candidatos, None)
    except OpenNotebookIndisponivelError as erro:
        logger.warning(
            'open-notebook: %s; a sincronização foi pulada (%s)', erro.causa, erro.dica or DICA_INSTANCIA
        )
        return
    except Exception as erro:  # noqa: BLE001 - nenhuma falha da integração derruba a análise
        logger.warning('open-notebook: falha inesperada na sincronização: %s', erro)
        logger.debug('open-notebook: detalhe da falha', exc_info=True)
        return
    logger.info('open-notebook: %s', relatorio.formatar().replace('\n', '; '))
    for falha in relatorio.falhas:
        logger.warning('open-notebook: %s', falha)


# PCI Concursos


def configuracao_pci(contexto: Contexto) -> ConfiguracaoPciMcp:
    try:
        return pci_mcp.ler_configuracao(contexto.config_global)
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(str(erro), f'corrija a seção [pci_mcp] de {contexto.config_global}') from erro


def exigir_pci_ligado(configuracao: ConfiguracaoPciMcp) -> None:
    if not configuracao.enabled:
        raise ErroDoUsuario(
            'a integração com o PCI Concursos está desligada', 'ligue com `concurso-analise pci enable`'
        )


def aviso_pci(url: str, configuracao: ConfiguracaoPciMcp) -> str:
    return '\n'.join(
        [
            f'O servidor MCP público do PCI Concursos em {url} vai receber só termos de busca:',
            '- cargos, UF, cidade, região e termos de prova (do comando ou de [pci] no perfil do candidato).',
            'Nome, CPF, inscrição e notas não saem do computador.',
            f'As respostas ficam em .concurso/cache/ por {configuracao.ttl_horas:g} h; o servidor é beta, e o PCI '
            'complementa, mas não substitui, o edital oficial.',
            'Depois de cada análise, o radar de prazos consulta o PCI; `--offline` usa só o cache.',
        ]
    )


def ligar_pci(contexto: Contexto, url: str) -> None:
    pci_mcp.gravar_configuracao(contexto.config_global, enabled=True, url=url)


def desligar_pci(contexto: Contexto) -> None:
    pci_mcp.gravar_configuracao(contexto.config_global, enabled=False)


def alvos_do_candidato(contexto: Contexto) -> tuple[tuple[str, ...], str]:
    try:
        candidato = escolher_candidato(contexto)
    except ErroDoUsuario:
        return (), ''
    if candidato is None:
        return (), ''
    try:
        return alvos_pci(contexto.home, candidato)
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(str(erro), 'corrija a seção [pci] do perfil do candidato') from erro


def filtros_pci(
    contexto: Contexto,
    configuracao: ConfiguracaoPciMcp,
    cargos: list[str],
    uf: str | None,
    cidade: str | None,
    regiao: str | None,
    termo: str | None,
) -> dict:
    """Sem nenhum filtro, os cargos e a UF do candidato; sem eles, os de [pci_mcp]."""
    alvos, uf_alvo = alvos_do_candidato(contexto)
    try:
        uf = validar_uf(uf if uf is not None else (uf_alvo or configuracao.uf), '--uf')
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(str(erro), 'use a sigla do estado, ex.: --uf sp') from erro
    if regiao is not None and regiao not in REGIOES:
        raise ErroDoUsuario(f'--regiao {regiao} é inválida', f'use uma de: {", ".join(REGIOES)}')
    if not (cargos or cidade or termo or regiao):
        cargos = list(alvos or configuracao.cargos)
        regiao = configuracao.regiao
    return {'cargos': cargos, 'uf': uf, 'cidade': cidade or '', 'regiao': regiao or '', 'termo': termo or ''}


def consultar_pci(opcoes: Opcoes, configuracao: ConfiguracaoPciMcp, refresh: bool, consulta):
    """Num comando explícito, a falha do PCI é erro: de parâmetro, do usuário; do servidor, do ambiente."""
    rede = opcoes.rede and not opcoes.dry_run
    try:
        with sessao_pci(
            opcoes.contexto.projeto, configuracao, rede=rede, refresh=refresh, gravar=not opcoes.dry_run
        ) as cliente:
            return consulta(cliente)
    except PciMcpParametroError as erro:
        raise ErroDoUsuario(erro.causa, erro.dica) from erro
    except PciMcpErro as erro:
        raise ErroDoAmbiente(erro.causa, erro.dica) from erro


def descobrir(
    opcoes: Opcoes,
    cargos: list[str] | None = None,
    uf: str | None = None,
    cidade: str | None = None,
    regiao: str | None = None,
    termo: str | None = None,
    professores: bool = False,
    refresh: bool = False,
) -> list[ConcursoPci]:
    configuracao = configuracao_pci(opcoes.contexto)
    exigir_pci_ligado(configuracao)
    filtros = filtros_pci(opcoes.contexto, configuracao, cargos or [], uf, cidade, regiao, termo)
    return consultar_pci(
        opcoes,
        configuracao,
        refresh,
        lambda cliente: cliente.buscar_concursos(**filtros, professores=professores),
    )


def interesses(contexto: Contexto) -> Interesses:
    try:
        return Interesses.do_projeto(contexto.projeto)
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(str(erro), 'corrija ou apague o arquivo de interesses') from erro


def registrar_interesse(opcoes: Opcoes, concursos: list[ConcursoPci], identificador: int) -> None:
    escolhido = next((c for c in concursos if c.id == identificador), None)
    if escolhido is None:
        raise ErroDoUsuario(
            f'o concurso {identificador} não está no resultado desta busca',
            'rode o discover com os filtros que o mostram e use um id da lista',
        )
    if opcoes.dry_run:
        opcoes.saida(f'registraria o interesse em {identificador} ({escolhido.titulo})')
        return
    registro = interesses(opcoes.contexto)
    novo = registro.registrar(escolhido)
    registro.gravar()
    acao = 'registrado' if novo else 'atualizado'
    opcoes.saida(f'interesse {acao}: {identificador} ({escolhido.titulo}); ele entra no radar de prazos')


def esquecer_interesse(opcoes: Opcoes, identificador: int) -> None:
    registro = interesses(opcoes.contexto)
    if registro.obter(identificador) is None:
        raise ErroDoUsuario(
            f'o concurso {identificador} não está nos interesses', f'confira {registro.caminho}'
        )
    if opcoes.dry_run:
        opcoes.saida(f'deixaria de acompanhar {identificador}')
        return
    registro.esquecer(identificador)
    registro.gravar()
    opcoes.saida(f'interesse removido: {identificador}')


@dataclass(frozen=True)
class ProvasAnteriores:
    alvo: ConcursoConfig | None
    termo: str
    provas: list[ProvaAnteriorPci]


def provas_anteriores(
    opcoes: Opcoes,
    concurso: str | None = None,
    termos: list[str] | None = None,
    refresh: bool = False,
) -> ProvasAnteriores:
    """Busca as provas anteriores e, com concurso-alvo, grava `provas_anteriores.md` na análise dele."""
    contexto = opcoes.contexto
    configuracao = configuracao_pci(contexto)
    exigir_pci_ligado(configuracao)
    alvo = concurso_alvo(contexto, concurso) if concurso else None
    explicitos = list(termos or [])
    automaticos = termos_automaticos(alvo) if alvo is not None and not explicitos else []
    if not (explicitos or automaticos):
        raise ErroDoUsuario(
            'falta o que buscar nas provas anteriores',
            'passe o concurso-alvo (com `cargo` no concurso.yaml) ou --termo "<cargo> <órgão>"',
        )

    def consulta(cliente: ClientePciMcp) -> tuple[str, list[ProvaAnteriorPci]]:
        if explicitos:
            juntas: dict[int, ProvaAnteriorPci] = {}
            for termo in explicitos:
                for prova in cliente.pesquisar_provas_anteriores(termo):
                    juntas.setdefault(prova.id, prova)
            return ' / '.join(explicitos), list(juntas.values())
        for termo in automaticos:
            if provas := cliente.pesquisar_provas_anteriores(termo):
                return termo, provas
        return automaticos[-1], []

    termo, provas = consultar_pci(opcoes, configuracao, refresh, consulta)
    if alvo is not None and not opcoes.dry_run:
        gravar_provas_anteriores(
            pasta_do_candidato(contexto) / alvo.pasta.name, alvo.pasta.name, termo, provas
        )
    return ProvasAnteriores(alvo, termo, provas)


def importar_simulado(
    opcoes: Opcoes,
    provas: list[ProvaAnteriorPci],
    identificador: int,
    alvo: ConcursoConfig | None,
    esperar: Callable[..., dict[str, Path]] | None = None,
) -> int:
    """O clique no PDF é do usuário, no navegador dele: o app nunca pede o link do arquivo ao PCI.

    `esperar` troca a espera na pasta de downloads (a GUI passa uma que pode ser cancelada).
    """
    configuracao = configuracao_pci(opcoes.contexto)
    prova = next((p for p in provas if p.id == identificador), None)
    if prova is None:
        raise ErroDoUsuario(
            f'a prova {identificador} não está no resultado desta busca',
            'rode `pci provas` com os termos que a mostram e use um id da lista',
        )
    contexto = opcoes.contexto
    exigir_provas(contexto.provas)
    if opcoes.dry_run:
        opcoes.saida(
            f'abriria {prova.link} e importaria os PDFs baixados para {contexto.provas / nome_da_pasta(prova)}'
        )
        return 0
    if not opcoes.rede:
        raise ErroDoUsuario(
            '--download abre a página da prova, e foi pedido --offline', 'rode de novo sem --offline'
        )
    link = validar_link(prova.link)
    try:
        arquivos = ler_arquivos(baixar_pagina(link, configuracao.timeout))
    except PciMcpErro as erro:
        logger.warning('PCI: %s; baixe os arquivos que a página mostrar', erro.causa)
        arquivos = []
    pasta, avisos = preparar_pasta(contexto.provas, prova, alvo)
    for aviso in avisos:
        logger.warning('%s: %s', pasta.name, aviso)
    downloads = download_assistido.pasta_de_downloads(configuracao.pasta_downloads)
    desde = download_assistido.instante_atual()
    relatorio_html.abrir_no_navegador(link)
    if not arquivos:
        opcoes.saida(
            f'abri {link}; salve os PDFs da prova e do gabarito em {pasta} e rode `concurso-analise add {pasta}`'
        )
        return 0
    opcoes.saida(
        f'abri {link} no navegador. Baixe os arquivos que quiser: {", ".join(a.rotulo for a in arquivos)}.\n'
        f'esperando em {downloads} (até {configuracao.timeout_download:g} s)...'
    )
    esperar = esperar or download_assistido.esperar_downloads
    encontrados = esperar(downloads, [a.nome for a in arquivos], desde, configuracao.timeout_download)
    if not encontrados:
        raise ErroDoUsuario(
            f'nenhum arquivo da prova apareceu em {downloads}',
            f'salve os PDFs em {pasta} e rode `concurso-analise add {pasta}` (ou ajuste pasta_downloads em [pci_mcp])',
        )
    for copiado in download_assistido.importar(encontrados, pasta):
        opcoes.saida(f'importado: {copiado}')
    try:
        cadastrado = cadastrar(pasta, opcoes.interacao_ou_automatica())
    except ValueError as erro:
        raise ErroDoUsuario(
            f'{pasta.name}: o cadastro não terminou ({erro})',
            f'confira os arquivos e rode `concurso-analise add {pasta}`',
        ) from erro
    if not cadastrado:
        return 1
    opcoes.saida(
        f'simulado pronto em {pasta}; acrescente suas respostas com '
        f'`concurso-analise add <arquivo> --candidate <nome> --concurso {pasta.name}`'
    )
    return 0


def radar_pci(opcoes: Opcoes, candidato: str | None, destino: Path) -> bool:
    """Depois da análise, com o PCI ligado: falha vira aviso e não muda o código de saída. Devolve se o radar
    mudou, para o índice ser refeito."""
    contexto = opcoes.contexto
    try:
        configuracao = pci_mcp.ler_configuracao(contexto.config_global)
        if not configuracao.enabled:
            return False
        cargos, uf = alvos_pci(contexto.home, candidato) if candidato else ((), '')
        cargos, uf = cargos or configuracao.cargos, uf or configuracao.uf
        registro = Interesses.do_projeto(contexto.projeto).itens
        encontrados = []
        if cargos:
            with sessao_pci(contexto.projeto, configuracao, rede=opcoes.rede) as cliente:
                encontrados = cliente.buscar_concursos(cargos=cargos, uf=uf)
    except (PciMcpErro, ConfiguracaoInvalidaError, OSError) as erro:
        logger.warning('PCI: radar não atualizado: %s', getattr(erro, 'causa', erro))
        return False
    radar = montar_radar(encontrados, registro, configuracao.dias_alerta, tuple(cargos), date.today())
    return gravar_radar(destino, radar)


def linhas_do_radar(contexto: Contexto) -> list[str]:
    """Só o radar gravado na última análise: o `status` não fala com o PCI."""
    try:
        if not pci_mcp.ler_configuracao(contexto.config_global).enabled:
            return []
    except ConfiguracaoInvalidaError:
        return []
    linhas = []
    for pasta in [contexto.analises, *sorted(p for p in contexto.analises.glob('*') if p.is_dir())]:
        if (radar := ler_radar(pasta)) is not None:
            dono = f' ({pasta.name})' if pasta != contexto.analises else ''
            linhas.append(f'radar PCI{dono}: {resumo_radar(radar)}')
    return linhas
