import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from concursos.concurso_config import ARQUIVO_CONFIG, ConcursoConfig, ProvaConfig
from concursos.deteccao import ArquivoDetectado, Papel, arquivo_do_sistema, classificar_arquivo, normalizar
from concursos.gabarito import GabaritoInvalidoError, cargo_cebraspe, carregar_gabarito
from concursos.modelo import Pontuacao, Resultado

logger = logging.getLogger(__name__)

PASTA_HISTORICO = 'historico'
ARQUIVO_DIFF = 'diff_gabarito.csv'
COLUNAS_DIFF = [
    'prova',
    'questao',
    'gabarito_preliminar',
    'gabarito_definitivo',
    'mudanca',
    'resposta',
    'acerto_antes',
    'acerto_depois',
]
_COLUNAS_PRELIMINAR = {'prova', 'questao', 'gabarito', 'anulada'}


@dataclass(frozen=True)
class Troca:
    prova: str
    anterior: str
    novo: str


@dataclass(frozen=True)
class Pendencias:
    trocas: tuple[Troca, ...] = ()
    motivos: tuple[str, ...] = ()


def verificar(config: ConcursoConfig) -> Pendencias:
    """Procura gabaritos definitivos para provas preliminares e arquivos não cadastrados na pasta.

    Troca só quando cada prova tem um único candidato e não há outro arquivo pendente; qualquer outro caso
    vira motivo de concurso desatualizado.
    """
    instrucao = f'rode `concursos adicionar {config.pasta}`'
    preliminares = [p for p in config.provas if p.gabarito.status == 'preliminar']
    candidatos: dict[str, list[str]] = {p.chave: [] for p in preliminares}
    motivos = []
    for prova in preliminares:
        if (
            classificar_arquivo(config.caminho(prova.gabarito.arquivo), config.pasta).status_gabarito
            == 'definitivo'
        ):
            candidatos[prova.chave].append(prova.gabarito.arquivo)
    for caminho in _nao_cadastrados(config):
        detectado = classificar_arquivo(caminho, config.pasta)
        nome = caminho.relative_to(config.pasta).as_posix()
        if detectado.papel is Papel.IGNORADO:
            continue
        if detectado.papel is not Papel.GABARITO or detectado.status_gabarito != 'definitivo':
            motivos.append(f'{nome}: arquivo não cadastrado ({detectado.papel}); {instrucao}')
            continue
        provas = [p for p in preliminares if _corresponde_a_prova(config, p, detectado)]
        if not provas:
            motivos.append(
                f'{nome}: gabarito definitivo não corresponde a nenhuma prova com gabarito preliminar '
                f'(banca, cargo/tipo e faixa de itens); {instrucao}'
            )
        for prova in provas:
            candidatos[prova.chave].append(nome)

    trocas = []
    for prova in preliminares:
        nomes = candidatos[prova.chave]
        if len(nomes) > 1:
            motivos.append(
                f'prova {prova.chave}: mais de um gabarito definitivo ({", ".join(nomes)}); {instrucao}'
            )
        elif nomes:
            trocas.append(Troca(prova.chave, prova.gabarito.arquivo, nomes[0]))
    return Pendencias(() if motivos else tuple(trocas), tuple(motivos))


def trocar_gabaritos(config: ConcursoConfig, trocas: tuple[Troca, ...], destino: Path) -> None:
    """Guarda as saídas atuais no histórico e atualiza o concurso.yaml."""
    _guardar_saidas(destino)
    _atualizar_config(config, trocas)
    for troca in trocas:
        logger.info(
            '%s: gabarito definitivo %s substitui %s (prova %s)',
            config.nome,
            troca.novo,
            troca.anterior,
            troca.prova,
        )


def questoes_preliminares(destino: Path) -> pd.DataFrame | None:
    """Tabela de questões do snapshot mais antigo do histórico, feito antes da primeira troca de gabarito."""
    snapshots = sorted((destino / PASTA_HISTORICO).glob('*/questoes.csv'))
    if not snapshots:
        return None
    tabela = pd.read_csv(snapshots[0], keep_default_na=False, dtype={'prova': str, 'gabarito': str})
    if not set(tabela.columns) >= _COLUNAS_PRELIMINAR:
        logger.warning(
            '%s: snapshot sem gabarito por questão; o diff de gabarito não será gerado', snapshots[0]
        )
        return None
    return tabela


