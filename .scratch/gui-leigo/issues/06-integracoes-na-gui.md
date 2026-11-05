# 06: Integrações na GUI

**What to build:** open-notebook (aviso, ligar, desligar, sincronizar, estado), PCI (aviso, ligar, descobrir com filtros, acompanhar no radar, provas anteriores, importar simulado pelo download assistido), prática no TEC (soltar exportações) e "Instalar captura do TEC".

**Blocked by:** 01, 02, 03

**Status:** todo

- [ ] Cada integração mostra o texto de `aplicacao.integracoes.aviso_*` antes de ligar; desligada, nada é chamado.
- [ ] Descobrir renderiza `ConcursoPci` e "Acompanhar" chama `registrar_interesse`.
- [ ] Importar simulado roda numa thread, com cancelar.
- [ ] Soltar uma exportação inválida mostra `erro:` e `dica:` e não copia nada.
