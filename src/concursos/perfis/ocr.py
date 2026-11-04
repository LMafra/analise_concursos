from dataclasses import dataclass, fields

from concursos.perfis.banca import PerfilInvalidoError


@dataclass(frozen=True)
class PerfilOcr:
    """Uma folha de resposta: as letras na ordem da grade e os limiares da leitura.

    `vazio` e `cheio` são as frações de tinta de uma bolha vazia e de uma cheia típicas; `limiar_marcada`
    é a nota (0 a 1 entre as duas) a partir da qual a bolha conta como marcada; `largura` é a largura em
    pixels para a qual a página é normalizada."""

    id: str
    alternativas: str
    itens_por_coluna: int | None = None
    vazio: float = 0.2
    cheio: float = 0.9
    limiar_marcada: float = 0.5
    largura: int = 2480


def de_dict_ocr(dados: dict, origem: str = 'perfil de OCR') -> PerfilOcr:
    conhecidos = {campo.name for campo in fields(PerfilOcr)}
    if desconhecidos := sorted(set(dados) - conhecidos):
        raise PerfilInvalidoError(f'{origem}: campos desconhecidos: {", ".join(desconhecidos)}')
    for obrigatorio in ('id', 'alternativas'):
        if not dados.get(obrigatorio):
            raise PerfilInvalidoError(f'{origem}: campo obrigatório {obrigatorio!r} ausente')
    perfil = PerfilOcr(**{**dados, 'id': str(dados['id']), 'alternativas': str(dados['alternativas'])})
    if not 0 <= perfil.vazio < perfil.cheio <= 1 or not 0 < perfil.limiar_marcada < 1:
        raise PerfilInvalidoError(
            f'{origem}: limiares fora de 0 ≤ vazio < cheio ≤ 1 e 0 < limiar_marcada < 1'
        )
    return perfil
