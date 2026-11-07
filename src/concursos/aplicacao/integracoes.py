import json
import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from concursos import relatorio_html
from concursos.analytics.consolidado import concursos_analisados
from concursos.aplicacao import estudo
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.pratica import caderno_de_erros, fontes_de_estudo
from concursos.aplicacao.projeto import (
    candidatos_da_execucao,
    concurso_alvo,
    escolher_candidato,
    exigir_provas,
    pasta_do_candidato,
    proxima_pasta,
)
from concursos.aplicacao.simulados import revisar_simulado
from concursos.cadastro import cadastrar
from concursos.candidatos import alvos_pci, slug
from concursos.concurso_config import ConcursoConfig, ConfiguracaoInvalidaError, gravar_dados, ler_dados
from concursos.config.contexto import Contexto
from concursos.configuracao import configuracao_do_projeto
from concursos.erros import ErroDoAmbiente, ErroDoUsuario, avisar
from concursos.integracoes import download_assistido, pci_mcp
from concursos.integracoes.cache_pci import ARQUIVO_CACHE
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
from concursos.livros import envio
from concursos.municipios import REGIAO_DA_UF, cidade_da_uf
from concursos.status import listar_concursos

logger = logging.getLogger(__name__)

INSTANCIA_GERENCIADA = 'gerenciada'
NACIONAL = 'Nacional — todas as regiões'


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
            'Não consegui ler a configuração do seu programa de estudo (open-notebook).',
            'configure de novo em Configurações > Avançado.',
            f'{erro} (seção [open_notebook] de {contexto.config_global})',
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
    gerenciada = not configuracao.ativa and estudo.situacao_do_estudo(contexto).preparado
    if not configuracao.ativa and not gerenciada:
        raise ErroDoUsuario(
            'O envio das análises para os seus materiais de estudo está desligado.',
            'prepare a biblioteca em Estudar, ou ligue o seu próprio open-notebook em Configurações > Avançado.',
        )
    if not opcoes.rede:
        raise ErroDoUsuario(
            'Atualizar os materiais de estudo usa a internet, e você pediu para não usar (--offline).',
            'rode de novo sem --offline.',
        )
    candidatos = candidatos_da_execucao(contexto, todos or opcoes.todos)
    if opcoes.dry_run:
        for nome_candidato in candidatos:
            pasta = contexto.analises / nome_candidato if nome_candidato else contexto.analises
            prefixo = f'{nome_candidato}/' if nome_candidato else ''
            for nome in concursos_analisados(contexto.provas, pasta):
                if concurso in (None, nome):
                    destino = 'o open-notebook do app' if gerenciada else configuracao.url
                    opcoes.saida(f'{prefixo}{nome}: enviaria para {destino}')
        return None
    try:
        if gerenciada:
            return sincronizar_gerenciada(contexto, candidatos, concurso)
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
    return _sincronizar_candidatos(contexto, sincronizador, candidatos, concurso, configuracao.incluir_nome)


def sincronizar_gerenciada(
    contexto: Contexto, candidatos: list[str | None], concurso: str | None
) -> RelatorioSincronizacao:
    """O open-notebook do app: sem consentimento, com pseudônimo, notebooks com o nome da pasta do
    projeto e achados só pelo ID, e os livros da biblioteca vinculados aos concursos associados."""
    try:
        cliente = estudo.cliente_gerenciado(contexto)
    except ErroDoAmbiente as erro:
        raise OpenNotebookIndisponivelError(erro.causa, erro.dica) from erro
    sincronizador = Sincronizador(
        cliente,
        EstadoSincronizacao.ler(contexto.projeto / ARQUIVO_ESTADO),
        embed=True,
        instancia=INSTANCIA_GERENCIADA,
        por_nome=False,
        prefixo_nome=f'{contexto.raiz.name} · ',
    )
    livros = envio.sources_por_concurso(estudo.biblioteca(contexto))
    return _sincronizar_candidatos(contexto, sincronizador, candidatos, concurso, False, livros)


