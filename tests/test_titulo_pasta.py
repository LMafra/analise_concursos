from concursos.aplicacao.nomes import titulo_amigavel_da_pasta
from concursos.linguagem import caminho_curto


def test_titulo_amigavel_remove_sufixo_pci_e_underscores():
    assert titulo_amigavel_da_pasta('camara_dos_deputados_2002_pci11873702') == 'Camara dos deputados 2002'


def test_titulo_amigavel_mantem_nome_ja_limpo():
    assert titulo_amigavel_da_pasta('TCU 2025') == 'TCU 2025'


def test_caminho_curto_abreviado():
    assert caminho_curto('/mnt/c/Users/lucas/Documents/Concursos') == '…/Documents/Concursos'


def test_caminho_curto_curto_permanece():
    assert caminho_curto('/tmp/x') == '/tmp/x'
