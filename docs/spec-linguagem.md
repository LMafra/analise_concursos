# Spec: linguagem leiga e o index.html como painel de gestão

Tema transversal, não é uma fase. As decisões e as alternativas descartadas estão em `docs/decisoes-linguagem.md`.

O público é leigo em programação e em ciência de dados: quer saber "como estou saindo" e "o que fazer", não como o cálculo foi feito. Duas frentes, com o mesmo mapa de linguagem:

- **Frente A, reescrita:** mensagens da CLI, textos da GUI, README, `relatorio.md` (e o `relatorio.html` por concurso), rótulos de arquivo e mensagens de atualização. O layout não muda.
- **Frente B, redesenho:** o `index.html` consolidado vira um painel de gestão, com resumo, cards, selos de status, ações e um apêndice técnico fechado.

Nada técnico é apagado: vai para o apêndice (`<details>`), para a linha `detalhe:` das mensagens ou para `docs/detalhes-tecnicos.md`.

## 1. Princípios

1. Ordem pelas perguntas do usuário: como estou saindo, onde vou bem, onde preciso melhorar, estou evoluindo, o que fazer e, por último, os detalhes técnicos.
2. Ação antes de mecanismo ("Atualizar meus materiais de estudo", não "Sincronizar").
3. Uma frase comum antes do termo técnico, que fica entre parênteses, no apêndice ou no `detalhe:`.
4. No `index.html`, os cards de resumo vêm antes das tabelas.
5. Status sempre com ícone e texto, nunca só com cor: ✓ acima, ! no limite, ✗ abaixo, – sem corte.
6. Voz ativa. O app fala em primeira pessoa ("Não encontrei…", "Vou usar…"); a `dica:` é imperativa e traz uma ação concreta.
7. Todo diagnóstico tem uma ação sugerida.
8. Honestidade: "melhorando" ou "piorando" só com p < 0,05; sem isso, "ainda não dá para afirmar" ou "estável".
9. Nunca culpar o usuário ("Não encontrei a pasta", não "pasta inválida").
10. Edital, gabarito e banca são termos do domínio e ficam.

## 2. Mapa de linguagem

Fonte única do vocabulário. Vale para o `index.html`, o `relatorio.md`/`relatorio.html`, a GUI e as mensagens da CLI. Um termo novo entra aqui antes de entrar no código.

### 2.1 Relatórios

