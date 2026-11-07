"""Prova anterior do PCI como simulado: um concurso próprio em `provas/<orgao>_<ano>_pci<id>/`."""

import logging
import re
from pathlib import Path

from concursos.arquivos import gravar_se_mudou
from concursos.concurso_config import ConcursoConfig, gravar_dados, ler_dados
from concursos.integracoes.pci_mcp import ProvaAnteriorPci
from concursos.perfis import PerfilInvalidoError, perfil_da_banca, perfis_de_banca
from concursos.texto import normalizar

logger = logging.getLogger(__name__)

ARQUIVO_PROVAS_ANTERIORES = 'provas_anteriores.md'
BANCA_RESERVA = 'generic'
_PREFIXO_CARGO = re.compile(r'^\s*(cargo\s*)?\d+\s*[:\-–]\s*', re.IGNORECASE)
_PALAVRAS_VAZIAS = {'de', 'da', 'do', 'das', 'dos', 'e', 'em', 'area', 'área', 'nivel', 'nível'}


def banca_da_organizadora(organizadora: str) -> str | None:
    """O perfil cujo `id` ou alguma `marca` aparece, como palavra inteira, no nome da organizadora."""
    nome = normalizar(organizadora)
    if not nome:
        return None
    for perfil in perfis_de_banca():
        for marca in (perfil.id.upper(), *perfil.marcas):
            if marca and re.search(rf'\b{re.escape(normalizar(marca))}\b', nome):
                return perfil.id
    return None


