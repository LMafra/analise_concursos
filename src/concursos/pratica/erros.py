class ExportacaoInvalidaError(ValueError):
    pass


class CompletudeInvalidaError(ExportacaoInvalidaError):
    """Mais questões no arquivo que o caderno declara em `cads.res`."""