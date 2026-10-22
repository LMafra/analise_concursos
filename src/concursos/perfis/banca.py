from dataclasses import dataclass, field, fields

FORMATOS = ('certo_errado', 'multipla_escolha')
SEGMENTACOES = ('questoes', 'itens')
ORDEM_PADRAO = 100


class PerfilInvalidoError(ValueError):
    pass


@dataclass(frozen=True)
class PerfilBanca:
    """O que muda de uma banca para outra na leitura e na correção.

    `leitor_gabarito` lê um gabarito PDF que já traz os itens; `leitor_secoes`, um que traz uma seção
    por cargo e tipo de caderno. `chaves_prova` diz a chave da prova pelo cabeçalho do gabarito, e
    `marca_caderno_padrao` separa o caderno da prova padrão dos demais."""

    id: str
    marcas: tuple[str, ...]
    nome: str = ''
    ordem: int = ORDEM_PADRAO
    formato: str = 'multipla_escolha'
    alternativas: int | None = None
    penalidade: float = 0.0
    leitor_gabarito: str | None = None
    leitor_secoes: str | None = None
    leitor_cargo: str | None = None
    leitor_resultado: str = 'padrao'
    segmentacao: str = 'questoes'
    disciplinas_pelo_caderno: bool = False
    chaves_prova: tuple[tuple[str, str], ...] = ()
    chave_padrao: str = 'unica'
    marca_caderno_padrao: str | None = None
    templates_folha: dict[str, str] = field(default_factory=dict)

    def chave_da_prova(self, cabecalho_normalizado: str) -> str:
        return next(
            (chave for marca, chave in self.chaves_prova if marca in cabecalho_normalizado), self.chave_padrao
        )

    def template_folha(self, total_itens: int) -> str | None:
        return self.templates_folha.get(str(total_itens)) or self.templates_folha.get('*')


def de_dict(dados: dict, origem: str = 'perfil') -> PerfilBanca:
    conhecidos = {campo.name for campo in fields(PerfilBanca)}
    if desconhecidos := sorted(set(dados) - conhecidos):
        raise PerfilInvalidoError(f'{origem}: campos desconhecidos: {", ".join(desconhecidos)}')
    if not dados.get('id'):
        raise PerfilInvalidoError(f"{origem}: campo obrigatório 'id' ausente")
    if dados.get('marcas') is None:
        raise PerfilInvalidoError(
            f"{origem}: campo obrigatório 'marcas' ausente (lista vazia: nunca detectado)"
        )
    _opcao(dados, 'formato', FORMATOS, origem)
    _opcao(dados, 'segmentacao', SEGMENTACOES, origem)
    try:
        return PerfilBanca(
            **{
                **dados,
                'id': str(dados['id']),
                'marcas': tuple(str(m) for m in dados['marcas']),
                'penalidade': float(dados.get('penalidade', 0.0)),
                'chaves_prova': tuple(
                    (str(marca), str(chave)) for marca, chave in dados.get('chaves_prova', ())
                ),
                'templates_folha': {str(k): str(v) for k, v in (dados.get('templates_folha') or {}).items()},
            }
        )
    except (TypeError, ValueError) as erro:
        raise PerfilInvalidoError(f'{origem}: {erro}') from erro


def _opcao(dados: dict, campo: str, opcoes: tuple[str, ...], origem: str) -> None:
    if campo in dados and dados[campo] not in opcoes:
        raise PerfilInvalidoError(
            f"{origem}: {campo}: valor '{dados[campo]}' inválido (use {', '.join(opcoes)})"
        )
