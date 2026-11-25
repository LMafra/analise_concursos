# Spec — Dashboard de entrada + 1 relatório por fonte

Decisões NotebookLM + A1–A3 (2026-11-25).

## Artefatos

| Arquivo | Conteúdo |
|---|---|
| `index.html` | **Só** o dashboard (3 sub-dashboards) |
| `concursos.html` | Raio-X de provas reais (ex-conteúdo longo do index) |
| `tec.html` | Prática TEC (`mat`→`ass`, filtros na GUI) |
| `simulados.html` | PCI + TEC misturados por propósito |

## Dashboard (≤3 KPIs, zero gráfico/prosa)

### Concursos
1. Distância do corte (última prova) + selo Acima/Limite/Abaixo  
2. Tendência (média últimas 3 vs histórico anterior) — linguagem leiga  
3. Média de acertos (todas as provas)  
`<details>`: nº de concursos, melhor pontuação.

### TEC
1. Taxa geral de acertos (+ n) + selo por metas do usuário  
2. Maior gargalo `mat`→`ass` (amostra ≥ `amostra_minima`)  
3. Desempenho na **banca alvo** (config)  

### Simulados (PCI+TEC unificados)
1. Resultado do último + origem na legenda + selo por metas  
2. Evolução vs anterior  
3. Gargalo nos simulados  

### Empty (card nunca some)
- Concursos: *Cadastre sua primeira prova real…* → CTA Cadastrar Primeira Prova  
- TEC: *Importe seu histórico…* → CTA Importar Respostas do TEC  
- Simulados: *Gere ou registre um simulado…* → CTA Registrar Primeiro Simulado  

## Metas (usuário define) — `[dashboard]` no `config.toml`

```toml
[dashboard]
tec_meta_alta = 0.80
tec_meta_media = 0.70
simulado_meta_alta = 0.75
simulado_meta_media = 0.65
amostra_minima_assunto = 10
banca_alvo = ""   # vazia: fallback banca mais frequente no CSV
```

## GUI
- Home `/`: dashboard (mesmos KPIs)  
- Resultados: abas **Concursos | TEC | Simulados** (HTML gerado / iframe)  
- Configurações: sliders das metas + campo banca alvo  

## Paridade
Mesmos KPIs/ordem/selos (forma+ícone+texto+cor). CTAs/filtros só na GUI.
