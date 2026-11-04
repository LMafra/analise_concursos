import os
import uuid

import pytest

from concursos.integracoes.open_notebook import ClienteOpenNotebook
from concursos.integracoes.sincronizacao_notebook import Documento, EstadoSincronizacao, Sincronizador

URL = os.environ.get('OPEN_NOTEBOOK_URL')

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason='defina OPEN_NOTEBOOK_URL para testar contra uma instância real'),
]


@pytest.fixture
def cliente() -> ClienteOpenNotebook:
    return ClienteOpenNotebook(URL, os.environ.get('OPEN_NOTEBOOK_PASSWORD'))


def test_sincroniza_duas_vezes_sem_escrever_na_segunda(cliente, tmp_path):
    nome = f'concurso-analise teste {uuid.uuid4().hex[:8]}'
    documento = Documento('relatorio.md', 'concurso-analise: teste/relatorio.md', '# Relatório fictício\n')
    nota = Documento('resumo', 'concurso-analise: resumo executivo', 'Resumo fictício.\n')
    estado = EstadoSincronizacao.ler(tmp_path / 'estado.json')

    primeira = Sincronizador(cliente, estado)
    notebook_id = primeira.notebook('teste', nome, [documento], [nota])
    segunda = Sincronizador(cliente, estado)
    segunda.notebook('teste', nome, [documento], [nota])

    try:
        assert primeira.relatorio.sucesso and primeira.relatorio.sources_enviadas == 1
        assert segunda.relatorio.sources_puladas == 1 and segunda.relatorio.notas_puladas == 1
        assert [s['title'] for s in cliente.listar_sources(notebook_id)] == [documento.titulo]
    finally:
        for source in cliente.listar_sources(notebook_id):
            cliente.apagar_source(source['id'])
