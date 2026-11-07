"""A página de uma prova no PCI (`/provas/download/<slug>`): só os nomes dos arquivos, nunca o PDF.

Os links de verdade saem de `POST /provas/link` depois do captcha, e o `robots.txt` proíbe `*.pdf` a robôs;
por isso o app lê só o HTML da página, que é permitido."""

import urllib.error
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser

from concursos.integracoes.pci_mcp import DICA_SERVIDOR, PciMcpFormatoError, PciMcpIndisponivelError

PREFIXO_PAGINA = 'https://www.pciconcursos.com.br/provas/'
AGENTE = 'concurso-analise (leitura da página da prova)'


@dataclass(frozen=True)
class ArquivoProvaPci:
    nome: str
    rotulo: str


class _Leitor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.arquivos: dict[str, str] = {}
        self._atual: str | None = None
        self._texto: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != 'a':
            return
        atributos = dict(attrs)
        classes = (atributos.get('class') or '').split()
        nome = atributos.get('data-arquivo')
        if 'prova-pdf-link' in classes and nome and atributos.get('data-acao') in (None, 'ver', 'baixar'):
            self._atual = nome
            self._texto = []

    def handle_data(self, dados: str) -> None:
        if self._atual is not None:
            self._texto.append(dados)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'a' and self._atual is not None:
            rotulo = ' '.join(''.join(self._texto).split()).removeprefix('Ver ').removeprefix('Baixar ')
            self.arquivos.setdefault(self._atual, rotulo or self._atual)
            self._atual = None


def ler_arquivos(html: str) -> list[ArquivoProvaPci]:
    """Os arquivos na ordem da página, um por `data-arquivo` (a página repete cada um em ver e baixar)."""
    leitor = _Leitor()
    leitor.feed(html)
    return [ArquivoProvaPci(nome, rotulo) for nome, rotulo in leitor.arquivos.items()]


def validar_link(link: str) -> str:
    if not link.startswith(PREFIXO_PAGINA) or link.lower().endswith('.pdf'):
        raise PciMcpFormatoError(
            'Este link não é de uma página de prova do PCI.',
            'escolha a prova pela busca de provas anteriores.',
            f'link de prova inesperado: {link}; o app só abre páginas em /provas/ do PCI',
        )
    return link


def baixar_pagina(link: str, timeout: float) -> str:
    requisicao = urllib.request.Request(validar_link(link), headers={'User-Agent': AGENTE})
    try:
        with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
            return resposta.read().decode('utf-8', errors='replace')
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise PciMcpIndisponivelError(
            'Não consegui abrir a página da prova no PCI.', DICA_SERVIDOR, f'{link}: {erro}'
        ) from erro
