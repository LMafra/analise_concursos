"""Transporte falso do PCI: repete as respostas reais de tests/fixtures/pci/ e registra as chamadas."""

import json
from pathlib import Path
from typing import Any

from concursos.integracoes.pci_mcp import FERRAMENTAS, PciMcpIndisponivelError, interpretar

FIXTURES = Path(__file__).parent / 'fixtures' / 'pci'


def fixture(nome: str) -> dict:
    return json.loads((FIXTURES / f'{nome}.json').read_text(encoding='utf-8'))


def resposta(nome: str) -> dict:
    gravada = fixture(nome)
    return interpretar(gravada['ferramenta'], gravada['is_error'], gravada['texto'])


def payload(data: list[dict], data_atual: str = '2026-11-05', **meta: Any) -> dict:
    return {'meta': {'total': len(data), 'data_atual': data_atual, **meta}, 'data': data, 'errors': []}


def concurso(id: int, **campos: Any) -> dict:
    datas = {
        'inicio': '2026-11-01',
        'fim': '2026-11-20',
        'texto': '',
        'aberto': True,
        'em_breve': False,
        'dias_ate_inicio': -4,
        'dias_ate_fim': 15,
    } | campos.pop('datas', {})
    return {
        'id': id,
        'titulo': f'Concurso {id}',
        'cargos_resumo': 'Analista',
        'cargos': ['ANALISTA'],
        'cargos_total': 1,
        'vagas_salario': '1 vaga',
        'formacao': 'Superior',
        'regiao': 'SUDESTE',
        'uf': 'MG',
        'datas': datas,
        'noticia': {
            'id': id,
            'titulo': f'Concurso {id}',
            'link': f'https://www.pciconcursos.com.br/noticias/{id}',
        },
    } | campos


class TransporteFalso:
    """`respostas` mapeia a ferramenta para um payload, uma exceção ou uma função dos argumentos."""

    def __init__(
        self, respostas: dict[str, Any] | None = None, ferramentas: tuple[str, ...] = FERRAMENTAS
    ) -> None:
        self.respostas = respostas if respostas is not None else {f: resposta(f) for f in FERRAMENTAS}
        self._ferramentas = frozenset(ferramentas)
        self.chamadas: list[tuple[str, dict]] = []
        self.listagens = 0

    def ferramentas(self) -> frozenset[str]:
        self.listagens += 1
        return self._ferramentas

    def chamar(self, ferramenta: str, argumentos: dict[str, Any]) -> dict:
        self.chamadas.append((ferramenta, dict(argumentos)))
        valor = self.respostas.get(ferramenta)
        if valor is None:
            raise PciMcpIndisponivelError(f'{ferramenta}: sem resposta no transporte falso')
        if isinstance(valor, Exception):
            raise valor
        if callable(valor):
            return valor(argumentos)
        return valor
