"""O que o app faz com o PCI: descoberta, interesses (`.concurso/interesses_pci.yaml`) e a sessão de consultas."""

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date
from pathlib import Path

import yaml

from concursos.arquivos import gravar_se_mudou
from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.integracoes import pci_mcp
from concursos.integracoes.cache_pci import ARQUIVO_CACHE, CachePci
from concursos.integracoes.pci_mcp import ClientePciMcp, ConcursoPci, ConfiguracaoPciMcp
from concursos.texto import abreviar

logger = logging.getLogger(__name__)

ARQUIVO_INTERESSES = 'interesses_pci.yaml'


@contextmanager
def sessao_pci(
    projeto: Path, configuracao: ConfiguracaoPciMcp, *, rede: bool, refresh: bool = False, gravar: bool = True
) -> Iterator[ClientePciMcp]:
    """Sem `rede`, só o cache; sem `gravar` (`--dry-run`), o cache não é regravado. No fim, o resumo no log."""
    cache = CachePci(projeto / ARQUIVO_CACHE, configuracao.ttl_horas, gravar=gravar)
    transporte = pci_mcp.abrir_transporte(configuracao) if rede else None
    cliente = ClientePciMcp(transporte, cache, refresh=refresh)
    try:
        yield cliente
    finally:
        try:
            cache.salvar()
        finally:
            fechar = getattr(transporte, 'fechar', None)
            if fechar is not None:
                fechar()
            logger.info(cliente.resumo())


def situacao(concurso: ConcursoPci) -> str:
    datas = concurso.datas
    if datas.aberto:
        if datas.dias_ate_fim is None:
            return 'inscrições abertas'
        return 'fecha hoje' if datas.dias_ate_fim == 0 else f'aberto, fecha em {datas.dias_ate_fim} dias'
    if datas.em_breve:
        if datas.dias_ate_inicio is None:
            return 'abre em breve'
        return f'abre em {datas.dias_ate_inicio} dias'
    return datas.texto or 'encerrado'


def _ordem(concurso: ConcursoPci) -> tuple:
    datas = concurso.datas
    return (not datas.aberto, datas.dias_ate_fim if datas.dias_ate_fim is not None else 10**6, concurso.id)


def ordenar(concursos: list[ConcursoPci]) -> list[ConcursoPci]:
    """Os abertos primeiro, pelo prazo; depois os que vão abrir."""
    return sorted(concursos, key=_ordem)


def _periodo(concurso: ConcursoPci) -> str:
    datas = concurso.datas
    if datas.inicio or datas.fim:
        return f'{datas.inicio or "?"} a {datas.fim or "?"}'
    return datas.texto or '-'


def formatar_tabela(concursos: list[ConcursoPci]) -> str:
    if not concursos:
        return 'nenhum concurso encontrado no PCI com esses filtros'
    linhas = []
    referencia = concursos[0].data_referencia
    for concurso in ordenar(concursos):
        cargos = abreviar(', '.join(concurso.cargos) or concurso.cargos_resumo, 70)
        linhas += [
            f'{concurso.id}  {concurso.titulo} ({concurso.uf or "?"})',
            f'    inscrições: {_periodo(concurso)} ({situacao(concurso)})',
            f'    cargos: {cargos or "-"}',
            f'    {concurso.link or "-"}',
        ]
    linhas.append(
        f'{len(concursos)} concurso(s); prazos do PCI em {referencia or "?"}. O PCI é um complemento: '
        'confira o edital no site do órgão ou da banca.'
    )
    return '\n'.join(linhas)


def como_json(concursos: list[ConcursoPci]) -> str:
    return json.dumps([asdict(c) for c in ordenar(concursos)], ensure_ascii=False, indent=2)


class Interesses:
    """Concursos do PCI que o candidato marcou para acompanhar, sem criar pasta em `provas/`."""

    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho
        self.itens: list[dict] = self._ler()

    @classmethod
    def do_projeto(cls, projeto: Path) -> 'Interesses':
        return cls(projeto / ARQUIVO_INTERESSES)

    def _ler(self) -> list[dict]:
        if not self.caminho.exists():
            return []
        try:
            dados = yaml.safe_load(self.caminho.read_text(encoding='utf-8')) or {}
        except yaml.YAMLError as erro:
            raise ConfiguracaoInvalidaError(f'{self.caminho}: {erro}') from erro
        itens = dados.get('interesses') if isinstance(dados, dict) else None
        if not isinstance(itens, list) or not all(
            isinstance(i, dict) and isinstance(i.get('id'), int) for i in itens
        ):
            raise ConfiguracaoInvalidaError(
                f'{self.caminho}: esperado `interesses:` com uma lista de itens com `id`'
            )
        return itens

    def obter(self, identificador: int) -> dict | None:
        return next((i for i in self.itens if i['id'] == identificador), None)

    def registrar(self, concurso: ConcursoPci, hoje: date | None = None) -> bool:
        """Devolve se o interesse é novo; um já registrado só tem os prazos atualizados."""
        dados = {
            'id': concurso.id,
            'titulo': concurso.titulo,
            'uf': concurso.uf,
            'inicio': concurso.datas.inicio,
            'fim': concurso.datas.fim,
            'link': concurso.link,
        }
        existente = self.obter(concurso.id)
        if existente is not None:
            existente.update(dados)
            return False
        self.itens.append(dados | {'registrado_em': (hoje or date.today()).isoformat()})
        return True

    def esquecer(self, identificador: int) -> bool:
        antes = len(self.itens)
        self.itens = [i for i in self.itens if i['id'] != identificador]
        return len(self.itens) != antes

    def vincular(self, identificador: int, pasta: str) -> dict:
        item = self.obter(identificador)
        if item is None:
            raise KeyError(identificador)
        item['concurso'] = pasta
        return item

    def gravar(self) -> bool:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        texto = yaml.safe_dump({'interesses': self.itens}, allow_unicode=True, sort_keys=False)
        return gravar_se_mudou(self.caminho, texto)