| Antes | Depois (parte principal) | Onde fica o técnico |
|---|---|---|
| "Nenhuma disciplina melhorou de forma significativa (p < 0,05)" | "Nenhuma disciplina mostrou melhora consistente entre os concursos." | apêndice |
| "slope +0,81 z por concurso, p = 0,112, n = 45, 4 concursos" | (sai da parte principal) | apêndice |
| "ρ = -0,53, p = 0,148, 9 concursos" | "Leve queda, ainda dentro da variação normal." | apêndice |
| "7 tópicos ficam abaixo de 60% (ajustado) em 2 concursos ou mais, com n somado ≥ 5" | "7 tópicos precisam de atenção: ficaram abaixo do esperado em mais de um concurso." | apêndice |
| "-43% em n = 7, abaixo em 2 de 2 concursos (pf_perito, cd_25)" | "Acertou 2 de 7 questões, menos do que acertaria chutando. Ficou abaixo em todos os concursos em que apareceu (pf_perito, cd_25)." | apêndice (−43%, fórmula) |
| tópico com percentual ajustado positivo abaixo do limiar (ex.: 30%, n = 9) | "Acertou 5 de 9; descontado o chute, ficou em 30%, abaixo do mínimo de 60% que você definiu." | apêndice |
| "A média dos z-scores de um concurso fica perto de 0 por construção" | (sai) | apêndice |
| "O ranking muda: 11 de 11 linhas mudam de posição, até 6 posições" | "Sua posição muda bastante quando consideramos a regra de correção e o chute; veja o gráfico." | apêndice |
| "Percentual ajustado ao acaso" | "Desempenho descontado o chute" | apêndice |
| "Gap para o corte" | "Quanto falta para o corte" | apêndice (tabela original) |
| "atinge o corte" / "Atingido: sim" | selo "✓ Acima do corte" | apêndice |
| "abaixo do corte" / "Atingido: não" | selo "✗ Abaixo do corte" | apêndice |
| a até 2 p.p. do corte, para cima ou para baixo | selo "! No limite" | — |
| sem corte no edital | selo "– Sem corte no edital" | — |
| corte por escore padronizado ou classificação | selo "– Corte não calculável" | apêndice (motivo) |
| "Percentual pela regra" | "Nota pela regra" | — |
| "Sensibilidade: sem o nível médio" | (sai) | apêndice |
| "O que o app decidiu sozinho" | (sai) | apêndice, "Como o app chegou nesses números" |
| "Avisos" | (sai) | apêndice, "Observações sobre os dados" |
| "nota líquida" / `nota_liquida` | "nota depois dos descontos" | apêndice (coluna crua) |
| "anuladas" | "anuladas (contam como acerto)" | — |
| "score 0,42" / "score baixo" | "baixa certeza" | apêndice (número) |
| "tópico sugerido por similaridade" | "tópico escolhido pelo app; confira" | apêndice |
| "confiança OCR" / `confianca_ocr` / "limiar de confiança" | "leitura incerta" | apêndice (número) |
| "Formato: multipla_escolha" | "Tipo de prova: múltipla escolha" (certo ou errado; discursiva) | — |
| "Pontuação: cebraspe" | "Como a nota é calculada: uma errada anula uma certa" | — |
| "Pontuação: bruta" / "fator 0" | "Como a nota é calculada: cada acerto vale um ponto, sem desconto" | `detalhe:` |
| "regra do perfil da banca" | "regra padrão da banca" | `detalhe:` / apêndice |
| "regra padrão" / "default (bruta, fator 0)" | "regra padrão: cada acerto vale um ponto" | `detalhe:` / apêndice |
| "z-score" (eixo do gráfico) | "acima ou abaixo da sua média" | apêndice |
| "Percentual por tópico e concurso" | "Como você foi em cada tópico" | — |
| "Painel de correção: bruto, corrigido e ajustado" | "Sua nota com e sem a regra de correção e o chute" | — |

### 2.2 Aplicativo e mensagens

| Antes | Depois | Onde fica o técnico |
|---|---|---|
| "concurso.yaml" | "os dados do concurso" (na GUI: tela Concursos) | `detalhe:` |
| "perfil da banca fgv (fator 0)" | "regra padrão da FGV" | `detalhe:` |
| "Tesseract" | "componente de leitura de PDF escaneado" | `detalhe:` |
| "OCR" | "leitura da imagem" | `detalhe:` |
| "modo mínimo" | "sem o conteúdo do edital" | `detalhe:` |
| "cache" | "resultado guardado da última busca" | `detalhe:` |
| "YAML inválido" | "Não consegui ler o arquivo" | `detalhe:` |
| "CSV" | "planilha" | `detalhe:` |
| "MCP", "endpoint", "servidor do PCI" | "o site do PCI Concursos" | `detalhe:` / `docs/detalhes-tecnicos.md` |
| "PCI Concursos" (ação) | "Buscar concursos abertos (PCI Concursos)" | — |
| "radar de prazos" | "concursos que você acompanha" / "prazos dos editais" | — |
| "Registrar no radar" / "Acompanhar" | "Acompanhar este concurso" | — |
| "Sincronizar com open-notebook" / "Enviar agora" | "Atualizar meus materiais de estudo" | Avançado |
| "Usar um open-notebook que já tenho" | "Usar meu próprio programa de estudo" | texto explicativo de Avançado |
| "Limiar de confiança da leitura" | "Quando considerar uma leitura confiável" | — |
| "Limiar de tópico fraco" | "Quando considerar um tópico fraco" | — |
| "Usar IA para ler editais (requer chave)" / "LLM" | "Usar inteligência artificial para ler editais" + frase curta sobre a chave | `detalhe:` |
| "Desligar o PCI" | "Parar de buscar concursos abertos" | — |
| "Atualizar agora" (PCI) | "Buscar de novo agora" | — |
| "CSV (Excel, planilhas)" / "Parquet" / "Markdown" | "Planilha (abre no Excel)" / "Para programadores (Parquet)" / "Texto" | — |
| "assinatura do manifesto e o SHA-256 conferirem" | "A atualização é segura. Se o arquivo estiver corrompido, o app avisa e não instala." | `docs/detalhes-tecnicos.md` |
| "WARNING …" no terminal | `aviso:` + `dica:` + `detalhe:` | `detalhe:` |
| "pasta de provas não encontrada" | "Não encontrei a pasta onde ficam suas provas ({caminho})." | — |

