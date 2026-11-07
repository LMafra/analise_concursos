"""Estudar com os livros: preparar o open-notebook no computador, enviar, listar, remover e perguntar.

As mensagens daqui aparecem para o usuário leigo; o teste de vocabulário as confere.
"""

import atexit
import logging
import re
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from concursos.analytics.dicionario_topicos import expandir_consulta
from concursos.analytics.taxonomia import carregar_taxonomia
from concursos.aplicacao import atualizador as atualizacao
from concursos.aplicacao.dicionario import dicionario_do_projeto
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.projeto import curto, pasta_do_candidato
from concursos.biblioteca import consultas_do_topico, topicos_fracos
from concursos.config.contexto import Contexto
from concursos.configuracao import configuracao_do_projeto
from concursos.erros import ErroDoAmbiente, ErroDoUsuario
from concursos.estudo import embeddings, instalacao
from concursos.estudo.instalacao import PacoteDisponivel, Pastas
from concursos.estudo.supervisor import VARIAVEL_CIFRA, Sessao, Supervisor
from concursos.integracoes.open_notebook import ClienteOpenNotebook, OpenNotebookIndisponivelError
from concursos.livros import envio, fila, indice, perguntas
from concursos.livros.fila import Livro, PastasBiblioteca
from concursos.livros.validacao import EXTENSOES
from concursos.llm import (
    ConfiguracaoLlm,
    gravar_consentimento_livros,
    guardar_chave,
    obter_chave,
    obter_chave_da_variavel,
)
from concursos.llm import ler_configuracao as ler_configuracao_llm
from concursos.modelo import EstadoLivro, OndeProcurar
from concursos.status import listar_concursos
from concursos.texto import abreviar

logger = logging.getLogger(__name__)

TAMANHO_ESTIMADO_MB = 360
TEXTO_PREPARAR = (
    'Para estudar com seus livros, o app precisa preparar o open-notebook no seu computador. '
    'É um download único de cerca de {mb} MB; seus livros não saem do computador.'
)
TEXTO_PREPARANDO = 'Sua biblioteca está sendo preparada; os envios continuam sozinhos.'
TEXTO_FORA = 'O open-notebook não abriu agora. A busca continua nos seus livros, só que mais simples.'

ProgressoEstudo = Callable[[str, float], None]

INTERVALO_CONFERENCIA = 3.0
ESPERA_MAXIMA_ENVIO = 30 * 60.0

_supervisores: dict[Path, Supervisor] = {}
_trabalhos: dict[Path, '_Trabalho'] = {}
_trava = threading.Lock()


@dataclass(frozen=True)
class SituacaoEstudo:
    disponivel_no_sistema: bool
    versao: str | None
    aberto: bool
    fora_do_ar: bool
    mensagem: str

    @property
    def preparado(self) -> bool:
        return self.versao is not None


def pastas(contexto: Contexto) -> Pastas:
    return Pastas.do_home(contexto.home)


def chave_de_cifra(home: Path) -> str:
    """A chave que cifra as credenciais no banco do open-notebook; gerada uma vez e guardada no keyring."""
    encontrada = obter_chave_da_variavel(VARIAVEL_CIFRA, home)
    if encontrada:
        return encontrada[0]
    chave = secrets.token_urlsafe(32)
    guardar_chave(VARIAVEL_CIFRA, chave, home)
    return chave


def _registrar_embeddings(sessao: Sessao) -> None:
    embeddings.registrar(ClienteOpenNotebook(sessao.url, sessao.senha, timeout=60))


def supervisor(contexto: Contexto) -> Supervisor:
    """Um supervisor por pasta global, parado quando o app fecha."""
    with _trava:
        existente = _supervisores.get(contexto.home)
        if existente is not None:
            return existente
        novo = Supervisor(
            pastas(contexto),
            contexto.logs,
            chave_cifra=lambda: chave_de_cifra(contexto.home),
            ambiente_ia=lambda: ambiente_da_ia(contexto),
            ao_subir=[_registrar_embeddings],
        )
        novo.vigiar()
        atexit.register(novo.parar)
        _supervisores[contexto.home] = novo
        return novo