def _slug(texto: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', normalizar(texto).lower()).strip('_')


def nome_da_pasta(prova: ProvaAnteriorPci) -> str:
    base = _slug(prova.orgao) or _slug(prova.descricao) or 'prova'
    return f'{base}_{prova.ano or "sem_ano"}_pci{prova.id}'


def edital_emprestado(alvo: ConcursoConfig | None) -> str | dict | None:
    if alvo is None or alvo.edital is None:
        return None
    prefixo = f'../{alvo.pasta.name}/'
    edital: dict = {}
    if alvo.edital.arquivo:
        edital['arquivo'] = prefixo + alvo.edital.arquivo
    if alvo.edital.anexos:
        edital['anexos'] = [prefixo + anexo for anexo in alvo.edital.anexos]
    if alvo.edital.manual:
        edital['manual'] = prefixo + alvo.edital.manual
    if list(edital) == ['arquivo']:
        return edital['arquivo']
    return edital or None


def dados_iniciais(prova: ProvaAnteriorPci, banca: str, alvo: ConcursoConfig | None) -> dict:
    """O `concurso.yaml` antes do cadastro, que acrescenta provas, gabaritos e respostas e preserva o resto."""
    simulado = {
        'fonte': 'pci',
        'id_pci': prova.id,
        'ano_original': prova.ano,
        'organizadora': prova.organizadora,
        'orgao': prova.orgao,
        'descricao': prova.descricao,
        'link': prova.link,
        'concurso_alvo': alvo.pasta.name if alvo else None,
        'cargo_alvo': alvo.cargo if alvo else None,
    }
    dados: dict = {
        'nome': f'{prova.orgao or prova.descricao} {prova.ano or ""} (simulado PCI {prova.id})'.replace(
            '  ', ' '
        ),
        'banca': banca,
    }
    if edital := edital_emprestado(alvo):
        dados['edital'] = edital
    dados['simulado'] = {chave: valor for chave, valor in simulado.items() if valor not in (None, '')}
    return dados


def preparar_pasta(
    raiz_provas: Path, prova: ProvaAnteriorPci, alvo: ConcursoConfig | None
) -> tuple[Path, list[str]]:
    """Cria a pasta e o `concurso.yaml` inicial; devolve a pasta e os avisos (banca e edital)."""
    avisos = []
    banca = banca_da_organizadora(prova.organizadora)
    if banca is None:
        banca = BANCA_RESERVA
        avisos.append(
            f'o app não conhece a banca "{prova.organizadora or "?"}"; usei a regra padrão ({BANCA_RESERVA}). '
            'Confira o tipo de prova e o desconto por erro no cadastro.'
        )
    if alvo is None or alvo.edital is None:
        avisos.append(
            'sem o edital do concurso que você quer, as questões do simulado ficam sem tópico; '
            'escolha o concurso-alvo para usar o edital dele.'
        )
    pasta = raiz_provas / nome_da_pasta(prova)
    pasta.mkdir(parents=True, exist_ok=True)
    iniciais = dados_iniciais(prova, banca, alvo)
    anteriores = ler_dados(pasta)
    dados = {**iniciais, **anteriores, 'simulado': iniciais['simulado']}
    if dados != anteriores:
        gravar_dados(pasta, dados)
    return pasta, avisos


def limpar_cargo(cargo: str) -> str:
    return _PREFIXO_CARGO.sub('', cargo).strip()


def termos_automaticos(alvo: ConcursoConfig) -> list[str]:
    """As duas primeiras palavras do cargo com a banca e, depois, sem ela; o servidor exige todas as palavras."""
    explicitos = (ler_dados(alvo.pasta).get('pci') or {}).get('termos_provas')
    if isinstance(explicitos, list) and all(isinstance(t, str) and t.strip() for t in explicitos):
        return [t.strip() for t in explicitos]
    palavras = [p for p in limpar_cargo(alvo.cargo or '').lower().split() if p not in _PALAVRAS_VAZIAS]
    if not palavras:
        return []
    base = ' '.join(palavras[:2])
    termos = [f'{base} {alvo.banca}'] if _banca_tem_marca(alvo.banca) else []
    return [*termos, base]


def _banca_tem_marca(banca: str) -> bool:
    """O perfil genérico não tem marca e não é nome de banca que o PCI conheça."""
    try:
        return bool(perfil_da_banca(banca).marcas)
    except PerfilInvalidoError:
        return False


def formatar_provas(provas: list[ProvaAnteriorPci]) -> str:
    if not provas:
        return 'nenhuma prova anterior encontrada no PCI; tente com menos palavras em --termo'
    linhas = []
    for prova in sorted(provas, key=lambda p: (-(p.ano or 0), p.id)):
        linhas += [
            f'{prova.id}  {prova.ano or "?"}  {prova.orgao}: {prova.descricao} ({prova.organizadora or "?"})',
            f'    {prova.link}',
        ]
    linhas.append(
        f'{len(provas)} prova(s). Para treinar com uma: `concurso-analise pci provas <concurso> --download <id>`'
    )
    return '\n'.join(linhas)


def _celula(texto: str) -> str:
    return texto.replace('|', '/').replace('\n', ' ')


def gravar_provas_anteriores(destino: Path, alvo: str, termo: str, provas: list[ProvaAnteriorPci]) -> bool:
    linhas = [
        f'# Provas anteriores: {alvo}',
        '',
        f'Busca no PCI Concursos por "{termo}". O PCI é colaborativo e pode não ter todas as provas.',
        '',
        '| id | ano | órgão | cargo | banca | página |',
        '|---|---|---|---|---|---|',
    ]
    for prova in sorted(provas, key=lambda p: (-(p.ano or 0), p.id)):
        linhas.append(
            f'| {prova.id} | {prova.ano or "?"} | {_celula(prova.orgao)} | {_celula(prova.descricao)} '
            f'| {_celula(prova.organizadora)} | [abrir]({prova.link}) |'
        )
    if not provas:
        linhas.append('| - | - | nenhuma prova encontrada | - | - | - |')
    linhas += [
        '',
        f'Para treinar com uma delas: `concurso-analise pci provas {alvo} --download <id>`. O simulado vira um '
        'concurso próprio, corrigido pela banca da prova, com os tópicos deste edital.',
        '',
    ]
    destino.mkdir(parents=True, exist_ok=True)
    return gravar_se_mudou(destino / ARQUIVO_PROVAS_ANTERIORES, '\n'.join(linhas))
