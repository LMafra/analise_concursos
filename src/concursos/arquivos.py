from pathlib import Path


def gravar_se_mudou(caminho: Path, texto: str) -> bool:
    """Grava só quando o conteúdo muda, para que reexecuções não mexam no `mtime` das análises."""
    if caminho.exists() and caminho.read_text(encoding='utf-8') == texto:
        return False
    caminho.write_text(texto, encoding='utf-8')
    return True
