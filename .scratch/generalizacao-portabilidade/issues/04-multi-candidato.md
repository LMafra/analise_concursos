# 04: Multi-candidato

**What to build:** cada concurso guarda os arquivos comuns, e cada candidato tem a subpasta `candidatos/<slug>/`, com as respostas e o `candidato.yaml` (fonte de respostas, template, total de itens e identificador no resultado oficial).

- **Saídas:** ficam em `analises/<slug>/<concurso>/`, com um consolidado por candidato.
- **Manifesto:** passa a valer por par (candidato, concurso).
- **Escolha do candidato:** `--candidate`; sem a flag, vale o último usado no projeto.
- **Comparativo:** `--all-candidates` gera o comparativo entre candidatos.
- **Novo candidato:** `add <arquivo> --candidate <slug>` acrescenta um candidato a um concurso existente.

**Blocked by:** 03

**Status:** done

- [x] Alice e Bob no mesmo concurso sintético geram `analises/alice/...` e `analises/bob/...`, cada um com o seu consolidado e as notas corretas.
- [x] Mudar o arquivo de respostas de Bob reprocessa só o par de Bob. Mudar o gabarito reprocessa os dois.
- [x] Sem `--candidate`, vale o último candidato usado, gravado em `./.concurso/config.toml`.
- [x] `add <arquivo> --candidate bob` copia o arquivo para `candidatos/bob/` e gera o `candidato.yaml`.
- [x] Uma subpasta `candidatos/<slug>/` sem perfil cria o candidato, com aviso.
- [x] `--all-candidates` gera o comparativo entre candidatos.
- [x] O `docs/modelo.md` descreve o `candidato.yaml`, o perfil do candidato e o layout novo.
