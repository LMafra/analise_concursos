import contextlib
import filecmp
import shutil
import tempfile
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from concursos.analytics.nome_concurso import titulo_pelo_edital
from concursos.analytics.regras_edital import Identificacao, identificar_edital
from concursos.aplicacao.integracoes import interesses as ler_interesses
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.projeto import concurso_alvo, concurso_do_arquivo, exigir_provas
from concursos.cadastro import cadastrar
from concursos.candidatos import adicionar_arquivo, gravar_perfil_global, pasta_do_candidato, slug
from concursos.concurso_config import ARQUIVO_CONFIG, ConfiguracaoInvalidaError, gravar_dados, ler_dados
from concursos.config.contexto import Contexto
from concursos.deteccao import ArquivoDetectado, Papel, classificar_arquivo
from concursos.erros import ErroDoUsuario
from concursos.integracoes.sincronizacao_pci import Interesses
from concursos.respostas import RespostasInvalidasError, ler_respostas_csv
from concursos.texto import extrair_paginas

PAPEIS_DO_CANDIDATO = frozenset({Papel.RESPOSTAS, Papel.FOLHA})
PASTA_ENVIOS = 'envios'
ENVIO_ABANDONADO = 24 * 60 * 60
ARQUIVO_DIGITADAS = 'respostas.csv'


@dataclass(frozen=True)
class FolhaManual:
    questoes: list[int]
    alternativas: list[str]


def cadastrar_pasta(opcoes: Opcoes, caminho: Path, pci: int | None = None) -> int:
    """Cadastra a pasta de um concurso (o `concurso.yaml`), com as perguntas de `opcoes.interacao`."""
    registro = ler_interesses(opcoes.contexto) if pci is not None else None
    if registro is not None and registro.obter(pci) is None:
        raise ErroDoUsuario(
            f'o concurso {pci} do PCI não está nos interesses',
            f'registre antes com `concurso-analise discover --register {pci}`',
        )
    if opcoes.dry_run:
        vinculo = f' e vincularia ao concurso {pci} do PCI' if pci is not None else ''
        opcoes.saida(f'cadastraria {caminho} (concurso.yaml){vinculo}')
        return 0
    if not cadastrar(caminho, opcoes.interacao_ou_automatica()):
        return 1
    if registro is not None and pci is not None:
        vincular_ao_pci(opcoes, caminho, registro, pci)
    return 0


def adicionar_respostas(
    opcoes: Opcoes, caminho: Path, candidato: str | None = None, concurso: str | None = None
) -> Path | None:
    """Copia a folha ou as respostas de um candidato para `provas/<concurso>/candidatos/<slug>/`."""
    contexto = opcoes.contexto
    if not caminho.is_file():
        raise ErroDoUsuario(f'arquivo não encontrado: {caminho}', 'confira o caminho do arquivo de respostas')
    nome = candidato or contexto.candidato
    if not nome:
        raise ErroDoUsuario(
            'falta dizer de qual candidato é o arquivo', 'rode de novo com --candidate <nome>'
        )
    exigir_provas(contexto.provas)
    pasta = concurso_do_arquivo(contexto.provas, caminho, concurso)
    if opcoes.dry_run:
        opcoes.saida(f'copiaria {caminho} para {pasta_do_candidato(pasta, slug(nome))}')
        return None
    destino = adicionar_arquivo(pasta, caminho, nome)
    gravar_perfil_global(contexto.home, nome)
    opcoes.saida(f'{caminho.name} copiado para {destino}')
    datar_simulado(opcoes, pasta)
    return destino


def pasta_do_concurso(contexto: Contexto, nome: str) -> Path:
    try:
        return contexto.provas / slug(nome)
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(
            f'nome de concurso inválido: {nome!r}', 'use letras e números, ex.: tcu_2025'
        ) from erro


def nova_pasta_de_envio(contexto: Contexto) -> Path:
    """Onde os arquivos soltos na GUI esperam a confirmação do papel: em `.concurso/`, fora do git.

    Envios abandonados há mais de um dia são apagados, porque guardam cópias de folhas e provas."""
    raiz = contexto.projeto / PASTA_ENVIOS
    raiz.mkdir(parents=True, exist_ok=True)
    for antigo in raiz.iterdir():
        if antigo.is_dir() and time.time() - antigo.stat().st_mtime > ENVIO_ABANDONADO:
            shutil.rmtree(antigo, ignore_errors=True)
    return Path(tempfile.mkdtemp(dir=raiz))


