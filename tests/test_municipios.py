from concursos import municipios


def test_lista_do_ibge_tem_as_27_ufs_e_todos_os_municipios():
    assert len(municipios.ufs()) == 27
    assert sum(len(municipios.municipios(uf)) for uf in municipios.ufs()) >= 5570
    assert set(municipios.ufs()) == set(municipios.REGIAO_DA_UF)


def test_municipios_da_uf_em_qualquer_caixa_e_vazio_sem_uf():
    assert 'Belo Horizonte' in municipios.municipios('mg')
    assert municipios.municipios('') == []
    assert municipios.municipios('BR') == []


def test_cidade_da_uf_ignora_acento_e_caixa_e_recusa_outra_uf():
    assert municipios.cidade_da_uf('sao paulo', 'SP') == 'São Paulo'
    assert municipios.cidade_da_uf('Belo Horizonte', 'SP') is None
