# Spec: integração com o PCI Concursos (MCP)

Os fatos do servidor estão em `docs/pesquisa-pci-mcp.md`; os campos de arquivo, em `docs/modelo.md`.

## Objetivo

Usar o servidor MCP público da PCI Concursos como fonte estruturada, e opcional, para três coisas: descobrir concursos com inscrições abertas, achar provas anteriores (que viram simulados) e avisar dos prazos que estão fechando. O PCI é um complemento colaborativo e pode não cobrir todos os editais; a análise local continua sendo a fonte de verdade dos dados do candidato. Sem configuração, nenhuma saída muda e nenhuma chamada de rede acontece.

## Termos

| Termo | No PCI | No projeto |
|---|---|---|
| concurso PCI | item de `buscar_por_cargo` etc., com `id`, prazos e notícia | `ConcursoPci`; não é um concurso local até virar pasta em `provas/` |
| interesse | — | concurso PCI registrado em `.concurso/interesses_pci.yaml` |
| prova anterior | item de `pesquisar_provas` (`id`, órgão, ano, organizadora, página) | `ProvaAnteriorPci` |
| simulado | — | prova anterior baixada que virou concurso local (`provas/<orgao>_<ano>_pci<id>/`, bloco `simulado:`) |
| alvo | — | concurso local cujo edital empresta os tópicos ao simulado |
| radar | — | concursos PCI dos cargos-alvo que abrem ou fecham em breve, mais os interesses |

## Entrega em 3 PRs

1. **Cliente, cache e descoberta:** `[pci_mcp]`, `[pci]` no perfil do candidato, `integracoes/pci_mcp.py`, `integracoes/cache_pci.py`, `discover`, `pci enable/disable` e fixtures reais.
2. **Provas anteriores e simulados:** `pci provas`, `integracoes/pagina_pci.py`, `integracoes/download_assistido.py`, bloco `simulado:`, edital emprestado só para tópicos, simulados fora do consolidado por padrão.
3. **Radar:** radar depois da análise, `radar_editais.md`, seções no `index.html`, linha no `status` e item no `doctor`, ambos só pelo cache.

Cada PR passa pela paridade com a integração desligada.

## Comandos

- `concurso-analise pci enable [--url URL]`: mostra o que vai para o PCI (só termos de busca) e grava `[pci_mcp] enabled = true`. Sem terminal, só com `--yes`.
- `concurso-analise pci disable`: grava `enabled = false`.
- `concurso-analise discover [--cargo X ...] [--cidade C --uf sp] [--regiao R] [--termo T] [--professores] [--refresh] [--json] [--register ID] [--forget ID]`:
  - sem filtro, usa os cargos-alvo do candidato; sem cargos, `listar_concursos`;
  - lista título, UF, cargos, inscrições (início, fim, dias) e link; `--json` imprime a lista em JSON;
  - `--register ID` grava o concurso (que precisa estar no resultado) em `interesses_pci.yaml`; `--forget ID` o remove.
- `concurso-analise pci provas [concurso] [--termo T ...] [--download ID] [--refresh] [--json]`:
  - termos: `--termo`; senão, `pci.termos_provas` do `concurso.yaml`; senão, as duas primeiras palavras do `cargo` (sem "CARGO N:") com a banca, e depois só o cargo;
  - com concurso, grava `analises/<candidato>/<concurso>/provas_anteriores.md`;
  - `--download ID`: abre a página da prova no navegador do usuário, espera os arquivos na pasta de downloads (até `timeout_download`), cria o simulado e roda o cadastro.
- `concurso-analise add <pasta> --pci ID`: cadastra a pasta e grava o vínculo com o interesse (`pci:` no `concurso.yaml`, `concurso` no interesse).
- Depois de cada análise, com `enabled` e rede, roda o radar. A falha vira aviso; o código de saída continua o da análise.
- `--offline` usa só o cache, mesmo vencido, com aviso; `--dry-run` não chama a rede nem grava nada.

## Decisões

