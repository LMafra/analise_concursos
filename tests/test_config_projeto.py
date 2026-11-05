import re
from pathlib import Path

import pytest

from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.config.contexto import resolver_contexto
from concursos.configuracao import ConfiguracaoGlobal, configuracao_do_projeto

RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parents[1]
PACOTE = RAIZ_DO_REPOSITORIO / 'src' / 'concursos'


def projeto_com(tmp_path: Path, config_toml: str | None = None) -> Path:
    raiz = tmp_path / 'projeto'
    (raiz / '.concurso').mkdir(parents=True)
    if config_toml is not None:
        (raiz / '.concurso' / 'config.toml').write_text(config_toml, encoding='utf-8')
    return raiz


def contexto_de(raiz: Path, **extra):
    return resolver_contexto(cwd=raiz, ambiente={'CONCURSO_HOME': str(raiz.parent / 'home')}, **extra)


def test_limiares_e_alvo_vem_do_config_toml_do_projeto(tmp_path):
    raiz = projeto_com(
        tmp_path, '[analise]\nlimiar_topico_baixo = 0.5\nlimiar_confianca = 0.8\nconcurso_alvo = "alvo_26"\n'
    )

    configuracao = configuracao_do_projeto(contexto_de(raiz))

    assert configuracao == ConfiguracaoGlobal(0.8, 0.5, 'alvo_26')


def test_sem_config_toml_usa_os_padroes(tmp_path):
    assert configuracao_do_projeto(contexto_de(projeto_com(tmp_path))) == ConfiguracaoGlobal()


@pytest.mark.parametrize(
    ('conteudo', 'mensagem'),
    [
        ('[analise]\nlimiar = 0.5\n', 'campos desconhecidos limiar'),
        ('[analise]\nlimiar_topico_baixo = 1.5\n', 'limiar_topico_baixo deve ser um número entre 0 e 1'),
        ('[analise]\nconcurso_alvo = ""\n', 'concurso_alvo'),
        ('[analise\n', 'config.toml'),
    ],
)
def test_config_toml_invalido_aponta_o_campo(tmp_path, conteudo, mensagem):
    raiz = projeto_com(tmp_path, conteudo)

    with pytest.raises(ConfiguracaoInvalidaError, match=mensagem):
        configuracao_do_projeto(contexto_de(raiz))


def test_contexto_sobe_ate_a_pasta_do_projeto(tmp_path):
    raiz = projeto_com(tmp_path)
    (raiz / 'notebooks').mkdir()

    contexto = contexto_de(raiz / 'notebooks')

    assert contexto.raiz == raiz
    assert contexto.provas == raiz / 'provas'


def test_contexto_nao_confunde_a_pasta_global_com_a_do_projeto(tmp_path):
    home = tmp_path / 'usuario'
    (home / '.concurso').mkdir(parents=True)
    (home / 'trabalho').mkdir()

    contexto = resolver_contexto(cwd=home / 'trabalho', ambiente={'CONCURSO_HOME': str(home / '.concurso')})

    assert contexto.raiz == home / 'trabalho'


def test_pastas_do_config_toml_com_flag_e_variavel_por_cima(tmp_path):
    raiz = projeto_com(tmp_path, '[pastas]\nprovas = "minhas_provas"\nanalises = "/fora/saida"\n')
    ambiente = {'CONCURSO_HOME': str(tmp_path / 'home')}

    padrao = resolver_contexto(cwd=raiz, ambiente=ambiente)
    por_variavel = resolver_contexto(cwd=raiz, ambiente={**ambiente, 'CONCURSO_PROVAS': 'outra'})
    por_flag = resolver_contexto(
        cwd=raiz, ambiente={**ambiente, 'CONCURSO_PROVAS': 'outra'}, provas=Path('da_flag')
    )

    assert (padrao.provas, padrao.analises) == (raiz / 'minhas_provas', Path('/fora/saida'))
    assert por_variavel.provas == raiz / 'outra'
    assert por_flag.provas == raiz / 'da_flag'


def test_taxonomia_fica_na_pasta_do_projeto(tmp_path):
    raiz = projeto_com(tmp_path)
    (raiz / 'taxonomia.yaml').write_text('{}', encoding='utf-8')

    assert contexto_de(raiz).taxonomia == raiz / '.concurso' / 'taxonomia.yaml'


CPF = re.compile(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b')
CAMINHO_DE_USUARIO = re.compile(r'/home/\w+|/Users/\w+|[A-Za-z]:\\\\?Users\\\\?\w+')


def arquivos_do_pacote() -> list[Path]:
    do_pacote = [p for p in PACOTE.rglob('*') if p.suffix in {'.py', '.yaml', '.yml', '.toml'}]
    empacotamento = RAIZ_DO_REPOSITORIO / 'empacotamento'
    extensoes = {'.py', '.spec', '.iss', '.ps1', '.sh', '.md'}
    return do_pacote + [
        p for p in empacotamento.rglob('*') if p.suffix in extensoes and 'construcao' not in p.parts
    ]


def test_sem_dado_pessoal_no_pacote():
    problemas = [
        f'{arquivo.relative_to(RAIZ_DO_REPOSITORIO)}: {achado.group()}'
        for arquivo in arquivos_do_pacote()
        for padrao in (CPF, CAMINHO_DE_USUARIO)
        for achado in padrao.finditer(arquivo.read_text(encoding='utf-8'))
    ]
    assert problemas == []


def test_nenhum_concurso_local_citado_no_pacote():
    provas = RAIZ_DO_REPOSITORIO / 'provas'
    if not provas.is_dir():
        pytest.skip('sem provas/ locais para conferir')
    slugs = [p.name for p in provas.iterdir() if p.is_dir() and not p.name.startswith('.')]
    padrao = re.compile(r'\b(' + '|'.join(map(re.escape, slugs)) + r')\b')
    problemas = [
        f'{arquivo.relative_to(RAIZ_DO_REPOSITORIO)}: {achado.group()}'
        for arquivo in arquivos_do_pacote()
        for achado in padrao.finditer(arquivo.read_text(encoding='utf-8'))
    ]
    assert problemas == []
