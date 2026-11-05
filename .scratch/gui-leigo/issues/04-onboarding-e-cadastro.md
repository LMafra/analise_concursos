# 04: Onboarding, cadastro com detecção e respostas manuais

**What to build:** onboarding em formulário; `InteracaoGui`; novo concurso com arquivos soltos, papel detectado por `deteccao.classificar_arquivo` e confirmação; respostas do candidato em `provas/<concurso>/candidatos/<nome>/`; seletor de candidato e "analisar todos"; aviso sem Tesseract e formulário manual que grava `respostas.csv`.

**Blocked by:** 03

**Status:** done

- [x] O onboarding grava pelas mesmas funções do `init` (`onboarding.aplicar` e `gravar`).
- [x] Trocar o papel antes de cadastrar muda o nome ou a pasta do arquivo conforme o cadastro espera.
- [x] As perguntas do `cadastrar` chegam como diálogos; cancelar não grava nada.
- [x] O CSV do formulário manual é aceito por `respostas.ler_respostas_csv`.
- [x] Com mais de um candidato, o seletor aparece e "todos" chama a análise com `todos=True`.

Notas:

- O papel trocado vale por `cadastrar(..., papeis)`, que vence a detecção sem renomear o arquivo; folha e respostas vão para a pasta do candidato, e "ignorar" não copia o arquivo.
- A leitura da folha usa o OpenCV, não o Tesseract. Sem o Tesseract, o que se perde é a leitura de PDFs escaneados (edital e prova sem texto); o aviso diz isso, e o formulário manual cobre a folha que não for lida.
- Soltar arquivos usa o `ui.upload` (arrastar e soltar do Quasar) nos três sistemas; o evento `drop` com caminhos da janela nativa ficou de fora, porque o upload já cobre a janela nativa.