"open-notebook" aparece como crédito na tela Sobre e no texto explicativo de Avançado; nunca num botão.

## 3. Matriz única de auditoria

Colunas: ponto de comunicação, termo atual, termo novo (pelo mapa da seção 2), onde fica o detalhe técnico, frente e artefato. As mensagens individuais são reescritas nas fatias de código, e o teste da seção 6 garante a cobertura.

### 3.1 index.html (frente B, gerador `relatorio_html.py`)

| Ponto | Atual | Novo | Técnico | Artefato |
|---|---|---|---|---|
| Título | "Relatório de X" | "Relatório de X" + data + resumo executivo | — | código |
| Tabela Concursos | Acertos, Percentual pela regra, Edital (selo de nível), Correção (selo de fonte) | "Como estou saindo": nome, data, nota pela regra, selo de status, quanto falta | nível do edital e fonte da regra no apêndice | código |
| Tabela Gap | Percentual ponderado, Menor gap, Corte mais distante, Atingido sim/não | na linha de "Como estou saindo" | tabela original no apêndice | código |
| Simulados | "Simulados (provas anteriores do PCI)", nota sobre `incluir_simulados` | "Simulados que você fez" | a configuração no apêndice | código |
| O que o app decidiu sozinho | lista técnica (fator, concurso.yaml, similaridade) | apêndice, "Como o app chegou nesses números", em linguagem leiga | o texto original junto, como `detalhe` | código |
| Avisos | texto do `edital_estruturado.json` | apêndice, "Observações sobre os dados", por `traduzir_aviso` | sem padrão: "Observação técnica: <original>" | código |
| Evolução | `relatorio_evolucao.md` inteiro (p, slope, ρ, z) | "Estou evoluindo?": frase-resposta e situação por disciplina | o markdown inteiro no apêndice | código |
| Figuras | títulos com "z-score" | `<figure>` com título e legenda leigos | — | código + PNG |
| Radar, simulado focado, recomendações, prática | markdowns embutidos (topo e fim) | seções próprias depois de "O que fazer agora" | — | código + md |
| Rodapé | versão, data, pasta | sem mudança | — | — |

### 3.2 relatorio.md e relatorio.html (frente A, `relatorio.py`)

| Ponto | Atual | Novo | Técnico |
|---|---|---|---|
| Cabeçalho | "Formato: multipla_escolha", "Pontuação: cebraspe", "Gabarito: preliminar" | "Tipo de prova", "Como a nota é calculada", "Gabarito: preliminar (provisório)" | — |
| Resumo por prova | colunas `nota_liquida`, `anuladas`, `em_branco` | "## Resumo": nota final, acertos, aproveitamento | tabela crua em "Detalhes técnicos" |
| Desempenho por disciplina | colunas cruas | cabeçalhos legíveis (Questões, Acertos, Erros, Em branco, Aproveitamento) | — |
| Tópicos com menor desempenho | "até 10", colunas cruas | "Onde você mais errou" | tabela crua em "Detalhes técnicos" |
| Questões para revisar | "limiar de confiança", `confianca_ocr`, "score baixo", `revisao/questoes_revisado.csv` | "O que conferir": N leituras incertas e N tópicos escolhidos pelo app, com a ação | tabelas cruas em "Detalhes técnicos" |
| Preliminar → Definitivo | "nota líquida" | "Gabarito preliminar → definitivo", "nota depois dos descontos" | tabela do diff em "Detalhes técnicos" |
| Detalhes técnicos | — | `## Detalhes técnicos` no fim; no `relatorio.html`, tudo depois desse título vai para um `<details>` fechado | — |

Testes que leem o conteúdo do `relatorio.md` e mudam na fatia (k): `test_cli_topicos`, `test_cli_correcao_edital`, `test_cli_gabarito_definitivo`, `test_cli_regras_edital`, `test_cli_consolidado`, `test_cli_resultado_oficial` e `test_cli_analisar`.

