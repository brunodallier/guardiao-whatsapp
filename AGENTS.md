# Regras permanentes do Guardião IA

- `main` representa a versão estável. A publicação inicial da Etapa 01 é a única exceção para um commit direto. Depois dela, não desenvolver nem criar commits diretamente na `main`.
- Criar uma branch própria para cada funcionalidade ou correção. A branch `feat/historico-conversas` está reservada para a Etapa 02; não iniciar essa etapa sem uma nova instrução do usuário.
- Preservar o design e todas as funcionalidades existentes.
- Antes de abrir qualquer Pull Request, executar os testes e revisar a segurança dos arquivos versionados.
- Integrar funcionalidades à `main` exclusivamente por Pull Request. O usuário revisa e aprova; não fazer merge nem habilitar auto-merge automaticamente.
- Nunca executar `git push --force`, `--force-with-lease` ou reescrever histórico sem autorização explícita. Não usar atalhos para desabilitar os hooks de proteção.
- Nunca apagar funcionalidades, arquivos ou dados para resolver conflitos sem aprovação. Interromper e informar quando houver conflito ou histórico que exija uma decisão do usuário.
- Não versionar `.env`, credenciais, SQLite, chaves, sessões, tokens, conversas, dados privados de participantes, backups nem mídias de usuários, mesmo em repositório privado.
- Usar apenas dados fictícios em testes e demonstrações. Uma exceção ao `.gitignore` para incluir uma mídia de design exige revisar explicitamente o arquivo; nunca incluir mídias de participantes.
- Se a revisão encontrar dados sensíveis em arquivos a publicar ou no histórico, interromper a publicação e informar o usuário antes de qualquer limpeza.
- Git versiona código. Bancos e outros dados de execução precisam de backups separados e protegidos.
- Não fazer deploy, conectar WhatsApp ou ativar serviços externos fora do escopo autorizado.

Veja `CONTRIBUTING.md` para o fluxo e os comandos de verificação.
