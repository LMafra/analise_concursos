"""Montagem do `ConcursoConfig` a partir do YAML."""

import re
from datetime import date
from pathlib import Path

from concursos.concurso_config_modelos import (
    ConcursoConfig,
    ConfiguracaoInvalidaError,
    CorrecaoConfig,
    EditalConfig,
    FaixaDisciplina,
    FolhaConfig,
    GabaritoConfig,
    PesoItens,
    ProvaConfig,
    ResultadoOficialConfig,
    SimuladoConfig,
    VarianteCorrecaoConfig,
)
from concursos.modelo import (
    LETRAS,
    Escolaridade,
    Formato,
    ModeloCorrecao,
    Nivel,
    Pontuacao,
    StatusGabarito,
)
from concursos.perfis import ids_de_banca

_DATA_ISO = re.compile(r'\d{4}-\d{2}-\d{2}')


def _respostas_do_yaml(dados: dict) -> dict:
    respostas = dados.get('respostas') or {}
    if respostas.get('arquivo') and respostas.get('folha'):
        raise ConfiguracaoInvalidaError("respostas: use 'arquivo' ou 'folha', não ambos")
    return respostas


def _campos_obrigatorios_concurso(
    pasta: Path, dados: dict, provas: tuple[ProvaConfig, ...], formato: Formato
):
    return {
        'nome': dados.get('nome', pasta.name),
        'pasta': pasta,
        'banca': _opcao(_obrigatorio(dados, 'banca'), ids_de_banca(), 'banca'),
        'formato': formato,
        'pontuacao': _enum(Pontuacao, dados.get('pontuacao', 'simples'), 'pontuacao'),
        'provas': provas,
        'alternativas': _alternativas(dados.get('alternativas'), formato),
        'cargo': dados.get('cargo'),
        'tipo': None if dados.get('tipo') is None else str(dados['tipo']),
    }


def _campos_opcionais_concurso(dados: dict, respostas: dict) -> dict:
    return {
        'respostas_arquivo': respostas.get('arquivo'),
        'folha': _montar_folha(respostas) if respostas.get('folha') else None,
        'edital': _montar_edital(dados['edital']) if dados.get('edital') else None,
        'resultado_oficial': _montar_resultado(dados['resultado_oficial'])
        if dados.get('resultado_oficial')
        else None,
        'correcao': _montar_correcao(dados['correcao']) if dados.get('correcao') else None,
        'data_prova': _data_opcional(dados, 'data_prova'),
        'nivel': _enum(Nivel, dados.get('nivel') or Nivel.NAO_INFORMADO, 'nivel'),
        'escolaridade': _enum(
            Escolaridade, dados.get('escolaridade') or Escolaridade.NAO_INFORMADO, 'escolaridade'
        ),
        'ignorar': tuple(dados.get('ignorar') or ()),
        'historico': tuple(dados.get('historico') or ()),
        'simulado': _montar_simulado(dados['simulado']) if dados.get('simulado') else None,
        'titulo': _texto_opcional(dados.get('titulo'), 'titulo'),
        'pci_titulo': _texto_opcional((dados.get('pci') or {}).get('titulo') or None, 'pci.titulo'),
    }


def _montar(pasta: Path, dados: dict) -> ConcursoConfig:
    provas = tuple(_montar_prova(chave, valor) for chave, valor in _obrigatorio(dados, 'provas').items())
    _validar_faixas_disjuntas(provas)
    respostas = _respostas_do_yaml(dados)
    formato = _enum(Formato, _obrigatorio(dados, 'formato'), 'formato')
    return ConcursoConfig(
        **_campos_obrigatorios_concurso(pasta, dados, provas, formato),
        **_campos_opcionais_concurso(dados, respostas),
    )


def _texto_opcional(valor: object, campo: str) -> str | None:
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise ConfiguracaoInvalidaError(f"{campo}: valor '{valor}' não é texto")
    return valor.strip() or None


