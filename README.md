# Guardião IA

Primeira etapa de uma plataforma local para administrar comunidades. Backend Python/FastAPI, SQLite e frontend HTML/CSS/JavaScript sem build, CDN ou conexão externa. O nome IA representa o projeto futuro; a classificação atual usa somente regras.

## Versionamento

Repositório: [brunodallier/guardiao-whatsapp](https://github.com/brunodallier/guardiao-whatsapp). `main` mantém a versão estável; funcionalidades usam branches próprias e Pull Requests com revisão do usuário. Não fazer merge automático nem reescrever histórico. Leia [CONTRIBUTING.md](CONTRIBUTING.md) e [AGENTS.md](AGENTS.md). SQLite, conversas, credenciais e backups permanecem fora do Git.

## Executar no Windows

Requer Python 3.12 ou superior. Validado neste ambiente com Python 3.14. No PowerShell, dentro da pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Abra **http://127.0.0.1:8000**. No primeiro acesso, escolha seu usuário e senha (mínimo de 10 caracteres). Não existe uma senha padrão. Não precisa ativar o ambiente virtual. Para parar, pressione Ctrl+C no terminal.

Nos próximos acessos, execute apenas o comando do uvicorn. Alternativa: `powershell -ExecutionPolicy Bypass -File .\start.ps1 -Install` para preparar e iniciar; depois use `powershell -ExecutionPolicy Bypass -File .\start.ps1`.

O servidor deve permanecer em 127.0.0.1 nesta etapa. A configuração inicial do administrador acontece no primeiro acesso local. Não exponha o cadastro inicial à internet.

## O que está funcionando

- Painel com grupos, mensagens analisadas, suspeitas, críticas, pendências, atividade por hora e ocorrências recentes.
- Cadastro e edição de grupos, descrição, contagem informada e pausa das simulações.
- Cadastro, edição e exclusão de plataformas, domínio, link próprio, código, parâmetros, prefixo de caminho e autorizações.
- Sete regras editáveis no painel: apostas, afiliados, marketplaces, links desconhecidos/encurtados, repetição, frequência de mensagens e frequência de links.
- Simulação por grupo e participante, resultado explicado e recomendações de ações sem execução real.
- Histórico com busca, filtros, paginação, detalhes, revisão de alertas e exclusão por grupo ou total com confirmação.
- Autenticação de um administrador, hash PBKDF2, sessão assinada de oito horas, cookies HttpOnly/SameSite, proteção CSRF, limite de tentativas de login e validação de Host.
- Retenção de histórico de sete dias por padrão, editável entre 1 e 365. Limpeza no início, a cada hora, ao analisar e ao consultar o histórico/painel. Reduzir o prazo apaga registros vencidos imediatamente.

## Demonstração e teste de regras

A primeira inicialização cria três grupos e oito mensagens **fictícios**, sem afiliados preenchidos. São 700 participantes informados apenas como exemplo; não há importação nem contagem real. Os dados demo entram nos indicadores. A demonstração é criada uma vez; apagar o histórico não a recria. Para começar sem demonstração, defina `SEED_DEMO=false` antes da primeira inicialização de um banco vazio.

No simulador, use os botões de exemplos. `https://cassino-demo.example/bonus` é crítico. “Eu li sobre cassino, BET e Shopee” é permitido. Um marketplace é suspeito e exige contexto. Links desconhecidos/encurtados não são abertos, resolvidos ou seguidos.

**A lista inicial de apostas contém apenas domínios fictícios `.example`.** Adicione domínios confirmados no painel Regras. Este conjunto inicial não constitui uma lista de bloqueio completa. A correspondência de domínios usa limites corretos: `sub.dominio.example` pertence a `dominio.example`; `dominio.example.outro.example` não pertence.

Para testar afiliados, cadastre uma plataforma **fictícia**:

| Campo | Exemplo fictício |
| --- | --- |
| Plataforma | Plataforma de teste |
| Domínio | plataforma.example |
| Link | https://plataforma.example/?ref=MEU-DEMO |
| Código | MEU-DEMO |
| Parâmetros | ref |

`?ref=MEU-DEMO` será permitido; `?ref=OUTRO-DEMO` será suspeito. Parâmetros globais e os da plataforma são considerados juntos. Duplicar um parâmetro com códigos diferentes continua suspeito. O código cadastrado é usado quando o link próprio não informa o valor daquele parâmetro. Sem código/link próprio, indicações não são presumidas autorizadas.

Para indicações no caminho, como `/convite/MEU-DEMO`, configure o prefixo `/convite/` e o link completo (ou o código). Sem um prefixo, o motor não tenta adivinhar a identidade de afiliado no caminho. Links comuns dentro do domínio da plataforma são permitidos. Os cadastros devem representar os domínios reais de indicação; um redirecionador externo fica suspeito até confirmação.

Autorizações exatas comparam domínio, caminho e parâmetros, normalizando protocolo HTTP/HTTPS, ordem de parâmetros e fragmento. Não seguem redirecionamentos. Autorizar um domínio inclui subdomínios; use links exatos se precisar de uma permissão restrita. Domínios de cassino e encurtadores têm precedência sobre autorizações. Em plataformas cadastradas, a autorização do domínio não ignora códigos de terceiros. Links de afiliado para plataformas não cadastradas permanecem suspeitos.

Limites incluem a mensagem atual. Por padrão, três textos iguais em 120 segundos, seis mensagens em dez segundos ou cinco links em 30 segundos acionam alertas. Os contadores se restringem ao mesmo nome de participante e grupo. Nesta simulação, o nome é a identidade local; uma integração futura deve fornecer um identificador estável. Repetição ignora caixa e espaços redundantes. Revisar um alerta não altera sua classificação nem remove os dados da janela.

Desligar uma regra desativa sua classificação, inclusive a regra de apostas. As alterações valem para novas mensagens; análises históricas preservam o resultado e a justificativa original.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes usam bancos temporários e dados fictícios. Cobrem URLs, menções permitidas, afiliados, prioridades, limites, janelas, concorrência, autenticação, CSRF, CRUD, filtros, revisão, retenção e exclusão. Não fazem chamadas externas.

`requirements.lock` fixa as dependências de execução validadas. Para repetir exatamente o ambiente de servidor, instale `-r requirements.lock`. O arquivo de desenvolvimento acrescenta pytest e httpx2 (cliente de testes do Starlette); não há dependência de Node para executar a aplicação.

## Estrutura

```text
app/
  main.py                  Rotas, segurança HTTP e ciclo de vida
  config.py                Configuração e segredo local
  db.py                    Esquema SQLite e retenção
  models.py                Validação das entradas
  security.py              Senhas
  moderation/
    engine.py              Classificador puro, sem acesso à rede
    urls.py                Extração e normalização de URLs
  services/
    messages.py            Entrada, análise e persistência transacional
    notifications.py       Contrato de notificações, implementação local
  static/                  Painel sem ferramentas de build
config/rules.json          Regras iniciais, copiadas para SQLite uma vez
tests/                    Testes de regras e integração
data/                     Banco e chave de sessão (ignorados pelo Git)
```

O painel modifica a configuração no SQLite. Editar `config/rules.json` altera apenas os padrões para bancos novos. O serviço de mensagens desacopla a análise da origem; futuros adaptadores podem reutilizá-lo sem vincular o projeto a uma biblioteca de WhatsApp. `source=simulator` ou `demo` identifica a origem atual. O contrato `NotificationSink` reserva a entrada para futuros canais; nesta etapa os alertas ficam no histórico local, sem envio externo.

## Dados e acesso

O banco inicial fica em `data/guardiao.sqlite3`. A chave de sessão é gerada em `data/session.key` quando `SESSION_SECRET` está vazio. A senha usa hash com salt aleatório; nenhuma credencial foi incluída no código. `.env`, banco e chave estão ignorados pelo Git. Para backups coerentes, pare o servidor antes de copiar a pasta `data`; SQLite usa WAL. Cópias de backup são independentes da retenção e da exclusão pelo painel.

Existe uma única conta administrativa nesta etapa. Recuperação de senha e múltiplos administradores ainda não estão implementados. Mantenha o acesso local. A retenção remove registros logicamente do SQLite; não promete eliminação forense dos bytes nem de backups. Todas as mensagens desta etapa são simuladas; a importação de conversas reais exige definir consentimento, acesso e política de armazenamento na próxima etapa.

## Docker preparado, sem deploy

`Dockerfile` e `compose.yaml` estão disponíveis para avaliação posterior. O container usa usuário sem privilégios, volume persistente e porta vinculada ao localhost do host. A imagem foi construída e a configuração do Compose foi validada localmente. Um teste descartável valida a inicialização HTTP, o cadastro inicial e o SQLite. Nenhum deploy foi realizado.

Para repetir a validação local da imagem, com Docker Desktop ativo:

```powershell
docker compose config --quiet
docker build -t guardiao-ia:local .
$smokeFile = (Resolve-Path .\tests\smoke_container.py).Path
docker run --rm --mount "type=bind,source=$smokeFile,target=/tmp/check.py,readonly" guardiao-ia:local python /tmp/check.py
```

Antes da VPS, configure um segredo forte, HTTPS, `COOKIE_SECURE=true`, o hostname em `ALLOWED_HOSTS`, desative a demonstração e cadastre o administrador em ambiente privado. O uso da mesma VPS de outro projeto exige rever portas, proxy reverso, volumes e recursos. Docker Compose fornece somente a aplicação; não configura Hostinger nem proxy.

## Próxima etapa

Não implementados: conexão experimental com WhatsApp, validação de suporte a Comunidades, monitoramento 24h, Telegram, processamento de imagem/vídeo, importação de exportações, relatórios Markdown/JSONL, identificação de dúvidas frequentes, agendamentos, respostas por menção/comandos, IA opcional e hospedagem. A integração e as capacidades de bibliotecas oficiais ou não oficiais serão avaliadas separadamente. Nenhuma ação real de exclusão, advertência ou remoção está disponível.

Referências de implementação: [documentação oficial do FastAPI](https://fastapi.tiangolo.com/) e [middleware de sessões do Starlette](https://starlette.dev/middleware/#sessionmiddleware).
