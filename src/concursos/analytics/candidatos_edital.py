"""Registro versionado dos candidatos a metadado do edital: o que procurar, para que serve e o que fazer com
cada um. Mudar um candidato (padrão, uso, status) sobe a versão."""

from dataclasses import dataclass
from enum import StrEnum

VERSAO_CANDIDATOS = 2


class Impacto(StrEnum):
    ALTO = 'alto'
    MEDIO = 'medio'
    BAIXO = 'baixo'


class StatusCandidato(StrEnum):
    APLICADO = 'aplicado'
    PROPOSTO = 'proposto'
    DESCARTADO = 'descartado'


@dataclass(frozen=True)
class Candidato:
    """`padroes` são regex sobre o texto corrido; o grupo `valor`, quando existe, é o valor. Sem padrões, o
    valor é derivado das regras já extraídas. `unico`: valores diferentes no edital deixam o candidato
    ambíguo. `conhecido` é falso nas descobertas além da lista inicial. `proposta` é o diff estimado de uma
    evolução que muda código já validado, e só entra com confirmação."""

    chave: str
    informacao: str
    uso: str
    impacto: Impacto
    status: StatusCandidato
    severidade_se_ausente: str
    padroes: tuple[str, ...] = ()
    unico: bool = False
    conhecido: bool = True
    proposta: str | None = None
    motivo_do_descarte: str | None = None


_NAO_MUDA_NOTA = 'não muda nota, gap nem ranking'

