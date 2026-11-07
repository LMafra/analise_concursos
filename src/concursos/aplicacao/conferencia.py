"""Conferência pela tela: os tópicos das questões, os dados do edital a confirmar e as disciplinas.

Cada gravação muda só o arquivo de entrada conferido; a reanálise seguinte refaz só os concursos cujo
manifesto mudou."""

import json
import logging
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from concursos.analytics.taxonomia import TaxonomiaInvalidaError, carregar_taxonomia
from concursos.aplicacao import analise
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.projeto import pasta_do_candidato
from concursos.arquivos import gravar_se_mudou
from concursos.concurso_config import (
    ARQUIVO_CONFIRMACAO,
    CAMPOS_CONFIRMAVEIS,
    ConfiguracaoInvalidaError,
    carregar_concurso,
)
from concursos.config.contexto import Contexto
from concursos.correcao import ARQUIVO_QUESTOES
from concursos.edital import ARQUIVO_EDITAL_ESTRUTURADO
from concursos.edital_a_confirmar import gravar_valores
from concursos.erros import ErroDoUsuario
from concursos.modelo import Bloco, TipoCampo
from concursos.topicos import ARQUIVO_REVISAO, NAO_MAPEADO, SCORE_BAIXO, gravar_revisao_editada

logger = logging.getLogger(__name__)

TIPO_DO_CAMPO = {
    'data_prova': TipoCampo.DATA,
    'alternativas': TipoCampo.INTEIRO,
    'fator_penalidade': TipoCampo.NUMERO,
    'nota_corte': TipoCampo.NUMERO,
}
LIMITES = {'alternativas': (2, 10), 'fator_penalidade': (0, 10), 'nota_corte': (0, None)}
ROTULO_DO_CAMPO = {
    'data_prova': 'Data da prova objetiva',
    'alternativas': 'Alternativas por questão',
    'fator_penalidade': 'Quantos acertos cada erro anula',
    'nota_corte': 'Nota mínima nas provas objetivas (pontos)',
}
EXPLICACAO_DO_CAMPO = {
    'data_prova': 'O dia em que a prova objetiva foi aplicada.',
    'alternativas': 'Quantas opções cada questão tinha, de 2 a 10.',
    'fator_penalidade': '0 se o erro não desconta; 1 na Cebraspe; 0,25 se 4 erros anulam 1 acerto.',
    'nota_corte': 'A nota mínima no conjunto das provas objetivas, em pontos. Deixe vazio se o edital não tem.',
}
BLOCOS = (Bloco.GERAL, Bloco.ESPECIFICO)


def pasta_do_concurso(contexto: Contexto, concurso: str) -> Path:
    pasta = contexto.provas / concurso
    if not pasta.is_dir():
        raise ErroDoUsuario(f'o concurso {concurso} não existe', 'escolha um concurso da lista')
    return pasta


# tópicos


@dataclass(frozen=True)
class LinhaTopico:
    questao: int
    prova: str
    enunciado: str
    disciplina_sugerida: str
    topico_sugerido: str
    score: float
    disciplina: str = ''
    topico: str = ''

    @property
    def chave(self) -> tuple[int, str]:
        return self.questao, self.prova

    @property
    def pendente(self) -> bool:
        """Sem revisão e com a sugestão fraca: o app não achou um tópico em que confie."""
        return not self.topico and (self.topico_sugerido == NAO_MAPEADO or self.score < SCORE_BAIXO)


@dataclass(frozen=True)
class OpcaoTopico:
    disciplina: str
    topico: str

    @property
    def rotulo(self) -> str:
        return f'{self.disciplina} — {self.topico}' if self.disciplina else self.topico


def _numero(texto: str) -> float:
    try:
        return float(texto)
    except ValueError:
        return 0.0


def topicos_para_conferir(contexto: Contexto, concurso: str) -> list[LinhaTopico]:
    caminho = pasta_do_concurso(contexto, concurso) / ARQUIVO_REVISAO
    if not caminho.exists():
        return []
    tabela = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    return [
        LinhaTopico(
            int(linha.questao),
            linha.prova,
            linha.enunciado,
            linha.disciplina_sugerida,
            linha.topico_sugerido,
            _numero(linha.score),
            linha.disciplina.strip(),
            linha.topico.strip(),
        )
        for linha in tabela.itertuples()
    ]


def _edital_estruturado(contexto: Contexto, concurso: str) -> Path | None:
    try:
        preferido = pasta_do_candidato(contexto) / concurso / ARQUIVO_EDITAL_ESTRUTURADO
    except ErroDoUsuario:
        preferido = None
    if preferido is not None and preferido.exists():
        return preferido
    if not contexto.analises.is_dir():
        return None
    return next(iter(sorted(contexto.analises.glob(f'**/{concurso}/{ARQUIVO_EDITAL_ESTRUTURADO}'))), None)


