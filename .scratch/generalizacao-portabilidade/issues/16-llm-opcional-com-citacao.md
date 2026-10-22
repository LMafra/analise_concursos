# 16: LLM opcional com citação

**What to build:** quem configurou um provedor tem uma camada LLM no fallback do edital, entre o perfil e a heurística.

- **Clientes:** um cliente compatível com OpenAI, que cobre OpenAI, OpenRouter, Gemini e Ollama, e um adaptador Anthropic.
- **O que vai para o provedor:** só o texto do edital e dos anexos, depois de um consentimento único.
- **Citação:** um valor sem trecho literal conferível é descartado.
- **Chave:** lida da variável de ambiente, depois do keyring, depois do `.env` com permissão 600 e aviso.
- **Interface:** a pergunta 5 entra no wizard, e o `doctor` passa a verificar a chave.
- **Desligamento:** `--no-llm` e `--offline` desligam a camada.

**Blocked by:** 11, 14

**Status:** done

- [x] Um servidor HTTP local de teste recebe só texto do edital. Nada de `candidatos/` aparece no corpo da requisição.
- [x] Uma resposta com trecho literal preenche o campo com fonte `llm`. Uma resposta sem trecho conferível é descartada, e o campo cai para a heurística.
- [x] Com `--offline` ou `--no-llm`, nenhuma requisição chega ao servidor.
- [x] Sem chave, a mensagem diz qual variável definir. A chave nunca é gravada em texto plano sem aviso.
- [x] O consentimento é pedido uma vez e fica gravado na configuração global.