def situacao_do_estudo(contexto: Contexto, sistema: str | None = None) -> SituacaoEstudo:
    try:
        instalacao.plataforma(*([sistema] if sistema else []))
    except ErroDoUsuario as erro:
        return SituacaoEstudo(False, None, False, False, erro.causa)
    raiz = instalacao.instalado(pastas(contexto))
    if raiz is None:
        return SituacaoEstudo(True, None, False, False, TEXTO_PREPARAR.format(mb=TAMANHO_ESTIMADO_MB))
    versao = instalacao.ler_estado(pastas(contexto)).atual
    existente = _supervisores.get(contexto.home)
    aberto = existente is not None and existente.sessao is not None
    fora = existente is not None and existente.indisponivel
    mensagem = TEXTO_FORA if fora else 'Sua biblioteca está pronta.'
    return SituacaoEstudo(True, versao, aberto, fora, mensagem)


def procurar_pacote(opcoes: Opcoes, transporte=None) -> PacoteDisponivel | None:  # noqa: ANN001
    if not opcoes.rede:
        raise ErroDoUsuario(
            'sem internet não dá para preparar a biblioteca', 'tente de novo com a internet ligada'
        )
    canal = atualizacao.ler_preferencias(opcoes.contexto.config_global).canal
    versao = atualizacao.versao_instalada()
    return instalacao.procurar(canal, transporte or atualizacao.TransporteHttps(versao), versao)


def preparar_estudo(
    opcoes: Opcoes,
    *,
    consentiu: bool,
    arquivo: Path | None = None,
    progresso: ProgressoEstudo | None = None,
    transporte=None,  # noqa: ANN001
) -> str:
    """Baixa (ou instala de `arquivo`) o pacote de estudo; devolve a versão instalada."""
    if opcoes.dry_run:
        opcoes.saida('prepararia o open-notebook no computador')
        return ''
    alvo = pastas(opcoes.contexto)
    if arquivo is not None:
        encontrada = re.match(r'estudo-(\d+\.\d+\.\d+-\d+)-', arquivo.name)
        if encontrada is None:
            raise ErroDoUsuario(
                f'{arquivo.name} não é um pacote de estudo', 'use o arquivo estudo-<versão>-<sistema>'
            )
        versao = encontrada.group(1)
        instalacao.instalar_arquivo(alvo, arquivo, versao)
        opcoes.saida(f'biblioteca preparada (open-notebook {versao.split("-")[0]})')
        return versao
    if not consentiu:
        raise ErroDoUsuario(
            'a biblioteca só é preparada depois que você concordar', 'clique em "Preparar agora"'
        )
    if progresso:
        progresso('Procurando a versão mais nova…', 0.0)
    disponivel = procurar_pacote(opcoes, transporte)
    if disponivel is None:
        raise ErroDoAmbiente(
            'ainda não há uma biblioteca para esta versão do app', 'atualize o app e tente de novo'
        )
    if not instalacao.tem_atualizacao(alvo, disponivel):
        return disponivel.manifesto.versao

    def ao_baixar(feito: int, total: int) -> None:
        if progresso:
            progresso(f'Baixando: {feito * 100 // max(total, 1)}%', feito / max(total, 1))

    raiz = instalacao.instalar(
        alvo,
        disponivel,
        transporte or atualizacao.TransporteHttps(atualizacao.versao_instalada()),
        consentiu=True,
        offline=not opcoes.rede,
        progresso=ao_baixar,
    )
    if progresso:
        progresso('Pronto', 1.0)
    opcoes.saida(f'biblioteca preparada (open-notebook {disponivel.manifesto.open_notebook})')
    logger.info('pacote de estudo instalado em %s', raiz)
    return disponivel.manifesto.versao


