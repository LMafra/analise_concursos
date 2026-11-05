"""Recurso de versão dos `.exe` do Windows (aba Detalhes nas propriedades do arquivo e o nome no SmartScreen).

O Windows só aceita quatro números; a parte de pré-release da versão PEP 440 fica no texto de `ProductVersion`.
"""

import re

EDITOR = 'LMafra'
PRODUTO = 'concurso-analise'
COPYRIGHT = 'Copyright (c) 2026 LMafra. Licença MIT.'


def versao_numerica(versao: str) -> tuple[int, int, int, int]:
    partes = [int(p) for p in re.match(r'\d+(?:\.\d+)*', versao).group().split('.')][:3]
    partes += [0] * (3 - len(partes))
    pos = re.search(r'\.post(\d+)', versao)
    return (*partes, int(pos.group(1)) if pos else 0)


def recurso_de_versao(versao: str, nome_interno: str, descricao: str) -> str:
    """Texto no formato de `pyi-grab_version`, que o `EXE(version=...)` do PyInstaller lê."""
    numeros = versao_numerica(versao)
    textos = {
        'CompanyName': EDITOR,
        'FileDescription': descricao,
        'FileVersion': versao,
        'InternalName': nome_interno,
        'LegalCopyright': COPYRIGHT,
        'OriginalFilename': f'{nome_interno}.exe',
        'ProductName': PRODUTO,
        'ProductVersion': versao,
    }
    linhas = ',\n            '.join(f'StringStruct({chave!r}, {valor!r})' for chave, valor in textos.items())
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numeros},
    prodvers={numeros},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('041604B0', [
            {linhas}
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1046, 1200])])
  ]
)
"""
