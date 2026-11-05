import tomllib
from pathlib import Path

import pytest
import yaml
from concurso_sintetico import ARQUIVOS_SIMPLES, config_simples, criar_concurso

from concursos import onboarding
from concursos.aplicacao import cadastro, inicio
from concursos.aplicacao.opcoes import Opcoes
from concursos.cadastro import cadastrar
from concursos.candidatos import ARQUIVO_CANDIDATO
from concursos.config.contexto import resolver_contexto
from concursos.deteccao import Papel
from concursos.erros import ErroDoUsuario
from concursos.modelo import Formato
from concursos.respostas import ler_respostas_csv

GABARITO_FGV = '# FGV - Gabarito definitivo\n1 A\n2 B\n'


class Roteiro:
    """Responde como o usuário: banca fgv, a sugestão no resto e `gravar` na confirmação."""

    def __init__(self, gravar: bool = True):
        self.gravar = gravar
        self.perguntas: list[str] = []
        self.mostrados: list[str] = []

    def escolher(self, pergunta, opcoes, sugestao=None):
        self.perguntas.append(pergunta)
        return 'fgv' if 'banca' in pergunta else sugestao or opcoes[0]

    def perguntar(self, pergunta, sugestao=None):
        self.perguntas.append(pergunta)
        return sugestao

    def confirmar(self, pergunta, padrao=False):
        return self.gravar

    def mostrar(self, texto):
        self.mostrados.append(texto)


@pytest.fixture
def raiz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / 'projeto'
    (pasta / 'provas').mkdir(parents=True)
    monkeypatch.chdir(pasta)
    return pasta


@pytest.fixture
def envio(tmp_path: Path) -> Path:
    pasta = tmp_path / 'envio'
    pasta.mkdir()
    return pasta


def opcoes(raiz: Path, interacao=None, saida=None) -> Opcoes:
    return Opcoes(resolver_contexto(cwd=raiz), interacao=interacao, saida=saida or (lambda _texto: None))


def test_papel_escolhido_pelo_usuario_vence_a_deteccao_sem_perguntar(tmp_path):
    pasta = tmp_path / 'alfa'
    pasta.mkdir()
    (pasta / 'notas.txt').write_text('1 A\n2 B\n', encoding='utf-8')
    roteiro = Roteiro()

    assert cadastrar(pasta, roteiro, {'notas.txt': Papel.GABARITO})

    dados = yaml.safe_load((pasta / 'concurso.yaml').read_text(encoding='utf-8'))
    assert [p['gabarito']['arquivo'] for p in dados['provas'].values()] == ['notas.txt']
    assert not any('gabarito ou respostas' in pergunta for pergunta in roteiro.perguntas)


def test_detectar_classifica_os_arquivos_enviados(envio):
    (envio / 'gabarito.txt').write_text(GABARITO_FGV, encoding='utf-8')
    (envio / 'respostas.txt').write_text('1 A\n2 C\n', encoding='utf-8')

    detectados = {d.caminho.name: d for d in cadastro.detectar_envio(envio)}

    assert detectados['gabarito.txt'].papel is Papel.GABARITO
    assert detectados['gabarito.txt'].banca == 'fgv'
    assert detectados['respostas.txt'].papel is Papel.RESPOSTAS


def test_envio_poe_a_prova_no_concurso_e_as_respostas_na_pasta_do_candidato(raiz, envio):
    (envio / 'gabarito.txt').write_text(GABARITO_FGV, encoding='utf-8')
    (envio / 'minhas.txt').write_text('1 A\n2 C\n', encoding='utf-8')
    papeis = {envio / 'gabarito.txt': Papel.GABARITO, envio / 'minhas.txt': Papel.RESPOSTAS}

    pasta = cadastro.cadastrar_envio(opcoes(raiz, Roteiro()), 'TCU 2025', papeis, 'Ana Teste')

    assert pasta == raiz / 'provas' / 'tcu_2025'
    dados = yaml.safe_load((pasta / 'concurso.yaml').read_text(encoding='utf-8'))
    assert 'respostas' not in dados
    assert 'minhas.txt' not in dados.get('ignorar', [])
    assert (pasta / 'candidatos' / 'ana_teste' / 'minhas.txt').is_file()
    perfil = yaml.safe_load(
        (pasta / 'candidatos' / 'ana_teste' / ARQUIVO_CANDIDATO).read_text(encoding='utf-8')
    )
    assert perfil['respostas'] == {'arquivo': 'minhas.txt'}


