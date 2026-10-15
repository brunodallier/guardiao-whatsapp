# Validação da Etapa 02

Verificação local em 15/10/2026, exclusivamente na branch `feat/historico-conversas`.

- PR nº 1 conferido como integrado. A branch de trabalho recebeu a atualização da `main` por avanço direto, preservando os commits e sem alterar a `main`.
- **126 testes aprovados**: 74 anteriores e 52 novos casos de importação, privacidade, retenção, agrupamentos, relatórios e integração, incluindo limpeza de prévias expiradas sem novas consultas. A execução final completou sem avisos.
- `node --check` aprovado para `app/static/app.js` e `community.js`; `pip check` sem incompatibilidades; `git diff --check` sem erros.
- Navegador com banco temporário separado: login fictício, importação de TXT Android, prévia minimizada, confirmação, inteligência, agrupamento das três dúvidas de saque na HUB, alteração do título de um assunto, confirmação humana de resposta e download de CSV para 30 dias com retenção mantida em sete.
- Viewport móvel de 390 × 844 sem transbordamento horizontal da página; tabelas mantêm rolagem própria. A tela compacta e o painel em desktop preservam cores, tipografia e componentes da Etapa 01.
- Imagem Docker `guardiao-ia:etapa02` construída localmente. Teste em container descartável, sem root: servidor, sessão, preservação da demonstração da Etapa 01, importação fictícia, painel de inteligência e relatório CSV aprovados. Nenhum deploy realizado.
- Antes de iniciar o servidor de desenvolvimento com o banco existente, foi criado um backup local consistente do SQLite e das chaves disponíveis na pasta privada de dados. Nenhum conteúdo do banco foi exibido. Nenhuma conversa real foi importada durante os testes.
- O classificador original `app/moderation/engine.py` e a folha de estilos original `app/static/styles.css` não foram modificados. As novas telas usam um módulo de interface adicional.

Os TXT em `tests/fixtures` são integralmente fictícios. Telefones/documentos em testes de minimização usam somente números de exemplo inválidos, como sequências de zeros. Relatórios, capturas, bancos, chaves e backups locais permanecem ignorados pelo Git.

Limitações documentadas: interpretação por regras e termos, cobertura parcial de formatos do TXT, datas/fuso explícitos, duplicações indistinguíveis sem IDs de origem, revisão de texto livre, mídias sem análise visual, hipótese de pergunta sem resposta, prévias em memória por processo e relatórios conforme os dados efetivamente retidos.

O PR da Etapa 02 deve permanecer aberto para revisão do usuário, sem merge automático. WhatsApp, serviços de IA e deploy não foram ativados.