def atualizacao_da_biblioteca(opcoes: Opcoes, transporte=None) -> PacoteDisponivel | None:  # noqa: ANN001
    """O pacote mais novo que o da biblioteca preparada; sem biblioteca, nenhuma consulta."""
    alvo = pastas(opcoes.contexto)
    if instalacao.instalado(alvo) is None:
        return None
    disponivel = procurar_pacote(opcoes, transporte)
    return disponivel if instalacao.tem_atualizacao(alvo, disponivel) else None


def atualizar_biblioteca(
    opcoes: Opcoes,
    *,
    consentiu: bool,
    progresso: ProgressoEstudo | None = None,
    transporte=None,  # noqa: ANN001
) -> str:
    """Instala o pacote novo; o open-notebook em uso para e volta, no próximo uso, já no novo (com backup)."""
    versao = preparar_estudo(opcoes, consentiu=consentiu, progresso=progresso, transporte=transporte)
    existente = _supervisores.get(opcoes.contexto.home)
    if existente is not None:
        existente.parar()
    return versao


def avisar_atualizacao_da_biblioteca(opcoes: Opcoes, transporte=None) -> None:  # noqa: ANN001
    """A parte da biblioteca no `upgrade`: só informa; instalar é o `estudo preparar`."""
    if opcoes.dry_run or not opcoes.rede:
        return
    try:
        disponivel = atualizacao_da_biblioteca(opcoes, transporte)
    except (ErroDoUsuario, ErroDoAmbiente) as erro:
        opcoes.saida(f'biblioteca: não deu para procurar a versão nova ({erro.causa})')
        return
    if disponivel is not None:
        opcoes.saida(
            f'biblioteca: versão nova {disponivel.manifesto.versao}; '
            'para instalar: concurso-analise estudo preparar'
        )


def cliente_gerenciado(contexto: Contexto) -> ClienteOpenNotebook:
    """O cliente da instância gerenciada, subindo os processos se preciso."""
    sessao = supervisor(contexto).garantir()
    return ClienteOpenNotebook(sessao.url, sessao.senha, timeout=300)


def parar_estudo(contexto: Contexto) -> None:
    existente = _supervisores.get(contexto.home)
    if existente is not None:
        existente.parar()


# livros


def biblioteca(contexto: Contexto) -> PastasBiblioteca:
    return PastasBiblioteca.do_home(contexto.home)


@dataclass(frozen=True)
class ResultadoAdicao:
    nome: str
    novo: bool = False
    erro: str = ''


def arquivos_da_pasta(pasta: Path) -> list[Path]:
    return sorted(p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() in EXTENSOES)


def adicionar_livros(
    opcoes: Opcoes,
    arquivos: list[Path],
    *,
    disciplina: str | None = None,
    concursos: list[str] | tuple[str, ...] = (),
    ao_mudar: Callable[[], None] | None = None,
) -> list[ResultadoAdicao]:
    """Copia os livros para a biblioteca e começa a leitura (e o envio) em segundo plano."""
    resultados = []
    for arquivo in arquivos:
        try:
            if opcoes.dry_run:
                from concursos.livros.validacao import validar

                validar(arquivo)
                opcoes.saida(f'{arquivo.name}: entraria na biblioteca')
                resultados.append(ResultadoAdicao(arquivo.name, True))
                continue
            adicao = fila.adicionar(
                biblioteca(opcoes.contexto), arquivo, disciplina=disciplina, concursos=concursos
            )
        except ErroDoUsuario as erro:
            resultados.append(ResultadoAdicao(arquivo.name, erro=f'{erro.causa} ({erro.dica})'))
            continue
        if not adicao.novo:
            opcoes.saida(f'{arquivo.name}: este livro já está na sua biblioteca')
        resultados.append(ResultadoAdicao(arquivo.name, adicao.novo))
    if not opcoes.dry_run and any(not r.erro for r in resultados):
        iniciar_trabalho(opcoes.contexto, ao_mudar)
    return resultados


