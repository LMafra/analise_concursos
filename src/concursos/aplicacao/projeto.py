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
            f'Não encontrei a pasta onde ficam suas provas ({raiz_provas}).',
            'cadastre um concurso pela janela (Novo concurso) ou com concurso-analise add, ou indique a pasta '
            'com --provas.',
        )


def escolher_candidato(contexto: Contexto) -> str | None:
    """O escolhido, o último usado ou o único; sem nenhum, o layout das fases 1 a 3."""
    if contexto.candidato:
        return contexto.candidato
    existentes = candidatos_existentes(contexto.provas)
    if len(existentes) <= 1:
        return existentes[0] if existentes else None
    raise ErroDoUsuario(
        f'Este projeto tem mais de um candidato ({", ".join(existentes)}) e não sei de qual é a análise.',
        'escolha o candidato na janela ou rode com --candidate <nome> (ou --all-candidates para todos).',
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
            'Ainda não há respostas de nenhum candidato.',
            'acrescente a folha de respostas pela janela (Novo concurso) ou com '
            'concurso-analise add <arquivo> --candidate <nome> --concurso <pasta>.',
            'nenhum candidato em provas/<concurso>/candidatos/',
        )
    return list(candidatos)


def concurso_do_arquivo(raiz_provas: Path, arquivo: Path, concurso: str | None) -> Path:
    if concurso:
        pasta = raiz_provas / concurso
        if not pasta.is_dir():
            raise ErroDoUsuario(
                f'Não encontrei o concurso {concurso}.',
                'use em --concurso o nome de um concurso já cadastrado (veja concurso-analise status).',
                f'pasta {pasta} não existe',
            )
        return pasta
    absoluto, raiz = arquivo.resolve(), raiz_provas.resolve()
    if absoluto.is_relative_to(raiz) and len(absoluto.relative_to(raiz).parts) > 1:
        return raiz_provas / absoluto.relative_to(raiz).parts[0]
    pastas = listar_concursos(raiz_provas)
    if len(pastas) == 1:
        return pastas[0]
    raise ErroDoUsuario(
        'Não sei a qual concurso esse arquivo pertence.', 'rode de novo com --concurso <nome do concurso>.'
    )


def proxima_pasta(contexto: Contexto, base: str) -> Path:
    """`provas/<base>` ou, se já existir, `<base>_2`, `<base>_3`…"""
    pasta, numero = contexto.provas / base, 2
    while pasta.exists():
        pasta, numero = contexto.provas / f'{base}_{numero}', numero + 1
    return pasta


def concurso_alvo(contexto: Contexto, nome: str) -> ConcursoConfig:
    pasta = contexto.provas / nome
    if not pasta.is_dir():
        raise ErroDoUsuario(
            f'Não encontrei o concurso {nome}.',
            'escolha um concurso já cadastrado (veja concurso-analise status).',
            f'pasta {pasta} não existe',
        )
    try:
        return carregar_concurso(pasta)
    except (ConfiguracaoInvalidaError, FileNotFoundError) as erro:
        raise ErroDoUsuario(
            f'Não consegui ler o cadastro do concurso {nome}.',
            f'cadastre-o de novo pela janela ou com concurso-analise add {pasta}.',
            str(erro),
        ) from erro


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
            'Não consegui reorganizar as pastas do projeto para o formato novo; nada foi perdido.',
            'resolva o problema descrito no detalhe e abra o app de novo; a reorganização recomeça do zero.',
            str(erro),
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