### 3.3 Markdowns embutidos no índice (frente A, só o texto)

| Arquivo | Gerador | Atual | Novo |
|---|---|---|---|
| `radar_editais.md` | `integracoes/radar_pci.py` | "radar", "PCI", "cache" | "Prazos dos editais", "concursos que você acompanha" |
| `consolidado/simulado_focado.md` | `simulado_focado.py` | "ajustado", "n" | linguagem de acertos e tópicos |
| `consolidado/recomendacoes_estudo.md` | `biblioteca.py` | "tópicos fracos (ajustado)" | "Onde estudar" |
| `pratica/resumo_pratica.md` | `pratica_tec.py` | "Erros repetidos", colunas cruas | "Prática no TEC" em linguagem leiga |

### 3.4 Mensagens da CLI (frente A)

Formato: `erro:` ou `aviso:` (texto leigo, primeira pessoa), `dica:` (ação no imperativo) e, quando houver, `detalhe:` (o texto técnico atual). O texto guardado nos arquivos de dados não muda.

| Origem | Mensagens | Jargão típico | Fatia |
|---|---|---|---|
| `analytics/correcao.py` | 9 avisos | concurso.yaml, perfil da banca, fator, default, pesos, variante | h1 |
| `pipeline.py` | 6 avisos | Tesseract, OCR, modo mínimo, nao_mapeado, edital.manual | h1 |
| `analytics/regras_edital.py` | avisos de cargo, corte e padrão | concurso.yaml, escopo, unidade | h1 |
| `analytics/consolidado.py`, `taxonomia.py` | avisos de regra e de taxonomia | default, fator, canônica | h1 |
| `aplicacao/*` (analise, cadastro, conferencia, inicio, pratica, projeto, preferencias, ia, exemplo, dicionario, estudo, integracoes, atualizador) | cerca de 90 erros | CSV, --reuse-csv, concurso.yaml, [pratica], config.toml, YAML | h2 |
| `integracoes/*`, `estudo/*`, `atualizador.py`, `livros/*` | cerca de 35 erros e avisos | MCP, cache, servidor, manifesto, SHA-256, assinatura, GitHub | h3 |
| `cli/comandos.py`, `cli/__init__.py`, `llm.py`, `edital_llm.py`, `edital_a_confirmar.py`, `folha.py`, `candidatos.py`, `cadastro.py`, `texto.py`, `legislacao.py`, `analytics/dicionario_topicos.py`, `gui/estado.py` e as mensagens dos validadores que chegam por `str(erro)` | o resto | uv, PATH, LLM, keyring, perfil, CSV, YAML | h4 |

Exemplos (antes → depois):

- `regra de correção não encontrada no edital nem no concurso.yaml; usando a do perfil da banca fgv (fator 0)` → `aviso: alfa: não encontrei a regra de correção no edital. Vou usar a regra padrão da FGV.` / `dica: se estiver errada, ajuste em Concursos > Conferir > Dados do edital.` / `detalhe: regra do perfil da banca fgv (fator 0); o edital e o concurso.yaml não a trazem`
- `Tesseract ausente` → `aviso: alfa: não consegui ler o edital escaneado porque falta o componente de leitura de PDF escaneado.` / `dica: o instalador já traz esse componente; na versão de terminal, rode concurso-analise doctor para ver como instalar.` / `detalhe: Tesseract não está instalado; modo mínimo, tópicos nao_mapeado`
- `pasta de provas não encontrada: provas` → `erro: Não encontrei a pasta onde ficam suas provas (provas).` / `dica: cadastre um concurso pela janela (Novo concurso) ou com concurso-analise add, ou indique a pasta com --provas.` O app nunca pergunta e nunca cria a pasta, nem com `--yes`.
- `o edital não traz X; preencha edital_a_confirmar.yaml e rode de novo` → `aviso: alfa: o edital não trouxe algumas informações que mudam a nota. Preenchi o que faltava com valores padrão.` / `dica: confira em Concursos > Conferir > Dados do edital.` / `detalhe: campos: X; arquivo edital_a_confirmar.yaml`

