# 06: Integrações na GUI

**What to build:** open-notebook (aviso, ligar, desligar, sincronizar, estado), PCI (aviso, ligar, descobrir com filtros, acompanhar no radar, provas anteriores, importar simulado pelo download assistido), prática no TEC (soltar exportações) e "Instalar captura do TEC".

**Blocked by:** 01, 02, 03

**Status:** done

- [x] Cada integração mostra o texto de `aplicacao.integracoes.aviso_*` antes de ligar; desligada, nada é chamado.
- [x] Descobrir renderiza `ConcursoPci` e "Acompanhar" chama `registrar_interesse`.
- [x] Importar simulado roda numa thread, com cancelar.
- [x] Soltar uma exportação inválida mostra `erro:` e `dica:` e não copia nada.

Notas:

- A prática e a captura do TEC ficam na mesma aba (Prática no TEC), e Resultados aponta para ela quando ainda não há prática.
- Sem `[pratica]`, a importação pela GUI grava `entrada_tec = "tec"`; o dono da prática continua sendo o candidato da execução, como na CLI.
- Ligar e desligar recarregam a tela de Integrações, para as duas abas do PCI ficarem no mesmo estado.