def listar_livros(contexto: Contexto) -> list[Livro]:
    pastas_bib = biblioteca(contexto)
    if not pastas_bib.banco.exists():
        return []
    conexao = fila.conectar(pastas_bib)
    try:
        return fila.listar(conexao)
    finally:
        conexao.close()


def situacao_do_livro(livro: Livro, preparado: bool = True) -> str:
    """O texto da etapa do livro para a tela."""
    match livro.estado:
        case EstadoLivro.NA_FILA:
            return 'Na fila'
        case EstadoLivro.LENDO:
            return f'Lendo página {livro.pagina} de {livro.paginas}' if livro.paginas else 'Lendo'
        case EstadoLivro.LIDO:
            return 'Pronto para buscar; esperando o open-notebook' if preparado else 'Pronto para buscar'
        case EstadoLivro.ENVIANDO:
            return 'Preparando para perguntas'
        case EstadoLivro.PRONTO:
            return 'Pronto para perguntas'
        case _:
            return livro.erro or 'Não foi possível ler este arquivo.'


def _cliente_se_preparado(contexto: Contexto) -> ClienteOpenNotebook | None:
    if not situacao_do_estudo(contexto).preparado:
        return None
    try:
        return cliente_gerenciado(contexto)
    except ErroDoAmbiente as erro:
        logger.warning('open-notebook: %s', erro.causa)
        return None


def remover_livro(contexto: Contexto, sha: str) -> Livro | None:
    """Tira o livro do open-notebook (se abrir), do índice e da pasta."""
    cliente = _cliente_se_preparado(contexto)
    try:
        return envio.remover_livro(cliente, biblioteca(contexto), sha)
    except OpenNotebookIndisponivelError as erro:
        logger.warning('open-notebook: %s; o livro sai só da biblioteca local', erro.causa)
        return envio.remover_livro(None, biblioteca(contexto), sha)


def mudar_disciplina(contexto: Contexto, sha: str, disciplina: str) -> Livro | None:
    cliente = _cliente_se_preparado(contexto)
    try:
        return envio.mudar_disciplina(cliente, biblioteca(contexto), sha, disciplina)
    except OpenNotebookIndisponivelError as erro:
        logger.warning('open-notebook: %s; a disciplina muda lá na próxima vez', erro.causa)
        return envio.mudar_disciplina(None, biblioteca(contexto), sha, disciplina)


@dataclass
class _Trabalho:
    """A leitura e o envio dos livros, numa thread por pasta global."""

    contexto: Contexto
    ao_mudar: list[Callable[[], None]]
    fila: fila.Fila
    thread: threading.Thread | None = None
    pedido: threading.Event = None  # type: ignore[assignment]

    def avisar(self) -> None:
        for chamada in list(self.ao_mudar):
            try:
                chamada()
            except Exception:
                logger.exception('falha ao avisar a mudança dos livros')

    def rodar(self) -> None:
        while True:
            self.pedido.clear()
            try:
                self.fila.processar()
                self._enviar()
            except Exception:
                logger.exception('falha no trabalho dos livros')
            with _trava:
                if not self.pedido.is_set():
                    self.thread = None
                    return

    def _enviar(self) -> None:
        cliente = _cliente_se_preparado(self.contexto)
        if cliente is None:
            return
        pastas_bib = biblioteca(self.contexto)
        limite = time.monotonic() + ESPERA_MAXIMA_ENVIO
        while time.monotonic() < limite:
            relatorio = envio.processar_envios(cliente, pastas_bib)
            if relatorio.enviados or relatorio.prontos:
                self.avisar()
            if relatorio.falhas or not any(
                livro.estado is EstadoLivro.ENVIANDO for livro in listar_livros(self.contexto)
            ):
                return
            supervisor(self.contexto).usar()
            time.sleep(INTERVALO_CONFERENCIA)


