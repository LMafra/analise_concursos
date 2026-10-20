import difflib
import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from concursos.assistente import Interacao
from concursos.concurso_config import ARQUIVO_CONFIG, BANCAS, validar_dados
from concursos.deteccao import (
    ArquivoDetectado,
    Papel,
    arquivo_do_sistema,
    classificar_arquivo,
    eh_anexo,
    normalizar,
)
from concursos.gabarito import Secao, cargo_cebraspe, ler_gabarito_cebraspe, ler_gabarito_texto, listar_secoes
from concursos.modelo import Formato, Pontuacao
from concursos.texto import extrair_texto

TEMPLATES_FOLHA = ('cebraspe_ce', 'fgv_mod70ae', 'fgv_cpnu_90')
_TEMPLATE_FGV_POR_TOTAL = {70: 'fgv_mod70ae', 90: 'fgv_cpnu_90'}
_CHAVES_CEBRASPE = (('CONHECIMENTOS GERAIS', 'cg'), ('CONHECIMENTOS BASICOS', 'cb'))
_IGNORAR = 'ignorar'
_NENHUM = '(nenhum)'


@dataclass(frozen=True)
class _Gabarito:
    nome: str
    status: str | None
    chave: str
    secoes: list[Secao]


def cadastrar(pasta: Path, interacao: Interacao) -> bool:
    """Detecta os arquivos da pasta, resolve ambiguidades com o usuário e grava o concurso.yaml.

    Retorna False se o usuário recusar a gravação.
    """
    if not pasta.is_dir():
        raise FileNotFoundError(f'{pasta}: pasta do concurso não encontrada')
    return _Cadastro(pasta, interacao).executar()


