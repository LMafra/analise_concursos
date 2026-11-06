import shutil
from dataclasses import replace
from pathlib import Path

from concursos import doctor as diagnostico
from concursos.aplicacao.opcoes import Opcoes
from concursos.candidatos import candidatos_existentes, slug
from concursos.concurso_config import ConcursoConfig, ConfiguracaoInvalidaError, carregar_concurso
from concursos.config.contexto import Contexto, gravar_no_config_projeto, ler_toml
from concursos.erros import ErroDoAmbiente, ErroDoUsuario
from concursos.migracao import MigracaoError, executar_migracao, migrar_biblioteca_yaml, planejar_migracao
from concursos.status import listar_concursos


def com_candidato(contexto: Contexto, candidato: str | None) -> Contexto:
    return replace(contexto, candidato=slug(candidato)) if candidato else contexto


def curto(caminho: Path, raiz: Path) -> Path:
    """Relativo à pasta atual quando está dentro dela, para os relatórios não citarem a pasta do usuário."""
    return caminho.relative_to(raiz) if caminho.is_relative_to(raiz) else caminho


def exigir_provas(raiz_provas: Path) -> None:
    if not raiz_provas.is_dir():
        raise ErroDoUsuario(
            f'pasta de provas não encontrada: {raiz_provas}',
            'crie uma subpasta por concurso (ex.: provas/meu_concurso/) ou indique outra pasta com --provas',
        )


def escolher_candidato(contexto: Contexto) -> str | None:
    """O escolhido, o último usado ou o único; sem nenhum, o layout das fases 1 a 3."""
    if contexto.candidato:
        return contexto.candidato
    existentes = candidatos_existentes(contexto.provas)
    if len(existentes) <= 1:
        return existentes[0] if existentes else None
    raise ErroDoUsuario(
        f'há mais de um candidato ({", ".join(existentes)}) e nenhum foi escolhido',
        'rode com --candidate <nome> ou com --all-candidates',
    )


def pasta_do_candidato(contexto: Contexto) -> Path:
    candidato = escolher_candidato(contexto)
    return contexto.analises / candidato if candidato else contexto.analises


def lembrar_candidato(contexto: Contexto, candidato: str) -> None:
    if ler_toml(contexto.config_projeto).get('candidato', {}).get('ultimo') != candidato:
        gravar_no_config_projeto(contexto, 'candidato', {'ultimo': candidato})


def candidatos_da_execucao(contexto: Contexto, todos: bool) -> list[str | None]:
    if not todos:
        return [escolher_candidato(contexto)]
    candidatos = candidatos_existentes(contexto.provas)
    if not candidatos:
        raise ErroDoUsuario(
            'nenhum candidato encontrado em provas/<concurso>/candidatos/',
            'acrescente um com `concurso-analise add <arquivo> --candidate <nome> --concurso <pasta>`',
        )
    return list(candidatos)


def concurso_do_arquivo(raiz_provas: Path, arquivo: Path, concurso: str | None) -> Path:
    if concurso:
        pasta = raiz_provas / concurso
        if not pasta.is_dir():
            raise ErroDoUsuario(
                f'concurso não encontrado: {pasta}', 'use o nome de uma pasta em provas/ no --concurso'
            )
        return pasta
    absoluto, raiz = arquivo.resolve(), raiz_provas.resolve()
    if absoluto.is_relative_to(raiz) and len(absoluto.relative_to(raiz).parts) > 1:
        return raiz_provas / absoluto.relative_to(raiz).parts[0]
    pastas = listar_concursos(raiz_provas)
    if len(pastas) == 1:
        return pastas[0]
    raise ErroDoUsuario(
        'não dá para saber a qual concurso o arquivo pertence', 'rode de novo com --concurso <pasta>'
    )


def concurso_alvo(contexto: Contexto, nome: str) -> ConcursoConfig:
    pasta = contexto.provas / nome
    if not pasta.is_dir():
        raise ErroDoUsuario(f'concurso não encontrado: {pasta}', 'use o nome de uma pasta em provas/')
    try:
        return carregar_concurso(pasta)
    except (ConfiguracaoInvalidaError, FileNotFoundError) as erro:
        raise ErroDoUsuario(str(erro), f'cadastre o concurso com `concurso-analise add {pasta}`') from erro


def migrar(opcoes: Opcoes) -> Opcoes:
    """Passa para o layout multi-candidato o que estiver no formato das fases 1 a 3."""
    contexto = opcoes.contexto
    try:
        if not opcoes.dry_run:
            migrar_biblioteca_yaml(contexto)
        migracao = planejar_migracao(contexto)
        if migracao.vazia:
            return opcoes
        if opcoes.dry_run:
            for operacao in migracao.operacoes(contexto):
                opcoes.saida(operacao)
            return opcoes
        executar_migracao(migracao, contexto)
    except MigracaoError as erro:
        raise ErroDoAmbiente(
            str(erro), 'resolva o problema e rode de novo; a migração recomeça do zero'
        ) from erro
    return replace(opcoes, contexto=replace(contexto, candidato=migracao.candidato))


def ocr_disponivel() -> bool:
    """Sem o Tesseract, PDFs escaneados (sem texto) ficam sem leitura; a folha de respostas não depende dele."""
    return shutil.which('tesseract') is not None


def diagnosticar(contexto: Contexto) -> list[diagnostico.Item]:
    return diagnostico.diagnosticar(
        [contexto.provas, contexto.analises, contexto.projeto, contexto.home],
        contexto.home,
        contexto.analises,
    )
