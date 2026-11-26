"""Hero, gráfico nota × corte e até três ações, a partir do resumo já calculado."""

import math
from html import escape
from urllib.parse import quote

from nicegui import ui

from concursos.aplicacao.resultados import PontoDeNota, ResumoVisual, TopicoParaAgir
from concursos.gui import tema
from concursos.gui.componentes.situacao import situacao
from concursos.gui.tema import Tom
from concursos.texto import abreviar


def _numero(valor: float) -> str:
    return f'{valor:.1f}'.replace('.', ',')


def cartao_metrica(rotulo: str, valor: str, legenda: str, tom: Tom) -> None:
    with ui.card().classes(f'w-full ca-metrica ca-tom-{tom}').style(tema.gap('xs')):
        ui.label(rotulo).classes('text-caption ca-texto-suave')
        ui.label(valor).classes('text-h5 font-bold')
        ui.label(legenda).classes('text-sm ca-texto-suave')


def hero(
    ponto: PontoDeNota,
    *,
    atalho: bool = True,
    rotulo_atalho: str = 'Ver resultados e o que fazer',
    destino: str = '/resultados?aba=concursos',
) -> None:
    abaixo = ponto.atingido is False and ponto.corte is not None
    tom = Tom.ERRO if abaixo else Tom.SUCESSO if ponto.atingido else Tom.INFO
    with (
        ui.card().classes(f'w-full ca-hero ca-tom-{tom}').mark('hero-nota'),
        ui.row().classes('w-full items-center justify-between flex-wrap').style(tema.gap('lg')),
    ):
        with ui.column().style(tema.gap('xs')):
            if ponto.corte is None:
                situacao('Sem corte calculável', Tom.INFO, icone='flag')
                ui.label(ponto.concurso).classes('text-h6 font-bold')
                ui.label(f'Sua nota foi {_numero(ponto.nota)}%.').classes('ca-texto-suave')
            else:
                falta = ponto.corte - ponto.nota
                if abaixo:
                    situacao('Abaixo do corte', Tom.ERRO, icone='close')
                    frase = f'{ponto.concurso} — {_numero(falta)} pontos percentuais abaixo do corte'
                elif ponto.atingido:
                    situacao('Acima do corte', Tom.SUCESSO, icone='check')
                    frase = (
                        f'{ponto.concurso} — {_numero(ponto.nota - ponto.corte)} '
                        'pontos percentuais acima do corte'
                    )
                else:
                    situacao('No limite', Tom.ALERTA, icone='priority_high')
                    frase = f'{ponto.concurso} — no limite do corte'
                ui.label(frase).classes('text-h6 font-bold')
                if abaixo:
                    apoio = (
                        f'Faltaram {_numero(falta)} pontos percentuais. Atacar os tópicos abaixo '
                        'é o caminho mais curto para passar do corte.'
                    )
                elif ponto.atingido:
                    apoio = (
                        f'Você superou a nota de corte em {_numero(ponto.nota - ponto.corte)} '
                        'pontos percentuais. Continue mantendo os pontos fortes.'
                    )
                else:
                    apoio = f'Sua nota foi {_numero(ponto.nota)}% para um corte de {_numero(ponto.corte)}%.'
                ui.label(apoio).classes('ca-texto-suave')
        if atalho:
            ui.button(rotulo_atalho, icon='arrow_forward', on_click=lambda: ui.navigate.to(destino)).classes(
                'ca-alvo'
            )


