# Chave do manifesto de atualização

A chave pública está em `atualizador.CHAVES_PUBLICAS`. A privada (Ed25519, PEM) foi gerada na máquina do mantenedor, fora do repositório, em `~/.concurso/chave-atualizacao-privada.pem` (permissão 600).

## Configurar no GitHub (uma vez)

1. Settings > Environments > New environment: `release`.
2. Em `release`, ligue "Required reviewers" com o mantenedor e restrinja "Deployment branches and tags" às tags `v*`.
3. Ainda em `release`, crie o secret `CHAVE_ATUALIZACAO` com o conteúdo inteiro do PEM (incluindo as linhas `-----BEGIN PRIVATE KEY-----` e `-----END PRIVATE KEY-----`).
4. Guarde uma cópia do PEM num cofre de senhas e apague o arquivo local.

Sem o secret, o job `publicar` falha no passo "Manifesto de atualização assinado": nenhuma release sai sem manifesto.

## Rotacionar

1. `uv run python scripts/assinar_manifesto.py gerar-chave nova.pem` imprime a chave pública nova.
2. Acrescente a pública nova em `CHAVES_PUBLICAS` (sem tirar a antiga) e publique uma versão assinada ainda com a antiga.
3. Troque o secret `CHAVE_ATUALIZACAO` pelo PEM novo. Depois que a maioria tiver atualizado, tire a pública antiga numa versão seguinte.

Se a privada vazar: troque o secret, publique logo uma versão com só a pública nova e avise na página de releases para quem estiver nas versões anteriores atualizar à mão.

## Teste ponta a ponta antes de promover

Com a release nova publicada como prerelease (ou como latest, para o stable), rode o workflow `atualizacao` com `de` = a tag anterior que já tem o atualizador (a primeira é a v0.6.0b1), `esperada` = a versão nova e o canal. Só depois promova a release a "latest".
