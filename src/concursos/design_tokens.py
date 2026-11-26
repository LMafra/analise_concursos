"""Tokens de marca compartilhados pela GUI e pelo HTML estático (sem dependência do NiceGUI)."""

FONTE = '-apple-system, "Segoe UI", Roboto, "Noto Sans", Ubuntu, sans-serif'
ESPACOS = {'xs': '4px', 'sm': '8px', 'md': '16px', 'lg': '24px', 'xl': '40px', '2xl': '64px'}
RAIO_CARTAO = '10px'
RAIO_GRANDE = '14px'
RAIO_PILL = '9999px'
ELEVACAO_1 = '0 1px 2px rgb(20 40 43 / .05), 0 6px 16px rgb(20 40 43 / .04)'

TOKENS_RELATORIO = {
    '--color-primary': '#14282B',
    '--color-bg-base': '#F8FAFC',
    '--color-bg-surface': '#FFFFFF',
    '--color-text-main': '#14282B',
    '--color-text-muted': '#475569',
    '--color-border': '#E2E8F0',
    '--color-status-pass-bg': '#ECFDF5',
    '--color-status-pass': '#117A4B',
    '--color-status-warn-bg': '#FFFBEB',
    '--color-status-warn': '#92400E',
    '--color-status-alert-bg': '#FEF2EE',
    '--color-status-alert': '#9A3412',
    '--font-family-body': FONTE,
    '--space-xs': ESPACOS['xs'],
    '--space-sm': ESPACOS['sm'],
    '--space-md': ESPACOS['md'],
    '--space-lg': ESPACOS['lg'],
    '--space-xl': ESPACOS['xl'],
    '--radius-sm': '4px',
    '--radius-md': RAIO_CARTAO,
    '--radius-lg': RAIO_GRANDE,
    '--radius-pill': RAIO_PILL,
    '--shadow-sm': ELEVACAO_1,
}


def css_root_do_relatorio() -> str:
    pares = ' '.join(f'{k}: {v};' for k, v in TOKENS_RELATORIO.items())
    return f':root {{ {pares} }}'
