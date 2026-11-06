"""Registra no open-notebook gerenciado o modelo de embeddings servido pelo pacote de estudo.

O modelo fica sem credencial: o endereço e o token vão pelas variáveis
`OPENAI_COMPATIBLE_BASE_URL_EMBEDDING` e `OPENAI_COMPATIBLE_API_KEY_EMBEDDING` na partida da API e do
worker, e mudam a cada sessão sem gravar nada no banco.
"""

from concursos.integracoes.open_notebook import ClienteOpenNotebook

PROVEDOR = 'openai_compatible'
NOME_MODELO = 'paraphrase-multilingual-MiniLM-L12-v2'


def registrar(cliente: ClienteOpenNotebook, nome: str = NOME_MODELO) -> str:
    """O ID do modelo de embeddings padrão, criando-o e marcando-o como padrão se faltar."""
    existentes = [
        m
        for m in cliente.listar_modelos('embedding')
        if m.get('provider') == PROVEDOR and str(m.get('name', '')).lower() == nome.lower()
    ]
    modelo_id = existentes[0]['id'] if existentes else cliente.criar_modelo(nome, PROVEDOR, 'embedding')['id']
    if (cliente.modelos_padrao() or {}).get('default_embedding_model') != modelo_id:
        cliente.gravar_modelos_padrao(default_embedding_model=modelo_id)
    return modelo_id
