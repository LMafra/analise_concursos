import logging

CODIGO_USUARIO = 1
CODIGO_AMBIENTE = 2


class ErroDoUsuario(Exception):
    """Falha que o usuário resolve sozinho: a causa em linguagem leiga, a dica com a ação e, quando houver, o
    detalhe técnico (nome de arquivo, campo, mensagem da biblioteca)."""

    codigo = CODIGO_USUARIO

    def __init__(self, causa: str, dica: str | None = None, detalhe: str | None = None) -> None:
        super().__init__(causa)
        self.causa = causa
        self.dica = dica
        self.detalhe = detalhe


class ErroDoAmbiente(ErroDoUsuario):
    codigo = CODIGO_AMBIENTE


def linhas_do_erro(erro: BaseException) -> list[str]:
    """`erro:`, e `dica:` e `detalhe:` só quando existem; vale para todo erro com `causa` (e `dica`)."""
    linhas = [f'erro: {getattr(erro, "causa", None) or erro}']
    linhas += [
        f'{rotulo}: {valor}' for rotulo in ('dica', 'detalhe') if (valor := getattr(erro, rotulo, None))
    ]
    return linhas


def avisar(logger: logging.Logger, texto: str, dica: str | None = None, detalhe: str | None = None) -> None:
    """Aviso em até três linhas na tela (`aviso:`, `dica:` e `detalhe:`); o texto não passa por `%`."""
    logger.warning('%s', texto, extra={'dica': dica, 'detalhe': detalhe})


def linhas_extras(record: logging.LogRecord) -> list[str]:
    return [
        f'{rotulo}: {valor}'
        for rotulo in ('dica', 'detalhe')
        if (valor := getattr(record, rotulo, None)) not in (None, '')
    ]


class FormatoComDica(logging.Formatter):
    """O formato pedido na primeira linha e a `dica:` e o `detalhe:` recuados nas seguintes."""

    def format(self, record: logging.LogRecord) -> str:
        return '\n'.join([super().format(record), *(f'    {linha}' for linha in linhas_extras(record))])
