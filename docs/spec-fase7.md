# Spec da fase 7: estudar com o open-notebook, dicionário de temas e fluxos assistidos

As decisões, com as alternativas descartadas, estão em `docs/decisoes-fase7.md`; as fontes, em `docs/pesquisa-open-notebook-embarcado.md`; os campos de arquivo, em `docs/modelo.md`. As fases anteriores continuam valendo; esta fase só acrescenta.

## Objetivo

O usuário leigo estuda com os próprios livros, encontra concursos e importa a prática do TEC sem sair da GUI e sem saber o que é Docker, terminal, endereço local ou arquivo de configuração. Três frentes:

1. **Estudar (frente C):** o app instala (com consentimento) e supervisiona o open-notebook no próprio computador; o usuário envia livros, vê a lista e pergunta, com a resposta citando arquivo e página.
2. **Análises (frente A):** dicionário de temas opcional que aproxima sinônimos do edital, com a métrica de ganho medida sobre as revisões; telas de conferência no lugar dos arquivos editados à mão; nome do concurso tirado do edital.
3. **Integrações (frente B):** encontrar concursos com filtros simples e adicionar ao projeto num clique; provas anteriores em lote com simulado focado; planilha do TEC com mapeamento assistido.

## Termos

| Termo | Significado |
|---|---|
| pacote de estudo | arquivo por sistema, assinado, com o Python, o open-notebook travado, o SurrealDB, o servidor de embeddings e o modelo |
| instância gerenciada | o open-notebook que o app sobe em `127.0.0.1`, com portas e senha por sessão |
| instância externa | um open-notebook do próprio usuário, informado por URL no Avançado |
| biblioteca | `~/.concurso/biblioteca/`: originais, texto por página, índice FTS5 e fila |
| livro | um arquivo enviado (PDF, EPUB, DOCX, TXT), identificado pelo SHA-256 |
| trecho | parte do texto de um livro com o número da página (ou da seção) |
| dicionário de temas | `.concurso/taxonomia_topicos.yaml`: termos e expressões por tópico |
| conferência | telas que substituem `questoes_revisado.csv`, `edital_a_confirmar.yaml`, `taxonomia.yaml` e o dicionário |

## Histórias

1. Como candidato, quero clicar em "Preparar agora" uma vez e passar a estudar com meus livros, sem instalar mais nada.
2. Como candidato, quero arrastar meus PDFs, EPUBs e documentos do Word e ver cada um passar por "Lendo página N de M" até "Pronto para perguntas".
3. Como candidato com apostila escaneada, quero buscar nas páginas já lidas enquanto o resto continua.
4. Como candidato, quero perguntar "o que cai sobre licitações?" e ver os trechos com o arquivo e a página; com a IA ligada, quero também uma resposta, avisada como da IA.
5. Como candidato, quero que reenviar o mesmo livro diga "Este livro já está na sua biblioteca".
6. Como candidato, quero que o tópico fraco do relatório tenha "Estudar este tópico nos meus livros".
7. Como candidato, quero conferir os tópicos das questões, os dados do edital, as disciplinas e os temas em telas, sem abrir arquivo.
8. Como candidato, quero ligar o dicionário de temas e ver se ele melhorou ou piorou a classificação.
9. Como candidato, quero que o nome do concurso venha do edital, e poder corrigi-lo quando o app errar.
10. Como candidato, quero escolher a UF e a cidade numa lista, ver a região e as datas em DD/MM/AAAA, e adicionar o concurso ao meu projeto num clique.
11. Como candidato, quero importar várias provas anteriores em sequência e um simulado com as questões dos meus tópicos fracos.
12. Como candidato, quero importar a planilha do TEC, conferir as colunas e os assuntos, e ver o cruzamento com meu desempenho.
13. Como mantenedor, quero que cada release do open-notebook vire um pacote novo só depois de passar pelos testes de contrato.

## Entregas

Branch `fase-7`, PR único no fim, um commit verde por fatia (`uv run pytest`, `ruff`, paridade onde se aplica):

1. Docs: esta spec, as decisões, a pesquisa e as regras novas do `AGENTS.md`.
2. Pacote de estudo e `estudo.yml`.
3. Supervisor e instalação.
4. Biblioteca local: leitura com OCR, FTS5 e fila.
5. Envio ao open-notebook e registro dos embeddings; sincronização automática da instância gerenciada.
6. Estudar > Meus livros.
7. Estudar > Perguntar.
8. Telas de conferência, reanálise automática e migração do `biblioteca.yaml`.
9. Dicionário de temas, métrica de ganho e tela.
10. Nome do concurso pelo edital (pendência 12).
11. Concursos > Encontrar.
12. Concursos > Provas anteriores e simulado focado.
13. Importar do TEC.
14. Navegação e linguagem.
15. Máquina limpa, README e `0.7.0b1`.

## Seams de teste

- **open-notebook:** o servidor HTTP falso de `tests/servidor_open_notebook.py`, estendido com credenciais, modelos, `ask/simple`, `embed` e `full_text`; os testes de contrato contra o pacote real ficam em `tests/contrato_open_notebook/`, marcados `open_notebook_real`.
- **Supervisor:** os comandos dos processos vêm de uma função trocável; os testes usam scripts Python falsos que respondem `/health`.
- **Leitura de livros:** OCR por uma função trocável; PDF, EPUB e DOCX gerados no próprio teste.
- **Rede:** um teste bloqueia sockets fora de `127.0.0.1` durante o envio, a busca e a pergunta sem IA.
- **Dicionário:** `sugerir_topicos` sem dicionário é igual ao atual por propriedade; consolidados sintéticos para a métrica.
- **GUI:** fixture `user` do NiceGUI com a camada de aplicação trocada por `monkeypatch`.

## Fora do escopo

- A interface web do open-notebook, o Ollama e o docling.
- Pacote de estudo no macOS (a tela diz "ainda não disponível neste sistema").
- Classificar tópicos com embeddings ou IA.
- Baixar o PDF do PCI pelo app.
- Os itens 13 e 14 de `docs/pendencias.md`.

## Critérios de aceitação

Os critérios por entrega estão no plano da fase e se resumem a:

- máquina limpa (Windows Sandbox, `debian:12` e `ubuntu:22.04` sem Python): instalar, abrir, preparar a biblioteca, enviar um PDF com uma página escaneada, perguntar e ver o trecho com a página, sem nenhum termo proibido na tela;
- nada escuta fora de `127.0.0.1`, e nenhuma chamada de rede acontece sem opt-in;
- sem dicionário, sem conferência e sem planilha, a paridade fica idêntica;
- o README tem as seções leigas sem Docker, API, porta nem `localhost`; os termos técnicos só aparecem em "Desenvolvimento".