def opcoes_de_topico(contexto: Contexto, concurso: str) -> list[OpcaoTopico]:
    """Os tópicos do conteúdo programático do edital; sem ele, os que o app já sugeriu."""
    caminho = _edital_estruturado(contexto, concurso)
    if caminho is not None:
        dados = json.loads(caminho.read_text(encoding='utf-8'))
        opcoes = [
            OpcaoTopico(disciplina['nome'], topico['nome'])
            for conhecimento in dados.get('conhecimentos') or []
            for disciplina in conhecimento.get('disciplinas') or []
            for topico in disciplina.get('topicos') or []
        ]
        if opcoes:
            return list(dict.fromkeys(opcoes))
    return list(
        dict.fromkeys(
            OpcaoTopico(linha.disciplina_sugerida, linha.topico_sugerido)
            for linha in topicos_para_conferir(contexto, concurso)
            if linha.topico_sugerido != NAO_MAPEADO
        )
    )


def gravar_topicos(
    contexto: Contexto, concurso: str, escolhas: dict[tuple[int, str], OpcaoTopico | None]
) -> bool:
    """Grava o tópico escolhido de cada questão; `None` é "Nenhum" (a questão fica fora do edital)."""
    caminho = pasta_do_concurso(contexto, concurso) / ARQUIVO_REVISAO
    if not caminho.exists():
        raise ErroDoUsuario(
            f'o concurso {concurso} ainda não tem tópicos para conferir', 'analise o concurso primeiro'
        )
    edicoes = {
        chave: (opcao.disciplina, opcao.topico) if opcao is not None else ('', NAO_MAPEADO)
        for chave, opcao in escolhas.items()
    }
    return gravar_revisao_editada(caminho, edicoes)


# dados do edital


@dataclass(frozen=True)
class CampoAConfirmar:
    campo: str
    rotulo: str
    explicacao: str
    tipo: TipoCampo
    valor: str = ''


def _ler_confirmacao(pasta: Path) -> dict | None:
    caminho = pasta / ARQUIVO_CONFIRMACAO
    if not caminho.exists():
        return None
    dados = yaml.load(caminho.read_text(encoding='utf-8'), Loader=yaml.BaseLoader) or {}
    return dados if isinstance(dados, dict) else {}


def campos_a_confirmar(contexto: Contexto, concurso: str) -> list[CampoAConfirmar]:
    """Os campos que a análise pediu em `edital_a_confirmar.yaml`, com o valor já preenchido (texto)."""
    dados = _ler_confirmacao(pasta_do_concurso(contexto, concurso))
    if dados is None:
        return []
    return [
        CampoAConfirmar(
            campo,
            ROTULO_DO_CAMPO[campo],
            EXPLICACAO_DO_CAMPO[campo],
            TIPO_DO_CAMPO[campo],
            dados[campo] or '',
        )
        for campo in CAMPOS_CONFIRMAVEIS
        if campo in dados
    ]


def validar_campo(campo: str, texto: str) -> object:
    """O valor tipado de um campo digitado; vazio é None. Levanta ErroDoUsuario com o que esperar."""
    texto = (texto or '').strip()
    if not texto:
        return None
    rotulo = ROTULO_DO_CAMPO[campo]
    tipo = TIPO_DO_CAMPO[campo]
    if tipo is TipoCampo.DATA:
        try:
            dia, mes, ano = texto.split('/') if '/' in texto else reversed(texto.split('-'))
            return date(int(ano), int(mes), int(dia)).isoformat()
        except ValueError as erro:
            raise ErroDoUsuario(f'{rotulo}: "{texto}" não é uma data', 'use DD/MM/AAAA') from erro
    try:
        valor = int(texto) if tipo is TipoCampo.INTEIRO else float(texto.replace(',', '.'))
    except ValueError as erro:
        esperado = 'um número inteiro' if tipo is TipoCampo.INTEIRO else 'um número'
        raise ErroDoUsuario(f'{rotulo}: "{texto}" não é {esperado}', f'digite {esperado}') from erro
    minimo, maximo = LIMITES[campo]
    if valor < minimo or (maximo is not None and valor > maximo):
        faixa = f'entre {minimo} e {maximo}' if maximo is not None else f'a partir de {minimo}'
        raise ErroDoUsuario(f'{rotulo}: {texto} fora do esperado', f'use um valor {faixa}')
    return valor


def gravar_campos(contexto: Contexto, concurso: str, valores: dict[str, str]) -> bool:
    """Valida cada campo pelo tipo e grava no `edital_a_confirmar.yaml`, preservando os comentários."""
    pasta = pasta_do_concurso(contexto, concurso)
    caminho = pasta / ARQUIVO_CONFIRMACAO
    if not caminho.exists():
        raise ErroDoUsuario(f'o concurso {concurso} não tem dados do edital a confirmar', 'nada a gravar')
    tipados = {campo: validar_campo(campo, texto) for campo, texto in valores.items()}
    anterior = caminho.read_text(encoding='utf-8')
    mudou = gravar_valores(caminho, tipados)
    try:
        carregar_concurso(pasta)
    except ConfiguracaoInvalidaError as erro:
        caminho.write_text(anterior, encoding='utf-8')
        raise ErroDoUsuario(str(erro), 'confira os valores digitados') from erro
    return mudou


