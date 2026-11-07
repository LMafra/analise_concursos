"""O dicionário de temas pela tela e pela CLI: começar com o inicial, ligar e desligar, sugerir termos das
revisões, editar os termos de um tópico e medir o ganho."""

from dataclasses import dataclass, replace
from datetime import datetime
from importlib import resources

import yaml

from concursos.analytics.dicionario_topicos import (
    ARQUIVO_GANHO,
    Dicionario,
    EntradaTema,
    Ganho,
    SugestaoTermo,
    avaliar_ganho,
    carregar_dicionario,
    com_recusa,
    com_termo,
    dicionario_em_dados,
    dicionario_em_yaml,
    ganho_em_markdown,
    ler_dicionario,
    questoes_revisadas,
    slug,
    sugerir_termos,
)
from concursos.analytics.taxonomia import carregar_taxonomia
from concursos.aplicacao.projeto import pasta_do_candidato
from concursos.arquivos import gravar_se_mudou
from concursos.config.contexto import SECAO_DICIONARIO, Contexto, gravar_no_config_projeto, ler_toml
from concursos.datas import data_br
from concursos.erros import ErroDoUsuario

ARQUIVO_INICIAL = 'inicial.yaml'


@dataclass(frozen=True)
class UltimoGanho:
    antes: float
    depois: float
    n: int
    data: str
    alerta: bool


@dataclass(frozen=True)
class SituacaoDicionario:
    existe: bool
    ligado: bool
    entradas: int
    ultimo: UltimoGanho | None


def resumo_do_ultimo(ultimo: UltimoGanho) -> str:
    return (
        f'Último teste: acertos {100 * ultimo.antes:.0f}% → {100 * ultimo.depois:.0f}% '
        f'(n = {ultimo.n}), em {data_br(ultimo.data)}'
    )


def termos_do_texto(texto: str) -> list[str]:
    """Os termos digitados na tela, separados por vírgula ou ponto e vírgula."""
    return [t.strip() for t in texto.replace(';', ',').split(',') if t.strip()]


def rotulo_do_tema(entrada: EntradaTema) -> str:
    return entrada.nomes[0] if entrada.nomes else entrada.topico.replace('_', ' ').capitalize()


def temas(contexto: Contexto) -> list[EntradaTema]:
    return sorted(carregar(contexto).entradas, key=lambda e: (e.disciplina, rotulo_do_tema(e)))


def inicial() -> Dicionario:
    texto = resources.files('concursos.dicionarios').joinpath(ARQUIVO_INICIAL).read_text(encoding='utf-8')
    return ler_dicionario(yaml.safe_load(texto), ARQUIVO_INICIAL)


def carregar(contexto: Contexto) -> Dicionario:
    if not contexto.dicionario.exists():
        return Dicionario(())
    return carregar_dicionario(contexto.dicionario)


def dicionario_do_projeto(contexto: Contexto) -> Dicionario | None:
    """O dicionário que a análise usa: None sem o arquivo ou desligado."""
    return carregar(contexto) if contexto.dicionario_ligado else None


def _secao(contexto: Contexto) -> dict:
    return ler_toml(contexto.config_projeto).get(SECAO_DICIONARIO, {})


def situacao(contexto: Contexto) -> SituacaoDicionario:
    secao = _secao(contexto)
    ultimo = None
    if 'antes' in secao:
        ultimo = UltimoGanho(
            float(secao['antes']),
            float(secao['depois']),
            int(secao['n']),
            str(secao['data']),
            bool(secao['alerta']),
        )
    existe = contexto.dicionario.exists()
    return SituacaoDicionario(existe, contexto.dicionario_ligado, len(carregar(contexto).entradas), ultimo)


def gravar(contexto: Contexto, dicionario: Dicionario) -> bool:
    contexto.projeto.mkdir(parents=True, exist_ok=True)
    return gravar_se_mudou(contexto.dicionario, dicionario_em_yaml(dicionario))


