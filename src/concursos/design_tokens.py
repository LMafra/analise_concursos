"""Tokens de marca compartilhados pela GUI e pelo HTML estático (sem dependência do NiceGUI)."""

FONTE = '-apple-system, "Segoe UI", Roboto, "Noto Sans", Ubuntu, sans-serif'
ESPACOS = {'xs': '4px', 'sm': '8px', 'md': '16px', 'lg': '24px', 'xl': '32px'}
RAIO_CARTAO = '8px'
RAIO_PILL = '9999px'
ELEVACAO_1 = '0 1px 2px rgb(0 0 0 / .08)'

TOKENS_RELATORIO = {
    '--color-primary': '#14282B',
    '--color-bg-base': '#FAFAFA',
    '--color-bg-surface': '#FFFFFF',
    '--color-text-main': '#14282B',
    '--color-text-muted': '#475569',
    '--color-border': '#CBD5E1',
    '--color-status-pass-bg': '#E6F4ED',
    '--color-status-pass': '#0E5A37',
    '--color-status-warn-bg': '#FEF3C7',
    '--color-status-warn': '#92400E',
    '--color-status-alert-bg': '#FCEBE6',
    '--color-status-alert': '#8C2D0D',
    '--font-family-body': FONTE,
    '--space-xs': ESPACOS['xs'],
    '--space-sm': ESPACOS['sm'],
    '--space-md': ESPACOS['md'],
    '--space-lg': ESPACOS['lg'],
    '--space-xl': ESPACOS['xl'],
    '--radius-sm': '4px',
    '--radius-md': RAIO_CARTAO,
    '--radius-pill': RAIO_PILL,
    '--shadow-sm': ELEVACAO_1,
}


def css_root_do_relatorio() -> str:
    pares = ' '.join(f'{k}: {v};' for k, v in TOKENS_RELATORIO.items())
    return f':root {{ {pares} }}'