### 3.5 GUI (frente A)

| Tela | Atual | Novo |
|---|---|---|
| Configurações | "Limiar de confiança da leitura", "Limiar de tópico fraco" | "Quando considerar uma leitura confiável", "Quando considerar um tópico fraco" |
| Configurações | "Usar IA para ler editais (requer chave)", "IA para ler editais" | "Usar inteligência artificial para ler editais" |
| Configurações > Avançado | "Usar um open-notebook que já tenho", "Endereço do open-notebook", "Enviar agora", "Deixar de usar" | "Usar meu próprio programa de estudo", "Endereço do programa", "Atualizar meus materiais de estudo", "Deixar de usar" |
| Encontrar concursos | "Acompanhando no radar de prazos", "Desligar o PCI", "Atualizar agora", "Acompanhar" | "Concursos que você acompanha", "Parar de buscar concursos abertos", "Buscar de novo agora", "Acompanhar este concurso" |
| Resultados > Exportar | "CSV (Excel, planilhas)", "Parquet (pandas, análise de dados)", "Markdown (texto)" | "Planilha (abre no Excel)", "Para programadores (Parquet)", "Texto" |
| Novo concurso | aviso do Tesseract, "modo mínimo" | "Falta o componente que lê PDF escaneado…" |
| Sobre | "assinatura do manifesto e o SHA-256" | "A atualização é segura. Se o arquivo estiver corrompido, o app avisa e não instala." |
| Sobre (biblioteca) | "usados só se a assinatura conferir" | "O app confere o arquivo antes de usar; se estiver corrompido, avisa e não instala." |
| Erros | erro e dica | erro e dica abertos; o `detalhe` num "Ver detalhes técnicos" fechado |
| Projeto e consentimento | `provas/`, `analises/`, lista de arquivos | rótulo amigável ao lado do nome real (seção 4) |

### 3.6 README (frente A)

| Seção | Atual | Novo | Técnico vai para |
|---|---|---|---|
| Instalação para usuários leigos | `chmod +x`, `APPIMAGE_EXTRACT_AND_RUN=1`, `sha256sum`, `Get-FileHash` | sem nenhum comando obrigatório | `docs/detalhes-tecnicos.md` |
| Atualizar | `upgrade --run`, manifesto, SHA-256 | "Configurações > Verificar atualizações"; a atualização é segura | idem |
| Por que o Windows avisa | SmartScreen, SignPath, SHA256SUMS | frase comum e o que clicar | idem |
| Estudar com seus livros / open-notebook | docker, `notebook enable` | "O app pode guardar seus livros e responder perguntas sobre eles (open-notebook)" | idem |
| Encontrar concursos / PCI | MCP, endpoint, `ttl_horas`, `.cursor/mcp.json` | "O app busca concursos abertos no PCI Concursos" | idem |
| Problemas comuns | flags e arquivos | o que fazer, pela janela primeiro | idem |
| Novas | — | "Como ler o relatório" e "O que cada arquivo contém" | — |

## 4. Rótulos de arquivo

Os nomes reais não mudam (compatibilidade). Na GUI, o nome aparece com o rótulo ao lado, por `linguagem.rotulo_do_arquivo`.

| Arquivo | Rótulo |
|---|---|
| `provas/` | Suas provas |
| `analises/` | Suas análises |
| `.concurso/` | Configuração do projeto |
| `respostas.txt` | Suas respostas |
| `respostas.csv` | Suas respostas (planilha) |
| `respostas_extraidas.csv` | Respostas lidas da folha |
| `questoes.csv` | Questões da prova |
| `edital_estruturado.json` | O que o app leu do edital |
| `discrepancias_edital.csv` | O que o app conferiu no edital |
| `catalogo_edital.md` | Descobertas no edital |
| `diff_gabarito.csv` | Mudanças do gabarito preliminar para o definitivo |
| `depuracao/` | Arquivos para investigar problemas |
| `relatorio.md` | Relatório do concurso (texto) |
| `desempenho_por_disciplina.csv` | Desempenho por disciplina |
| `desempenho_por_topico.csv` | Desempenho por tópico |
| `edital_a_confirmar.yaml` | Dados do edital a confirmar |