def _sincronizar_candidatos(
    contexto: Contexto,
    sincronizador: Sincronizador,
    candidatos: list[str | None],
    concurso: str | None,
    incluir_nome: bool,
    livros: dict[str, set[str]] | None = None,
) -> RelatorioSincronizacao:
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
                incluir_nome=incluir_nome,
                concurso=concurso,
                fontes=fontes,
                caderno_de_erros=caderno.get(candidato),
                livros=livros,
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
        avisar(
            logger,
            'Não consegui ler a configuração do open-notebook; não atualizei seus materiais de estudo.',
            'configure de novo em Configurações > Avançado.',
            str(erro),
        )
        return
    gerenciada = not configuracao.ativa and estudo.situacao_do_estudo(contexto).preparado
    if not configuracao.ativa and not gerenciada:
        return
    try:
        if gerenciada:
            relatorio = sincronizar_gerenciada(contexto, candidatos, None)
        else:
            relatorio = sincronizar_notebooks(contexto, configuracao, candidatos, None)
    except OpenNotebookIndisponivelError as erro:
        avisar(
            logger,
            'Não consegui falar com o open-notebook; não atualizei seus materiais de estudo.',
            erro.dica or DICA_INSTANCIA,
            erro.causa,
        )
        return
    except Exception as erro:  # noqa: BLE001 - nenhuma falha da integração derruba a análise
        avisar(
            logger,
            'Algo deu errado ao atualizar seus materiais de estudo; a análise seguiu normalmente.',
            'tente de novo mais tarde; se continuar, veja o registro em ~/.concurso/logs/.',
            str(erro),
        )
        logger.debug('open-notebook: detalhe da falha', exc_info=True)
        return
    logger.info('open-notebook: %s', relatorio.formatar().replace('\n', '; '))
    for falha in relatorio.falhas:
        avisar(logger, 'Um item não foi para os seus materiais de estudo.', detalhe=f'open-notebook: {falha}')


# PCI Concursos


def configuracao_pci(contexto: Contexto) -> ConfiguracaoPciMcp:
    try:
        return pci_mcp.ler_configuracao(contexto.config_global)
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(
            'Não consegui ler a configuração da busca de concursos abertos.',
            'configure de novo em Concursos > Encontrar concursos.',
            f'{erro} (seção [pci_mcp] de {contexto.config_global})',
        ) from erro


def exigir_pci_ligado(configuracao: ConfiguracaoPciMcp) -> None:
    if not configuracao.enabled:
        raise ErroDoUsuario(
            'A busca de concursos abertos (PCI Concursos) está desligada.',
            'ligue em Concursos > Encontrar concursos ou com concurso-analise pci enable.',
        )