def _montar_simulado(simulado: dict) -> SimuladoConfig:
    if not isinstance(simulado, dict):
        raise ConfiguracaoInvalidaError('simulado: esperado um mapa (fonte, id_pci, ano_original, ...)')
    for campo in ('id_pci', 'ano_original'):
        valor = simulado.get(campo)
        if valor is not None and (isinstance(valor, bool) or not isinstance(valor, int)):
            raise ConfiguracaoInvalidaError(f"simulado.{campo}: valor '{valor}' não é inteiro")
    textos = ('organizadora', 'orgao', 'descricao', 'link')
    return SimuladoConfig(
        fonte=str(simulado.get('fonte') or 'manual'),
        id_pci=simulado.get('id_pci'),
        ano_original=simulado.get('ano_original'),
        **{campo: str(simulado.get(campo) or '') for campo in textos},
        concurso_alvo=simulado.get('concurso_alvo') or None,
        cargo_alvo=simulado.get('cargo_alvo') or None,
    )


def _montar_prova(chave: str, dados: dict) -> ProvaConfig:
    gabarito = _obrigatorio(dados, 'gabarito', f'provas.{chave}.')
    if isinstance(gabarito, str):
        gabarito = {'arquivo': gabarito}
    inicio, fim = _obrigatorio(dados, 'itens', f'provas.{chave}.')
    faixas = tuple(
        FaixaDisciplina(f['inicio'], f['fim'], f['disciplina']) for f in dados.get('disciplinas') or ()
    )
    gabarito = GabaritoConfig(**gabarito)
    status = _enum(StatusGabarito, gabarito.status, f'provas.{chave}.gabarito.status')
    gabarito = GabaritoConfig(gabarito.arquivo, status)
    return ProvaConfig(chave, gabarito, int(inicio), int(fim), faixas, dados.get('caderno'))


def _montar_folha(respostas: dict) -> FolhaConfig:
    return FolhaConfig(
        arquivo=respostas['folha'],
        template=respostas.get('template'),
        total_itens=respostas.get('total_itens'),
        itens_por_coluna=respostas.get('itens_por_coluna'),
    )


def _montar_edital(edital: str | dict) -> EditalConfig:
    if isinstance(edital, str):
        return EditalConfig(edital)
    manual = edital.get('manual')
    arquivo = edital.get('arquivo') if manual else _obrigatorio(edital, 'arquivo', 'edital.')
    retificacoes = edital.get('retificacoes') or []
    if not isinstance(retificacoes, list) or not all(isinstance(r, str) for r in retificacoes):
        raise ConfiguracaoInvalidaError('edital.retificacoes: deve ser uma lista de arquivos')
    return EditalConfig(arquivo, tuple(edital.get('anexos') or ()), manual, tuple(retificacoes))


def _montar_resultado(resultado: str | dict) -> ResultadoOficialConfig:
    if isinstance(resultado, str):
        return ResultadoOficialConfig(resultado)
    identificador = resultado.get('identificador')
    return ResultadoOficialConfig(
        _obrigatorio(resultado, 'arquivo', 'resultado_oficial.'),
        None if identificador is None else str(identificador),
        _montar_pesos(resultado.get('pesos'), 'resultado_oficial.pesos'),
    )


def _montar_pesos(pesos: list[dict] | None, campo: str) -> tuple[PesoItens, ...]:
    faixas = tuple(PesoItens(int(p['itens'][0]), int(p['itens'][1]), float(p['peso'])) for p in pesos or ())
    for faixa in faixas:
        if faixa.inicio > faixa.fim:
            raise ConfiguracaoInvalidaError(f'{campo}: faixa {faixa.inicio}-{faixa.fim} inválida')
        if faixa.peso <= 0:
            raise ConfiguracaoInvalidaError(f'{campo}: peso {faixa.peso:g} deve ser maior que 0')
    return faixas


