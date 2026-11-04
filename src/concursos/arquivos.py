import copy
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Concatenate, ParamSpec, TypeVar

from concursos.manifesto import hash_arquivo

P = ParamSpec('P')
R = TypeVar('R')


def gravar_se_mudou(caminho: Path, texto: str) -> bool:
    """Grava só quando o conteúdo muda, para que reexecuções não mexam no `mtime` das análises."""
    if caminho.exists() and caminho.read_text(encoding='utf-8') == texto:
        return False
    caminho.write_text(texto, encoding='utf-8')
    return True


def lido_uma_vez(leitura: Callable[Concatenate[Path, P], R]) -> Callable[Concatenate[Path, P], R]:
    """Guarda o resultado de uma leitura de arquivo pelo caminho e pelo hash do conteúdo: o mesmo PDF pedido
    de novo na execução (o próximo candidato, o status depois da análise) não é relido nem passa de novo pelo
    OCR. O primeiro argumento é o caminho; o resultado volta como cópia rasa, para quem o altera."""
    guardados: dict[tuple, R] = {}

    @wraps(leitura)
    def ler(caminho: Path, /, *args: P.args, **kwargs: P.kwargs) -> R:
        chave = (caminho.resolve(), hash_arquivo(caminho), args, tuple(sorted(kwargs.items())))
        if chave not in guardados:
            guardados[chave] = leitura(caminho, *args, **kwargs)
        return copy.copy(guardados[chave])

    return ler
