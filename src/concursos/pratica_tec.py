"""Prática no TEC: lê as exportações do tec-erros, liga matéria e assunto à disciplina canônica e ao tópico do
edital do `concurso_alvo` e grava o desempenho em `analises/<candidato>/pratica/`.

As regras de mesclagem repetem as de `core/nucleo.js` do tec-erros (`docs/contrato.md` de lá)."""

import csv
import html
import io
import json
import logging
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import yaml

from concursos.analytics.consolidado import N_MINIMO_TOPICO
from concursos.analytics.taxonomia import DisciplinaCanonica
from concursos.arquivos import gravar_se_mudou
from concursos.assistente import Interacao
from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.config.contexto import ler_toml
from concursos.edital import ARQUIVO_EDITAL_ESTRUTURADO, Conhecimento, Disciplina, Edital, Topico
from concursos.modelo import ModoCaderno, OrigemErroTec
from concursos.topicos import NAO_MAPEADO, SCORE_BAIXO, chave_de_palavras, palavras_chave, sugerir_topicos

if TYPE_CHECKING:
    from concursos.analytics.dicionario_topicos import Dicionario

logger = logging.getLogger(__name__)

SECAO = 'pratica'
APP = 'tec-erros'
APP_ESTADO = 'tec-erros-caderno'
VERSAO = 1
ARQUIVO_ESTADO = 'caderno-estado.json'
ARQUIVO_ESCOLHAS = 'pratica_tec.yaml'
PASTA_PRATICA = 'pratica'
ARQUIVO_ERROS = 'erros_tec.csv'
ARQUIVO_CADERNOS = 'cadernos_tec.csv'
ARQUIVO_DESEMPENHO = 'desempenho_pratica_por_disciplina.csv'
ARQUIVO_REVISAO = 'revisao_aliases.csv'
ARQUIVO_RESUMO = 'resumo_pratica.md'
ARQUIVO_SIMULADO = 'simulado_tec.html'
MAXIMO_SIMULADO = 40
MAXIMO_SIMULADO_POR_TOPICO = 10
SEM_DISCIPLINA = 'Sem disciplina'
MAXIMO_REPETIDOS = 20
TAMANHO_DIGITAL = 300
FORA_DO_EDITAL = 'fora_do_edital'
NENHUM = 'nenhum'
OPCAO_NENHUM = 'não pertence a nenhum tópico'
OPCAO_DEPOIS = 'decidir depois'
OPCOES_MODO = {'registrar tudo': ModoCaderno.TUDO, 'só acompanhar daqui': ModoCaderno.DAQUI}
MAXIMO_OPCOES = 30

_CAMPOS_EXPORTACAO = {'app', 'v', 'em', 'dev', 'erros', 'cads'}
_CAMPOS_CONFIGURACAO = {'entrada_tec', 'candidato', 'open_notebook'}
_CAMPOS_TEXTO = ('mat', 'ass', 'cad', 'banca', 'orgao', 'ano', 'enun', 'marc', 'gab', 'prof', 'url')
_TOTAIS = ('res', 'ac', 'er')

COLUNAS_ERROS = [
    'id', 'v', 'primeira_data', 'ultima_data', 'origem', 'materia_tec', 'disciplina', 'assunto', 'topico',
    'banca', 'orgao', 'ano', 'caderno',
]  # fmt: skip
COLUNAS_CADERNOS = [
    'id', 'caderno', 'materia_tec', 'disciplina', 'modo', 'total', 'resolvidas', 'acertos', 'erros',
    'percentual', 'amostra_insuficiente',
]  # fmt: skip
COLUNAS_DESEMPENHO = [
    'disciplina', 'n', 'acertos', 'erros', 'percentual', 'amostra_insuficiente', 'cadernos',
    'erros_registrados', 'repetidos',
]  # fmt: skip
COLUNAS_REVISAO = ['assunto', 'disciplina', 'sugestao', 'score', 'topico']


class ExportacaoInvalidaError(ValueError):
    pass


@dataclass(frozen=True)
class ConfiguracaoPratica:
    entrada: Path
    candidato: str | None = None
    open_notebook: bool = False


def ler_configuracao(config_projeto: Path, raiz: Path) -> ConfiguracaoPratica | None:
    """A seção `[pratica]` do `config.toml` do projeto; sem ela, a prática fica de fora da análise."""
    secao = ler_toml(config_projeto).get(SECAO)
    if secao is None:
        return None
    if desconhecidos := sorted(set(secao) - _CAMPOS_CONFIGURACAO):
        raise ConfiguracaoInvalidaError(
            f'{config_projeto}: [pratica] campos desconhecidos {", ".join(desconhecidos)} '
            f'(use {", ".join(sorted(_CAMPOS_CONFIGURACAO))})'
        )
    entrada = secao.get('entrada_tec')
    if not isinstance(entrada, str) or not entrada.strip():
        raise ConfiguracaoInvalidaError(
            f'{config_projeto}: [pratica] entrada_tec é a pasta das exportações do TEC'
        )
    candidato = secao.get('candidato')
    if candidato is not None and (not isinstance(candidato, str) or not candidato.strip()):
        raise ConfiguracaoInvalidaError(f'{config_projeto}: [pratica] candidato deve ser o nome da subpasta')
    enviar = secao.get('open_notebook', False)
    if not isinstance(enviar, bool):
        raise ConfiguracaoInvalidaError(f'{config_projeto}: [pratica] open_notebook deve ser true ou false')
    caminho = Path(entrada).expanduser()
    return ConfiguracaoPratica(caminho if caminho.is_absolute() else raiz / caminho, candidato, enviar)


