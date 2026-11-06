"""Monta o pacote de estudo de um sistema e o manifesto `estudo.json` da release.

Roda no `estudo.yml`, no runner do próprio sistema (o Python do pacote precisa rodar para o uv
instalar as dependências nativas certas):

    uv run --no-sync python empacotamento/estudo/montar.py montar linux-x86_64 dist/estudo
    uv run --no-sync python empacotamento/estudo/montar.py manifesto dist/estudo
    uv run --no-sync python empacotamento/estudo/montar.py upstream   # tag nova do open-notebook, ou nada

Layout dentro do pacote (a raiz é `estudo-<versao>/`):

    python/                  Python 3.12 standalone, com o open-notebook e os embeddings instalados
    open-notebook/           código da tag (api/, commands/, open_notebook/, prompts/, migrations)
    bin/surreal[.exe]        SurrealDB 2.x
    modelo/                  ONNX e tokenizer do modelo de embeddings
    tiktoken/                cache do o200k_base, para o open-notebook não baixar nada
    servidor_embeddings.py
    LICENSES/
    estudo.toml              versões, lido pelo supervisor
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'src'))

from concursos.estudo import manifesto  # noqa: E402

AQUI = Path(__file__).resolve().parent
VERSAO = AQUI / 'versao.toml'
SISTEMAS = ('linux-x86_64', 'windows-x64')
URL_PYTHON = 'https://github.com/astral-sh/python-build-standalone/releases/download'
URL_SURREAL = 'https://github.com/surrealdb/surrealdb/releases/download'
URL_UPSTREAM = 'https://github.com/lfnovo/open-notebook'
URL_HF = 'https://huggingface.co'
REMOVER_DO_CODIGO = ('frontend', 'docs', 'tests', '.github', 'docker', 'scripts', 'setup_guide')
REMOVER_DO_PYTHON = ('pip', 'pandas/tests')
# o podcast_creator importa o imageio_ffmpeg ao carregar; os podcasts ficam fora do pacote
SUBSTITUTOS = {
    'imageio_ffmpeg': (
        'def get_ffmpeg_exe():\n    raise RuntimeError("os podcasts não fazem parte do pacote de estudo")\n'
    ),
}


def ler_versao(caminho: Path = VERSAO) -> dict:
    return tomllib.loads(caminho.read_text(encoding='utf-8'))


def versao_do_pacote(config: dict) -> str:
    return f'{config["open_notebook"]["tag"].removeprefix("v")}-{config["revisao"]}'


def nome_do_arquivo(versao: str, sistema: str) -> str:
    return f'estudo-{versao}-{manifesto.SUFIXOS[sistema]}'


def nome_cache_tiktoken(url: str) -> str:
    """O tiktoken guarda cada arquivo pelo SHA-1 da URL."""
    return hashlib.sha1(url.encode()).hexdigest()


def python_do_pacote(raiz: Path, sistema: str) -> Path:
    return raiz / 'python' / ('python.exe' if sistema == 'windows-x64' else 'bin/python3')


def comando_export(config: dict, completo: bool, destino: Path) -> list[str]:
    comando = ['uv', 'export', '--frozen', '--no-dev', '--no-emit-project', '--no-hashes', '-o', str(destino)]
    if not completo:
        for pacote in config['open_notebook'].get('excluir', []):
            comando += ['--no-emit-package', pacote]
    return comando


def _baixar(url: str, destino: Path, sha256: str | None = None) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as resposta, destino.open('wb') as arquivo:
        shutil.copyfileobj(resposta, arquivo)
    if sha256 and manifesto.sha256_do_arquivo(destino) != sha256:
        destino.unlink()
        raise SystemExit(f'SHA-256 de {url} não confere')
    return destino


def _extrair_tar(arquivo: Path, destino: Path) -> None:
    with tarfile.open(arquivo) as tar:
        tar.extractall(destino, filter='data')


def _tamanho(pasta: Path) -> int:
    return sum(p.stat().st_size for p in pasta.rglob('*') if p.is_file() and not p.is_symlink())


def site_packages(python: Path) -> Path:
    saida = subprocess.run(
        [str(python), '-c', 'import sysconfig; print(sysconfig.get_paths()["purelib"])'],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(saida.stdout.strip())


def escrever_substitutos(python: Path) -> None:
    """Módulos vazios no lugar dos pacotes excluídos que o open-notebook importa ao abrir, e a
    remoção do que não roda no pacote (pip, testes do pandas)."""
    pacotes = site_packages(python)
    for modulo, codigo in SUBSTITUTOS.items():
        (pacotes / modulo).mkdir(exist_ok=True)
        (pacotes / modulo / '__init__.py').write_text(codigo, encoding='utf-8')
    for sobra in REMOVER_DO_PYTHON:
        shutil.rmtree(pacotes / sobra, ignore_errors=True)


def montar(sistema: str, saida: Path, completo: bool = False, config: dict | None = None) -> Path:
    config = config or ler_versao()
    versao = versao_do_pacote(config)
    temporaria = Path(tempfile.mkdtemp(prefix='estudo-'))
    raiz = temporaria / f'estudo-{versao}'
    raiz.mkdir()

    py = config['python'][sistema]
    arquivo_py = _baixar(
        f'{URL_PYTHON}/{config["python"]["build"]}/{py["arquivo"]}', temporaria / py['arquivo'], py['sha256']
    )
    _extrair_tar(arquivo_py, raiz)

    commit = config['open_notebook']['commit']
    codigo = _baixar(f'{URL_UPSTREAM}/archive/{commit}.tar.gz', temporaria / 'open-notebook.tar.gz')
    _extrair_tar(codigo, temporaria)
    origem = temporaria / f'open-notebook-{commit}'
    requisitos = temporaria / 'requisitos.txt'
    subprocess.run(comando_export(config, completo, requisitos), cwd=origem, check=True)
    python = python_do_pacote(raiz, sistema)
    subprocess.run(
        [
            *(
                'uv',
                'pip',
                'install',
                '--python',
                str(python),
                '--break-system-packages',
                '--compile-bytecode',
            ),
            *('--no-deps', '-r', str(requisitos)),
        ],
        check=True,
    )
    emb = config['embeddings']
    travados = requisitos.read_text(encoding='utf-8').lower()
    extras = [f'onnxruntime=={emb["onnxruntime"]}']
    if 'tokenizers==' not in travados:
        extras.append(f'tokenizers=={emb["tokenizers"]}')
    subprocess.run(
        [
            'uv',
            'pip',
            'install',
            '--python',
            str(python),
            '--break-system-packages',
            '--compile-bytecode',
            *extras,
        ],
        check=True,
    )
    escrever_substitutos(python)
    for nome in REMOVER_DO_CODIGO:
        shutil.rmtree(origem / nome, ignore_errors=True)
    shutil.copytree(origem, raiz / 'open-notebook')

    sur = config['surreal'][sistema]
    baixado = _baixar(
        f'{URL_SURREAL}/{config["surreal"]["versao"]}/{sur["arquivo"]}',
        temporaria / sur['arquivo'],
        sur['sha256'],
    )
    (raiz / 'bin').mkdir()
    if sistema == 'windows-x64':
        shutil.copy2(baixado, raiz / 'bin' / 'surreal.exe')
    else:
        _extrair_tar(baixado, temporaria / 'surreal')
        shutil.copy2(temporaria / 'surreal' / 'surreal', raiz / 'bin' / 'surreal')
        (raiz / 'bin' / 'surreal').chmod(0o755)

    modelo = config['modelo']
    for item in modelo['arquivos']:
        url = f'{URL_HF}/{modelo["repositorio"]}/resolve/{modelo["revisao"]}/{item["nome"]}'
        _baixar(url, raiz / 'modelo' / item['nome'], item['sha256'])

    tik = config['tiktoken']
    _baixar(tik['url'], raiz / 'tiktoken' / nome_cache_tiktoken(tik['url']), tik['sha256'])

    shutil.copy2(AQUI / 'servidor_embeddings.py', raiz / 'servidor_embeddings.py')
    licencas = raiz / 'LICENSES'
    licencas.mkdir()
    shutil.copy2(origem / 'LICENSE', licencas / 'open-notebook-MIT.txt')
    _baixar(
        f'{URL_SURREAL}/{config["surreal"]["versao"]}/LICENSE',
        licencas / 'surrealdb-BSL-1.1.txt',
        config['surreal']['licenca_sha256'],
    )
    (licencas / 'modelo.txt').write_text(
        f'{modelo["nome"]} ({modelo["repositorio"]}, revisão {modelo["revisao"]}): {modelo["licenca"]}\n',
        encoding='utf-8',
    )
    licenca_py = next((raiz / 'python').glob('**/LICENSE.txt'), None)
    if licenca_py:
        shutil.copy2(licenca_py, licencas / 'python-PSF.txt')

    (raiz / 'estudo.toml').write_text(
        '\n'.join(
            [
                f'versao = "{versao}"',
                f'open_notebook = "{config["open_notebook"]["tag"].removeprefix("v")}"',
                f'surreal = "{config["surreal"]["versao"]}"',
                f'modelo = "{modelo["nome"]}"',
                f'dimensoes = {modelo["dimensoes"]}',
                f'tiktoken = "{nome_cache_tiktoken(tik["url"])}"',
                '',
            ]
        ),
        encoding='utf-8',
    )

    saida.mkdir(parents=True, exist_ok=True)
    destino = saida / nome_do_arquivo(versao, sistema)
    if sistema == 'windows-x64':
        with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as arquivo_zip:
            for caminho in sorted(raiz.rglob('*')):
                arquivo_zip.write(caminho, caminho.relative_to(temporaria).as_posix())
    else:
        with tarfile.open(destino, 'w:xz', preset=6) as tar:
            tar.add(raiz, arcname=raiz.name)
    (saida / f'{destino.name}.extraido').write_text(str(_tamanho(raiz)), encoding='utf-8')
    shutil.rmtree(temporaria, ignore_errors=True)
    return destino


def gerar_manifesto(pasta: Path, config: dict | None = None, hoje: str | None = None) -> Path:
    config = config or ler_versao()
    versao = versao_do_pacote(config)
    extraidos = {}
    for sistema in SISTEMAS:
        marca = pasta / f'{nome_do_arquivo(versao, sistema)}.extraido'
        if not marca.exists():
            raise SystemExit(f'falta o pacote de {sistema} em {pasta}')
        extraidos[sistema] = int(marca.read_text(encoding='utf-8'))
    modelo = config['modelo']
    conteudo = manifesto.montar_manifesto(
        open_notebook=config['open_notebook']['tag'].removeprefix('v'),
        revisao=config['revisao'],
        app_minimo=config['app_minimo'],
        publicado_em=hoje or datetime.now(UTC).date().isoformat(),
        modelo={'nome': modelo['nome'], 'revisao': modelo['revisao'], 'dimensoes': modelo['dimensoes']},
        arquivos=sorted(pasta.iterdir()),
        extraidos=extraidos,
    )
    destino = pasta / manifesto.ARQUIVO_MANIFESTO
    destino.write_bytes(conteudo)
    return destino


def tag_upstream_nova(config: dict, tags: list[str]) -> str | None:
    """A tag estável mais nova do upstream, se for diferente da do `versao.toml`."""
    from packaging.version import InvalidVersion, Version

    estaveis = []
    for tag in tags:
        try:
            versao = Version(tag.removeprefix('v'))
        except InvalidVersion:
            continue
        if not versao.is_prerelease:
            estaveis.append((versao, tag))
    if not estaveis:
        return None
    mais_nova = max(estaveis)[1]
    atual = Version(config['open_notebook']['tag'].removeprefix('v'))
    return mais_nova if Version(mais_nova.removeprefix('v')) > atual else None


def trocar_upstream(texto: str, tag: str, commit: str) -> str:
    """O `versao.toml` apontando para outra tag do open-notebook, com a revisão de volta a 1."""
    linhas = []
    secao = ''
    for linha in texto.splitlines(keepends=True):
        limpa = linha.strip()
        if limpa.startswith('['):
            secao = limpa
        if secao == '' and limpa.startswith('revisao ='):
            linha = 'revisao = 1\n'
        elif secao == '[open_notebook]' and limpa.startswith('tag ='):
            linha = f'tag = "{tag}"\n'
        elif secao == '[open_notebook]' and limpa.startswith('commit ='):
            linha = f'commit = "{commit}"\n'
        linhas.append(linha)
    return ''.join(linhas)


def _api_github(caminho: str) -> object:
    cabecalhos = {'Accept': 'application/vnd.github+json'}
    if os.environ.get('GITHUB_TOKEN'):
        cabecalhos['Authorization'] = f'Bearer {os.environ["GITHUB_TOKEN"]}'
    pedido = urllib.request.Request(
        f'https://api.github.com/repos/lfnovo/open-notebook/{caminho}', headers=cabecalhos
    )
    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        return json.loads(resposta.read())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    comandos = parser.add_subparsers(dest='comando', required=True)
    p_montar = comandos.add_parser('montar')
    p_montar.add_argument('sistema', choices=SISTEMAS)
    p_montar.add_argument('saida', type=Path)
    p_montar.add_argument('--completo', action='store_true')
    comandos.add_parser('manifesto').add_argument('pasta', type=Path)
    comandos.add_parser('upstream')
    comandos.add_parser('atualizar').add_argument('tag')
    comandos.add_parser('versao')
    args = parser.parse_args(argv)
    if args.comando == 'montar':
        print(f'gravado: {montar(args.sistema, args.saida, args.completo)}')  # noqa: T201
    elif args.comando == 'manifesto':
        print(f'gravado: {gerar_manifesto(args.pasta)}')  # noqa: T201
    elif args.comando == 'upstream':
        releases = _api_github('releases?per_page=20')
        nova = tag_upstream_nova(ler_versao(), [r['tag_name'] for r in releases if not r.get('draft')])
        print(nova or '')  # noqa: T201
    elif args.comando == 'atualizar':
        commit = _api_github(f'commits/{args.tag}')['sha']
        VERSAO.write_text(
            trocar_upstream(VERSAO.read_text(encoding='utf-8'), args.tag, commit), encoding='utf-8'
        )
        print(f'{args.tag} ({commit})')  # noqa: T201
    else:
        print(versao_do_pacote(ler_versao()))  # noqa: T201
    return 0


if __name__ == '__main__':
    sys.exit(main())
