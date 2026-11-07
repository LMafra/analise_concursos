"""Radar de prazos: concursos do PCI dos cargos-alvo que abrem ou fecham em breve, mais os interesses."""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from concursos.arquivos import gravar_se_mudou
from concursos.datas import data_br
from concursos.integracoes.pci_mcp import ConcursoPci
from concursos.integracoes.sincronizacao_pci import situacao

logger = logging.getLogger(__name__)

ARQUIVO_RADAR = 'radar_editais.md'
ARQUIVO_RADAR_JSON = 'radar_editais.json'
_SEM_PRAZO = 10**6


@dataclass(frozen=True)
class ItemRadar:
    id: int
    titulo: str
    uf: str
    inicio: str
    fim: str
    situacao: str
    dias_ate_fim: int | None
    link: str
    interesse: bool = False
    concurso: str = ''


@dataclass(frozen=True)
class Radar:
    """`data_referencia` é o `meta.data_atual` do PCI: a mesma resposta em cache gera o mesmo radar."""

    data_referencia: str
    dias_alerta: int
    cargos: tuple[str, ...]
    itens: tuple[ItemRadar, ...]


def no_radar(concurso: ConcursoPci, dias_alerta: int) -> bool:
    """Aberto e fechando em até `dias_alerta` dias, ou abrindo nesse prazo; o `em_breve` do PCI sozinho vale
    para qualquer concurso que ainda não abriu, por isso o prazo de início é exigido."""
    datas = concurso.datas
    if datas.aberto:
        return datas.dias_ate_fim is not None and 0 <= datas.dias_ate_fim <= dias_alerta
    return datas.em_breve and datas.dias_ate_inicio is not None and 0 <= datas.dias_ate_inicio <= dias_alerta


def montar_radar(
    encontrados: list[ConcursoPci],
    interesses: list[dict],
    dias_alerta: int,
    cargos: tuple[str, ...],
    hoje: date,
) -> Radar:
    referencia = next((c.data_referencia for c in encontrados if c.data_referencia), '') or hoje.isoformat()
    por_id = {c.id: c for c in encontrados}
    marcados = {i['id']: i for i in interesses}
    itens: dict[int, ItemRadar] = {}
    for concurso in encontrados:
        if no_radar(concurso, dias_alerta):
            itens[concurso.id] = _do_pci(concurso, marcados.get(concurso.id))
    for interesse in interesses:
        if interesse['id'] in itens:
            continue
        atual = por_id.get(interesse['id'])
        if atual is not None:
            if atual.datas.aberto or atual.datas.em_breve:
                itens[atual.id] = _do_pci(atual, interesse)
            continue
        if item := _do_interesse(interesse, referencia):
            itens[item.id] = item
    ordem = sorted(
        itens.values(), key=lambda i: (i.dias_ate_fim if i.dias_ate_fim is not None else _SEM_PRAZO, i.id)
    )
    return Radar(referencia, dias_alerta, tuple(cargos), tuple(ordem))


def _do_pci(concurso: ConcursoPci, interesse: dict | None) -> ItemRadar:
    return ItemRadar(
        id=concurso.id,
        titulo=concurso.titulo,
        uf=concurso.uf,
        inicio=concurso.datas.inicio,
        fim=concurso.datas.fim,
        situacao=situacao(concurso),
        dias_ate_fim=concurso.datas.dias_ate_fim,
        link=concurso.link,
        interesse=interesse is not None,
        concurso=str((interesse or {}).get('concurso') or ''),
    )


def _data(texto: object) -> date | None:
    try:
        return date.fromisoformat(str(texto))
    except ValueError:
        return None


