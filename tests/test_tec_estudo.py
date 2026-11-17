"""Explicação TEC via open-notebook (HTTP mockado)."""

from types import SimpleNamespace

from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.tec_estudo import BLOCO_ALTERNATIVAS, PROMPT_ME, explicar_erros_tec
from concursos.pratica_tec import ConfiguracaoPratica


class ClienteFalso:
    def __init__(self):
        self.sources = []
        self.notas = []
        self.perguntas = []

    def listar_modelos(self, tipo=None):
        return [{'id': 'm1', 'name': 'm1'}]

    def buscar_notebook_por_nome(self, nome):
        return {'id': 'nb1', 'name': nome}

    def criar_notebook(self, nome, descricao=''):
        return {'id': 'nb1', 'name': nome}

    def listar_notas(self, notebook_id):
        return list(self.notas)

    def adicionar_source_texto(self, notebook_id, titulo, conteudo, embed=False):
        self.sources.append(titulo)
        return {'id': f's{len(self.sources)}'}

    def perguntar(self, pergunta, modelo_id):
        self.perguntas.append(pergunta)
        return {'answer': 'explicação gerada\n## A\nok\n## B\nok'}

    def criar_nota(self, notebook_id, titulo, conteudo):
        self.notas.append({'id': f'n{len(self.notas) + 1}', 'title': titulo, 'content': conteudo})
        return self.notas[-1]

    def atualizar_nota(self, nota_id, conteudo):
        return {}


def test_prompt_me_exige_alternativas_uma_a_uma():
    assert '{bloco}' in PROMPT_ME
    assert 'uma por uma' in BLOCO_ALTERNATIVAS
    formatado = PROMPT_ME.format(
        enun='x', alts='- A: a', gab='B', marc='A', com='', ass='Y', bloco=BLOCO_ALTERNATIVAS
    )
    assert BLOCO_ALTERNATIVAS in formatado


def test_explicar_erros_cria_source_e_note(tmp_path, monkeypatch):
    from concursos.aplicacao import tec_estudo

    entrada = tmp_path / 'tec'
    entrada.mkdir()
    (entrada / 'e.json').write_text(
        """{"app":"tec-erros","v":1,"erros":[{
          "id":"q1","enun":"Pergunta","gab":"B","marc":"A","ass":"Neurais","mat":"Redes",
          "alts":[{"l":"A","t":"um"},{"l":"B","t":"dois"},{"l":"C","t":"tres"}]
        }],"cads":[]}""",
        encoding='utf-8',
    )
    (tmp_path / 'analises' / 'ana' / 'pratica').mkdir(parents=True)
    (tmp_path / 'analises' / 'ana' / 'pratica' / 'tec_respostas.csv').write_text(
        'id,tipo_questao,mat,ass,banca,ano,gab,marc,resultado,tem_comentario\n'
        'q1,multipla_escolha,Redes,Neurais,,2020,B,A,erro,nao\n',
        encoding='utf-8',
    )

    cliente = ClienteFalso()
    monkeypatch.setattr(
        tec_estudo.pratica_app,
        'exigir_configuracao_pratica',
        lambda _c: ConfiguracaoPratica(entrada=entrada, candidato='ana'),
    )
    monkeypatch.setattr(tec_estudo, '_cliente', lambda _o: (cliente, 'm1'))
    monkeypatch.setattr(
        tec_estudo,
        'pasta_do_candidato',
        lambda _c, _n: tmp_path / 'analises' / 'ana',
    )
    monkeypatch.setattr(tec_estudo, 'ler_configuracao', lambda _p: SimpleNamespace(ativa=True))

    opcoes = Opcoes(
        contexto=SimpleNamespace(config_global=tmp_path / 'g.toml', raiz=tmp_path),
        saida=lambda _t: None,
    )
    resultado = explicar_erros_tec(opcoes, incluir_acertos=False)
    assert resultado.explicadas == 1
    assert any('Erro TEC — q1' in s for s in cliente.sources)
    assert any(n['title'].startswith('Explicação — q1') for n in cliente.notas)
    assert any(BLOCO_ALTERNATIVAS in p for p in cliente.perguntas)
    assert resultado.similares == 1