def iniciar_trabalho(contexto: Contexto, ao_mudar: Callable[[], None] | None = None) -> None:
    """Lê os livros na fila e envia os lidos; chamado ao adicionar e ao abrir a tela de livros."""
    with _trava:
        trabalho = _trabalhos.get(contexto.home)
        if trabalho is None:
            trabalho = _Trabalho(contexto, [], fila.Fila(biblioteca(contexto)), pedido=threading.Event())
            trabalho.fila.ao_mudar.append(trabalho.avisar)
            atexit.register(trabalho.fila.encerrar)
            _trabalhos[contexto.home] = trabalho
        if ao_mudar is not None and ao_mudar not in trabalho.ao_mudar:
            trabalho.ao_mudar.append(ao_mudar)
        trabalho.pedido.set()
        if trabalho.thread is None:
            trabalho.thread = threading.Thread(target=trabalho.rodar, name='livros', daemon=True)
            trabalho.thread.start()


def esperar_trabalho(contexto: Contexto, timeout: float | None = None) -> None:
    trabalho = _trabalhos.get(contexto.home)
    thread = trabalho.thread if trabalho is not None else None
    if thread is not None:
        thread.join(timeout)


def concursos_do_projeto(contexto: Contexto) -> list[str]:
    return [pasta.name for pasta in listar_concursos(contexto.provas)] if contexto.provas.is_dir() else []


def disciplinas_sugeridas(contexto: Contexto) -> list[str]:
    """As opções do campo de disciplina: `Geral`, as da taxonomia e as dos livros já enviados."""
    nomes = {fila.DISCIPLINA_PADRAO}
    try:
        nomes |= {d.nome for d in carregar_taxonomia(contexto.taxonomia).values()}
    except (OSError, ValueError):
        logger.debug('taxonomia ilegível; disciplinas só dos livros', exc_info=True)
    nomes |= {livro.disciplina for livro in listar_livros(contexto)}
    return [fila.DISCIPLINA_PADRAO, *sorted(nomes - {fila.DISCIPLINA_PADRAO})]


# perguntar

TITULO_IA = 'Resposta da IA — confira nos trechos'
TEXTO_NADA = 'Não achei isso nos seus livros. Tente outras palavras ou adicione livros.'
TEXTO_IA_LIVROS = (
    'Com esta opção, a sua pergunta e trechos dos seus livros vão para {provedor} escrever a resposta. '
    'Respostas da prova, notas e inscrição não saem do computador.'
)
LIMITE_TRECHOS = 12
TRECHOS_POR_LIVRO_CITADO = 2
MAXIMO_SUGESTOES = 4
TAMANHO_SUGESTAO = 40


@dataclass(frozen=True)
class TrechoEncontrado:
    """Um trecho para conferir: de um livro (com a página) ou de um relatório da análise (com a seção)."""

    nome: str
    texto: str
    caminho: Path
    pagina: int | None = None
    secao: str = ''

    @property
    def de_livro(self) -> bool:
        return self.pagina is not None


@dataclass(frozen=True)
class Resposta:
    trechos: list[TrechoEncontrado]
    resposta_ia: str | None = None
    livros_citados: tuple[str, ...] = ()
    avisos: tuple[str, ...] = ()


@dataclass(frozen=True)
class Sugestao:
    rotulo: str
    pergunta: str


def ia_nos_livros(contexto: Contexto) -> ConfiguracaoLlm | None:
    """A IA do usuário, se ele concordou em mandar trechos dos livros a ela."""
    configuracao = ler_configuracao_llm(contexto.config_global)
    if configuracao is None or not configuracao.consentimento_livros:
        return None
    return configuracao


def texto_ia_livros(contexto: Contexto) -> str | None:
    configuracao = ler_configuracao_llm(contexto.config_global)
    return TEXTO_IA_LIVROS.format(provedor=configuracao.provedor) if configuracao else None