class _Cadastro:
    def __init__(self, pasta: Path, interacao: Interacao):
        self.pasta = pasta
        self.interacao = interacao
        self.anterior = self._config_anterior()

    def executar(self) -> bool:
        detectados = self._detectar()
        detectados = self._descartar_duplicados(detectados)
        detectados = self._resolver_desconhecidos(detectados)
        por_papel: dict[Papel, list[ArquivoDetectado]] = defaultdict(list)
        for detectado in detectados:
            por_papel[detectado.papel].append(detectado)
        dados = self._montar(self._banca(detectados), por_papel)
        return self._gravar(dados)

    def _nome(self, detectado: ArquivoDetectado) -> str:
        return detectado.caminho.relative_to(self.pasta).as_posix()

    def _arquivos(self) -> list[Path]:
        return sorted(
            p for p in self.pasta.rglob('*') if p.is_file() and not arquivo_do_sistema(p, self.pasta)
        )

    def _detectar(self) -> list[ArquivoDetectado]:
        detectados = [classificar_arquivo(caminho, self.pasta) for caminho in self._arquivos()]
        relevantes = [d for d in detectados if d.papel is not Papel.IGNORADO]
        self.interacao.mostrar('Arquivos detectados:')
        for detectado in relevantes:
            detalhes = [
                valor
                for valor in (
                    detectado.banca,
                    detectado.status_gabarito,
                    detectado.tipo_caderno and f'tipo {detectado.tipo_caderno}',
                )
                if valor
            ]
            sufixo = f' ({", ".join(detalhes)})' if detalhes else ''
            self.interacao.mostrar(f'  {self._nome(detectado)}: {detectado.papel}{sufixo}')
        return relevantes

    def _descartar_duplicados(self, detectados: list[ArquivoDetectado]) -> list[ArquivoDetectado]:
        grupos: dict[str, list[ArquivoDetectado]] = defaultdict(list)
        for detectado in detectados:
            grupos[hashlib.sha256(detectado.caminho.read_bytes()).hexdigest()].append(detectado)
        mantidos = []
        for grupo in grupos.values():
            if len(grupo) == 1:
                mantidos.extend(grupo)
                continue
            nomes = sorted((self._nome(d) for d in grupo), key=lambda n: (len(n), n))
            escolhido = self.interacao.escolher(
                f'Arquivos com conteúdo idêntico: {", ".join(nomes)}. Qual manter? (os demais serão ignorados)',
                nomes,
                nomes[0],
            )
            mantidos.extend(d for d in grupo if self._nome(d) == escolhido)
        return sorted(mantidos, key=self._nome)

    def _resolver_desconhecidos(self, detectados: list[ArquivoDetectado]) -> list[ArquivoDetectado]:
        papeis = [p.value for p in Papel if p not in {Papel.IGNORADO, Papel.DESCONHECIDO}]
        resolvidos = []
        for detectado in detectados:
            if detectado.papel is not Papel.DESCONHECIDO:
                resolvidos.append(detectado)
                continue
            escolha = self.interacao.escolher(
                f'{self._nome(detectado)}: papel não reconhecido. O que é este arquivo?', [_IGNORAR, *papeis]
            )
            if escolha != _IGNORAR:
                resolvidos.append(replace(detectado, papel=Papel(escolha)))
        return resolvidos

    def _banca(self, detectados: list[ArquivoDetectado]) -> str:
        contagem = Counter(d.banca for d in detectados if d.banca).most_common()
        if contagem and (len(contagem) == 1 or contagem[0][1] > contagem[1][1]):
            return contagem[0][0]
        pergunta = 'Qual é a banca? (banca não detectada nos arquivos)'
        if contagem:
            pergunta = f'Qual é a banca? (arquivos citam {", ".join(b for b, _ in contagem)})'
        return self.interacao.escolher(pergunta, list(BANCAS))

    def _montar(self, banca: str, por_papel: dict[Papel, list[ArquivoDetectado]]) -> dict:
        if not por_papel[Papel.GABARITO]:
            raise ValueError(
                f'{self.pasta}: nenhum gabarito encontrado; adicione o gabarito (PDF ou txt) à pasta'
            )
        gabaritos = self._escolher_gabaritos(
            [self._ler_gabarito(d, banca) for d in por_papel[Papel.GABARITO]]
        )
        cadernos = list(por_papel[Papel.PROVA])
        dados: dict = {'nome': self.anterior.get('nome', self.pasta.name), 'banca': banca}
        provas = {}
        for chave, gabarito in sorted(gabaritos.items(), key=lambda par: min(_itens(par[1].secoes[0]))):
            secao = self._escolher_secao(gabarito, cadernos)
            if secao.cargo:
                dados['cargo'] = secao.cargo
                if secao.tipo:
                    dados['tipo'] = secao.tipo
            provas[chave] = self._prova(chave, gabarito, secao, cadernos, banca)
        if 'cargo' not in dados and self.anterior.get('cargo'):
            dados['cargo'] = self.anterior['cargo']
        valores = {i.resposta for g in gabaritos.values() for s in g.secoes for i in s.itens if not i.anulada}
        certo_errado = banca == 'cebraspe' or valores <= set(Formato.CERTO_ERRADO.alternativas)
        dados['formato'] = (Formato.CERTO_ERRADO if certo_errado else Formato.MULTIPLA_ESCOLHA).value
        dados['pontuacao'] = (Pontuacao.CEBRASPE if certo_errado else Pontuacao.SIMPLES).value
        if edital := self._edital(por_papel[Papel.EDITAL]):
            dados['edital'] = edital
        dados['provas'] = provas
        total_itens = max(prova['itens'][1] for prova in provas.values())
        if respostas := self._respostas(
            por_papel[Papel.RESPOSTAS] + por_papel[Papel.FOLHA], banca, total_itens
        ):
            dados['respostas'] = respostas
        if resultado := self._resultado(por_papel[Papel.RESULTADO]):
            dados['resultado_oficial'] = resultado
        if ignorar := self._ignorados(dados):
            dados['ignorar'] = ignorar
        if historico := self.anterior.get('historico'):
            dados['historico'] = historico
        return dados

    def _ler_gabarito(self, detectado: ArquivoDetectado, banca: str) -> _Gabarito:
        nome = self._nome(detectado)
        cargo = cargo_cebraspe(detectado.texto) if banca == 'cebraspe' else ''
        if detectado.caminho.suffix.lower() != '.pdf':
            secoes = [Secao(cargo, None, ler_gabarito_texto(detectado.texto, Formato.MULTIPLA_ESCOLHA, nome))]
        elif banca == 'cebraspe':
            secoes = [Secao(cargo, None, ler_gabarito_cebraspe(extrair_texto(detectado.caminho), nome))]
        else:
            secoes = listar_secoes(detectado.caminho, banca)
        return _Gabarito(nome, detectado.status_gabarito, _chave_prova(detectado.texto, banca), secoes)

    def _escolher_gabaritos(self, gabaritos: list[_Gabarito]) -> dict[str, _Gabarito]:
        grupos: dict[str, list[_Gabarito]] = defaultdict(list)
        for gabarito in gabaritos:
            grupos[gabarito.chave].append(gabarito)
        escolhidos = {}
        for chave, grupo in grupos.items():
            if len(grupo) == 1:
                escolhidos[chave] = grupo[0]
                continue
            definitivos = [g.nome for g in grupo if g.status == 'definitivo']
            descricao = ', '.join(f'{g.nome} ({g.status or "status desconhecido"})' for g in grupo)
            nome = self.interacao.escolher(
                f'Prova {chave}: mais de um gabarito ({descricao}). Qual usar?',
                [g.nome for g in grupo],
                definitivos[0] if len(definitivos) == 1 else None,
            )
            escolhidos[chave] = next(g for g in grupo if g.nome == nome)
        return escolhidos

    def _escolher_secao(self, gabarito: _Gabarito, cadernos: list[ArquivoDetectado]) -> Secao:
        if len(gabarito.secoes) == 1:
            return gabarito.secoes[0]
        rotulos = {_rotulo(s): s for s in gabarito.secoes}
        compativeis = [s for s in gabarito.secoes if any(_caderno_da_secao(c, s) for c in cadernos)]
        rotulo = self.interacao.escolher(
            f'{gabarito.nome}: qual é o seu cargo/tipo de caderno?',
            list(rotulos),
            _rotulo(compativeis[0]) if len(compativeis) == 1 else None,
        )
        return rotulos[rotulo]

    def _prova(
        self, chave: str, gabarito: _Gabarito, secao: Secao, cadernos: list[ArquivoDetectado], banca: str
    ) -> dict:
        prova: dict = {}
        if caderno := self._escolher_caderno(chave, secao, cadernos, banca):
            prova['caderno'] = caderno
        status = gabarito.status or self.interacao.escolher(
            f'{gabarito.nome}: status do gabarito não identificado',
            ['definitivo', 'preliminar'],
            'definitivo',
        )
        prova['gabarito'] = {'arquivo': gabarito.nome, 'status': status}
        itens = _itens(secao)
        prova['itens'] = [min(itens), max(itens)]
        disciplinas = self.anterior.get('provas', {}).get(chave, {}).get('disciplinas')
        if disciplinas:
            prova['disciplinas'] = disciplinas
        return prova

    def _escolher_caderno(
        self, chave: str, secao: Secao, cadernos: list[ArquivoDetectado], banca: str
    ) -> str | None:
        if not cadernos:
            return None
        if banca == 'cebraspe':
            candidatos = [c for c in cadernos if _caderno_cebraspe(c, chave)]
        else:
            candidatos = [c for c in cadernos if _mesmo_tipo(c, secao)]
            if len(candidatos) > 1 and secao.cargo:
                candidatos = [c for c in candidatos if _cita_cargo(c, secao)]
        if len(candidatos) == 1:
            escolhido = candidatos[0]
        else:
            nome = self.interacao.escolher(
                f'Prova {chave}: qual é o caderno de questões?', [self._nome(c) for c in cadernos] + [_NENHUM]
            )
            if nome == _NENHUM:
                return None
            escolhido = next(c for c in cadernos if self._nome(c) == nome)
        cadernos.remove(escolhido)
        return self._nome(escolhido)

    def _edital(self, editais: list[ArquivoDetectado]) -> str | dict | None:
        anterior = self.anterior.get('edital')
        manual = anterior.get('manual') if isinstance(anterior, dict) else None
        if not editais:
            return {'manual': manual} if manual else None
        nomes = [self._nome(e) for e in editais]
        principais = [self._nome(e) for e in editais if not eh_anexo(e.texto)]
        if len(editais) == 1 or len(principais) == 1:
            principal = principais[0] if principais else nomes[0]
        else:
            principal = self.interacao.escolher('Qual é o edital principal? (os demais serão anexos)', nomes)
        anexos = [n for n in nomes if n != principal]
        if not anexos and not manual:
            return principal
        edital: dict = {'arquivo': principal}
        if anexos:
            edital['anexos'] = anexos
        if manual:
            edital['manual'] = manual
        return edital

    def _respostas(self, fontes: list[ArquivoDetectado], banca: str, total_itens: int) -> dict | None:
        if not fontes:
            self.interacao.mostrar(
                'Aviso: nenhuma folha de resposta nem arquivo de respostas; o concurso ficará incompleto.'
            )
            return None
        escolhida = fontes[0]
        if len(fontes) > 1:
            manuais = [self._nome(f) for f in fontes if f.papel is Papel.RESPOSTAS]
            nome = self.interacao.escolher(
                'Mais de uma fonte de respostas. Qual usar?',
                [self._nome(f) for f in fontes],
                manuais[0] if len(manuais) == 1 else None,
            )
            escolhida = next(f for f in fontes if self._nome(f) == nome)
        if escolhida.papel is Papel.RESPOSTAS:
            return {'arquivo': self._nome(escolhida)}
        template = 'cebraspe_ce' if banca == 'cebraspe' else _TEMPLATE_FGV_POR_TOTAL.get(total_itens)
        if banca not in {'cebraspe', 'fgv'} or template is None:
            template = self.interacao.escolher(
                f'{self._nome(escolhida)}: qual é o modelo da folha de resposta?', list(TEMPLATES_FOLHA)
            )
        return {'folha': self._nome(escolhida), 'template': template, 'total_itens': total_itens}

    def _resultado(self, resultados: list[ArquivoDetectado]) -> dict | None:
        if not resultados:
            return None
        nome = self._nome(resultados[0])
        if len(resultados) > 1:
            nome = self.interacao.escolher(
                'Mais de um resultado oficial. Qual contém o seu desempenho?',
                [self._nome(r) for r in resultados] + [_NENHUM],
            )
            if nome == _NENHUM:
                return None
        anterior = self.anterior.get('resultado_oficial')
        sugestao = anterior.get('identificador') if isinstance(anterior, dict) else None
        identificador = self.interacao.perguntar(
            'Seu identificador no resultado oficial (inscrição; vazio se não souber)', sugestao
        )
        resultado: dict = {'arquivo': nome}
        if identificador:
            resultado['identificador'] = identificador
        if isinstance(anterior, dict) and anterior.get('pesos'):
            resultado['pesos'] = anterior['pesos']
        return resultado

    def _ignorados(self, dados: dict) -> list[str]:
        referenciados = set()
        for prova in dados['provas'].values():
            referenciados |= {prova['gabarito']['arquivo'], prova.get('caderno')}
        edital = dados.get('edital')
        if isinstance(edital, dict):
            referenciados |= {edital.get('arquivo'), *edital.get('anexos', ())}
        else:
            referenciados.add(edital)
        respostas = dados.get('respostas') or {}
        referenciados |= {respostas.get('arquivo'), respostas.get('folha')}
        referenciados.add((dados.get('resultado_oficial') or {}).get('arquivo'))
        todos = (p.relative_to(self.pasta).as_posix() for p in self._arquivos())
        return [nome for nome in todos if nome not in referenciados]

    def _config_anterior(self) -> dict:
        caminho = self.pasta / ARQUIVO_CONFIG
        if not caminho.exists():
            return {}
        try:
            return yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
        except yaml.YAMLError:
            return {}

    def _gravar(self, dados: dict) -> bool:
        validar_dados(self.pasta, dados)
        caminho = self.pasta / ARQUIVO_CONFIG
        if caminho.exists():
            if dados == self.anterior:
                self.interacao.mostrar(f'{caminho}: sem mudanças.')
                return True
            self.interacao.mostrar(f'Mudanças em {caminho}:')
            self.interacao.mostrar(_diff(self.anterior, dados))
            pergunta = 'Sobrescrever concurso.yaml?'
        else:
            self.interacao.mostrar(f'Configuração detectada:\n{_yaml(dados, ordenar=False)}')
            pergunta = 'Gravar concurso.yaml?'
        if not self.interacao.confirmar(pergunta):
            self.interacao.mostrar('Nada foi gravado.')
            return False
        caminho.write_text(_yaml(dados, ordenar=False), encoding='utf-8')
        self.interacao.mostrar(f'Gravado {caminho}.')
        return True


