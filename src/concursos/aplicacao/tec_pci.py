"""Busca no PCI Concursos provas anteriores ligadas aos assuntos errados no TEC."""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from pathlib import Path

from concursos.aplicacao import pratica as pratica_app
from concursos.aplicacao.integracoes import consultar_pci
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.projeto import pasta_do_candidato
from concursos.arquivos import gravar_se_mudou
from concursos.erros import ErroDoUsuario, avisar
from concursos.integracoes.pci_mcp import ler_configuracao as ler_pci
from concursos.pratica_tec import (
    ARQUIVO_PCI_PROVAS,
    ARQUIVO_RESPOSTAS,
    COLUNAS_PCI_PROVAS,
    PASTA_PRATICA,
    RESULTADO_ERRO,
    ler_entrada,
    so_erros,
)
from concursos.texto import normalizar

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProvaRelacionada:
    ass: str
    prova_url: str
    orgao: str
    banca: str
    ano: str
    tema_no_edital: bool
    fonte_tema: str


def _pasta(opcoes: Opcoes) -> Path:
    cfg = pratica_app.exigir_configuracao_pratica(opcoes.contexto)
    nome = cfg.candidato
    if not nome:
        raise ErroDoUsuario(
            'Não sei qual candidato usar.',
            'configure [pratica] candidato ou escolha o candidato na análise.',
        )
    return pasta_do_candidato(opcoes.contexto, nome) / PASTA_PRATICA


def _assuntos_com_erro(opcoes: Opcoes) -> list[tuple[str, str, str]]:
    pasta = _pasta(opcoes)
    caminho = pasta / ARQUIVO_RESPOSTAS
    if caminho.is_file():
        with caminho.open(encoding='utf-8', newline='') as arquivo:
            linhas = list(csv.DictReader(arquivo))
        return [
            (l.get('ass') or '', l.get('mat') or '', l.get('banca') or '')
            for l in linhas
            if l.get('resultado') == RESULTADO_ERRO and l.get('ass')
        ]
    cfg = pratica_app.exigir_configuracao_pratica(opcoes.contexto)
    pratica, _ = ler_entrada(cfg.entrada)
    return [
        (i.get('ass') or '', i.get('mat') or '', i.get('banca') or '')
        for i in so_erros(pratica.erros)
        if i.get('ass')
    ]


def _tema_no_edital_local(raiz: Path, ass: str) -> tuple[bool, str]:
    alvo = normalizar(ass)
    if not alvo:
        return False, ''
    provas = raiz / 'provas'
    if not provas.is_dir():
        return False, ''
    for edital in provas.glob('*/edital_estruturado.json'):
        try:
            texto = edital.read_text(encoding='utf-8')
        except OSError:
            continue
        if alvo in normalizar(texto):
            return True, f'edital local ({edital.parent.name})'
    return False, ''


def buscar_provas_por_assunto(opcoes: Opcoes, refresh: bool = False) -> list[ProvaRelacionada]:
    """Consulta o PCI por assunto/matéria; PCI desligado → aviso e lista vazia."""
    try:
        cfg = ler_pci(opcoes.contexto.config_global)
    except Exception as erro:  # noqa: BLE001
        avisar(logger, 'Não consegui ler a configuração do PCI.', detalhe=str(erro))
        return []
    if not getattr(cfg, 'enabled', False):
        avisar(
            logger,
            'A busca de provas no PCI está desligada.',
            'ligue o PCI Concursos nas Configurações se quiser provas anteriores por assunto.',
        )
        opcoes.saida('PCI desligado: busca de provas omitida.')
        return []

    assuntos = _assuntos_com_erro(opcoes)
    if not assuntos:
        opcoes.saida('Nenhum assunto com erro para buscar no PCI.')
        return []

    resultados: list[ProvaRelacionada] = []
    vistos: set[tuple[str, str]] = set()

    def consulta(cliente):
        achados: list[ProvaRelacionada] = []
        for ass, mat, banca in assuntos:
            termo = ' '.join(p for p in (ass, mat) if p).strip()
            if not termo:
                continue
            provas = cliente.pesquisar_provas_anteriores(termo)
            if banca:
                mesmas = [
                    p for p in provas if normalizar(p.organizadora or '') == normalizar(banca)
                ]
                if mesmas:
                    provas = mesmas
            tema, fonte = _tema_no_edital_local(opcoes.contexto.raiz, ass)
            for prova in provas[:5]:
                url = prova.link or ''
                chave = (ass, url)
                if not url or chave in vistos:
                    continue
                vistos.add(chave)
                achados.append(
                    ProvaRelacionada(
                        ass=ass,
                        prova_url=url,
                        orgao=prova.orgao or '',
                        banca=prova.organizadora or banca,
                        ano='' if prova.ano is None else str(prova.ano),
                        tema_no_edital=tema,
                        fonte_tema=fonte or 'pci',
                    )
                )
        return achados

    try:
        resultados = consultar_pci(opcoes, cfg, refresh, consulta)
    except ErroDoUsuario:
        raise
    except Exception as erro:  # noqa: BLE001
        avisar(logger, 'PCI: falha na busca por assunto.', detalhe=str(erro))
        return []

    pasta = _pasta(opcoes)
    pasta.mkdir(parents=True, exist_ok=True)
    linhas = [
        {
            'ass': r.ass,
            'prova_url': r.prova_url,
            'orgao': r.orgao,
            'banca': r.banca,
            'ano': r.ano,
            'tema_no_edital': 'sim' if r.tema_no_edital else 'nao',
            'fonte_tema': r.fonte_tema,
        }
        for r in resultados
    ]
    buf = io.StringIO()
    escritor = csv.DictWriter(buf, fieldnames=COLUNAS_PCI_PROVAS, lineterminator='\n')
    escritor.writeheader()
    escritor.writerows(linhas)
    gravar_se_mudou(pasta / ARQUIVO_PCI_PROVAS, buf.getvalue())

    por_ass: dict[str, list[ProvaRelacionada]] = {}
    for r in resultados:
        por_ass.setdefault(r.ass, []).append(r)
    for ass, lista in por_ass.items():
        opcoes.saida(
            f'Você errou em {ass}. Encontrei {len(lista)} prova(s) anterior(es) que cobrem esse tema: '
            + ', '.join(p.prova_url for p in lista[:3])
        )
    if not resultados:
        opcoes.saida('Nenhuma prova relacionada encontrada no PCI para os assuntos errados.')
    return resultados