def metricas_do_ponto(ponto: PontoDeNota, pontos: tuple[PontoDeNota, ...]) -> None:
    """Corte, nota e tendência, na ordem do protótipo, depois do banner."""
    abaixo = ponto.atingido is False and ponto.corte is not None
    if ponto.corte is None:
        corte, legenda_corte, tom_nota, legenda_nota = '—', 'Sem corte calculável', Tom.INFO, 'Nota da prova'
    else:
        corte = _numero(ponto.corte)
        legenda_corte = 'Nota mínima do último aprovado'
        if abaixo:
            tom_nota = Tom.ERRO
            legenda_nota = f'Faltaram {_numero(ponto.corte - ponto.nota)} pontos percentuais'
        elif ponto.atingido:
            tom_nota, legenda_nota = Tom.SUCESSO, 'Acima do corte'
        else:
            tom_nota, legenda_nota = Tom.ALERTA, 'No limite do corte'
    tendencia, legenda_tendencia = _tendencia(pontos)
    with (
        ui.element('div')
        .classes('w-full')
        .style(f'display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));{tema.gap("md")}')
        .mark('metricas-resultado')
    ):
        cartao_metrica('Corte', corte, legenda_corte, Tom.INFO)
        cartao_metrica('Sua nota', _numero(ponto.nota), legenda_nota, tom_nota)
        cartao_metrica('Tendência', tendencia, legenda_tendencia, Tom.SUCESSO)


def _tendencia(pontos: tuple[PontoDeNota, ...]) -> tuple[str, str]:
    notas = [ponto.nota for ponto in pontos]
    if len(notas) < 3:
        return 'Amostra inicial', 'A partir da terceira prova'
    recentes = notas[-3:]
    anteriores = notas[:-3] or [notas[0]]
    delta = sum(recentes) / len(recentes) - sum(anteriores) / len(anteriores)
    if abs(delta) < 0.5:
        return 'Estável', 'Evolução nas provas recentes'
    if delta > 0:
        return f'↗ {_numero(delta)} pontos percentuais', 'Evolução nas provas recentes'
    return f'↘ {_numero(abs(delta))} pontos percentuais', 'Evolução nas provas recentes'


def atalhos_de_pratica() -> None:
    with (
        ui.card().classes('w-full'),
        ui.row().classes('w-full items-center justify-between flex-wrap').style(tema.gap('md')),
    ):
        with ui.column().style(tema.gap('xs')):
            ui.label('Quer praticar agora mesmo?').classes('font-bold')
            ui.label('Abra um simulado curto ou atualize seu treino no TEC.').classes(
                'text-sm ca-texto-suave'
            )
        with ui.row().classes('items-center').style(tema.gap('sm')):
            ui.button(
                'Montar simulado',
                on_click=lambda: ui.navigate.to('/estudar?aba=simulado'),
            ).classes('ca-alvo')
            ui.button(
                'Importar prática do TEC',
                on_click=lambda: ui.navigate.to('/estudar?aba=pratica'),
            ).props('outline').classes('ca-alvo')


def grafico(pontos: tuple[PontoDeNota, ...], *, atual: str | None = None) -> None:
    distintos = {ponto.concurso for ponto in pontos}
    if len(distintos) < 2:
        ui.label('O gráfico de nota e corte aparece a partir da segunda prova analisada.').classes(
            'ca-texto-suave'
        ).mark('grafico-vazio')
        return
    with (
        ui.element('div').classes('w-full ca-grafico-caixa').style(tema.gap('md')).mark('grafico-nota-corte')
    ):
        with ui.row().classes('w-full items-center justify-between flex-wrap').style(tema.gap('sm')):
            with ui.column().style(tema.gap('xs')):
                ui.label('Sua nota comparada ao corte nas últimas provas').classes('text-lg font-bold')
                ui.label(_frase_da_serie(pontos)).classes('text-sm ca-texto-suave')
            with ui.row().classes('items-center').style(tema.gap('sm')):
                situacao('Sua nota', Tom.INFO, icone='show_chart')
                situacao('Zona de aprovação', Tom.SUCESSO, icone='check')
        ui.html(svg_nota_corte(pontos, atual=atual), sanitize=False).classes('w-full ca-grafico-svg')