def normalizar(texto) -> str:
    decomposto = unicodedata.normalize('NFD', str(texto or ''))
    sem_acento = ''.join(c for c in decomposto if not 0x300 <= ord(c) <= 0x36F)
    return ' '.join(sem_acento.lower().split())


def impressao_digital(enunciado) -> str:
    return normalizar(enunciado)[:TAMANHO_DIGITAL]


def ler_exportacao(caminho: Path) -> tuple[dict, list[str]]:
    try:
        dados = json.loads(caminho.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ExportacaoInvalidaError(f'{caminho}: não é um JSON legível ({erro})') from erro
    if not isinstance(dados, dict) or dados.get('app') != APP:
        raise ExportacaoInvalidaError(f'{caminho}: não é um arquivo do tec-erros (campo app)')
    if dados.get('v') != VERSAO:
        raise ExportacaoInvalidaError(f'{caminho}: versão {dados.get("v")} do arquivo; esperada {VERSAO}')
    avisos = [
        f'{caminho}: campo desconhecido ignorado: {campo}'
        for campo in sorted(set(dados) - _CAMPOS_EXPORTACAO)
    ]
    return {
        'erros': dados.get('erros') or [],
        'cads': dados.get('cads') or [],
        'dev': dados.get('dev'),
    }, avisos


def _vazio(valor) -> bool:
    return valor is None or valor == '' or (isinstance(valor, list) and not valor)


def _contagem(ds: list[str]) -> int:
    return len(ds) or 1


def fundir(a: dict, b: dict) -> dict:
    r = dict(a)
    for campo in (*_CAMPOS_TEXTO, 'alts', 'fp'):
        if _vazio(r.get(campo)) and not _vazio(b.get(campo)):
            r[campo] = b[campo]
    if not _vazio(b.get('com')) and len(str(b['com'])) > len(str(r.get('com') or '')):
        r['com'] = b['com']
        if not _vazio(b.get('prof')):
            r['prof'] = b['prof']
    r['ds'] = sorted({d for d in [*(a.get('ds') or []), *(b.get('ds') or [])] if d})
    r['v'] = _contagem(r['ds'])
    tempo_real = OrigemErroTec.TEMPO_REAL.value
    r['origem'] = (
        tempo_real
        if tempo_real in (a.get('origem'), b.get('origem')) or r['ds']
        else OrigemErroTec.HISTORICO.value
    )
    if datas := sorted(d for d in (a.get('d'), b.get('d'), r['ds'][0][:10] if r['ds'] else '') if d):
        r['d'] = datas[0]
    if b.get('dev') and (not a.get('dev') or (b.get('d') and a.get('d') and b['d'] < a['d'])):
        r['dev'] = b['dev']
    if {**r, 't': a.get('t')} == {**a, 't': a.get('t')}:
        return a
    r['t'] = max(a.get('t') or 0, b.get('t') or 0)
    return r


def mesclar_erros(base: list[dict], novos: list[dict]) -> list[dict]:
    """Casa por `id` e, sem ele, pela impressão digital; a ordem é a da primeira vez em que cada erro apareceu."""
    lista = list(base)
    por_id = {r['id']: i for i, r in enumerate(lista)}
    por_digital = {r['fp']: i for i, r in enumerate(lista) if r.get('fp')}
    for original in novos:
        r = {'ds': [], **original}
        if not r.get('fp') and r.get('enun'):
            r['fp'] = impressao_digital(r['enun'])
        if not isinstance(r['ds'], list):
            r['ds'] = []
        i = por_id.get(r.get('id'), por_digital.get(r['fp']) if r.get('fp') else None)
        if i is None:
            r['v'] = _contagem(r['ds'])
            lista.append(r)
            i = len(lista) - 1
        else:
            lista[i] = fundir(lista[i], r)
        por_id[r.get('id')] = i
        if r.get('fp'):
            por_digital[r['fp']] = i
    return lista


def mesclar_cadernos(base: list[dict], novos: list[dict]) -> list[dict]:
    """O progresso fica na conta do TEC e não diminui: vence o de maior `res` e, no empate, o mais recente."""
    por_id = {c['id']: c for c in base}
    for c in novos:
        atual = por_id.get(c['id'])
        if (
            atual is None
            or c.get('res', 0) > atual.get('res', 0)
            or (c.get('res', 0) == atual.get('res', 0) and (c.get('t') or 0) > (atual.get('t') or 0))
        ):
            por_id[c['id']] = {**(atual or {}), **c}
    return list(por_id.values())


@dataclass
class Pratica:
    erros: list[dict] = field(default_factory=list)
    cadernos: list[dict] = field(default_factory=list)
    estado: dict = field(default_factory=dict)


def ler_entrada(pasta: Path) -> tuple[Pratica, list[str]]:
    """Todas as exportações da pasta, mescladas, e o `caderno-estado.json` (sugestões do `caderno.html`).

    Um arquivo inválido vira aviso e os outros seguem."""
    pratica, avisos = Pratica(), []
    for caminho in sorted(pasta.glob('*.json')) if pasta.is_dir() else []:
        if caminho.name == ARQUIVO_ESTADO:
            pratica.estado, aviso = _ler_estado(caminho)
            avisos += aviso
            continue
        try:
            dados, aviso = ler_exportacao(caminho)
        except ExportacaoInvalidaError as erro:
            avisos.append(f'prática: {erro}; arquivo ignorado')
            continue
        avisos += aviso
        pratica.erros = mesclar_erros(
            pratica.erros, [e for e in dados['erros'] if isinstance(e, dict) and e.get('id')]
        )
        pratica.cadernos = mesclar_cadernos(
            pratica.cadernos, [c for c in dados['cads'] if isinstance(c, dict) and c.get('id')]
        )
    removidos = set(pratica.estado.get('removidos') or [])
    pratica.erros = [
        e for e in pratica.erros if e['id'] not in removidos and f'fp:{e.get("fp")}' not in removidos
    ]
    return pratica, avisos


def _ler_estado(caminho: Path) -> tuple[dict, list[str]]:
    try:
        dados = json.loads(caminho.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erro:
        return {}, [f'prática: {caminho} ilegível ({erro}); as escolhas do caderno.html ficaram de fora']
    if not isinstance(dados, dict) or dados.get('app') != APP_ESTADO:
        return {}, [f'prática: {caminho} não é um estado do caderno.html (campo app)']
    return dados, []


@dataclass
class Escolhas:
    """O que foi decidido uma vez e vale para as próximas importações (`.concurso/pratica_tec.yaml`)."""

    aliases: dict[str, str | None] = field(default_factory=dict)
    materias: dict[str, str] = field(default_factory=dict)
    cadernos: dict[str, dict] = field(default_factory=dict)
    planilhas: dict[str, dict] = field(default_factory=dict)


def ler_escolhas(caminho: Path) -> Escolhas:
    if not caminho.exists():
        return Escolhas()
    try:
        dados = yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError as erro:
        raise ConfiguracaoInvalidaError(f'{caminho}: {erro}') from erro
    if not isinstance(dados, dict):
        raise ConfiguracaoInvalidaError(f'{caminho}: esperado um mapa com aliases, materias e cadernos')
    return Escolhas(
        dict(dados.get('aliases') or {}),
        dict(dados.get('materias') or {}),
        dict(dados.get('cadernos') or {}),
        dict(dados.get('planilhas') or {}),
    )


def gravar_escolhas(caminho: Path, escolhas: Escolhas) -> bool:
    if escolhas == Escolhas() and not caminho.exists():
        return False
    caminho.parent.mkdir(parents=True, exist_ok=True)
    dados = {'aliases': escolhas.aliases, 'materias': escolhas.materias, 'cadernos': escolhas.cadernos}
    if escolhas.planilhas:
        dados['planilhas'] = escolhas.planilhas
    return gravar_se_mudou(caminho, yaml.safe_dump(dados, allow_unicode=True, sort_keys=True))


def disciplina_da_materia(
    materia: str | None, taxonomia: dict[str, DisciplinaCanonica], materias: dict[str, str]
) -> str | None:
    """A disciplina canônica da matéria do TEC: um nome da taxonomia (sem diferença de acento e caixa) ou a
    escolha gravada em `materias`."""
    if not materia:
        return None
    if materia in materias:
        return materias[materia]
    if materia in taxonomia:
        return taxonomia[materia].nome
    chave = chave_de_palavras(materia)
    return next((d.nome for nome, d in taxonomia.items() if chave_de_palavras(nome) == chave), None)


def carregar_edital(pasta_concurso: Path) -> Edital | None:
    caminho = pasta_concurso / ARQUIVO_EDITAL_ESTRUTURADO
    if not caminho.exists():
        return None
    dados = json.loads(caminho.read_text(encoding='utf-8'))
    return Edital(
        dados.get('fonte', ''),
        dados.get('cargo'),
        tuple(
            Conhecimento(
                c['nome'],
                tuple(
                    Disciplina(
                        d['nome'],
                        tuple(
                            Topico(t.get('numero', ''), t['nome'], t.get('descricao') or t['nome'])
                            for t in d.get('topicos', [])
                        ),
                    )
                    for d in c.get('disciplinas', [])
                ),
            )
            for c in dados.get('conhecimentos', [])
        ),
    )


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


@dataclass
class Pendencia:
    assunto: str
    disciplina: str | None
    sugestao: str | None
    score: float


def _resolver_assuntos(
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
    exatos = {chave_de_palavras(t): t for _, t in _topicos(edital)}
    abertos = [a for a in assuntos if a not in escolhas.aliases]
    for assunto in list(abertos):
        if (topico := exatos.get(chave_de_palavras(assunto))) is not None:
            escolhas.aliases[assunto] = topico
            abertos.remove(assunto)
    calculadas = sugerir_topicos(
        edital,
        dict(enumerate(abertos)),
        {i: assuntos[a] for i, a in enumerate(abertos) if assuntos[a]},
        dicionario,
    )
    pendentes = []
    for i, assunto in enumerate(abertos):
        if assunto in sugeridos:
            sugestao, score = sugeridos[assunto], 1.0
        else:
            calculada = calculadas[i]
            valida = calculada.topico != NAO_MAPEADO and calculada.score >= SCORE_BAIXO
            sugestao, score = (calculada.topico if valida else None), calculada.score
        if interacao is not None:
            opcao_sugerida = OPCAO_NENHUM if assunto in sugeridos and sugestao is None else sugestao
            opcoes = list(
                dict.fromkeys(
                    [
                        *filter(None, [opcao_sugerida]),
                        *_da_disciplina(edital, assuntos[assunto]),
                        OPCAO_NENHUM,
                        OPCAO_DEPOIS,
                    ]
                )
            )
            de = f' ({assuntos[assunto]})' if assuntos[assunto] else ''
            escolha = interacao.escolher(
                f'Assunto do TEC "{assunto}"{de}: qual tópico do edital?',
                opcoes,
                opcao_sugerida or OPCAO_DEPOIS,
            )
            if escolha != OPCAO_DEPOIS:
                escolhas.aliases[assunto] = None if escolha == OPCAO_NENHUM else escolha
                continue
        pendentes.append(Pendencia(assunto, assuntos[assunto], sugestao, round(score, 3)))
    return pendentes


def _ler_revisao(caminho: Path) -> dict[str, str | None]:
    if not caminho.exists():
        return {}
    with caminho.open(encoding='utf-8', newline='') as arquivo:
        linhas = list(csv.DictReader(arquivo))
    return {
        linha['assunto']: None if linha['topico'].strip() == NENHUM else linha['topico'].strip()
        for linha in linhas
        if (linha.get('topico') or '').strip()
    }


def _resolver_cadernos(
    cadernos: list[dict], escolhas: Escolhas, estado: dict, interacao: Interacao | None
) -> None:
    do_estado = estado.get('cadernos') or {}
    for c in cadernos:
        if c['id'] in escolhas.cadernos:
            continue
        sugerido = do_estado.get(c['id']) or {}
        if sugerido.get('modo') in {m.value for m in ModoCaderno}:
            modo = ModoCaderno(sugerido['modo'])
        elif interacao is not None:
            totais = ', '.join(f'{c.get(t, 0)} {t}' for t in _TOTAIS)
            nome = next(k for k, v in OPCOES_MODO.items() if v == ModoCaderno.TUDO)
            modo = OPCOES_MODO[
                interacao.escolher(
                    f'Caderno do TEC "{c.get("cad") or c["id"]}" ({totais}): registrar tudo ou só daqui em diante?',
                    list(OPCOES_MODO),
                    nome,
                )
            ]
        else:
            modo = ModoCaderno.TUDO
        if modo == ModoCaderno.TUDO:
            base = dict.fromkeys(_TOTAIS, 0)
        else:
            base = {t: int((sugerido.get('base') or c).get(t, 0) or 0) for t in _TOTAIS}
        escolhas.cadernos[c['id']] = {'modo': modo.value, 'base': base}


def _percentual(acertos: int, n: int) -> float | None:
    return round(100 * acertos / n, 1) if n else None


def _csv(colunas: list[str], linhas: list[dict]) -> str:
    saida = io.StringIO()
    escritor = csv.DictWriter(saida, fieldnames=colunas, lineterminator='\n')
    escritor.writeheader()
    for linha in linhas:
        escritor.writerow({c: '' if linha.get(c) is None else linha[c] for c in colunas})
    return saida.getvalue()


def _topico_do_erro(assunto: str | None, aliases: dict[str, str | None]) -> str:
    if not assunto or assunto not in aliases:
        return NAO_MAPEADO
    return aliases[assunto] or FORA_DO_EDITAL


def _linhas_de_erros(pratica: Pratica, escolhas: Escolhas, disciplinas: dict[str, str | None]) -> list[dict]:
    linhas = []
    for e in pratica.erros:
        datas = sorted({d[:10] for d in e.get('ds') or [] if d} | ({e['d']} if e.get('d') else set())) or ['']
        linhas.append(_linha_de_erro(e, datas, escolhas, disciplinas))
    return sorted(linhas, key=lambda linha: (-linha['v'], linha['primeira_data'], linha['id']))


def _linha_de_erro(e: dict, datas: list[str], escolhas: Escolhas, disciplinas: dict[str, str | None]) -> dict:
    return {
        'id': e['id'],
        'v': e.get('v') or _contagem(e.get('ds') or []),
        'primeira_data': datas[0],
        'ultima_data': datas[-1],
        'origem': e.get('origem', ''),
        'materia_tec': e.get('mat', ''),
        'disciplina': disciplinas.get(e.get('mat') or ''),
        'assunto': e.get('ass', ''),
        'topico': _topico_do_erro(e.get('ass'), escolhas.aliases),
        'banca': e.get('banca', ''),
        'orgao': e.get('orgao', ''),
        'ano': e.get('ano', ''),
        'caderno': e.get('cad', ''),
    }


def _linhas_de_cadernos(
    pratica: Pratica, escolhas: Escolhas, disciplinas: dict[str, str | None]
) -> list[dict]:
    linhas = []
    for c in sorted(pratica.cadernos, key=lambda c: c['id']):
        escolha = escolhas.cadernos[c['id']]
        res, ac, er = (max(0, int(c.get(t) or 0) - int(escolha['base'].get(t, 0))) for t in _TOTAIS)
        linhas.append(
            {
                'id': c['id'],
                'caderno': c.get('cad', ''),
                'materia_tec': c.get('mat', ''),
                'disciplina': disciplinas.get(c.get('mat') or ''),
                'modo': escolha['modo'],
                'total': c.get('tot'),
                'resolvidas': res,
                'acertos': ac,
                'erros': er,
                'percentual': _percentual(ac, res),
                'amostra_insuficiente': res < N_MINIMO_TOPICO,
            }
        )
    return linhas


def _linhas_de_desempenho(erros: list[dict], cadernos: list[dict]) -> list[dict]:
    por_disciplina: dict[str, dict] = {}
    for c in cadernos:
        if not c['disciplina']:
            continue
        linha = por_disciplina.setdefault(c['disciplina'], _linha_de_desempenho(c['disciplina']))
        linha['n'] += c['resolvidas']
        linha['acertos'] += c['acertos']
        linha['erros'] += c['erros']
        linha['cadernos'] += 1
    for e in erros:
        if not e['disciplina']:
            continue
        linha = por_disciplina.setdefault(e['disciplina'], _linha_de_desempenho(e['disciplina']))
        linha['erros_registrados'] += 1
        linha['repetidos'] += e['v'] >= 2
    for linha in por_disciplina.values():
        linha['percentual'] = _percentual(linha['acertos'], linha['n'])
        linha['amostra_insuficiente'] = linha['n'] < N_MINIMO_TOPICO
    return sorted(por_disciplina.values(), key=lambda linha: linha['disciplina'])


def _linha_de_desempenho(disciplina: str) -> dict:
    return {
        'disciplina': disciplina,
        'n': 0,
        'acertos': 0,
        'erros': 0,
        'cadernos': 0,
        'erros_registrados': 0,
        'repetidos': 0,
    }


@dataclass
class ResultadoPratica:
    mudou: bool
    avisos: list[str]
    pratica: Pratica
    escolhas: Escolhas
    disciplinas: dict[str, str | None]


def ler_pratica(
    entrada: Path, arquivo_escolhas: Path, taxonomia: dict[str, DisciplinaCanonica]
) -> ResultadoPratica:
    """A prática mesclada e a disciplina de cada matéria, sem gravar nem perguntar nada."""
    pratica, avisos = ler_entrada(entrada)
    escolhas = ler_escolhas(arquivo_escolhas)
    materias = {**(pratica.estado.get('materias') or {}), **escolhas.materias}
    nomes = {e.get('mat') for e in pratica.erros} | {c.get('mat') for c in pratica.cadernos}
    disciplinas = {m: disciplina_da_materia(m, taxonomia, materias) for m in nomes if m}
    return ResultadoPratica(False, avisos, pratica, escolhas, disciplinas)


def importar_pratica(
    entrada: Path,
    pasta_candidato: Path,
    arquivo_escolhas: Path,
    taxonomia: dict[str, DisciplinaCanonica],
    concurso_alvo: str | None,
    interacao: Interacao | None = None,
    fracos: pd.DataFrame | None = None,
    dicionario: 'Dicionario | None' = None,
) -> ResultadoPratica:
    """Lê a pasta de exportações e grava as tabelas de `pratica/`; sem terminal (`interacao` None), o assunto
    sem tópico vai para `revisao_aliases.csv`, e o caderno novo conta desde o início."""
    lido = ler_pratica(entrada, arquivo_escolhas, taxonomia)
    pratica, avisos, escolhas, disciplinas = lido.pratica, lido.avisos, lido.escolhas, lido.disciplinas
    pasta = pasta_candidato / PASTA_PRATICA
    revisao = pasta / ARQUIVO_REVISAO
    if desconhecidas := sorted(m for m, d in disciplinas.items() if d is None):
        avisos.append(
            f'prática: matéria do TEC sem disciplina ({", ".join(desconhecidas)}); acrescente-a em `nomes:` '
            'da disciplina no .concurso/taxonomia.yaml'
        )

    assuntos = {e['ass']: disciplinas.get(e.get('mat') or '') for e in pratica.erros if e.get('ass')}
    pendentes: list[Pendencia] | None = None
    edital = carregar_edital(pasta_candidato / concurso_alvo) if concurso_alvo else None
    if edital is None:
        if assuntos:
            motivo = (
                'sem concurso_alvo em [analise]'
                if not concurso_alvo
                else f'{concurso_alvo} sem edital estruturado'
            )
            avisos.append(f'prática: {motivo}; os assuntos do TEC ficam sem tópico do edital')
    else:
        sugeridos = {a: t for a, t in (pratica.estado.get('aliases') or {}).items() if a in assuntos}
        pendentes = _resolver_assuntos(
            assuntos, edital, escolhas, sugeridos, _ler_revisao(revisao), interacao, dicionario
        )
        if pendentes:
            avisos.append(
                f'prática: {len(pendentes)} assunto(s) do TEC sem tópico; preencha a coluna topico de '
                f'{revisao} (ou "{NENHUM}") e rode de novo'
            )
    _resolver_cadernos(pratica.cadernos, escolhas, pratica.estado, interacao)

    erros = _linhas_de_erros(pratica, escolhas, disciplinas)
    cadernos = _linhas_de_cadernos(pratica, escolhas, disciplinas)
    pasta.mkdir(parents=True, exist_ok=True)
    mudou = gravar_escolhas(arquivo_escolhas, escolhas)
    mudou |= gravar_se_mudou(pasta / ARQUIVO_ERROS, _csv(COLUNAS_ERROS, erros))
    mudou |= gravar_se_mudou(pasta / ARQUIVO_CADERNOS, _csv(COLUNAS_CADERNOS, cadernos))
    desempenho = _linhas_de_desempenho(erros, cadernos)
    mudou |= gravar_se_mudou(pasta / ARQUIVO_DESEMPENHO, _csv(COLUNAS_DESEMPENHO, desempenho))
    mudou |= gravar_se_mudou(pasta / ARQUIVO_RESUMO, resumo_markdown(erros, cadernos, desempenho, fracos))
    if pratica.erros:
        mudou |= gravar_se_mudou(
            pasta / ARQUIVO_SIMULADO, simulado_html(pratica.erros, escolhas.aliases, fracos)
        )
    if pendentes or (pendentes is not None and revisao.exists()):
        linhas = [
            {'assunto': p.assunto, 'disciplina': p.disciplina, 'sugestao': p.sugestao, 'score': p.score}
            for p in pendentes
        ]
        mudou |= gravar_se_mudou(revisao, _csv(COLUNAS_REVISAO, linhas))
    for aviso in avisos:
        logger.warning(aviso)
    return ResultadoPratica(mudou, avisos, pratica, escolhas, disciplinas)


def _numero(valor: float) -> str:
    return f'{float(valor):.1f}'.replace('.', ',')


def _celula(valor) -> str:
    from concursos.texto import abreviar

    texto = ' '.join(str(valor if valor not in (None, '') else '—').split())
    return abreviar(texto, 80).replace('|', '\\|')


def _rotulo_do_topico(topico: str) -> str:
    return {NAO_MAPEADO: 'não mapeado', FORA_DO_EDITAL: 'fora do edital'}.get(topico, topico)


def _desempenho(acertos: int, n: int) -> str:
    if n < N_MINIMO_TOPICO:
        return f'amostra insuficiente (n = {n})'
    return f'{_numero(100 * acertos / n)}% (n = {n})'


def _plural(n: int, singular: str, plural: str) -> str:
    return f'{n} {singular if n == 1 else plural}'


def resumo_markdown(
    erros: list[dict], cadernos: list[dict], desempenho: list[dict], fracos: pd.DataFrame | None
) -> str:
    """A seção "Prática no TEC" do `index.html`: prioridade de revisão, erros repetidos e desempenho."""
    repetidos = [e for e in erros if e['v'] >= 2]
    resolvidas = sum(c['resolvidas'] for c in cadernos)
    linhas = [
        '# Prática no TEC',
        '',
        f'{_plural(len(erros), "erro registrado", "erros registrados")} '
        f'({_plural(len(repetidos), "repetido", "repetidos")}, errado 2 vezes ou mais); '
        f'{_plural(resolvidas, "questão resolvida", "questões resolvidas")} nos cadernos acompanhados.',
        '',
        '## Prioridade de revisão',
        '',
        'Tópicos fracos na prova (abaixo do limiar em mais de um concurso) com erro repetido no TEC no mesmo '
        'tópico do edital.',
        '',
        *_prioridades(repetidos, fracos),
        '## Erros repetidos',
        '',
    ]
    if repetidos:
        linhas += [
            '| Vezes | Tópico do edital | Assunto no TEC | Última vez | Disciplina |',
            '|---|---|---|---|---|',
        ]
        linhas += [
            f'| {e["v"]} | {_celula(_rotulo_do_topico(e["topico"]))} | {_celula(e["assunto"])} | '
            f'{_celula(e["ultima_data"])} | {_celula(e["disciplina"])} |'
            for e in repetidos[:MAXIMO_REPETIDOS]
        ]
        if len(repetidos) > MAXIMO_REPETIDOS:
            linhas += ['', f'Mais {len(repetidos) - MAXIMO_REPETIDOS} em `pratica/{ARQUIVO_ERROS}`.']
    else:
        linhas.append('Nenhum erro repetido.')
    linhas += ['', '## Cadernos acompanhados', '']
    if cadernos:
        linhas += ['| Caderno | Modo | Acertos | Desempenho |', '|---|---|---|---|']
        linhas += [
            f'| {_celula(c["caderno"] or c["id"])} | {c["modo"]} | {c["acertos"]} | '
            f'{_desempenho(c["acertos"], c["resolvidas"])} |'
            for c in cadernos
        ]
    else:
        linhas.append('Nenhum caderno acompanhado.')
    if desempenho:
        linhas += ['', '## Desempenho por disciplina', '']
        linhas += ['| Disciplina | Nos cadernos | Erros registrados | Repetidos |', '|---|---|---|---|']
        linhas += [
            f'| {_celula(d["disciplina"])} | {_desempenho(d["acertos"], d["n"])} | {d["erros_registrados"]} | '
            f'{d["repetidos"]} |'
            for d in desempenho
        ]
    return '\n'.join(linhas).rstrip() + '\n'


def _prioridades(repetidos: list[dict], fracos: pd.DataFrame | None) -> list[str]:
    if fracos is None or fracos.empty:
        return ['Sem tópicos fracos persistentes na prova para cruzar.', '']
    por_topico: dict[str, list[dict]] = {}
    for e in repetidos:
        if e['topico'] not in (NAO_MAPEADO, FORA_DO_EDITAL):
            por_topico.setdefault(chave_de_palavras(e['topico']), []).append(e)
    linhas = []
    for fraco in fracos.itertuples():
        if cruzados := por_topico.get(chave_de_palavras(str(fraco.topico))):
            linhas.append(
                f'| {_celula(fraco.disciplina)} | {_celula(cruzados[0]["topico"])} | '
                f'{_numero(fraco.percentual)}% (n = {int(fraco.n)}) | {len(cruzados)} |'
            )
    if not linhas:
        return ['Nenhum tópico fraco da prova tem erro repetido no TEC.', '']
    cabecalho = [
        '| Disciplina | Tópico | Prova: percentual ajustado | Erros repetidos no TEC |',
        '|---|---|---|---|',
    ]
    return [*cabecalho, *linhas, '']


def questoes_do_simulado(
    erros: list[dict], aliases: dict[str, str | None], fracos: pd.DataFrame | None
) -> tuple[list[dict], bool]:
    """Os erros dos tópicos fracos, na ordem dos fracos e dos mais repetidos; sem cruzamento, os mais repetidos.
    Devolve também se o cruzamento com os tópicos fracos achou algum erro."""
    por_repeticao = sorted(erros, key=lambda e: (-(e.get('v') or 1), e['id']))
    por_topico: dict[str, list[dict]] = {}
    for e in por_repeticao:
        topico = _topico_do_erro(e.get('ass'), aliases)
        if topico not in (NAO_MAPEADO, FORA_DO_EDITAL):
            por_topico.setdefault(chave_de_palavras(topico), []).append(e)
    escolhidos: list[dict] = []
    for fraco in fracos.itertuples() if fracos is not None else []:
        do_topico = por_topico.get(chave_de_palavras(str(fraco.topico)), [])
        escolhidos += do_topico[: min(MAXIMO_SIMULADO_POR_TOPICO, MAXIMO_SIMULADO - len(escolhidos))]
        if len(escolhidos) >= MAXIMO_SIMULADO:
            break
    if escolhidos:
        return escolhidos, True
    return por_repeticao[:MAXIMO_REPETIDOS], False


def simulado_html(erros: list[dict], aliases: dict[str, str | None], fracos: pd.DataFrame | None) -> str:
    """Uma página para refazer as questões erradas, com as respostas só no fim."""
    questoes, cruzou = questoes_do_simulado(erros, aliases, fracos)
    explicacao = (
        'As questões que você errou no TEC nos seus tópicos mais fracos da prova, das mais repetidas para as menos.'
        if cruzou
        else 'Nenhum erro do TEC caiu nos tópicos fracos da prova; estas são as questões que você mais errou.'
    )
    corpo = []
    for numero, e in enumerate(questoes, start=1):
        origem = ' · '.join(str(e[c]) for c in ('mat', 'ass', 'banca', 'orgao', 'ano') if e.get(c))
        partes = [f'<h2>Questão {numero}</h2>', f'<p class="origem">{html.escape(origem)}</p>']
        if e.get('enun'):
            partes.append(f'<p>{html.escape(str(e["enun"]))}</p>')
        if alternativas := [a for a in e.get('alts') or [] if isinstance(a, dict)]:
            itens = ''.join(
                f'<li>{html.escape(str(a.get("l", "")))}) {html.escape(str(a.get("t", "")))}</li>'
                for a in alternativas
            )
            partes.append(f'<ul>{itens}</ul>')
        if e.get('url'):
            partes.append(f'<p><a href="{html.escape(str(e["url"]))}">abrir no TEC</a></p>')
        corpo.append(f'<section>{"".join(partes)}</section>')
    gabarito = ''.join(
        f'<li>Questão {numero}: {html.escape(str(e.get("gab") or "—"))}'
        + (f' (você marcou {html.escape(str(e["marc"]))})' if e.get('marc') else '')
        + '</li>'
        for numero, e in enumerate(questoes, start=1)
    )
    return (
        '<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
        '<title>Simulado com os meus erros</title>\n'
        '<style>body{font-family:sans-serif;max-width:48rem;margin:2rem auto;line-height:1.5}'
        '.origem{font-size:.9rem;opacity:.75}section{margin-bottom:2rem}</style>\n</head>\n<body>\n'
        f'<h1>Simulado com os meus erros</h1>\n<p>{html.escape(explicacao)}</p>\n'
        + '\n'.join(corpo)
        + f'\n<h2>Gabarito</h2>\n<ol class="gabarito">{gabarito}</ol>\n</body>\n</html>\n'
    )


def textos_do_caderno(resultado: ResultadoPratica) -> dict[str, str]:
    """Disciplina → markdown dos erros dela, para o notebook "Caderno de erros" do open-notebook."""
    por_disciplina: dict[str, list[dict]] = {}
    for e in resultado.pratica.erros:
        disciplina = resultado.disciplinas.get(e.get('mat') or '') or SEM_DISCIPLINA
        por_disciplina.setdefault(disciplina, []).append(e)
    textos = {}
    for disciplina, erros in sorted(por_disciplina.items()):
        linhas = [
            f'# Caderno de erros — {disciplina}',
            '',
            f'{_plural(len(erros), "questão errada", "questões erradas")} no TEC, das mais repetidas para as menos.',
            '',
        ]
        for e in sorted(erros, key=lambda e: (-(e.get('v') or 1), e['id'])):
            linhas += _questao(e, resultado.escolhas.aliases)
        textos[disciplina] = '\n'.join(linhas).rstrip() + '\n'
    return textos


def _questao(e: dict, aliases: dict[str, str | None]) -> list[str]:
    vezes = e.get('v') or 1
    linhas = [f'## {e.get("ass") or "Sem assunto"} — errada {_plural(vezes, "vez", "vezes")}', '']
    if origem := ' · '.join(str(e[c]) for c in ('banca', 'orgao', 'ano', 'cad') if e.get(c)):
        linhas += [origem, '']
    topico = _topico_do_erro(e.get('ass'), aliases)
    if topico not in (NAO_MAPEADO, FORA_DO_EDITAL):
        linhas += [f'Tópico do edital: {topico}', '']
    if e.get('enun'):
        linhas += [str(e['enun']), '']
    if alternativas := [a for a in e.get('alts') or [] if isinstance(a, dict)]:
        linhas += [*(f'- {a.get("l", "")}) {a.get("t", "")}' for a in alternativas), '']
    if e.get('marc') or e.get('gab'):
        linhas += [f'Sua resposta: {e.get("marc") or "—"}. Gabarito: {e.get("gab") or "—"}.', '']
    if e.get('com'):
        autor = f' ({e["prof"]})' if e.get('prof') else ''
        linhas += [f'Comentário{autor}: {e["com"]}', '']
    if e.get('url'):
        linhas += [f'Questão: {e["url"]}', '']
    return linhas


def textos_para_normas(resultado: ResultadoPratica) -> list[str]:
    """Enunciado e comentário de cada erro, onde `legislacao.extrair_citacoes` procura as normas citadas."""
    return ['\n'.join(str(e[c]) for c in ('enun', 'com') if e.get(c)) for e in resultado.pratica.erros]
