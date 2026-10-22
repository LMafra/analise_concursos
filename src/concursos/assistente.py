import sys
from collections.abc import Callable
from typing import Protocol, TextIO


class AmbiguidadeError(ValueError):
    pass


class Interacao(Protocol):
    def escolher(self, pergunta: str, opcoes: list[str], sugestao: str | None = None) -> str: ...

    def perguntar(self, pergunta: str, sugestao: str | None = None) -> str | None: ...

    def confirmar(self, pergunta: str, padrao: bool = False) -> bool: ...

    def mostrar(self, texto: str) -> None: ...


class InteracaoConsole:
    def __init__(self, saida: TextIO | None = None, entrada: Callable[[str], str] | None = None):
        self._saida = saida or sys.stdout
        self._entrada = entrada or input

    def escolher(self, pergunta: str, opcoes: list[str], sugestao: str | None = None) -> str:
        self.mostrar(pergunta)
        for indice, opcao in enumerate(opcoes, start=1):
            marca = ' (sugerido)' if opcao == sugestao else ''
            self.mostrar(f'  {indice}) {opcao}{marca}')
        padrao = f' [{opcoes.index(sugestao) + 1}]' if sugestao in opcoes else ''
        while True:
            resposta = self._entrada(f'Escolha{padrao}: ').strip()
            if not resposta and sugestao in opcoes:
                return sugestao
            if resposta.isdigit() and 1 <= int(resposta) <= len(opcoes):
                return opcoes[int(resposta) - 1]
            self.mostrar(f'Opção inválida: digite um número de 1 a {len(opcoes)}.')

    def perguntar(self, pergunta: str, sugestao: str | None = None) -> str | None:
        padrao = f' [{sugestao}]' if sugestao else ''
        return self._entrada(f'{pergunta}{padrao}: ').strip() or sugestao

    def confirmar(self, pergunta: str, padrao: bool = False) -> bool:
        resposta = self._entrada(f'{pergunta} {"[S/n]" if padrao else "[s/N]"} ').strip().lower()
        return padrao if not resposta else resposta in {'s', 'sim'}

    def mostrar(self, texto: str) -> None:
        self._saida.write(texto + '\n')


class InteracaoAutomatica:
    """Aceita as sugestões sem perguntar; falha quando não há sugestão."""

    def __init__(self, saida: TextIO | None = None):
        self._saida = saida or sys.stdout

    def escolher(self, pergunta: str, opcoes: list[str], sugestao: str | None = None) -> str:
        if sugestao is None:
            raise AmbiguidadeError(
                f'{pergunta} (opções: {", ".join(opcoes)}); rode sem --aceitar-sugestoes para escolher'
            )
        return sugestao

    def perguntar(self, pergunta: str, sugestao: str | None = None) -> str | None:
        return sugestao

    def confirmar(self, pergunta: str, padrao: bool = False) -> bool:
        return True

    def mostrar(self, texto: str) -> None:
        self._saida.write(texto + '\n')