def _do_interesse(interesse: dict, referencia: str) -> ItemRadar | None:
    """Interesse fora da busca de hoje: os prazos gravados no `--register`; sai do radar depois do `fim`."""
    hoje = _data(referencia)
    inicio, fim = _data(interesse.get('inicio')), _data(interesse.get('fim'))
    dias_ate_fim = (fim - hoje).days if fim and hoje else None
    if dias_ate_fim is not None and dias_ate_fim < 0:
        return None
    if inicio and hoje and inicio > hoje:
        texto = f'abre em {(inicio - hoje).days} dias'
    elif dias_ate_fim is None:
        texto = 'prazo não informado'
    else:
        texto = 'fecha hoje' if dias_ate_fim == 0 else f'aberto, fecha em {dias_ate_fim} dias'
    return ItemRadar(
        id=interesse['id'],
        titulo=str(interesse.get('titulo') or ''),
        uf=str(interesse.get('uf') or ''),
        inicio=str(interesse.get('inicio') or ''),
        fim=str(interesse.get('fim') or ''),
        situacao=texto,
        dias_ate_fim=dias_ate_fim,
        link=str(interesse.get('link') or ''),
        interesse=True,
        concurso=str(interesse.get('concurso') or ''),
    )


def _celula(texto: str) -> str:
    return texto.replace('|', '/').replace('\n', ' ')


def formatar_radar(radar: Radar) -> str:
    alvo = f'os cargos {", ".join(radar.cargos)}' if radar.cargos else 'os concursos que você acompanha'
    linhas = [
        '# Prazos dos editais',
        '',
        f'Editais que abrem ou fecham nos próximos {radar.dias_alerta} dias, para {alvo}, pelo site do PCI '
        f'Concursos em {data_br(radar.data_referencia)}. O PCI é colaborativo: confira o edital no site do '
        'órgão ou da banca antes de se inscrever.',
        '',
    ]
    if not radar.cargos:
        linhas += [
            'Sem cargos de interesse, aparecem só os concursos que você acompanha: escolha os cargos em '
            'Encontrar concursos.',
            '',
        ]
    if not radar.itens:
        linhas += [f'Nenhum edital abre ou fecha nos próximos {radar.dias_alerta} dias.', '']
        return '\n'.join(linhas)
    linhas += ['| Concurso | UF | Inscrições | Situação | Você acompanha |', '|---|---|---|---|---|']
    for item in radar.itens:
        titulo = _celula(item.titulo or str(item.id))
        nome = f'[{titulo}]({item.link})' if item.link else titulo
        periodo = (
            f'{data_br(item.inicio) or "?"} a {data_br(item.fim) or "?"}' if item.inicio or item.fim else '-'
        )
        acompanhado = ('sim' + (f' ({item.concurso})' if item.concurso else '')) if item.interesse else '-'
        linhas.append(f'| {nome} | {item.uf or "?"} | {periodo} | {item.situacao} | {acompanhado} |')
    linhas.append('')
    return '\n'.join(linhas)


def gravar_radar(destino: Path, radar: Radar) -> bool:
    destino.mkdir(parents=True, exist_ok=True)
    texto_json = json.dumps(asdict(radar), ensure_ascii=False, indent=2) + '\n'
    mudou_json = gravar_se_mudou(destino / ARQUIVO_RADAR_JSON, texto_json)
    mudou_md = gravar_se_mudou(destino / ARQUIVO_RADAR, formatar_radar(radar))
    return mudou_json or mudou_md


def ler_radar(destino: Path) -> Radar | None:
    """O radar da última análise, para `status` e `doctor`, que não falam com o PCI."""
    arquivo = destino / ARQUIVO_RADAR_JSON
    if not arquivo.exists():
        return None
    try:
        dados = json.loads(arquivo.read_text(encoding='utf-8'))
        return Radar(
            data_referencia=dados['data_referencia'],
            dias_alerta=dados['dias_alerta'],
            cargos=tuple(dados['cargos']),
            itens=tuple(ItemRadar(**item) for item in dados['itens']),
        )
    except (ValueError, KeyError, TypeError) as erro:
        logger.warning('%s ilegível (%s); rode a análise de novo para refazer o radar', arquivo, erro)
        return None


def resumo_radar(radar: Radar) -> str:
    if not radar.itens:
        return f'nenhum edital abre ou fecha em até {radar.dias_alerta} dias (PCI em {data_br(radar.data_referencia)})'
    primeiro = radar.itens[0]
    return (
        f'{len(radar.itens)} edital(is) no radar (PCI em {data_br(radar.data_referencia)}); o mais próximo: '
        f'{primeiro.titulo} ({primeiro.situacao})'
    )
