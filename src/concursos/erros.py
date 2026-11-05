CODIGO_USUARIO = 1
CODIGO_AMBIENTE = 2


class ErroDoUsuario(Exception):
    """Falha que o usuário resolve sozinho: a mensagem diz a causa e a dica diz o comando."""

    codigo = CODIGO_USUARIO

    def __init__(self, causa: str, dica: str | None = None) -> None:
        super().__init__(causa)
        self.causa = causa
        self.dica = dica


class ErroDoAmbiente(ErroDoUsuario):
    codigo = CODIGO_AMBIENTE