def _frase_da_serie(pontos: tuple[PontoDeNota, ...]) -> str:
    delta = pontos[-1].nota - pontos[0].nota
    if delta > 0.5:
        return 'A faixa verde é a zona acima do corte. Sua nota subiu da primeira para a última prova.'
    if delta < -0.5:
        return 'A faixa verde é a zona acima do corte. Sua nota caiu da primeira para a última prova.'
    return 'A faixa verde é a zona acima do corte. Sua nota ficou estável entre as provas.'


def svg_nota_corte(pontos: tuple[PontoDeNota, ...], *, atual: str | None = None) -> str:
    """Linha da nota, corte tracejado e a faixa acima do corte da prova em destaque."""
    largura, altura = 680, 230
    esquerda, direita, topo, base = 44, 24, 20, 38
    largura_util = largura - esquerda - direita
    altura_util = altura - topo - base
    valores = [ponto.nota for ponto in pontos]
    valores.extend(ponto.corte for ponto in pontos if ponto.corte is not None)
    minimo, maximo, marcas = _escala(valores)

    def y(valor: float) -> float:
        limitado = min(max(valor, minimo), maximo)
        return topo + altura_util - ((limitado - minimo) / (maximo - minimo)) * altura_util

    destaque = atual if atual is not None else pontos[-1].concurso
    corte_destaque = next((ponto.corte for ponto in pontos if ponto.concurso == destaque), None)
    xs = _xs_do_grafico(len(pontos), esquerda, largura_util)
    linha_nota = ' '.join(f'{x:.1f},{y(ponto.nota):.1f}' for x, ponto in zip(xs, pontos, strict=True))
    linha_corte = ' '.join(
        f'{x:.1f},{y(ponto.corte):.1f}'
        for x, ponto in zip(xs, pontos, strict=True)
        if ponto.corte is not None
    )
    pontos_svg = ''.join(
        _ponto_do_grafico(x, ponto, y, altura, ponto.concurso == destaque)
        for x, ponto in zip(xs, pontos, strict=True)
    )
    return (
        f'<svg class="ca-grafico-svg" viewBox="0 0 {largura} {altura}" role="img" '
        'aria-label="Gráfico comparando suas notas com a nota de corte de cada concurso">'
        f'{_faixa_acima_do_corte(esquerda, largura_util, maximo, corte_destaque, y)}'
        f'{_grades_do_grafico(esquerda, direita, largura, marcas, y)}'
        f'<polyline fill="none" stroke="var(--ca-borda)" stroke-width="2" stroke-dasharray="5 5" '
        f'points="{linha_corte}"></polyline>'
        f'<polyline fill="none" stroke="var(--ca-primaria)" stroke-width="3" stroke-linecap="round" '
        f'stroke-linejoin="round" points="{linha_nota}"></polyline>'
        f'{pontos_svg}</svg>'
    )


def _xs_do_grafico(quantidade: int, esquerda: float, largura_util: float) -> list[float]:
    if quantidade <= 1:
        return [esquerda + largura_util / 2]
    passo = largura_util / (quantidade - 1)
    return [esquerda + indice * passo for indice in range(quantidade)]


def _faixa_acima_do_corte(esquerda, largura_util, maximo, corte, y) -> str:
    if corte is None:
        return ''
    return (
        f'<rect x="{esquerda}" y="{y(maximo):.1f}" width="{largura_util}" '
        f'height="{max(0.0, y(corte) - y(maximo)):.1f}" fill="var(--ca-sucesso-icone)" '
        'fill-opacity="0.12"></rect>'
    )


def _grades_do_grafico(esquerda, direita, largura, marcas, y) -> str:
    return ''.join(
        f'<line x1="{esquerda}" y1="{y(marca):.1f}" x2="{largura - direita}" y2="{y(marca):.1f}" '
        f'stroke="var(--ca-borda)" stroke-width="1"></line>'
        f'<text x="{esquerda - 8}" y="{y(marca) + 4:.1f}" text-anchor="end" '
        f'fill="var(--ca-texto-suave)" font-size="11" font-weight="600">{marca}</text>'
        for marca in marcas
    )