def diff_gabarito(preliminar: pd.DataFrame, atual: pd.DataFrame) -> pd.DataFrame:
    """Questões alteradas ou anuladas entre o gabarito preliminar e o definitivo, com as respostas atuais."""
    chaves = ['prova', 'questao']
    antes = _normalizar_gabarito(preliminar[[*chaves, 'gabarito', 'anulada']])
    depois = _normalizar_gabarito(atual[[*chaves, 'gabarito', 'anulada', 'resultado', 'resposta']])
    juntos = antes.merge(depois, on=chaves, suffixes=('_antes', '_depois'))
    juntos = juntos[
        (juntos['gabarito_antes'] != juntos['gabarito_depois'])
        | (juntos['anulada_antes'] != juntos['anulada_depois'])
    ]
    anulada = juntos['anulada_depois'] & ~juntos['anulada_antes']
    resposta = juntos['resposta'].fillna('')
    acerto_antes = juntos['anulada_antes'] | ((resposta != '') & (resposta == juntos['gabarito_antes']))
    return pd.DataFrame(
        {
            'prova': juntos['prova'],
            'questao': juntos['questao'],
            'gabarito_preliminar': juntos['gabarito_antes'],
            'gabarito_definitivo': juntos['gabarito_depois'],
            'mudanca': anulada.map({True: 'anulada', False: 'alterada'}),
            'resposta': resposta,
            'acerto_antes': acerto_antes,
            'acerto_depois': juntos['resultado'] == Resultado.ACERTO,
        },
        columns=COLUNAS_DIFF,
    )


def impacto(diff: pd.DataFrame, pontuacao: Pontuacao) -> tuple[int, int]:
    """Variação de (acertos, nota líquida) causada pelas questões do diff."""
    respondida = diff['resposta'].astype(str) != ''
    acertos = int(diff['acerto_depois'].sum() - diff['acerto_antes'].sum())
    if pontuacao is not Pontuacao.CEBRASPE:
        return acertos, acertos
    erros = int((respondida & ~diff['acerto_depois']).sum() - (respondida & ~diff['acerto_antes']).sum())
    return acertos, acertos - erros


def _normalizar_gabarito(tabela: pd.DataFrame) -> pd.DataFrame:
    return tabela.assign(
        gabarito=tabela['gabarito'].fillna('').astype(str), anulada=tabela['anulada'].astype(bool)
    )


def _nao_cadastrados(config: ConcursoConfig) -> list[Path]:
    referenciados = {*config.ignorar}
    for prova in config.provas:
        referenciados |= {prova.gabarito.arquivo, prova.caderno}
    if config.edital is not None:
        referenciados |= {*config.edital.documentos, config.edital.manual}
    referenciados |= {config.respostas_arquivo, config.folha and config.folha.arquivo}
    referenciados.add(config.resultado_oficial and config.resultado_oficial.arquivo)
    return [
        caminho
        for caminho in sorted(config.pasta.rglob('*'))
        if caminho.is_file()
        and not arquivo_do_sistema(caminho, config.pasta)
        and caminho.relative_to(config.pasta).as_posix() not in referenciados
    ]


def _corresponde_a_prova(config: ConcursoConfig, prova: ProvaConfig, detectado: ArquivoDetectado) -> bool:
    if detectado.banca not in (None, config.banca):
        return False
    if config.banca == 'cebraspe':
        cargo = cargo_cebraspe(detectado.texto)
        if cargo and config.cargo and normalizar(cargo) != normalizar(config.cargo):
            return False
    try:
        itens = carregar_gabarito(
            detectado.caminho, config.formato, config.banca, config.cargo, config.tipo
        ).itens
    except GabaritoInvalidoError:
        return False
    return [item.questao for item in itens] == list(prova.questoes)


def _guardar_saidas(destino: Path) -> None:
    if not (destino / 'relatorio.md').exists():
        logger.info('%s: sem análise com o gabarito preliminar; o diff de gabarito não será gerado', destino)
        return
    alvo = destino / PASTA_HISTORICO / f'{datetime.now():%Y-%m-%dT%H-%M-%S}_gabarito_preliminar'
    shutil.copytree(
        destino, alvo, ignore=shutil.ignore_patterns(PASTA_HISTORICO, 'depuracao', '.manifesto.json')
    )
    logger.info('Saídas com o gabarito preliminar guardadas em %s', alvo)


def _atualizar_config(config: ConcursoConfig, trocas: tuple[Troca, ...]) -> None:
    caminho = config.pasta / ARQUIVO_CONFIG
    dados = yaml.safe_load(caminho.read_text(encoding='utf-8'))
    data = datetime.now().date().isoformat()
    for troca in trocas:
        dados['provas'][troca.prova]['gabarito'] = {'arquivo': troca.novo, 'status': 'definitivo'}
        if troca.anterior != troca.novo:
            dados['ignorar'] = [*(dados.get('ignorar') or []), troca.anterior]
        evento = {
            'data': data,
            'tipo': 'gabarito_definitivo',
            'prova': troca.prova,
            'anterior': troca.anterior,
            'novo': troca.novo,
        }
        dados['historico'] = [*(dados.get('historico') or []), evento]
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=False), encoding='utf-8')
