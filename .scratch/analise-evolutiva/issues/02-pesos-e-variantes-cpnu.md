# 02: Pesos por faixa de itens e variantes (CPNU)

**What to build:** o modelo de correção passa a suportar pesos por faixa de itens e variantes nomeadas. Assim, concursos ponderados ficam com a nota corrigida correta, e um concurso com várias opções de cargo ganha uma variante de correção por cargo.

- **Pesos:**
  - No `concurso.yaml`, ficam dentro do bloco de correção como lista de faixas de itens com peso, no mesmo formato já usado pelos pesos do resultado oficial.
  - No edital, são extraídos de três padrões:
    - pontos diferentes por prova ou módulo, como no creci ("2,00 pontos … P2") e no dataprev ("valerá 2,5 pontos no Módulo …");
    - o quadro de pesos por eixo temático e cargo do anexo do CPNU (linhas como "B3-08-A 1 1 2 4 2");
    - penalidade fracionária ("a cada N erradas, anula-se uma certa"), por exemplo fator 0,25.
- **Variantes:**
  - O `concurso.yaml` declara variantes nomeadas pelo código do cargo. O CPNU declara B3-08-A, B3-10-A e B3-07-C, os cargos em que me inscrevi.
  - Os pesos de cada variante vêm do quadro do anexo (fonte `edital`) e podem ser sobrescritos pela configuração.
  - Os eixos do CPNU ocupam faixas consecutivas de 12 itens: 31–42, 43–54, 55–66, 67–78 e 79–90. Os gerais (1–30) têm peso 1.
- O arquivo de correção passa a conter uma configuração por variante. Um concurso sem variantes continua com uma só.
- O modelo é `ponderada` quando há pesos não uniformes e o fator é 0. Quando o fator é maior que 0, o modelo é `liquida`.
- O percentual por disciplina ou eixo não muda com os pesos, porque cada eixo tem um peso só. As variantes afetam só a nota do concurso, a nota normalizada e o ranking.

Ver `docs/spec-fase2.md` (histórias 3, 4, 13 e 14) e a seção "Pesos do CPNU".

**Blocked by:** 01 (Correção do edital ponta a ponta)

**Status:** done

- [x] Testes com trechos reais (quadro do CPNU, pesos por prova do creci e do dataprev) e sintéticos:
  - pesos por faixa;
  - variantes por cargo;
  - fator fracionário 0,25;
  - precedência da configuração sobre o edital nos pesos de uma variante.
- [x] Aceitação do CPNU contra o resultado oficial. Com 16 acertos nos gerais e 8, 3, 11, 9 e 5 nos eixos, as notas são B3-08-A = 95, B3-10-A = 95 e B3-07-C = 87.
- [x] Confirmar que as faixas de eixo do CPNU batem com as faixas de disciplina do caderno, cada uma com 12 itens. Se não baterem, ajustar e registrar.
  - Conferido no `questoes.csv`: gerais 1–30 e eixos 31–42, 43–54, 55–66, 67–78 e 79–90, 12 itens cada. A anulada (questão 49, eixo 2) já entra como acerto nos 3 acertos do eixo.
- [x] Com dados reais, o CPNU resolve como `ponderada` com 3 variantes, fonte `edital`, documento de origem igual ao anexo do bloco 3 e trecho e página do quadro de pesos (p.91–92).
- [x] `concurso.yaml` do CPNU com as 3 variantes declaradas.
- [x] `docs/modelo.md` atualizado com pesos e variantes.
- [x] `uv run pytest` e `ruff` verdes.