def _ponto_do_grafico(x: float, ponto: PontoDeNota, y, altura: int, destaque: bool) -> str:
    nome = escape(abreviar(ponto.concurso, 18))
    nota = escape(_numero(ponto.nota))
    cor = 'var(--ca-primaria)'
    if ponto.corte is not None:
        cor = 'var(--ca-sucesso-icone)' if ponto.nota >= ponto.corte else 'var(--ca-erro-icone)'
    raio = 7 if destaque else 5
    peso = 800 if destaque else 600
    corte = ''
    if ponto.corte is not None:
        corte = (
            f'<circle cx="{x:.1f}" cy="{y(ponto.corte):.1f}" r="4" fill="var(--ca-superficie)" '
            'stroke="var(--ca-borda)" stroke-width="2"></circle>'
            f'<text x="{x:.1f}" y="{y(ponto.corte) - 9:.1f}" text-anchor="middle" '
            f'fill="var(--ca-texto-suave)" font-size="11" font-weight="600">'
            f'Corte {escape(_numero(ponto.corte))}</text>'
        )
    return (
        f'{corte}'
        f'<circle cx="{x:.1f}" cy="{y(ponto.nota):.1f}" r="{raio}" fill="{cor}" '
        'stroke="var(--ca-superficie)" stroke-width="2"></circle>'
        f'<text x="{x:.1f}" y="{y(ponto.nota) - 12:.1f}" text-anchor="middle" fill="var(--ca-texto)" '
        f'font-size="12" font-weight="800">{nota}</text>'
        f'<text x="{x:.1f}" y="{altura - 10}" text-anchor="middle" fill="var(--ca-texto-suave)" '
        f'font-size="12" font-weight="{peso}">{nome}</text>'
    )


def _escala(valores: list[float]) -> tuple[float, float, list[int]]:
    baixo, alto = min(valores), max(valores)
    folga = max(5.0, (alto - baixo) * 0.35)
    minimo = max(0.0, math.floor((baixo - folga) / 5) * 5)
    maximo = min(100.0, math.ceil((alto + folga) / 5) * 5)
    if maximo - minimo < 10:
        maximo = min(100.0, minimo + 10)
        minimo = max(0.0, maximo - 10)
    passo = 5 if maximo - minimo <= 30 else 10
    marcas = list(range(int(minimo), int(maximo) + 1, passo))
    return float(minimo), float(maximo), marcas


def acoes(fracos: tuple[TopicoParaAgir, ...]) -> None:
    if not fracos:
        return
    with ui.column().classes('w-full').style(tema.gap('md')):
        with ui.column().style(tema.gap('xs')):
            ui.label('O que fazer agora').classes('text-lg font-bold')
            ui.label('Os 3 assuntos que trazem mais pontos com menos esforço de revisão.').classes(
                'ca-texto-suave'
            )
        with ui.element('div').classes('w-full ca-grade-acoes').mark('acoes-topicos'):
            for item in fracos:
                with ui.card().classes('w-full ca-acao'):
                    with ui.column().classes('w-full').style(tema.gap('xs')):
                        situacao(f'{_numero(item.percentual)}% de acerto', Tom.ALERTA, icone='warning')
                        ui.label(abreviar(item.topico, 80)).classes('ca-acao-titulo')
                        ui.label(item.disciplina).classes('ca-acao-nota')
                    with ui.element('div').classes('ca-botoes'):
                        ui.button(
                            'Treinar no simulado',
                            on_click=lambda t=item.topico: ui.navigate.to(
                                f'/estudar?aba=simulado&topico={quote(t)}'
                            ),
                        ).props('unelevated no-caps').classes('ca-alvo')
                        ui.button(
                            'Praticar no TEC',
                            on_click=lambda: ui.navigate.to('/estudar?aba=pratica'),
                        ).props('outline no-caps').classes('ca-alvo')


def ultimo(resumo: ResumoVisual) -> PontoDeNota | None:
    return resumo.pontos[-1] if resumo.pontos else None