def ligar(contexto: Contexto, usar: bool) -> None:
    gravar_no_config_projeto(contexto, SECAO_DICIONARIO, {**_secao(contexto), 'usar': usar})


def iniciar(contexto: Contexto) -> int:
    """Acrescenta ao dicionário do projeto as entradas do inicial que ele ainda não tem; liga o dicionário.
    Devolve quantas entradas entraram."""
    atual = carregar(contexto)
    tem = {(e.disciplina, e.topico) for e in atual.entradas}
    novas = [e for e in inicial().entradas if (e.disciplina, e.topico) not in tem]
    gravar(contexto, Dicionario((*atual.entradas, *novas), atual.recusados))
    ligar(contexto, True)
    return len(novas)


def _canonicas(contexto: Contexto) -> dict[str, str]:
    taxonomia = carregar_taxonomia(contexto.taxonomia) if contexto.taxonomia.exists() else {}
    return {bruto: disciplina.nome for bruto, disciplina in taxonomia.items()}


def _revisadas(contexto: Contexto) -> dict:
    try:
        analises = pasta_do_candidato(contexto)
    except ErroDoUsuario:
        analises = contexto.analises
    return questoes_revisadas(contexto.provas, analises)


def sugestoes(contexto: Contexto) -> list[SugestaoTermo]:
    return sugerir_termos(_revisadas(contexto), carregar(contexto))


def aceitar(contexto: Contexto, sugestao: SugestaoTermo) -> bool:
    return gravar(contexto, com_termo(carregar(contexto), sugestao))


def recusar(contexto: Contexto, sugestao: SugestaoTermo) -> bool:
    return gravar(contexto, com_recusa(carregar(contexto), sugestao))


def gravar_topico(
    contexto: Contexto, disciplina: str, topico: str, termos: list[str], expressoes: list[str]
) -> bool:
    """Troca os termos e as expressões de um tópico (cria a entrada se preciso); listas vazias tiram o
    tópico do dicionário. A validação é a mesma da leitura do arquivo."""
    atual = carregar(contexto)
    chave = (slug(disciplina), slug(topico))
    limpos = [t.strip() for t in termos if t.strip()]
    expr = [t.strip() for t in expressoes if t.strip()]
    entradas = []
    achou = False
    for entrada in atual.entradas:
        if (entrada.disciplina, entrada.topico) != chave:
            entradas.append(entrada)
            continue
        achou = True
        if limpos or expr:
            entradas.append(replace(entrada, termos=tuple(limpos), expressoes=tuple(expr)))
    if not achou and (limpos or expr):
        nomes = () if topico == chave[1] else (topico,)
        entradas.append(EntradaTema(*chave, nomes=nomes, termos=tuple(limpos), expressoes=tuple(expr)))
    novo = Dicionario(tuple(entradas), atual.recusados)
    ler_dicionario(dicionario_em_dados(novo), 'dicionário')
    return gravar(contexto, novo)


def avaliar(contexto: Contexto) -> Ganho:
    """Mede o ganho, grava `.concurso/ganho_dicionario.md` e guarda o resumo para a tela."""
    dicionario = carregar(contexto)
    if not dicionario.entradas:
        raise ErroDoUsuario('o dicionário de temas está vazio', 'comece com o dicionário inicial')
    ganho = avaliar_ganho(_revisadas(contexto), dicionario, _canonicas(contexto))
    contexto.projeto.mkdir(parents=True, exist_ok=True)
    gravar_se_mudou(contexto.projeto / ARQUIVO_GANHO, ganho_em_markdown(ganho))
    gravar_no_config_projeto(
        contexto,
        SECAO_DICIONARIO,
        {
            **_secao(contexto),
            'antes': round(ganho.geral.taxa_antes, 4),
            'depois': round(ganho.geral.taxa_depois, 4),
            'n': ganho.geral.n,
            'data': f'{datetime.now():%Y-%m-%d}',
            'alerta': ganho.alerta,
        },
    )
    return ganho