def ligar_ia_nos_livros(contexto: Contexto, ligar: bool) -> None:
    gravar_consentimento_livros(contexto.config_global, ligar)


def ambiente_da_ia(contexto: Contexto) -> dict[str, str]:
    """As variáveis da IA para os processos do open-notebook; vazio sem consentimento ou sem chave."""
    configuracao = ia_nos_livros(contexto)
    if configuracao is None:
        return {}
    chave = None
    if configuracao.variavel_chave is not None:
        encontrada = obter_chave(configuracao, contexto.home)
        if encontrada is None:
            logger.warning('IA nos livros sem chave (%s); seguindo sem ela', configuracao.variavel_chave)
            return {}
        chave = encontrada[0]
    return perguntas.ambiente_da_ia(configuracao, chave)


def _modelo_da_ia(cliente: ClienteOpenNotebook, configuracao: ConfiguracaoLlm) -> str:
    provedor = perguntas.provedor_do_modelo(configuracao)
    for modelo in cliente.listar_modelos('language'):
        if modelo.get('name') == configuracao.modelo and modelo.get('provider') == provedor:
            return modelo['id']
    return cliente.criar_modelo(configuracao.modelo, provedor, 'language')['id']


def _livros_apontados(
    cliente: ClienteOpenNotebook, pergunta: str, livros: list[Livro], por_source: dict[str, Livro]
) -> list[str]:
    notebooks = sorted({livro.notebook_id for livro in livros if livro.notebook_id})
    if not notebooks:
        return []
    resultados = cliente.buscar_vetorial(pergunta, notebooks) + cliente.buscar_texto(pergunta, notebooks)
    shas = []
    for resultado in resultados:
        livro = por_source.get(
            str(resultado.get('parent_id') or resultado.get('id') or '').removeprefix('source:')
        )
        if livro is not None and livro.sha not in shas:
            shas.append(livro.sha)
    return shas


def termos_do_dicionario(contexto: Contexto, pergunta: str) -> list[str]:
    """Os termos do dicionário de temas que a pergunta menciona, em OR na busca; dicionário inválido não
    impede a busca."""
    try:
        return expandir_consulta(dicionario_do_projeto(contexto), pergunta)
    except ErroDoUsuario as erro:
        logger.warning('dicionário de temas: %s', erro.causa)
        return []


def _trechos_dos_livros(
    contexto: Contexto, pergunta: str, livros: list[Livro], primeiro: list[str]
) -> list[TrechoEncontrado]:
    pastas_bib = biblioteca(contexto)
    if not pastas_bib.banco.exists() or not livros:
        return []
    por_sha = {livro.sha: livro for livro in livros}
    conexao = indice.abrir(pastas_bib.banco)
    try:
        achados = [
            trecho
            for sha in primeiro
            if sha in por_sha
            for trecho in indice.localizar_trechos(conexao, sha, pergunta, TRECHOS_POR_LIVRO_CITADO)
        ]
        vistos = {(t.sha, t.pagina) for t in achados}
        achados += [
            t
            for t in indice.buscar(
                conexao,
                pergunta,
                shas=list(por_sha),
                limite=LIMITE_TRECHOS,
                termos_extra=termos_do_dicionario(contexto, pergunta),
            )
            if (t.sha, t.pagina) not in vistos
        ]
    finally:
        conexao.close()
    return [
        TrechoEncontrado(por_sha[t.sha].nome, t.trecho, por_sha[t.sha].arquivo(pastas_bib), pagina=t.pagina)
        for t in achados[:LIMITE_TRECHOS]
    ]


def _pasta_das_analises(contexto: Contexto) -> Path | None:
    try:
        return pasta_do_candidato(contexto)
    except ErroDoUsuario as erro:
        logger.warning('análises: %s', erro.causa)
        return None