def _chave_prova(texto: str, banca: str) -> str:
    """Chave da prova Cebraspe pelo cabeçalho do gabarito (um gabarito por prova); demais bancas têm prova única."""
    if banca != 'cebraspe':
        return 'unica'
    cabecalho = normalizar(texto[:1500])
    return next((chave for marca, chave in _CHAVES_CEBRASPE if marca in cabecalho), 'ce')


def _itens(secao: Secao) -> list[int]:
    return [item.questao for item in secao.itens]


def _rotulo(secao: Secao) -> str:
    return f'{secao.cargo} (tipo {secao.tipo})' if secao.tipo else secao.cargo


def _caderno_cebraspe(caderno: ArquivoDetectado, chave: str) -> bool:
    return ('CONHECIMENTOS ESPECIFICOS' in normalizar(caderno.texto)) == (chave == 'ce')


def _mesmo_tipo(caderno: ArquivoDetectado, secao: Secao) -> bool:
    tipo = caderno.tipo_caderno
    return secao.tipo is None or tipo is None or tipo.lstrip('0') == str(secao.tipo).lstrip('0')


def _cita_cargo(caderno: ArquivoDetectado, secao: Secao) -> bool:
    cargo = re.sub(r'^\d+\s*-\s*', '', normalizar(secao.cargo))
    return cargo in normalizar(caderno.texto)


def _caderno_da_secao(caderno: ArquivoDetectado, secao: Secao) -> bool:
    """Caderno com tipo identificado igual ao da seção e que cita o cargo."""
    return caderno.tipo_caderno is not None and _mesmo_tipo(caderno, secao) and _cita_cargo(caderno, secao)


def _yaml(dados: dict, ordenar: bool) -> str:
    return yaml.safe_dump(dados, allow_unicode=True, sort_keys=ordenar)


def _diff(anterior: dict, novo: dict) -> str:
    linhas = difflib.unified_diff(
        _yaml(anterior, ordenar=True).splitlines(),
        _yaml(novo, ordenar=True).splitlines(),
        'concurso.yaml atual',
        'concurso.yaml novo',
        lineterm='',
    )
    return '\n'.join(linhas)