## 5. Wireframe do novo index.html

Estático, sem JavaScript, sem link absoluto, `max-width: 64rem`, system-ui.

1. **Cabeçalho**: `<h1>Relatório de {candidato}</h1>`, "Gerado em DD/MM/AAAA" e o resumo executivo (2 a 3 frases), por exemplo: "Você fez 9 concursos (11 provas). Ficou acima do corte em 7 delas. Seu melhor desempenho foi no TCU 2025 (72,5%). O ponto mais fraco é Língua Portuguesa, com 3 tópicos abaixo do esperado. Leve queda, ainda dentro da variação normal."
2. **Ir para**: `<nav>` com âncoras para as seções.
3. **Cards** (grid responsivo, 5 cards): número grande, rótulo curto, uma linha de contexto.
   - Concursos realizados: `9`, "11 provas no total (cada opção de cargo conta)".
   - Acima do corte: `7 de 11`, "4 abaixo" (só provas com corte conhecido; o resto aparece como "sem corte").
   - Melhor desempenho: `72,5%`, nome do concurso e opção de cargo.
   - Ponto mais fraco: a disciplina com mais tópicos fracos, "3 tópicos abaixo do esperado".
   - Tendência geral: ícone + "Leve queda", "veja Estou evoluindo?".
4. **Como estou saindo** (`<h2>`): tabela com `<caption>`, uma linha por prova: concurso (link para `<pasta>/relatorio.html`, sempre na primeira célula), data, nota pela regra, selo de status, quanto falta ("faltam 6,7 p.p." ou "+17,8 p.p. de folga"). Embaixo, "Simulados que você fez", quando houver.
5. **Meus pontos fortes** (`<h2>`): até 5 disciplinas, "Você vai bem em X: acertou 10 de 12; descontado o chute, 78%." Sem dados: "Ainda não há dados suficientes para apontar pontos fortes. Faça mais um concurso."
6. **Meus pontos a melhorar** (`<h2>`): um `<h3>` por disciplina ("Língua Portuguesa: 3 tópicos abaixo do esperado"), os tópicos em lista e a sugestão do grupo ("Considere revisar Língua Portuguesa antes do próximo concurso."). Disciplina que também é forte: "mesmo indo bem no geral, 1 tópico ficou abaixo".
7. **Estou evoluindo?** (`<h2>`): a frase-resposta, a situação por disciplina (melhorando, estável, precisa de atenção) e as 3 figuras, cada uma com `<figure>`, `alt` e `<figcaption>`:
   - `evolucao_zscore.png`: "Cada ponto é um concurso. Linha subindo = melhora; linha descendo = piora. Só aparecem disciplinas com pelo menos 3 concursos."
   - `heatmap_topicos.png`: "Vermelho = abaixo do esperado; verde = acima. Cada coluna é um concurso."
   - `painel_correcao.png`: "Mostra como a sua posição entre os concursos muda quando consideramos a regra de correção e o chute."
8. **O que fazer agora** (`<h2>`): 3 a 5 ações tiradas dos dados (disciplina foco, tópico abaixo em todos os concursos, prova no limite, leituras e tópicos a conferir, simulado focado e onde estudar, quando existem).
9. **Seções próprias**, só quando o arquivo existe, nesta ordem: Prazos dos editais, Simulado focado, Onde estudar, Prática no TEC.
10. **Detalhes técnicos** (`<details>` fechado): "Como o app chegou nesses números" (decisões automáticas), "Observações sobre os dados" (avisos), "Evolução técnica" (o `relatorio_evolucao.md` inteiro), "Quanto falta para o corte (tabela técnica)" e "Regras de correção e nível do edital".
11. **Rodapé**: versão e data, sem mudança.

Selos (texto escuro sobre fundo claro, AA):

| Status | Ícone | Classe | Fundo | Texto |
|---|---|---|---|---|
| Acima do corte | ✓ | `selo-acima` | `#d8f3dc` | `#14532d` |
| No limite | ! | `selo-limite` | `#fef3c7` | `#713f12` |
| Abaixo do corte | ✗ | `selo-abaixo` | `#fde2e1` | `#7f1d1d` |
| Sem corte / não calculável | – | `selo-neutro` | `#eef1f5` | `#374151` |

