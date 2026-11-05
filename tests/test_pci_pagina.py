import pytest
from transporte_pci import FIXTURES

from concursos.integracoes.pagina_pci import ArquivoProvaPci, ler_arquivos, validar_link
from concursos.integracoes.pci_mcp import PciMcpFormatoError


def test_pagina_real_lista_os_arquivos_uma_vez_cada():
    html = (FIXTURES / 'pagina_prova.html').read_text(encoding='utf-8')
    assert ler_arquivos(html) == [
        ArquivoProvaPci('prova1_auditor_fiscal.pdf', 'prova1-auditor-fiscal.pdf'),
        ArquivoProvaPci('provas_2e3_auditor_fiscal.pdf', 'provas-2e3-auditor-fiscal.pdf'),
        ArquivoProvaPci('gabaritos.pdf', 'gabaritos.pdf'),
        ArquivoProvaPci('gabarito_definitivo_auditor.pdf', 'gabarito-definitivo-auditor.pdf'),
    ]


def test_ignora_compartilhar_e_links_comuns():
    html = (
        '<a class="item-link prova-pdf-link" data-code="x" data-arquivo="p.pdf" data-acao="compartilhar">Compartilhar</a>'
        '<a href="/outra" data-arquivo="q.pdf">q</a>'
    )
    assert ler_arquivos(html) == []


@pytest.mark.parametrize(
    'link',
    [
        'https://www.pciconcursos.com.br/provas/123/abc/prova.pdf',
        'https://exemplo.com/provas/download/x',
        'https://www.pciconcursos.com.br/noticias/x',
    ],
)
def test_so_aceita_pagina_de_prova(link: str):
    with pytest.raises(PciMcpFormatoError):
        validar_link(link)
