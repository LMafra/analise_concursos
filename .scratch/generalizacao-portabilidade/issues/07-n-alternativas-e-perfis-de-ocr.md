# 07: Múltipla escolha com N alternativas e perfis de OCR

**What to build:** a múltipla escolha aceita 4 ou 5 alternativas, conforme o concurso ou o perfil.

Os três templates de folha (`cebraspe_ce`, `fgv_mod70ae`, `fgv_cpnu_90`) viram perfis de OCR em YAML, carregados pelo entry point `concurso.ocr`. Os limiares atuais (vazio, cheio, marcada, largura) passam a ser os padrões desses perfis.

**Blocked by:** 06

**Status:** done

- [x] Um gabarito e um `respostas.txt` de A a D são aceitos num concurso de 4 alternativas. A letra E é rejeitada, com mensagem que diz a linha e as letras aceitas.
- [x] Uma folha sintética de 4 alternativas é lida com o perfil correspondente.
- [x] Um perfil de OCR desconhecido gera erro com a lista dos perfis disponíveis.
- [x] O valor serializado `cebraspe` da pontuação continua aceito.
- [x] A paridade com os dados reais não mostra diferença.
