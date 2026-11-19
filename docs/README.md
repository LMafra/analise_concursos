# Documentação do Gabarito Vivo

Índice da pasta `docs/`. Canônicos de domínio e arquitetura ficam na raiz desta pasta; o resto por tipo.

## Canônicos (raiz)

| Documento | Para quê |
|---|---|
| [modelo.md](modelo.md) | Contratos de arquivo, fórmulas, schemas (`concurso.yaml`, config, parquet, …) |
| [arquitetura-plataforma.md](arquitetura-plataforma.md) | Mapa as-is: funcionalidades, UML, CC, métricas, gaps |
| [detalhes-tecnicos.md](detalhes-tecnicos.md) | Instalação, Docker, integrações e problemas no terminal |
| [marca-gabarito-vivo.md](marca-gabarito-vivo.md) | Identidade visual e voz da marca |
| [img/](img/) | Capturas usadas no README |

## Specs (`specs/`)

Leia a da fase antes de mudar comportamento.

| Documento | Escopo |
|---|---|
| [spec.md](specs/spec.md) | Fase 1 — correção por concurso |
| [spec-fase2.md](specs/spec-fase2.md) | Fase 2 — evolução entre concursos |
| [spec-fase3.md](specs/spec-fase3.md) | Fase 3 — edital como fonte de verdade |
| [spec-fase4.md](specs/spec-fase4.md) | Fase 4 — CLI, perfis, onboarding, distribuição |
| [spec-fase5.md](specs/spec-fase5.md) | Fase 5 — GUI NiceGUI e empacotamento |
| [spec-fase6.md](specs/spec-fase6.md) | Fase 6 — Windows/Linux, assinatura, atualizador |
| [spec-fase7.md](specs/spec-fase7.md) | Fase 7 — estudar, livros, dicionário, TEC/PCI assistidos |
| [spec-linguagem.md](specs/spec-linguagem.md) | Vocabulário leigo (transversal) |
| [spec-pci-mcp.md](specs/spec-pci-mcp.md) | Integração PCI Concursos |
| [spec-open-notebook.md](specs/spec-open-notebook.md) | Integração open-notebook |

## Decisões (`decisoes/`)

Registro curto das escolhas e alternativas descartadas.

| Documento | Par |
|---|---|
| [decisoes-fase5.md](decisoes/decisoes-fase5.md) | spec-fase5 |
| [decisoes-fase6.md](decisoes/decisoes-fase6.md) | spec-fase6 |
| [decisoes-fase7.md](decisoes/decisoes-fase7.md) | spec-fase7 |
| [decisoes-linguagem.md](decisoes/decisoes-linguagem.md) | spec-linguagem |
| [decisoes-tec-ciclo.md](decisoes/decisoes-tec-ciclo.md) | prática TEC |
| [decisoes-ux-gabarito-vivo.md](decisoes/decisoes-ux-gabarito-vivo.md) | rebrand / UX |

## Pesquisa (`pesquisa/`)

Fontes e achados que embasam specs.

| Documento | Tema |
|---|---|
| [pesquisa-fase4.md](pesquisa/pesquisa-fase4.md) | Bancas, CLI, OMR, distribuição |
| [pesquisa-pci-mcp.md](pesquisa/pesquisa-pci-mcp.md) | Servidor MCP da PCI |
| [pesquisa-open-notebook-embarcado.md](pesquisa/pesquisa-open-notebook-embarcado.md) | Pacote de estudo / open-notebook |

## Release (`release/`)

| Documento | Para quê |
|---|---|
| [release.md](release/release.md) | Como gerar, conferir e publicar uma versão |
| [release-v0.7.0b1.md](release/release-v0.7.0b1.md) | Notas da tag |
| [release-v0.7.0b2.md](release/release-v0.7.0b2.md) | Notas da tag |
| [release-v0.7.0b3.md](release/release-v0.7.0b3.md) | Notas da tag |

Notas novas: `docs/release/release-v<versão>.md` (o `release.yml` lê esse caminho).

## Produto (`produto/`)

| Documento | Para quê |
|---|---|
| [pendencias.md](produto/pendencias.md) | Itens abertos e ordem sugerida |
| [checklist-aceite-gabarito-vivo.md](produto/checklist-aceite-gabarito-vivo.md) | Aceite de UX / rebrand no PR de release |

## Fora desta pasta

- Regras para agentes: [`AGENTS.md`](../AGENTS.md)
- Uso do produto e desenvolvimento: [`README.md`](../README.md)
- Extensão TEC: [`tec-erros/docs/`](../tec-erros/docs/) (repo interno separado do pacote Python)
