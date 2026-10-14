# Validação da primeira etapa

Verificação local concluída em 14/10/2026.

- **71 testes automatizados aprovados**, sem avisos, com `python -m pytest -q` no ambiente virtual do projeto.
- JavaScript verificado com `node --check app/static/app.js`.
- Dependências verificadas com `python -m pip check`, sem incompatibilidades.
- Navegador: login com conta fictícia em banco temporário separado; painel; simulação crítica e permitida; detalhes e revisão de alerta; edição de grupo; cadastro de afiliado; salvamento de regras.
- Layout responsivo conferido com viewport de 390 × 844; sem transbordamento horizontal da página. As tabelas oferecem rolagem própria.
- Docker: `docker compose config --quiet`, construção da imagem `guardiao-ia:local` e inicialização HTTP/SQLite com usuário sem privilégios em container descartável. O container de teste foi removido automaticamente.
- O banco principal mantém três grupos e oito mensagens de demonstração. Nenhum administrador ou afiliado foi criado no banco principal. O primeiro acesso está disponível para o usuário cadastrar sua própria conta.

Uma captura do painel foi mantida apenas no diretório local `test-results`, ignorado pelo Git. A imagem mostra somente registros fictícios; os cadastros e as simulações da verificação visual não foram adicionados ao banco principal.

Não houve deploy, conexão com WhatsApp, chamada a API de IA, contratação de serviço ou publicação em repositório remoto. A construção Docker baixou a imagem oficial Python e dependências públicas, somente para validação local.

Limites desta etapa: texto/URLs; listas de domínios configuradas manualmente; nomes locais como identidade dos participantes; um único administrador; nenhuma automação real de remoção ou advertência. A lista de apostas inicial usa apenas domínios fictícios `.example`.

## Preparação para versionamento

- Suíte ampliada: **74 testes aprovados**, incluindo três verificações de segurança dos hooks Git em repositórios temporários.
- Index revisado antes da publicação: 40 arquivos de código, exemplos e documentação; nenhum banco, chave local, sessão, conversa, mídia de usuário ou credencial real incluído.
- Não existia repositório Git local; o remoto informado estava vazio. Nenhum histórico precisou ser limpo ou reescrito.
- `.gitignore` ampliado, hooks locais ativados, regras permanentes em `AGENTS.md`, fluxo em `CONTRIBUTING.md`, template de Pull Request e workflow de testes adicionados. As actions são fixadas por SHA e usam acesso de leitura.
- Design e funcionalidades da Etapa 01 preservados. A Etapa 02 não foi iniciada.
