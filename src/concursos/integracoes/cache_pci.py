"""Cache local das respostas do PCI (`.concurso/cache/pci_mcp.json`), com validade de `ttl_horas`."""

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from concursos.arquivos import gravar_se_mudou
from concursos.erros import avisar
from concursos.texto import normalizar

logger = logging.getLogger(__name__)

ARQUIVO_CACHE = Path('cache') / 'pci_mcp.json'


def argumentos_normalizados(argumentos: dict[str, Any]) -> dict[str, Any]:
    """Sem os vazios e sem o `False`, que é o padrão de toda opção booleana do servidor."""
    return {
        chave: valor.strip() if isinstance(valor, str) else valor
        for chave, valor in sorted(argumentos.items())
        if valor not in (None, '', False)
    }


def chave(ferramenta: str, argumentos: dict[str, Any]) -> str:
    """Sem acento e sem caixa: "Analista" e "analista" são a mesma consulta."""
    comparaveis = {
        nome: normalizar(valor) if isinstance(valor, str) else valor
        for nome, valor in argumentos_normalizados(argumentos).items()
    }
    texto = json.dumps([ferramenta, comparaveis], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class Entrada:
    resposta: dict
    vencida: bool
    obtido_em: str


class CachePci:
    def __init__(
        self,
        caminho: Path,
        ttl_horas: float,
        agora: Callable[[], datetime] = datetime.now,
        gravar: bool = True,
    ) -> None:
        self.caminho = caminho
        self.ttl = timedelta(hours=ttl_horas)
        self.agora = agora
        self.gravar = gravar
        self._entradas: dict[str, dict] | None = None

    @property
    def entradas(self) -> dict[str, dict]:
        if self._entradas is None:
            self._entradas = self._ler()
        return self._entradas

    def _ler(self) -> dict[str, dict]:
        if not self.caminho.exists():
            return {}
        try:
            dados = json.loads(self.caminho.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as erro:
            avisar(
                logger,
                'PCI: não consegui ler as buscas guardadas; vou buscar tudo de novo.',
                detalhe=f'cache ilegível em {self.caminho} ({erro}); começando vazio',
            )
            return {}
        return dados if isinstance(dados, dict) else {}

    def obter(self, ferramenta: str, argumentos: dict[str, Any]) -> Entrada | None:
        entrada = self.entradas.get(chave(ferramenta, argumentos))
        if not entrada:
            return None
        try:
            obtido = datetime.fromisoformat(entrada['obtido_em'])
        except (KeyError, TypeError, ValueError):
            return None
        return Entrada(entrada['resposta'], self.agora() - obtido > self.ttl, entrada['obtido_em'])

    def guardar(self, ferramenta: str, argumentos: dict[str, Any], resposta: dict) -> None:
        self.entradas[chave(ferramenta, argumentos)] = {
            'ferramenta': ferramenta,
            'argumentos': argumentos_normalizados(argumentos),
            'obtido_em': self.agora().isoformat(timespec='seconds'),
            'data_atual': (resposta.get('meta') or {}).get('data_atual', ''),
            'resposta': resposta,
        }

    def salvar(self) -> bool:
        if not self.gravar or self._entradas is None:
            return False
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        texto = json.dumps(self._entradas, ensure_ascii=False, indent=1, sort_keys=True) + '\n'
        return gravar_se_mudou(self.caminho, texto)
