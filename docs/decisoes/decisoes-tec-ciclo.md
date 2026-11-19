# Decisões: ciclo TEC (exportar todas → explicar → PCI → repetir)

## Explicação no open-notebook: `POST /api/search/ask/simple`

O cliente do app já usa `/api/search/ask/simple` (`ClienteOpenNotebook.perguntar`). Não há `/api/chat/execute` no cliente. A geração de explicações e similares reutiliza esse endpoint: source com o enunciado (e todas as alternativas na múltipla escolha) + note com a resposta. O prompt de múltipla escolha inclui o bloco fixo *"Explique por que cada alternativa errada está errada, uma por uma."*

## Exportação parcial (só erros)

O import não bloqueia quando `len(itens) == cads.er` ou `len < cads.er`: grava aviso e segue. Brancos não entram em `cads.res`, então `len == tot` também conta como exportação completa. Só `len > tot` rejeita o arquivo. Assim o modo antigo da extensão continua válido.

## Filtro PCI por assunto

A busca monta o termo com `ass` + `mat`, chama `pesquisar_provas`, prefere a mesma banca (`organizadora`) quando houver, e marca `tema_no_edital` se o assunto aparece em algum `edital_estruturado.json` local. Cache: `.concurso/cache/pci_mcp.json` (TTL do cliente). PCI desligado → omitir com aviso; import e repetição seguem offline.

## Captura de acerto e branco

Acerto: grava no tick em que `situacao === 'acertou'`. Branco: grava ao sair da questão (`id` muda) depois de pelo menos um tick estável em `sem_resolver` com `marc` vazio (anti-flicker). `gab` em acerto lê o bloco `.questao-enunciado-resolucao-acertou` ou Angular `numeroAlternativaCorreta` (hipótese confirmada por testes sintéticos; validar com Diagnóstico no TEC real).