def _trechos_das_analises(contexto: Contexto, pergunta: str) -> list[TrechoEncontrado]:
    pasta = _pasta_das_analises(contexto)
    if pasta is None:
        return []
    return [
        TrechoEncontrado(achado.arquivo.name, achado.trecho, achado.arquivo, secao=achado.secao)
        for achado in perguntas.buscar_nas_analises(pasta, pergunta)
    ]


def perguntar(
    opcoes: Opcoes,
    pergunta: str,
    *,
    onde: OndeProcurar = OndeProcurar.LIVROS,
    disciplina: str | None = None,
) -> Resposta:
    """Os trechos com página que respondem à pergunta e, com a IA consentida, a resposta escrita por ela.

    O open-notebook aponta os livros (busca por sentido e por texto); o índice local acha o trecho e a
    página. Com o open-notebook fora, só o índice local."""
    pergunta = ' '.join(pergunta.split())
    if not pergunta:
        raise ErroDoUsuario('a pergunta está vazia', 'escreva o que quer encontrar nos seus livros')
    contexto = opcoes.contexto
    avisos: list[str] = []
    trechos: list[TrechoEncontrado] = []
    resposta_ia = None
    citados: list[str] = []
    if onde in {OndeProcurar.LIVROS, OndeProcurar.TUDO}:
        livros = [
            livro
            for livro in listar_livros(contexto)
            if livro.estado is not EstadoLivro.ERRO and (not disciplina or livro.disciplina == disciplina)
        ]
        apontados: list[str] = []
        cliente = _cliente_se_preparado(contexto) if livros else None
        if cliente is not None:
            por_source = perguntas.por_source(envio.livros_por_source(biblioteca(contexto)))
            try:
                apontados = _livros_apontados(cliente, pergunta, livros, por_source)
                configuracao = ia_nos_livros(contexto)
                if configuracao is not None and opcoes.rede:
                    resposta = cliente.perguntar(pergunta, _modelo_da_ia(cliente, configuracao))
                    texto = resposta.get('answer') or ''
                    citados_shas = [por_source[s].sha for s in perguntas.citacoes(texto) if s in por_source]
                    citados = [livro.nome for livro in livros if livro.sha in citados_shas]
                    resposta_ia = perguntas.sem_citacoes(texto) or None
                    apontados = list(dict.fromkeys([*citados_shas, *apontados]))
            except OpenNotebookIndisponivelError as erro:
                logger.warning('open-notebook: %s; buscando só nos seus livros', erro.causa)
                avisos.append(TEXTO_FORA)
        elif livros and situacao_do_estudo(contexto).preparado:
            avisos.append(TEXTO_FORA)
        trechos += _trechos_dos_livros(contexto, pergunta, livros, apontados)
    if onde in {OndeProcurar.ANALISES, OndeProcurar.TUDO}:
        trechos += _trechos_das_analises(contexto, pergunta)
    if not trechos and resposta_ia is None:
        avisos.append(TEXTO_NADA)
    return Resposta(trechos, resposta_ia, tuple(citados), tuple(avisos))


def sugestoes_de_pergunta(contexto: Contexto) -> list[Sugestao]:
    """Uma pergunta por tópico fraco da última análise do candidato."""
    pasta = _pasta_das_analises(contexto)
    if pasta is None or not contexto.provas.is_dir():
        return []
    limiar = configuracao_do_projeto(contexto).limiar_topico_baixo
    fracos, _ = topicos_fracos(curto(contexto.provas, contexto.raiz), pasta, contexto.taxonomia, limiar)
    sugestoes = []
    for linha in fracos.head(MAXIMO_SUGESTOES).itertuples():
        topico = str(linha.topico)
        consulta = consultas_do_topico(topico)[0]
        sugestoes.append(
            Sugestao(f'Revisar {abreviar(consulta, TAMANHO_SUGESTAO)} nos seus livros', consulta)
        )
    return sugestoes
