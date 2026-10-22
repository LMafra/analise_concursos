# 06: Perfis de banca reproduzindo o comportamento atual

**What to build:** as bancas `cebraspe`, `fgv`, `selecon` e `quadrix` passam a ser perfis em YAML, carregados por um registro com entry point (`concurso.banca`).

O perfil passa a ser a fonte de:

- detecção da banca;
- lista de bancas aceitas;
- cadastro;
- segmentação da prova;
- leitores de gabarito e de resultado oficial;
- penalidade na agregação;
- blocos por chave de prova.

Os ramos `banca == 'cebraspe'` deixam de existir.

**Blocked by:** 01

**Status:** done

- [x] Um perfil de banca declara: marcas, formato padrão, alternativas, fator de penalidade, leitor de gabarito, segmentação, blocos por prova, leitor de resultado e templates de folha por total de itens.
- [x] Uma banca instalada por entry point num teste é detectada e usada sem mudar o núcleo.
- [x] Nenhum módulo das fases 1 a 3 compara o nome da banca com uma constante.
- [x] A suíte atual continua verde sem mudar as asserções.
- [x] A paridade com os dados reais não mostra diferença.