## 6. Regras de cálculo da parte principal

Moram em `analytics/painel.py`, com teste.

- **Prova:** cada par (concurso, variante). Simulados ficam fora dos KPIs.
- **Status:** pelo `menor_gap_percentual` de `comparar_percentual_e_gap` (gap = nota − corte). |gap| ≤ `FAIXA_NO_LIMITE` (2 p.p.): No limite; senão, `atingido` decide Acima ou Abaixo. Sem corte: Sem corte no edital.
- **Pontos fortes:** disciplinas com n ≥ `N_MINIMO_TOPICO` e percentual ajustado ≥ limiar, no máximo 5, da maior para a menor. Fortes e fracos usam o mesmo limiar; a faixa neutra é intencional.
- **Pontos a melhorar:** `topicos_fracos_persistentes`, prioridade = `len(concursos_abaixo) × (limiar − percentual)`; grupos por disciplina, ordenados pelo item de maior prioridade.
- **Frase do tópico:** ajustado < 0: "Acertou A de N questões, menos do que acertaria chutando" (sempre verdade: ajustado < 0 implica A < N/k). Ajustado ≥ 0: "Acertou A de N; descontado o chute, ficou em P%, abaixo do mínimo de L% que você definiu."
- **Tendência geral** (Spearman entre ordem e desempenho): p < `P_SIGNIFICATIVO`: Melhorando ou Piorando. Sem significância e |ρ| ≥ `RHO_LEVE` (0,3): Leve alta ou Leve queda, "ainda dentro da variação normal". Senão: Estável. Menos de `MINIMO_PONTOS_TENDENCIA` concursos com data: "Ainda não dá para afirmar".
- **Por disciplina:** só as com tendência calculável; p < 0,05 e slope > 0: melhorando; p < 0,05 e slope < 0: precisa de atenção; o resto: estável.
- **Ações:** `acoes_sugeridas(painel, fontes: FontesDasAcoes)`, 3 a 5 itens. `FontesDasAcoes` tem `simulado_focado`, `recomendacoes`, `radar`, `pratica` (`Path | None`), `leituras_a_conferir` e `topicos_a_conferir` (`int`).

## 7. Pontos de teste

- **Snapshots** (`syrupy`, grupo dev): cada seção do `index.html` como `.html` (`SingleFileSnapshotExtension`), com data e versão mascaradas e nomes fictícios; textos da CLI e da GUI no `.ambr` padrão.
- **Jargão na parte principal** (`tests/test_linguagem_leiga.py`):
  - `index.html` antes do `<details>`: sem "p <", "slope", "z-score", "Spearman", "ρ", "MCP", "embedding", "TF-IDF", "ajustado ao acaso", "score", "similaridade", "fator".
  - `relatorio.html` antes do `<details>`: sem "score", "similaridade", "TF-IDF", `confianca_ocr`, `nota_liquida`.
  - Primeiro argumento de `ErroDoUsuario`, `ErroDoAmbiente` e `avisar` (por AST, sem o prefixo, só as partes literais de f-string): sem YAML, MCP, cache, OCR, Tesseract, SHA-256, manifesto, "perfil da banca", "fator", CSV, PATH. A lista `PENDENTES` guarda os arquivos ainda não migrados e termina vazia.
- **Presença:** os 5 cards e um selo por prova.
- **Acessibilidade:** contraste AA dos selos; ícone com `aria-hidden`; `<caption>` e `th scope="col"`; títulos sem pular nível; `alt` e `<figcaption>`; `<nav>` com âncoras.
- **Formatter:** aviso com e sem `dica` e `detalhe`, em modo normal, `--quiet` e `--verbose`; nunca imprime "None".
- **Tradução de avisos:** cada aviso que o código produz tem padrão em `linguagem.traduzir_aviso`.
- **GUI:** nenhum `ui.button` com "open-notebook", "MCP", "embedding", "cache", "TF-IDF", "LLM", "CSV", "limiar"; todo nome de arquivo na tela vem de `rotulo_do_arquivo`.
- **Paridade:** `scripts/paridade.py comparar --esperadas scripts/paridade_esperadas.toml` sai com 0 depois da mudança.