- **Opt-in só com `enabled`:** só vão termos de busca (cargo, cidade, UF, região, termo); nenhum nome, slug, CPF ou inscrição. Por isso não há `consentimento`, ao contrário do LLM e do open-notebook.
- **SDK oficial isolado:** o `mcp` (2.x) fica num extra (`concurso-analise[pci]`) com import tardio; só `TransporteSdk` o conhece. O resto fala com o `TransporteMcp` (`ferramentas()`, `chamar(ferramenta, argumentos)`), e o cliente confere o `tools/list` antes da primeira chamada: ferramenta ausente vira aviso e o recurso é pulado.
- **Uma sessão por execução:** o `TransporteSdk` mantém o `Client` aberto num laço de eventos próprio, numa thread, e fecha no fim do comando.
- **Cache local com TTL:** `.concurso/cache/pci_mcp.json`, chave sha256 de ferramenta e argumentos normalizados (sem acento, minúsculas, chaves ordenadas), TTL de `ttl_horas` (24). Respostas vazias (`message`) entram; `isError` não. `--refresh` ignora o cache. O servidor é beta, sem limite publicado: o cache evita repetir a mesma busca e mantém o app útil com o servidor fora do ar.
- **Limite por execução:** `MAXIMO_CONSULTAS = 20` consultas ao servidor (o cache não conta). Passou disso, aviso, e o resto fica para a próxima execução.
- **Prazos do servidor:** os dias vêm dos campos calculados (`dias_ate_fim`, `dias_ate_inicio`) da resposta, relativos ao `meta.data_atual`, nunca de `now()`. Dentro do TTL, a mesma entrada gera a mesma saída, e `gravar_se_mudou` preserva o `mtime`.
- **Radar:** entram os concursos com inscrições abertas e `dias_ate_fim <= dias_alerta`, e os que abrem em até `dias_alerta` dias (`em_breve`); os interesses entram até o `fim`. Junta pelo `id`.
- **Cargos-alvo por candidato:** `[pci] cargos, uf` no perfil global (`~/.concurso/candidatos/<slug>.toml`), com `[pci_mcp] cargos, uf` como reserva. O `candidato.yaml` é por concurso e não serve para isso.
- **Interesse em vez de pasta vazia:** `--register` não cria `provas/<x>/` (ficaria INCOMPLETO no `status`). Depois do `fim`, o interesse sai do radar mas fica no arquivo até `--forget`.
- **Download assistido:** o captcha e o `robots.txt` impedem o download automático. O app lê a página HTML (permitida) para saber os nomes dos arquivos, abre a página no navegador padrão (no WSL, o do Windows) e importa da pasta de downloads o que o usuário baixou. Casa o nome exato ou com sufixo do navegador (`nome (1).pdf`), ignora `.crdownload` e `.part`, e só aceita arquivos modificados depois do início da espera. Nunca chama `/provas/link`.
- **Prova anterior vira simulado (concurso próprio):** uma prova com gabarito é um concurso para o app, então entra na correção sem código novo.
  - pasta `provas/<orgao>_<ano>_pci<id>/`, com `simulado:` no `concurso.yaml` (`fonte`, `id_pci`, `ano_original`, `organizadora`, `orgao`, `link`, `concurso_alvo`);
  - banca: a `organizadora` normalizada casada com o `id` e as `marcas` dos perfis; sem perfil, `generic` com aviso;
  - edital: `../<alvo>/<edital>` do alvo de `pci provas <alvo>`, **só para os tópicos**. A correção (penalidade, pesos, nota máxima) vem do perfil da banca da prova, e as regras do edital do alvo (pesos, cortes, cronograma, discrepâncias, catálogo) não são extraídas. Sem alvo, ou com alvo sem edital, o simulado fica em modo mínimo, com aviso;
  - `data_prova`: a data em que o candidato resolveu, gravada no `add` das respostas (padrão: hoje) quando o simulado ainda não tem data. O ano original fica em `simulado.ano_original`, para a ordem cronológica refletir a evolução do candidato.
- **Simulados fora das tendências por padrão:** não entram no consolidado (`desempenho_geral.csv`, comparativo) nem no parquet; `[analise] incluir_simulados = true` os inclui. Sem coluna nova, o schema do parquet não muda. Cada simulado tem relatório próprio e aparece na seção "Simulados (provas anteriores do PCI)" do `index.html`, fora da tabela de concursos.
- **`status` e `doctor` sem rede:** leem `analises/<candidato>/radar_editais.json`, gravado pelo radar.
- **Erros:** rede, timeout e HTTP viram `PciMcpIndisponivelError`; formato inesperado, `PciMcpFormatoError`; argumento recusado (`isError`), `PciMcpParametroError`. Num comando explícito, os dois primeiros saem como `ErroDoAmbiente` (código 2) e o último como `ErroDoUsuario` (código 1). Depois da análise, viram aviso.
- **Logs:** uma linha INFO por comando (`PCI: N consultas, M do cache, F falhas`); cada chamada, a duração e o hit/miss em DEBUG; falhas em WARNING.
- **Contrato:** `scripts/gravar_fixtures_pci.py` grava `tools/list` e uma resposta real de cada ferramenta em `tests/fixtures/pci/`. O teste de integração (`PCI_MCP_INTEGRACAO=1`, marker `pci_mcp`) compara o `tools/list` real com o gravado.
- **Cursor:** o README mostra o `.cursor/mcp.json` (só a URL pública) para o agente consultar o PCI direto; o arquivo não é versionado.

## Descartado

- `buscar_apostilas`: fora do `tools/list` e sem resultados.
- Baixar edital: o PCI não tem link de edital, só a notícia.
- Substituir o LLM: o LLM lê o texto do edital, não busca editais; o PCI não alimenta as regras do edital.
- Coluna `simulado` no parquet: mudaria o schema.

## Seams de teste

- Transporte: `TransporteFalso` em memória, com as fixtures reais, conta as chamadas; o `TransporteSdk` é testado com um `MCPServer` em processo.
- Cache e radar: relógio injetado; funções puras sobre dicionários.
- Página: HTML de fixture; o download assistido usa uma pasta temporária, o navegador do `conftest` e um relógio e um `dormir` falsos.
- CLI: `main([...])` com `CONCURSO_HOME` temporária e o transporte trocado por `monkeypatch` em `concursos.integracoes.pci_mcp.abrir_transporte`.
- Integração real: `@pytest.mark.pci_mcp`, pulado sem `PCI_MCP_INTEGRACAO=1`.

## Critérios de aceitação

- Desligada, a CLI se comporta como hoje, e a paridade não mostra diferença.
- `discover --cargo analista --uf mg` lista sem repetição e com prazos; a segunda execução dentro do TTL não usa a rede.
- `pci provas <alvo> --download <id>` cria `provas/<orgao>_<ano>_pci<id>/` com `simulado:`, e a análise corrige pelo perfil da banca da prova, com os tópicos do edital do alvo.
- Com `incluir_simulados = false`, o consolidado e as tendências ficam iguais aos de antes do simulado.
- O `index.html` mostra "Editais que fecham em breve" e "Simulados"; `status` e `doctor` mostram o radar só a partir do cache.
- Uma falha do PCI gera `erro:`/`dica:` num comando explícito e um aviso depois da análise, sem abortar nada.
