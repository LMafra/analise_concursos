from datetime import date
from pathlib import Path

from concursos.aplicacao.integracoes import interesses as ler_interesses
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.projeto import concurso_do_arquivo, exigir_provas
from concursos.cadastro import cadastrar
from concursos.candidatos import adicionar_arquivo, gravar_perfil_global, pasta_do_candidato, slug
from concursos.concurso_config import gravar_dados, ler_dados
from concursos.erros import ErroDoUsuario
from concursos.integracoes.sincronizacao_pci import Interesses


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
