# Manual da marca — Gabarito Vivo

Fonte de identidade visual e de voz. Tokens de código em `src/concursos/gui/tema.py` e `docs/modelo.md` § Tema; este arquivo explica o *porquê* e os usos.

## Posicionamento

Ferramenta desktop local que transforma a ansiedade pós-prova em diagnóstico técnico, humano e focado em evolução. Conselheiro empático — não BI frio nem gamificação infantil.

### Atributos

1. **Rigor diagnóstico** — dados reais de edital e corte, sem ilusão.
2. **Companheirismo empático** — acolhe a vulnerabilidade pós-prova.
3. **Evolução tangível** — a nota ganha forma a cada prova.
4. **Clareza cirúrgica** — só o que gera ação.

### Anti-padrões

- Gamificação infantil (moedas, mascotes, confetes).
- Dashboard corporativo com “KPI” / “ROI” na UI (usar “indicadores” / “ganho de pontos”).
- Tom punitivo (“FALHA”, “REPROVADO” em caixa alta; vermelho agressivo).

## Logo

- **Símbolo:** folha de respostas + check “vivo” (evolução do ícone em `empacotamento/icones/`).
- **Wordmark:** “Gabarito Vivo” ao lado do símbolo em Sobre, onboarding e instalador.
- **Usos:** favicon / ícone do SO; Sobre; rodapé do `index.html` (só texto + menção local).
- **Não** usar o símbolo sozinho em fundos que quebrem o contraste AA.

## Tipografia

- **Corpo:** `-apple-system, "Segoe UI", Roboto, "Noto Sans", Ubuntu, sans-serif`.
- Tamanhos funcionais: 12–14 px corpo; 18 px título de seção; 24 px título de página.
- Tipografia *display* de marca: fora desta especificação de implementação (leva futura).

## Escalas

| Token | Valor |
|---|---|
| espaço xs → xl | 4 / 8 / 16 / 24 / 32 px |
| raio sm / md / pill | 4 / 8 / 9999 px |
| elevação 1 / 2 | `0 1px 2px rgb(0 0 0 / .08)` / `0 8px 24px rgb(0 0 0 / .16)` |
| alvo mínimo | 44 × 44 px |
| foco | outline 3 px na cor `--ca-foco` |

## Cores

### Claro

| Papel | Hex |
|---|---|
| Primária (teal-ink) | `#14282B` |
| Sobre primária | `#FFFFFF` |
| Primária como texto / link | `#14282B` |
| Fundo / superfície | `#FAFAFA` / `#FFFFFF` |
| Texto / suave / borda | `#14282B` / `#475569` / `#CBD5E1` |
| Acima (fundo / texto) | `#E6F4ED` / `#0E5A37` |
| Limite (fundo / texto) | `#FEF3C7` / `#92400E` |
| Abaixo (fundo / texto) | `#FCEBE6` / `#8C2D0D` |
| Info | fundo `#E6F0F0`, ícone/texto `#14282B` |
| Erro (falha de sistema) | fundo `#FCEBE6`, ícone/texto `#8C2D0D` |

### Escuro

| Papel | Hex |
|---|---|
| Fundo / superfície | `#121E20` / `#1A2C2F` |
| Texto / suave | `#E6ECEC` / `#94A3B8` |
| Primária (destaque) | `#4ADE80` sobre superfície escura para botões; estrutura permanece teal |
| Acima | `#143324` / `#4ADE80` |
| Limite | `#3B2D11` / `#FCD34D` |
| Abaixo | `#3A1C14` / `#F87171` |
| Gráfico nota / corte | `#38BDF8` / `#FBBF24`; desvio `rgba(248,113,113,0.15)` |

Print (`@media print`): fundo `#FFFFFF`, texto `#111111`; ocultar navegação e CTAs de app.

## Selos de corte (codificação redundante)

| Estado | Forma | Ícone | Texto | ARIA |
|---|---|---|---|---|
| Acima | pill (`radius: 999px`) | ✓ | Acima do corte | `role="status"` `aria-label="Situação: Acima do corte"` |
| No limite | borda tracejada | ! | No limite | `aria-label="Situação: No limite da nota de corte"` |
| Abaixo | cantos retos (`radius: 2px`) | ✗ | Abaixo do corte | `aria-label="Situação: Abaixo do corte"` |

Nunca só cor. Em P&B: borda dupla / pontilhada / hachura.

## Ícones

Fonte padrão: **Material Icons** (NiceGUI/Quasar). Canônicos: diagnóstico (`insights`), corte (`flag`), tendência (`trending_up` / `trending_down`), fraco (`priority_high`), forte (`check_circle`), estudar (`menu_book`).

## Estados de componente

Botão / input / card / selo: hover (leve escurecimento da borda), focus-visible (anel 3 px), pressed, disabled (opacidade ~0,5, sem ação), loading (spinner + texto).

## Voz

- App em 1ª pessoa (“Não encontrei…”, “Vou usar…”).
- Erro: o que aconteceu + o que fazer (`erro:` / `dica:`).
- Aviso: não alarmista; sucesso: curto, com ação se couber.
- Empty (0 provas): “Seu Gabarito Vivo está pronto para começar…”
- 1 prova: “Primeiro raio-X concluído!…”
- Privacidade: “Seus dados pertencem a você…” / rodapé “Relatório gerado localmente pelo aplicativo Gabarito Vivo.”

## Tema na GUI

`[gui] tema` = `sistema` | `claro` | `escuro` em `~/.concurso/config.toml`. Controle segmentado Auto / Claro / Escuro em Configurações > Aparência.

## Nome técnico

| Superfície | Valor |
|---|---|
| Nome mostrado | Gabarito Vivo |
| CLI | `gabarito-vivo` (alias `concurso-analise` com deprecation) |
| Pacote PyPI / `importlib` | `concurso-analise` |
| Pacote Python | `concursos` |
| Pasta global | `~/.concurso/` |
| Artefatos de release | `gabarito-vivo-<versão>-…` (atualizador ainda aceita o prefixo legado) |
| Aceite | `docs/checklist-aceite-gabarito-vivo.md` |