def _montar_correcao(correcao: dict) -> CorrecaoConfig:
    modelo = correcao.get('modelo')
    if modelo is not None:
        modelo = _enum(ModeloCorrecao, modelo, 'correcao.modelo')
    fator, maxima, corte = (
        _numero_opcional(correcao, campo, 'correcao.')
        for campo in ('fator_penalidade', 'nota_maxima', 'nota_corte')
    )
    if fator is not None and fator < 0:
        raise ConfiguracaoInvalidaError('correcao.fator_penalidade: não pode ser negativo')
    ponderada = modelo is ModeloCorrecao.PONDERADA
    if (
        modelo is not None
        and fator is not None
        and ModeloCorrecao.pelo_fator(fator, ponderada=ponderada) is not modelo
    ):
        raise ConfiguracaoInvalidaError(
            f"correcao: modelo '{modelo}' incompatível com fator_penalidade {fator:g} "
            '(liquida exige fator maior que 0; bruta e ponderada, fator 0)'
        )
    if modelo is ModeloCorrecao.LIQUIDA and fator is None:
        raise ConfiguracaoInvalidaError("correcao: modelo 'liquida' exige fator_penalidade maior que 0")
    pesos = _montar_pesos(correcao.get('pesos'), 'correcao.pesos')
    variantes = _montar_variantes(correcao.get('variantes'))
    if ponderada and not pesos and not variantes:
        raise ConfiguracaoInvalidaError("correcao: modelo 'ponderada' exige pesos ou variantes")
    return CorrecaoConfig(modelo, fator, maxima, corte, pesos, variantes)


def _montar_variantes(variantes: list | None) -> tuple[VarianteCorrecaoConfig, ...]:
    montadas = []
    for variante in variantes or ():
        if not isinstance(variante, dict):
            variante = {'nome': variante}
        nome = str(_obrigatorio(variante, 'nome', 'correcao.variantes.'))
        if any(v.nome == nome for v in montadas):
            raise ConfiguracaoInvalidaError(f"correcao.variantes: '{nome}' repetida")
        montadas.append(
            VarianteCorrecaoConfig(
                nome, _montar_pesos(variante.get('pesos'), f'correcao.variantes.{nome}.pesos')
            )
        )
    return tuple(montadas)


def _numero_opcional(dados: dict, campo: str, prefixo: str = '') -> float | None:
    valor = dados.get(campo)
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        raise ConfiguracaoInvalidaError(f"{prefixo}{campo}: valor '{valor}' não é numérico") from None


def _data_opcional(dados: dict, campo: str) -> date | None:
    valor = dados.get(campo)
    if valor is None:
        return None
    try:
        if not _DATA_ISO.fullmatch(str(valor)):
            raise ValueError
        return date.fromisoformat(str(valor))
    except ValueError:
        raise ConfiguracaoInvalidaError(
            f"{campo}: valor '{valor}' não é uma data ISO 8601 (aaaa-mm-dd)"
        ) from None


def _obrigatorio(dados: dict, campo: str, prefixo: str = ''):
    if dados.get(campo) in (None, ''):
        raise ConfiguracaoInvalidaError(f"campo obrigatório '{prefixo}{campo}' ausente")
    return dados[campo]


def _alternativas(valor: object, formato: Formato) -> int | None:
    if valor is None:
        return None
    if formato is Formato.CERTO_ERRADO:
        raise ConfiguracaoInvalidaError(
            'alternativas: só vale para multipla_escolha (certo_errado tem C e E)'
        )
    if not isinstance(valor, int) or not 2 <= valor <= len(LETRAS):
        raise ConfiguracaoInvalidaError(
            f'alternativas: deve ser um inteiro de 2 a {len(LETRAS)}, recebido {valor!r}'
        )
    return valor


def _opcao(valor: str, opcoes: tuple[str, ...], campo: str) -> str:
    if valor not in opcoes:
        raise ConfiguracaoInvalidaError(f"{campo}: valor '{valor}' inválido (use {', '.join(opcoes)})")
    return valor


def _enum(tipo, valor, campo: str):
    try:
        return tipo(valor)
    except ValueError:
        opcoes = ', '.join(item.value for item in tipo)
        raise ConfiguracaoInvalidaError(f"{campo}: valor '{valor}' inválido (use {opcoes})") from None


def _validar_faixas_disjuntas(provas: tuple[ProvaConfig, ...]) -> None:
    ordenadas = sorted(provas, key=lambda p: p.inicio)
    for anterior, seguinte in zip(ordenadas, ordenadas[1:], strict=False):
        if seguinte.inicio <= anterior.fim:
            raise ConfiguracaoInvalidaError(
                f'faixas de itens sobrepostas: {anterior.chave} ({anterior.inicio}-{anterior.fim}) '
                f'e {seguinte.chave} ({seguinte.inicio}-{seguinte.fim})'
            )