def detectar_envio(pasta: Path) -> list[ArquivoDetectado]:
    return [classificar_arquivo(caminho, pasta) for caminho in sorted(pasta.iterdir()) if caminho.is_file()]


@dataclass(frozen=True)
class NomeDetectado:
    titulo: str
    origem: str


def identificar_envio(papeis: Mapping[Path, Papel]) -> Identificacao | None:
    """A identificação rápida do edital enviado (sem OCR nem IA); None sem edital legível."""
    editais = sorted(a for a, p in papeis.items() if p is Papel.EDITAL)
    documentos = {}
    for arquivo in editais:
        try:
            documentos[arquivo.name] = extrair_paginas(arquivo, ocr=False)
        except (OSError, UnicodeDecodeError, ValueError):
            continue
    return identificar_edital(documentos) if documentos else None


def nome_detectado(papeis: Mapping[Path, Papel]) -> NomeDetectado | None:
    identificacao = identificar_envio(papeis)
    titulo = titulo_pelo_edital(asdict(identificacao)) if identificacao else None
    return NomeDetectado(titulo, 'do edital') if titulo else None


def pasta_automatica(contexto: Contexto, identificacao: Identificacao | None) -> Path:
    """`sigla_ano` pelo edital (`tcu_2025`, depois `tcu_2025_2`); sem sigla, `concurso_AAAAMMDD`."""
    base = f'concurso_{date.today():%Y%m%d}'
    if identificacao is not None and identificacao.sigla.valor:
        partes = [identificacao.sigla.valor, identificacao.ano.valor]
        with contextlib.suppress(ConfiguracaoInvalidaError):
            base = slug(' '.join(str(p) for p in partes if p))
    pasta, numero = contexto.provas / base, 2
    while pasta.exists():
        pasta, numero = contexto.provas / f'{base}_{numero}', numero + 1
    return pasta


def corrigir_titulo(opcoes: Opcoes, concurso: str, titulo: str) -> None:
    """Grava o nome escolhido pelo usuário (`titulo`), que vence o do edital; vazio, volta ao do edital."""
    pasta = concurso_alvo(opcoes.contexto, concurso).pasta
    dados = ler_dados(pasta)
    novos = {k: v for k, v in dados.items() if k != 'titulo'}
    if titulo.strip():
        novos['titulo'] = titulo.strip()
    if opcoes.dry_run:
        opcoes.saida(f'gravaria o nome {titulo.strip() or "do edital"} em {pasta.name}')
        return
    if novos != dados:
        gravar_dados(pasta, novos)


def cadastrar_envio(
    opcoes: Opcoes, concurso: str | None, papeis: Mapping[Path, Papel], candidato: str | None
) -> Path | None:
    """Copia para o concurso os arquivos da prova e cadastra com os papéis confirmados; as respostas e a
    folha vão para a pasta do candidato. Sem `concurso`, a pasta é a automática, pelo edital. Recusado ou
    com falha, a pasta fica como estava; devolve None se o usuário recusar."""
    contexto = opcoes.contexto
    if concurso is None:
        pasta = pasta_automatica(contexto, identificar_envio(papeis))
    else:
        pasta = pasta_do_concurso(contexto, concurso)
    da_prova = {a: p for a, p in papeis.items() if p not in PAPEIS_DO_CANDIDATO | {Papel.IGNORADO}}
    do_candidato = sorted(a for a, p in papeis.items() if p in PAPEIS_DO_CANDIDATO)
    nome = candidato or contexto.candidato
    if do_candidato and not nome:
        raise ErroDoUsuario(
            'falta dizer de qual candidato são as respostas', 'escreva o nome do candidato antes de cadastrar'
        )
    nova = not pasta.exists()
    copiados = _copiar(list(da_prova), pasta)
    if da_prova or not (pasta / ARQUIVO_CONFIG).exists():
        try:
            gravou = cadastrar(
                pasta, opcoes.interacao_ou_automatica(), {a.name: p for a, p in da_prova.items()}
            )
        except BaseException:
            _desfazer(copiados, pasta, nova)
            raise
        if not gravou:
            _desfazer(copiados, pasta, nova)
            return None
    for arquivo in do_candidato:
        adicionar_respostas(opcoes, arquivo, nome, pasta.name)
    return pasta