def test_envio_recusado_nao_grava_nada_nem_deixa_a_pasta(raiz, envio):
    (envio / 'gabarito.txt').write_text(GABARITO_FGV, encoding='utf-8')

    pasta = cadastro.cadastrar_envio(
        opcoes(raiz, Roteiro(gravar=False)), 'alfa', {envio / 'gabarito.txt': Papel.GABARITO}, None
    )

    assert pasta is None
    assert not (raiz / 'provas' / 'alfa').exists()


def test_envio_que_falha_no_cadastro_desfaz_a_copia(raiz, envio):
    (envio / 'edital.txt').write_text('qualquer coisa\n', encoding='utf-8')

    with pytest.raises(ValueError, match='nenhum gabarito'):
        cadastro.cadastrar_envio(opcoes(raiz, Roteiro()), 'alfa', {envio / 'edital.txt': Papel.EDITAL}, None)

    assert not (raiz / 'provas' / 'alfa').exists()


def test_envio_ignora_o_que_o_usuario_marcou_para_ignorar(raiz, envio):
    (envio / 'gabarito.txt').write_text(GABARITO_FGV, encoding='utf-8')
    (envio / 'foto.txt').write_text('nada\n', encoding='utf-8')
    papeis = {envio / 'gabarito.txt': Papel.GABARITO, envio / 'foto.txt': Papel.IGNORADO}

    pasta = cadastro.cadastrar_envio(opcoes(raiz, Roteiro()), 'alfa', papeis, None)

    assert not (pasta / 'foto.txt').exists()


def test_envio_nao_sobrescreve_arquivo_diferente_com_o_mesmo_nome(raiz, envio):
    criar_concurso(raiz / 'provas', 'alfa', config_simples('alfa'), ARQUIVOS_SIMPLES)
    (envio / 'gabarito.txt').write_text(GABARITO_FGV, encoding='utf-8')

    with pytest.raises(ErroDoUsuario, match='gabarito.txt'):
        cadastro.cadastrar_envio(
            opcoes(raiz, Roteiro()), 'alfa', {envio / 'gabarito.txt': Papel.GABARITO}, None
        )

    assert (raiz / 'provas' / 'alfa' / 'gabarito.txt').read_text(encoding='utf-8') == '1 A\n2 B\n'


def test_respostas_sem_candidato_pedem_o_nome(raiz, envio):
    (envio / 'gabarito.txt').write_text(GABARITO_FGV, encoding='utf-8')
    (envio / 'respostas.txt').write_text('1 A\n2 C\n', encoding='utf-8')
    papeis = {envio / 'gabarito.txt': Papel.GABARITO, envio / 'respostas.txt': Papel.RESPOSTAS}

    with pytest.raises(ErroDoUsuario, match='candidato'):
        cadastro.cadastrar_envio(opcoes(raiz, Roteiro()), 'alfa', papeis, None)

    assert not (raiz / 'provas' / 'alfa').exists()


def test_so_respostas_num_concurso_cadastrado_nao_refaz_o_cadastro(raiz, envio):
    pasta = criar_concurso(raiz / 'provas', 'alfa', config_simples('alfa'), ARQUIVOS_SIMPLES)
    antes = (pasta / 'concurso.yaml').read_bytes()
    (envio / 'folha.txt').write_text('1 B\n2 B\n', encoding='utf-8')
    roteiro = Roteiro()

    cadastro.cadastrar_envio(
        opcoes(raiz, roteiro), 'alfa', {envio / 'folha.txt': Papel.RESPOSTAS}, 'Bruno Teste'
    )

    assert (pasta / 'concurso.yaml').read_bytes() == antes
    assert roteiro.perguntas == []
    assert (pasta / 'candidatos' / 'bruno_teste' / 'folha.txt').is_file()


