"""Busca PCI por assunto (MCP mockado)."""

from types import SimpleNamespace

from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.tec_pci import buscar_provas_por_assunto
from concursos.integracoes.pci_mcp import ProvaAnteriorPci
from concursos.pratica_tec import ARQUIVO_PCI_PROVAS, PASTA_PRATICA, ConfiguracaoPratica


def test_pci_desligado_omite_com_aviso(tmp_path, monkeypatch):
    from concursos.aplicacao import tec_pci

    monkeypatch.setattr(tec_pci, 'ler_pci', lambda _p: SimpleNamespace(enabled=False))
    msgs = []
    opcoes = Opcoes(contexto=SimpleNamespace(config_global=tmp_path / 'g'), saida=msgs.append)
    assert buscar_provas_por_assunto(opcoes) == []
    assert any('PCI desligado' in m for m in msgs)


def test_busca_grava_csv(tmp_path, monkeypatch):
    from concursos.aplicacao import tec_pci

    pasta = tmp_path / 'analises' / 'ana' / PASTA_PRATICA
    pasta.mkdir(parents=True)
    (pasta / 'tec_respostas.csv').write_text(
        'id,tipo_questao,mat,ass,banca,ano,gab,marc,resultado,tem_comentario\n'
        'q1,multipla_escolha,Redes,Neurais,FGV,2020,B,A,erro,nao\n',
        encoding='utf-8',
    )
    monkeypatch.setattr(tec_pci, 'ler_pci', lambda _p: SimpleNamespace(enabled=True))
    monkeypatch.setattr(
        tec_pci.pratica_app,
        'exigir_configuracao_pratica',
        lambda _c: ConfiguracaoPratica(entrada=tmp_path / 'tec', candidato='ana'),
    )
    monkeypatch.setattr(
        tec_pci,
        'pasta_do_candidato',
        lambda _c, _n: tmp_path / 'analises' / 'ana',
    )

    prova = ProvaAnteriorPci(
        id=1,
        descricao='Prova X',
        orgao='INSS',
        ano=2019,
        organizadora='FGV',
        link='https://pciconcursos.com.br/provas/1',
    )

    def fake_consultar(opcoes, cfg, refresh, consulta):
        cliente = SimpleNamespace(pesquisar_provas_anteriores=lambda termo: [prova])
        return consulta(cliente)

    monkeypatch.setattr(tec_pci, 'consultar_pci', fake_consultar)

    opcoes = Opcoes(
        contexto=SimpleNamespace(config_global=tmp_path / 'g', raiz=tmp_path),
        saida=lambda _t: None,
    )
    resultados = buscar_provas_por_assunto(opcoes)
    assert len(resultados) == 1
    assert resultados[0].ass == 'Neurais'
    assert (pasta / ARQUIVO_PCI_PROVAS).is_file()
    texto = (pasta / ARQUIVO_PCI_PROVAS).read_text(encoding='utf-8')
    assert 'Neurais' in texto
    assert 'pciconcursos.com.br' in texto