def aviso_pci(url: str, configuracao: ConfiguracaoPciMcp) -> str:
    return '\n'.join(
        [
            f'A busca de concursos consulta o PCI Concursos pela internet ({url}) e envia só termos de busca:',
            '- cargos, UF, cidade, região e as palavras procuradas nas provas anteriores.',
            'Nome, CPF, inscrição e notas não saem do computador.',
            f'As respostas ficam guardadas no computador por {configuracao.ttl_horas:g} h. A busca do PCI está em '
            'teste e complementa, mas não substitui, o edital oficial.',
            'Depois de cada análise, o radar de prazos consulta o PCI; sem internet, usa o que já está guardado.',
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
        raise ErroDoUsuario(
            'Não consegui ler os cargos de interesse do candidato.',
            'escolha os cargos de novo em Concursos > Encontrar concursos.',
            f'{erro} (seção [pci] do perfil do candidato)',
        ) from erro


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
        raise ErroDoUsuario(
            'Não reconheci o estado informado.', 'use a sigla do estado, por exemplo --uf sp.', str(erro)
        ) from erro
    if regiao is not None and regiao not in REGIOES:
        raise ErroDoUsuario(f'Não conheço a região “{regiao}”.', f'use uma destas: {", ".join(REGIOES)}.')
    if not (cargos or cidade or termo or regiao):
        cargos = list(alvos or configuracao.cargos)
        regiao = configuracao.regiao
        if configuracao.cidade and uf == configuracao.uf.lower():
            cidade = configuracao.cidade
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
        raise ErroDoUsuario(
            'Não consegui ler a lista dos concursos que você acompanha.',
            'apague o arquivo .concurso/interesses_pci.yaml e acompanhe os concursos de novo.',
            str(erro),
        ) from erro


def registrar_interesse(opcoes: Opcoes, concursos: list[ConcursoPci], identificador: int) -> None:
    escolhido = next((c for c in concursos if c.id == identificador), None)
    if escolhido is None:
        raise ErroDoUsuario(
            f'O concurso {identificador} não está no resultado desta busca.',
            'busque de novo com os filtros que o mostram e use um número da lista.',
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
            f'O concurso {identificador} não está entre os que você acompanha.',
            'confira a lista em Concursos > Encontrar concursos.',
            f'{registro.caminho}',
        )
    if opcoes.dry_run:
        opcoes.saida(f'deixaria de acompanhar {identificador}')
        return
    registro.esquecer(identificador)
    registro.gravar()
    opcoes.saida(f'interesse removido: {identificador}')


def regiao_do_concurso(concurso: ConcursoPci) -> str:
    """ "Sudeste · MG"; nos nacionais (UF `BR`), "Nacional — todas as regiões". O PCI não diz a cidade da prova."""
    uf = (concurso.uf or '').strip().upper()
    if uf == 'BR':
        return NACIONAL
    regiao = (
        '-'.join(p.capitalize() for p in concurso.regiao.strip().lower().split('-'))
        if concurso.regiao
        else ''
    )
    return ' · '.join(p for p in (regiao or REGIAO_DA_UF.get(uf, ''), uf) if p)


def gravar_filtros_pci(
    contexto: Contexto, cargos: list[str], uf: str | None, cidade: str | None, regiao: str | None
) -> ConfiguracaoPciMcp:
    """ "Lembrar estes filtros": grava em `[pci_mcp]`; a cidade só vale com a UF e tem de ser dela."""
    try:
        uf = validar_uf(uf or '', 'UF')
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(
            'Não reconheci o estado escolhido.', 'escolha a UF na lista.', str(erro)
        ) from erro
    if regiao and regiao not in REGIOES:
        raise ErroDoUsuario(f'Não conheço a região “{regiao}”.', f'use uma destas: {", ".join(REGIOES)}.')
    oficial = ''
    if cidade and cidade.strip():
        if not uf:
            raise ErroDoUsuario(
                f'Para buscar em {cidade}, preciso do estado.', 'escolha a UF antes da cidade.'
            )
        oficial = cidade_da_uf(cidade, uf)
        if oficial is None:
            raise ErroDoUsuario(
                f'Não encontrei a cidade {cidade} em {uf.upper()}.', 'escolha a cidade na lista da UF.'
            )
    return pci_mcp.gravar_configuracao(
        contexto.config_global,
        cargos=[c.strip() for c in cargos if c.strip()],
        uf=uf,
        cidade=oficial,
        regiao=regiao or '',
    )


def situacao_do_cache(contexto: Contexto, agora: datetime | None = None) -> str | None:
    """ "Atualizado há 3 horas", pela consulta mais recente guardada no cache; None sem cache."""
    caminho = contexto.projeto / ARQUIVO_CACHE
    try:
        entradas = json.loads(caminho.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    instantes = []
    for entrada in entradas.values() if isinstance(entradas, dict) else []:
        try:
            instantes.append(datetime.fromisoformat(entrada['obtido_em']))
        except (KeyError, TypeError, ValueError):
            continue
    if not instantes:
        return None
    horas = int(((agora or datetime.now()) - max(instantes)).total_seconds() // 3600)
    if horas < 1:
        return 'Atualizado agora há pouco'
    if horas < 48:
        return f'Atualizado há {horas} {"hora" if horas == 1 else "horas"}'
    return f'Atualizado há {horas // 24} dias'


def _pasta_vinculada(raiz_provas: Path, identificador: int) -> Path | None:
    for pasta in listar_concursos(raiz_provas):
        if (ler_dados(pasta).get('pci') or {}).get('id') == identificador:
            return pasta
    return None


def _base_da_pasta(concurso: ConcursoPci) -> str:
    """ "TRE-MG 2026 - Analista Judiciário" vira `tre_mg_2026`: o que vem antes do " - ", até 4 palavras."""
    cabeca = re.split(r'\s+[-–]\s+', concurso.titulo.strip(), maxsplit=1)[0]
    try:
        return slug(' '.join(cabeca.split()[:4]))
    except ConfiguracaoInvalidaError:
        return f'concurso_pci_{concurso.id}'


def adicionar_ao_projeto(opcoes: Opcoes, concursos: list[ConcursoPci], identificador: int) -> Path:
    """Do card ao projeto num clique: acompanha o concurso e cria a pasta com o vínculo ao PCI, à espera do
    edital e da prova. O título do PCI vale como nome "a confirmar" até o edital chegar. Já adicionado,
    devolve a mesma pasta."""
    escolhido = next((c for c in concursos if c.id == identificador), None)
    if escolhido is None:
        raise ErroDoUsuario(
            f'O concurso {identificador} não está no resultado desta busca.',
            'busque de novo com os filtros que o mostram.',
        )
    contexto = opcoes.contexto
    if (
        contexto.provas.is_dir()
        and (existente := _pasta_vinculada(contexto.provas, identificador)) is not None
    ):
        return existente
    pasta = proxima_pasta(contexto, _base_da_pasta(escolhido))
    if opcoes.dry_run:
        opcoes.saida(f'criaria {pasta} vinculada ao concurso {identificador} do PCI')
        return pasta
    registro = interesses(contexto)
    if registro.obter(identificador) is None:
        registro.registrar(escolhido)
    registro.vincular(identificador, pasta.name)
    registro.gravar()
    pasta.mkdir(parents=True)
    vinculo = {'id': identificador, 'titulo': escolhido.titulo, 'link': escolhido.link}
    gravar_dados(pasta, {'nome': pasta.name, 'pci': vinculo})
    opcoes.saida(f'{escolhido.titulo} adicionado ao projeto; falta o edital e os arquivos da prova')
    return pasta


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
            'Falta dizer o que buscar nas provas anteriores.',
            'escolha um concurso-alvo com cargo cadastrado, ou busque por "<cargo> <órgão>" (--termo).',
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


class ImportacaoCanceladaError(Exception):
    pass


def espera_cancelavel(cancelar: threading.Event) -> Callable[..., dict[str, Path]]:
    """A espera na pasta de downloads de `importar_simulado`, interrompida assim que `cancelar` é ligado."""

    def dormir(segundos: float) -> None:
        if cancelar.wait(segundos):
            raise ImportacaoCanceladaError

    def esperar(pasta: Path, esperados, desde: float, timeout: float) -> dict[str, Path]:
        if cancelar.is_set():
            raise ImportacaoCanceladaError
        return download_assistido.esperar_downloads(
            pasta, esperados, desde, timeout, dormir=dormir, intervalo=0.5
        )

    return esperar


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
            f'A prova {identificador} não está no resultado desta busca.',
            'busque de novo com os termos que a mostram e use um número da lista.',
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
            'Baixar a prova abre a página dela na internet, e você pediu para não usar (--offline).',
            'rode de novo sem --offline.',
        )
    link = validar_link(prova.link)
    try:
        arquivos = ler_arquivos(baixar_pagina(link, configuracao.timeout))
    except PciMcpErro as erro:
        avisar(
            logger,
            'Não consegui ver quais arquivos a página da prova tem.',
            'baixe os arquivos que a página mostrar.',
            f'PCI: {erro.causa}',
        )
        arquivos = []
    pasta, avisos = preparar_pasta(contexto.provas, prova, alvo)
    for aviso in avisos:
        avisar(logger, f'{pasta.name}: {aviso}')
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
            f'Nenhum arquivo da prova apareceu na sua pasta de downloads ({downloads}).',
            f'salve os PDFs em {pasta} e rode concurso-analise add {pasta}.',
            'a pasta de downloads se ajusta em pasta_downloads, na seção [pci_mcp]',
        )
    for copiado in download_assistido.importar(encontrados, pasta):
        opcoes.saida(f'importado: {copiado}')
    try:
        cadastrado = cadastrar(pasta, opcoes.interacao_ou_automatica())
    except ValueError as erro:
        raise ErroDoUsuario(
            f'{pasta.name}: não consegui terminar o cadastro da prova.',
            f'confira os arquivos e rode concurso-analise add {pasta}.',
            str(erro),
        ) from erro
    if not cadastrado:
        return 1
    revisar_simulado(contexto, pasta)
    opcoes.saida(
        f'simulado pronto em {pasta}; acrescente suas respostas com '
        f'`concurso-analise add <arquivo> --candidate <nome> --concurso {pasta.name}`'
    )
    return 0


@dataclass
class LoteDeSimulados:
    importadas: list[int] = field(default_factory=list)
    ja_importadas: list[int] = field(default_factory=list)
    falhas: dict[int, str] = field(default_factory=dict)
    nao_tentadas: list[int] = field(default_factory=list)

    @property
    def cancelado(self) -> bool:
        return bool(self.nao_tentadas)

    def resumo(self) -> str:
        partes = [f'{len(self.importadas)} importada(s)']
        if self.ja_importadas:
            partes.append(f'{len(self.ja_importadas)} já estava(m) no projeto')
        if self.falhas:
            partes.append(f'{len(self.falhas)} com falha')
        if self.nao_tentadas:
            partes.append(f'{len(self.nao_tentadas)} não tentada(s) (cancelado)')
        return '; '.join(partes)


def ja_importada(raiz_provas: Path, prova: ProvaAnteriorPci) -> bool:
    return bool(ler_dados(raiz_provas / nome_da_pasta(prova)).get('provas'))


def importar_simulados(
    opcoes: Opcoes,
    provas: list[ProvaAnteriorPci],
    identificadores: list[int],
    alvo: ConcursoConfig | None,
    esperar: Callable[..., dict[str, Path]] | None = None,
) -> LoteDeSimulados:
    """Uma prova por vez, cada uma com a página aberta e a espera na pasta de downloads. A falha de uma vira
    aviso e o lote segue; cancelar a espera encerra o lote, e as que faltavam ficam como não tentadas."""
    lote = LoteDeSimulados()
    pedidas = [p for i in identificadores for p in provas if p.id == i]
    for posicao, prova in enumerate(pedidas, start=1):
        if ja_importada(opcoes.contexto.provas, prova):
            lote.ja_importadas.append(prova.id)
            continue
        opcoes.saida(
            f'Passo {posicao} de {len(pedidas)}: o navegador vai abrir a página da prova {prova.orgao} '
            f'{prova.ano or ""}. Baixe a prova e o gabarito.'.replace('  ', ' ')
        )
        try:
            codigo = importar_simulado(opcoes, provas, prova.id, alvo, esperar)
        except ImportacaoCanceladaError:
            lote.nao_tentadas = [p.id for p in pedidas[posicao - 1 :]]
            break
        except (ErroDoUsuario, ErroDoAmbiente) as erro:
            avisar(logger, f'Prova {prova.id}: {erro.causa}', erro.dica, erro.detalhe)
            lote.falhas[prova.id] = erro.causa
            continue
        if codigo == 0:
            lote.importadas.append(prova.id)
        else:
            lote.falhas[prova.id] = 'o cadastro não terminou'
    opcoes.saida(f'provas anteriores: {lote.resumo()}')
    return lote


def termos_previstos(contexto: Contexto, concurso: str | None) -> list[str]:
    """Os termos que a busca usará sem termo digitado, para a tela mostrar antes de buscar."""
    if not concurso:
        return []
    try:
        return termos_automaticos(concurso_alvo(contexto, concurso))
    except (ErroDoUsuario, ConfiguracaoInvalidaError, FileNotFoundError):
        return []


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
        avisar(
            logger,
            'Não consegui atualizar os prazos dos editais; ficam os da última busca.',
            detalhe=f'PCI: {getattr(erro, "causa", erro)}',
        )
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