def test_nome_do_concurso_vazio_e_erro_do_usuario(raiz):
    with pytest.raises(ErroDoUsuario):
        cadastro.pasta_do_concurso(resolver_contexto(cwd=raiz), '  ')


def test_folha_manual_tem_as_questoes_e_as_letras_do_concurso(raiz):
    criar_concurso(raiz / 'provas', 'alfa', config_simples('alfa'), ARQUIVOS_SIMPLES)

    folha = cadastro.folha_manual(resolver_contexto(cwd=raiz), 'alfa')

    assert folha.questoes == [1, 2]
    assert set(folha.alternativas) == set(Formato.MULTIPLA_ESCOLHA.letras(None))


def test_respostas_digitadas_viram_csv_valido_na_pasta_do_candidato(raiz):
    pasta = criar_concurso(raiz / 'provas', 'alfa', config_simples('alfa'), ARQUIVOS_SIMPLES)

    destino = cadastro.gravar_respostas_digitadas(opcoes(raiz), 'alfa', 'Ana Teste', {1: 'A', 2: ''})

    assert destino == pasta / 'candidatos' / 'ana_teste' / 'respostas.csv'
    lidas = ler_respostas_csv(destino.read_bytes(), Formato.MULTIPLA_ESCOLHA, [1, 2], 'respostas.csv')
    assert [(r.questao, r.alternativa) for r in lidas][0] == (1, 'A')
    assert len(lidas) == 2


def test_resposta_digitada_invalida_nao_grava(raiz):
    pasta = criar_concurso(raiz / 'provas', 'alfa', config_simples('alfa'), ARQUIVOS_SIMPLES)

    with pytest.raises(ErroDoUsuario):
        cadastro.gravar_respostas_digitadas(opcoes(raiz), 'alfa', 'Ana Teste', {1: 'Z'})

    assert not (pasta / 'candidatos').exists()


def test_onboarding_pela_gui_grava_como_o_init_e_cria_a_pasta_de_provas(tmp_path, monkeypatch):
    raiz = tmp_path / 'novo projeto'
    raiz.mkdir()
    monkeypatch.chdir(raiz)
    contexto = resolver_contexto(cwd=raiz, data_dir=raiz / '.concurso')
    respostas = onboarding.Respostas(
        nome='Ana Teste', provas=raiz / 'provas', analises=raiz / 'analises', doctor=False
    )

    novas = inicio.concluir_onboarding(Opcoes(contexto), respostas)

    assert novas.contexto.candidato == 'ana_teste'
    assert (raiz / 'provas' / onboarding.ARQUIVO_LEIA_ME).is_file()
    config = tomllib.loads(contexto.config_projeto.read_text(encoding='utf-8'))
    assert config['pastas'] == {'provas': 'provas', 'analises': 'analises'}
    assert config['candidato'] == {'ultimo': 'ana_teste'}


def test_formulario_do_onboarding_exige_nome_e_resolve_pastas_relativas(tmp_path):
    contexto = resolver_contexto(cwd=tmp_path, data_dir=tmp_path / '.concurso')

    with pytest.raises(ErroDoUsuario, match='nome'):
        inicio.respostas_do_formulario(contexto, ' ', 'provas', 'analises', False)
    respostas = inicio.respostas_do_formulario(contexto, 'Ana Teste', 'minhas provas', '', True)

    assert respostas.provas == tmp_path / 'minhas provas'
    assert respostas.analises == contexto.analises


def test_respostas_atuais_do_onboarding_sao_os_padroes_do_init(tmp_path):
    contexto = resolver_contexto(cwd=tmp_path, data_dir=tmp_path / '.concurso')

    respostas = inicio.respostas_atuais(contexto)

    assert respostas.provas == tmp_path / 'provas'
    assert respostas.analises == tmp_path / 'analises'
    assert respostas.doctor is True