CANDIDATOS = (
    Candidato(
        'alternativas',
        'Número de alternativas',
        'Confere o gabarito: letras além das alternativas do edital, ou alternativas que ele nunca usa, '
        'são `error` no CSV de discrepâncias',
        Impacto.ALTO,
        StatusCandidato.APLICADO,
        'info',
        (r'(?P<valor>\d)\s*\([a-zç]+\)\s+(?:alternativas|opções\s+de\s+resposta)',),
        unico=True,
        proposta='Passar o número de alternativas ao OCR da folha de respostas (`folha.py` e os templates '
        'por banca), para ler só as bolhas que existem. Diff estimado: ~20 linhas em `folha.py` e um campo '
        'por template; muda a fase 1 já validada, por isso só com confirmação.',
    ),
    Candidato(
        'tipo_de_questao',
        'Tipo de questão',
        'Mesmo formato do `concurso.yaml` (`certo_errado` ou `multipla_escolha`)',
        Impacto.MEDIO,
        StatusCandidato.PROPOSTO,
        'info',
        (
            r'questões\s+(?:objetivas\s+)?de\s+(?P<valor>múltipla\s+escolha)',
            r'(?P<valor>certo\s+ou\s+errado)',
        ),
        unico=True,
    ),
    Candidato(
        'marcacao',
        'Formato de marcação',
        'Contexto da folha de respostas',
        Impacto.BAIXO,
        StatusCandidato.DESCARTADO,
        'info',
        (r'(?P<valor>caneta\s+esferográfica\s+de\s+tinta\s+preta[^.,;]{0,40})',),
        motivo_do_descarte='caneta contra lápis não é validada: sem sinal na folha digitalizada',
    ),
    Candidato(
        'tempo_de_prova',
        'Tempo de prova',
        'Ritmo de prova (itens por minuto)',
        Impacto.BAIXO,
        StatusCandidato.PROPOSTO,
        'info',
        (
            r'duração\s+de\s+(?P<valor>\d+\s*(?:\([^)]*\)\s*)?horas?'
            r'(?:\s+e\s+\d+\s*(?:\([^)]*\)\s*)?minutos)?)',
            r'das\s+(?P<valor>\d{1,2}h\d{0,2}\s+às\s+\d{1,2}h\d{0,2})',
        ),
    ),
    Candidato(
        'consulta',
        'Consulta durante a prova',
        'Contexto da prova',
        Impacto.BAIXO,
        StatusCandidato.DESCARTADO,
        'info',
        (r'(?P<valor>sem\s+consulta|vedad[ao][^.]{0,40}consulta)',),
        motivo_do_descarte=_NAO_MUDA_NOTA,
    ),
    Candidato(
        'fases',
        'Fases e caráter',
        'Quais etapas eliminam; a objetiva é a única com nota no projeto',
        Impacto.MEDIO,
        StatusCandidato.PROPOSTO,
        'info',
        (
            r'(?:etapa|fase|prova)[^.]{0,80}?de\s+caráter\s+'
            r'(?P<valor>eliminatório\s+e\s+classificatório|eliminatório|classificatório)',
        ),
    ),
    Candidato(
        'nota_final',
        'Peso das fases e fórmula da nota final',
        'Quanto a objetiva pesa na nota final do concurso',
        Impacto.ALTO,
        StatusCandidato.PROPOSTO,
        'warn',
        (
            r'(?P<valor>nota\s+final\s+'
            r'(?:no\s+concurso|do\s+concurso|no\s+processo\s+seletivo|do\s+candidato)?[^.]{0,60}?'
            r'será\s+(?:igual|a\s+soma|o\s+somatório|calculada|obtida)[^.]{0,120})',
        ),
        proposta='Ler o peso de cada fase na nota final e mostrar, no gap, a fração da nota final que vem da '
        'objetiva. Diff estimado: ~40 linhas em `regras_edital.py` e uma coluna em `gap_para_corte`.',
    ),
    Candidato(
        'aprovacao',
        'Critérios de aprovação',
        'Régua de cortes do edital estruturado e "atingido" no gap',
        Impacto.ALTO,
        StatusCandidato.APLICADO,
        'warn',
        (r'(?P<valor>será\s+(?:reprovad[oa]|eliminad[oa]|considerad[oa]\s+aprovad[oa])[^.]{0,120})',),
    ),
    Candidato(
        'desempate',
        'Critérios de desempate',
        'Mostrados na ordem do edital, sem cálculo',
        Impacto.MEDIO,
        StatusCandidato.APLICADO,
        'info',
    ),
    Candidato(
        'legislacao_base',
        'Legislação-base',
        'Marco de que lei posterior ao edital não é cobrada: prioriza o estudo',
        Impacto.MEDIO,
        StatusCandidato.PROPOSTO,
        'info',
        (
            r'(?P<valor>(?:legislação|leis?|normas?)[^.]{0,160}?(?:após|posterior(?:es)?\s+[àa])\s+(?:a\s+)?'
            r'(?:data\s+de\s+)?publicação[^.]{0,160}?não\s+ser(?:á|ão)\s+(?:objeto|cobrad)[^.]{0,60})',
        ),
    ),
    Candidato(
        'bibliografia',
        'Bibliografia',
        'Fontes de estudo indicadas',
        Impacto.BAIXO,
        StatusCandidato.PROPOSTO,
        'info',
        (r'(?P<valor>bibliografia[^.]{0,80})',),
    ),
    Candidato(
        'vagas',
        'Vagas e cadastro de reserva',
        'Contexto da concorrência na identificação; fora de cálculo',
        Impacto.MEDIO,
        StatusCandidato.APLICADO,
        'info',
        (r'(?P<valor>cadastro\s+de\s+reserva[^.]{0,60})',),
    ),
    Candidato(
        'validade',
        'Validade do concurso',
        'Contexto',
        Impacto.BAIXO,
        StatusCandidato.DESCARTADO,
        'info',
        (
            r'validade\s+do\s+(?:concurso|processo\s+seletivo|certame)[^.]{0,50}?\s(?:será|é)\s+de\s+'
            r'(?P<valor>\d+\s*(?:\([^)]*\)\s*)?(?:anos?|meses))',
        ),
        unico=True,
        motivo_do_descarte=_NAO_MUDA_NOTA,
    ),
    Candidato(
        'locais',
        'Locais de prova',
        'Contexto',
        Impacto.BAIXO,
        StatusCandidato.DESCARTADO,
        'info',
        (
            r'(?P<valor>provas?[^.]{0,60}?(?:realizadas?|aplicadas?)\s+nas?\s+cidades?\s+'
            r'(?:de\s+)?[^.;,]{0,60})',
        ),
        motivo_do_descarte=_NAO_MUDA_NOTA,
    ),
    Candidato(
        'anulacao',
        'Regra de anulação',
        'A anulada vale ponto ou acerto para todos, também nos cortes em acertos',
        Impacto.ALTO,
        StatusCandidato.APLICADO,
        'warn',
        (r'(?P<valor>anula\w*\s[^.]{0,200}?atribuíd[ao]s?\s+a\s+tod[oa]s[^.]{0,40})',),
    ),
    Candidato(
        'discursiva',
        'Critérios da discursiva',
        'Corte da discursiva registrado e exibido, fora do "atingido"',
        Impacto.MEDIO,
        StatusCandidato.APLICADO,
        'info',
        (r'(?P<valor>prova\s+discursiva[^.]{0,120}?(?:avaliad|critérios|NPD|NFPD|aspectos)[^.]{0,80})',),
    ),
    Candidato(
        'recurso',
        'Formato e prazo de recurso',
        'Prazo contra o gabarito no cronograma',
        Impacto.BAIXO,
        StatusCandidato.APLICADO,
        'info',
        (
            r'(?P<valor>(?:interpor|interposição\s+de)\s+recursos?[^.]{0,160}?(?:dias?|horas?|prazo)'
            r'[^.]{0,60})',
        ),
    ),
    Candidato(
        'corte_em_acertos_com_nota_ponderada',
        'Corte em acertos ao lado de nota ponderada',
        'O gap desse corte conta acertos crus, não a nota ponderada',
        Impacto.ALTO,
        StatusCandidato.APLICADO,
        'info',
        conhecido=False,
    ),
    Candidato(
        'desempate_por_acertos',
        'Desempate que separa nota líquida e acertos',
        'No empate, o número de acertos pesa além da nota líquida',
        Impacto.MEDIO,
        StatusCandidato.APLICADO,
        'info',
        (r'(?P<valor>maior\s+número\s+de\s+acertos[^.;]{0,80})',),
        conhecido=False,
    ),
    Candidato(
        'teto_de_classificados',
        'Teto de classificados',
        'Não é nota mínima: só os N primeiros seguem, e o gap não o trata como corte',
        Impacto.ALTO,
        StatusCandidato.APLICADO,
        'info',
        conhecido=False,
    ),
    Candidato(
        'soma_dos_pesos_dos_eixos',
        'Soma dos pesos dos eixos',
        'Confere a leitura do quadro de pesos (`error` no CSV de discrepâncias)',
        Impacto.MEDIO,
        StatusCandidato.APLICADO,
        'info',
        conhecido=False,
    ),
)

DESCARTADOS_SEM_CANDIDATO = tuple(
    (informacao, _NAO_MUDA_NOTA)
    for informacao in (
        'Taxa de inscrição',
        'Remuneração',
        'Jornada',
        'Lotação',
        'Percentuais de cota',
        'Isenção',
        'Atendimento especial',
        'Nome social',
        'Amamentação',
        'Heteroidentificação',
        'Perícia médica',
    )
)
