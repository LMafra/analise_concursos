# Revisão de segurança do atualizador (fatia E)

Escopo: `atualizador.py`, `aplicacao/atualizador.py`, o `upgrade` da CLI, o Sobre e o chip da GUI, o `[Run]`/`[Code]` do `.iss`, `scripts/assinar_manifesto.py` e o job `publicar` do `release.yml`.

## O que protege o usuário

- **Autenticidade:** o app só usa um manifesto com assinatura Ed25519 válida por uma das `CHAVES_PUBLICAS` embutidas. A assinatura é conferida antes do parse do JSON. Manifesto sem assinatura válida é erro, e nunca "sem novidade".
- **Integridade:** o artefato baixado precisa ter exatamente o SHA-256 do manifesto assinado. O download para em `tamanho` bytes, e o arquivo é apagado em qualquer falha.
- **Origem:** só `https` e hosts do GitHub (`HOSTS_PERMITIDOS`), conferidos na URL inicial e em cada redirecionamento. A URL do artefato é montada a partir da versão e do nome validados por regex, e não vem livre do manifesto. Os limites de tamanho valem para o manifesto (64 KB), a assinatura (1 KB) e a lista de releases (2 MB).
- **Downgrade e troca de canal:** só uma versão maior que a instalada é oferecida. Um cliente stable recusa um manifesto beta. Um manifesto antigo reapresentado (replay) só impede a atualização, sem instalar nada antigo.
- **Windows:** se o executável atual tem Authenticode válido, o setup baixado precisa ter o mesmo titular. O setup roda por lista de argumentos, sem shell. O PowerShell recebe o caminho por variável de ambiente, nunca interpolado no script. O setup baixado fica num `mkdtemp` do usuário.
- **Linux:** o AppImage novo é baixado para um temporário criado com `mkstemp` (O_EXCL, sem seguir links plantados) na mesma pasta e trocado com `os.replace`, que é atômico. Uma falha mantém o antigo intacto. Sem permissão de escrita, o app avisa e não tenta elevar privilégio.
- **Privacidade e rede:** nenhuma consulta sem pedido. O aviso no cabeçalho é opt-in (desligado por padrão), faz no máximo uma consulta a cada 24 h e grava o horário antes de tentar. Uma falha vai só para o log. `--offline` e `--dry-run` não consultam. O único dado enviado é o `User-Agent` com a versão instalada.

## Release

- O job `publicar` roda só em tag `v*`, no environment `release`, com revisor obrigatório. A chave privada fica só no secret `CHAVE_ATUALIZACAO` desse environment e só entra no passo que assina.
- O passo que assina usa só as dependências do `uv.lock` (com hash, `uv sync --frozen`). Antes ele fazia `uv run --with`, que resolve pacotes na hora: corrigido nesta revisão.
- O script recusa uma chave cuja pública não esteja em `CHAVES_PUBLICAS` e confere a assinatura que acabou de gravar. A tag precisa ser `v` + a versão do `pyproject.toml`.
- A chave privada nunca entrou no repositório; o procedimento de configurar e rotacionar está em `chave-atualizacao.md`.

## Riscos aceitos

- **Executável atual sem assinatura** (antes do SignPath ou com o fallback "sem assinatura"): a confiança fica só no manifesto assinado e no SHA-256. A conferência do titular só vale quando o atual está assinado. Se o `Get-AuthenticodeSignature` do atual não der `Valid` (por exemplo, sem rede para revogação), ela é pulada pelo mesmo motivo.
- **Chave privada comprometida:** quem a tiver publica uma atualização aceita. A mitigação é o revisor obrigatório no environment, a rotação por `CHAVES_PUBLICAS` e o aviso na página de releases.
- **Ações do GitHub fixadas por tag, não por SHA:** é a convenção do repositório. Fixar por SHA fica como melhoria futura do workflow inteiro.
- **Freeze attack** (servir sempre o manifesto antigo): o app só deixa de ver versões novas, e a checagem manual na página de releases continua disponível.