def folha_manual(contexto: Contexto, concurso: str) -> FolhaManual:
    config = concurso_alvo(contexto, concurso)
    return FolhaManual(
        [q for prova in config.provas for q in prova.questoes],
        sorted(config.formato.letras(config.n_alternativas)),
    )


def gravar_respostas_digitadas(
    opcoes: Opcoes, concurso: str, candidato: str, respostas: Mapping[int, str]
) -> Path:
    """Grava o `respostas.csv` (`questao,alternativa`) na pasta do candidato; as questões em branco ficam
    fora do arquivo, e a leitura as conta como branco."""
    config = concurso_alvo(opcoes.contexto, concurso)
    linhas = ['questao,alternativa'] + [
        f'{questao},{letra.strip().upper()}' for questao, letra in sorted(respostas.items()) if letra.strip()
    ]
    conteudo = ('\n'.join(linhas) + '\n').encode('utf-8')
    try:
        ler_respostas_csv(
            conteudo,
            config.formato,
            [q for prova in config.provas for q in prova.questoes],
            ARQUIVO_DIGITADAS,
            config.n_alternativas,
        )
    except RespostasInvalidasError as erro:
        raise ErroDoUsuario(
            str(erro), 'use só as alternativas da prova e deixe em branco a questão que não respondeu'
        ) from erro
    with tempfile.TemporaryDirectory() as temporaria:
        arquivo = Path(temporaria) / ARQUIVO_DIGITADAS
        arquivo.write_bytes(conteudo)
        destino = adicionar_respostas(opcoes, arquivo, candidato, config.pasta.name)
    return (destino or pasta_do_candidato(config.pasta, slug(candidato))) / ARQUIVO_DIGITADAS


def _copiar(arquivos: list[Path], pasta: Path) -> list[Path]:
    for arquivo in arquivos:
        destino = pasta / arquivo.name
        if destino.exists() and not filecmp.cmp(arquivo, destino, shallow=False):
            raise ErroDoUsuario(
                f'já existe outro {arquivo.name} em {pasta}',
                'renomeie o arquivo novo ou apague o antigo da pasta do concurso',
            )
    pasta.mkdir(parents=True, exist_ok=True)
    copiados = []
    for arquivo in arquivos:
        destino = pasta / arquivo.name
        if not destino.exists():
            shutil.copy2(arquivo, destino)
            copiados.append(destino)
    return copiados


def _desfazer(copiados: list[Path], pasta: Path, nova: bool) -> None:
    if nova:
        shutil.rmtree(pasta, ignore_errors=True)
        return
    for caminho in copiados:
        caminho.unlink(missing_ok=True)


def datar_simulado(opcoes: Opcoes, pasta: Path) -> None:
    """No simulado, `data_prova` é o dia em que o candidato o resolveu, não o ano da prova original."""
    dados = ler_dados(pasta)
    if not dados.get('simulado') or dados.get('data_prova'):
        return
    hoje = date.today().isoformat()
    data = hoje
    if opcoes.interacao is not None:
        data = opcoes.interacao.perguntar('Em que dia você resolveu o simulado? (aaaa-mm-dd)', hoje) or hoje
    try:
        date.fromisoformat(data)
    except ValueError as erro:
        raise ErroDoUsuario(f'data inválida: {data}', 'use aaaa-mm-dd, ex.: 2026-11-05') from erro
    gravar_dados(pasta, {**dados, 'data_prova': data})
    opcoes.saida(f'{pasta.name}: simulado datado de {data}')


def vincular_ao_pci(opcoes: Opcoes, pasta: Path, registro: Interesses, identificador: int) -> None:
    item = registro.vincular(identificador, pasta.resolve().name)
    registro.gravar()
    dados = ler_dados(pasta)
    vinculo = {'id': identificador, 'titulo': item.get('titulo', ''), 'link': item.get('link', '')}
    if dados.get('pci') != vinculo:
        gravar_dados(pasta, {**dados, 'pci': vinculo})
    opcoes.saida(f'{pasta.name} vinculado ao concurso {identificador} do PCI ({item.get("titulo", "")})')
