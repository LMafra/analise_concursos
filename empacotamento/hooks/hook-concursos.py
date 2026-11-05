# Os perfis YAML e o dist-info (versão e entry points `concurso.banca` e `concurso.ocr`) vão no pacote; os
# leitores de perfil citados como `modulo:funcao` são importados por nome, então todos os módulos entram.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

datas = collect_data_files('concursos') + copy_metadata('concurso-analise')
hiddenimports = collect_submodules('concursos')
