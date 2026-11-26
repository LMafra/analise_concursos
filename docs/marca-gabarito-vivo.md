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
| espaço xs → 2xl | 4 / 8 / 16 / 24 / 40 / 64 px |
| raio sm / md / lg / pill | 4 / 10 / 14 / 9999 px |
| elevação 1 / 2 | `0 1px 2px rgb(20 40 43 / .05), 0 6px 16px rgb(20 40 43 / .04)` / `0 8px 24px rgb(0 0 0 / .16)` |
| alvo mínimo | 44 × 44 px |
| foco | outline 3 px na cor `--ca-foco` |

## Cores

### Claro

| Papel | Hex |
|---|---|
| Primária (teal-ink) | `#14282B` |
| Sobre primária | `#FFFFFF` |
| Primária como texto / link | `#14282B` |
| Fundo / superfície | `#F8FAFC` / `#FFFFFF` |
| Texto / suave / borda | `#14282B` / `#475569` / `#E2E8F0` |
| Acima (fundo / texto) | `#ECFDF5` / `#117A4B` |
| Limite (fundo / texto) | `#FFFBEB` / `#92400E` |
| Abaixo (fundo / texto) | `#FEF2EE` / `#9A3412` |
| Info | fundo `#E6EFF0`, ícone/texto `#14282B` |
| Erro (falha de sistema) | fundo `#FEF2EE`, ícone/texto `#9A3412` |

### Escuro

| Papel | Hex |
|---|---|
| Fundo / superfície | `#0D1719` / `#142225` |
| Texto / suave | `#EAF2F3` / `#A8BDC1` |
| Primária (destaque) | `#4ADE80` sobre superfície escura para botões; estrutura permanece teal |
| Acima | `#112A20` / `#4ADE80` |
| Limite | `#2A200D` / `#FCD34D` |
| Abaixo | `#2D1812` / `#FBCFC0` |
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
| CLI | `gabarito-vivo` |
| Pacote PyPI / `importlib` | `gabarito-vivo` |
| Pacote Python | `concursos` |
| Pasta global | `~/.gabarito-vivo/` |
| Artefatos de release | `gabarito-vivo-<versão>-…` (atualizador ainda aceita o prefixo legado) |
| Aceite | `docs/produto/checklist-aceite-gabarito-vivo.md` |