@dataclass(frozen=True)
class Pendencias:
    topicos: int
    campos: int

    @property
    def total(self) -> int:
        return self.topicos + self.campos


def pendencias(contexto: Contexto, concurso: str) -> Pendencias:
    return Pendencias(
        sum(linha.pendente for linha in topicos_para_conferir(contexto, concurso)),
        sum(not campo.valor for campo in campos_a_confirmar(contexto, concurso)),
    )


# disciplinas


@dataclass(frozen=True)
class GrupoDisciplinas:
    canonica: str
    bloco: Bloco
    nomes: tuple[str, ...]


@dataclass(frozen=True)
class Taxonomia:
    grupos: list[GrupoDisciplinas]
    soltas: list[str]


def nomes_das_analises(contexto: Contexto) -> list[str]:
    """Os nomes de disciplina como aparecem nos `questoes.csv` das análises do projeto."""
    if not contexto.analises.is_dir():
        return []
    nomes: set[str] = set()
    for arquivo in contexto.analises.glob(f'**/{ARQUIVO_QUESTOES}'):
        tabela = pd.read_csv(arquivo, dtype=str, keep_default_na=False, usecols=['disciplina'])
        nomes |= {nome.strip() for nome in tabela['disciplina'] if nome.strip() and nome != NAO_MAPEADO}
    return sorted(nomes)


def taxonomia(contexto: Contexto) -> Taxonomia:
    try:
        mapa = carregar_taxonomia(contexto.taxonomia)
    except TaxonomiaInvalidaError as erro:
        raise ErroDoUsuario(str(erro), 'junte as disciplinas de novo nesta tela') from erro
    grupos: dict[str, list[str]] = {}
    blocos: dict[str, Bloco] = {}
    for bruto, disciplina in mapa.items():
        grupos.setdefault(disciplina.nome, [])
        blocos[disciplina.nome] = disciplina.bloco
        if bruto != disciplina.nome:
            grupos[disciplina.nome].append(bruto)
    agrupados = set(mapa)
    return Taxonomia(
        [GrupoDisciplinas(nome, blocos[nome], tuple(nomes)) for nome, nomes in sorted(grupos.items())],
        [nome for nome in nomes_das_analises(contexto) if nome not in agrupados],
    )


def gravar_taxonomia(contexto: Contexto, grupos: list[GrupoDisciplinas]) -> bool:
    vistos: dict[str, str] = {}
    dados = {}
    for grupo in grupos:
        if not grupo.canonica.strip():
            raise ErroDoUsuario('uma disciplina ficou sem nome', 'dê um nome à disciplina juntada')
        if grupo.bloco not in BLOCOS:
            raise ErroDoUsuario(f'{grupo.canonica}: escolha geral ou específica', 'marque uma das duas')
        for nome in dict.fromkeys([grupo.canonica, *grupo.nomes]):
            if nome in vistos and vistos[nome] != grupo.canonica:
                raise ErroDoUsuario(
                    f'"{nome}" está em {vistos[nome]} e em {grupo.canonica}', 'deixe o nome em uma só'
                )
            vistos[nome] = grupo.canonica
        nomes = [n for n in dict.fromkeys(grupo.nomes) if n != grupo.canonica]
        dados[grupo.canonica] = {'bloco': grupo.bloco.value, **({'nomes': nomes} if nomes else {})}
    contexto.taxonomia.parent.mkdir(parents=True, exist_ok=True)
    return gravar_se_mudou(contexto.taxonomia, yaml.safe_dump(dados, allow_unicode=True, sort_keys=False))


def juntar_disciplinas(contexto: Contexto, nomes: list[str], canonica: str, bloco: Bloco) -> bool:
    """Junta os nomes (soltos ou de outros grupos) na disciplina `canonica`, criando-a se preciso."""
    canonica = canonica.strip()
    atual = taxonomia(contexto)
    juntados = set(nomes) | {canonica}
    grupos = []
    destino = GrupoDisciplinas(canonica, bloco, ())
    for grupo in atual.grupos:
        if grupo.canonica == canonica:
            destino = GrupoDisciplinas(canonica, bloco, grupo.nomes)
            continue
        if grupo.canonica in juntados:
            destino = replace(destino, nomes=(*destino.nomes, *grupo.nomes))
            continue
        restantes = tuple(n for n in grupo.nomes if n not in juntados)
        grupos.append(replace(grupo, nomes=restantes))
    novos = [n for n in nomes if n != canonica and n not in destino.nomes]
    grupos.append(replace(destino, nomes=(*destino.nomes, *novos)))
    return gravar_taxonomia(contexto, sorted(grupos, key=lambda g: g.canonica))


def separar_disciplina(contexto: Contexto, canonica: str) -> bool:
    atual = taxonomia(contexto)
    return gravar_taxonomia(contexto, [g for g in atual.grupos if g.canonica != canonica])


# reanálise


def reanalisar_afetados(opcoes: Opcoes, concurso: str | None = None) -> int:
    """A análise de sempre: o manifesto de cada concurso decide quem é refeito (só os que mudaram)."""
    return analise.analisar(replace(opcoes, sim=True, abrir=False), concurso)
