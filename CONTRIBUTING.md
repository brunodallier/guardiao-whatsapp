# Desenvolvimento com branches e Pull Requests

`main` é a base estável. A Etapa 01 é publicada como o commit inicial; qualquer trabalho posterior acontece em uma branch própria. A branch `feat/historico-conversas` parte desse marco e aguarda autorização para começar a Etapa 02.

## Preparar uma cópia local

```powershell
git clone https://github.com/brunodallier/guardiao-whatsapp.git
Set-Location guardiao-whatsapp
git config --local core.hooksPath .githooks
git config --local pull.ff only
git config --local push.default simple
```

Hooks e configurações locais não são ativados automaticamente por `git clone`. Nesta pasta original, já foram configurados. Os hooks bloqueiam commits na `main` após o primeiro commit, atualizações diretas da `main` remota, exclusão de refs pelo push e alterações sem avanço de histórico. Se faltarem objetos remotos para a comparação, faça `git fetch origin` e confira a divergência.

Os hooks são uma proteção local e não substituem regras de proteção no GitHub. Outros clones e alterações pela interface web precisam seguir esta mesma política. Não usar `--no-verify` nem desligar os hooks para contornar uma rejeição. Uma rejeição exige revisar o estado do Git e escolher um fluxo que preserve o histórico.

No GitHub, a `main` está protegida: exige Pull Request e a verificação `tests` aprovada com a branch atualizada. A proteção inclui administradores e bloqueia force push e exclusão. Auto-merge está desabilitado. A revisão e o merge são manuais pelo proprietário; não é exigida a aprovação de outro colaborador, para permitir o fluxo de um único administrador. O agente não pode aprovar nem integrar PRs por conta própria.

## Começar uma funcionalidade autorizada

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c feat/nome-da-funcionalidade
```

Quando a Etapa 02 for autorizada, use a branch já criada:

```powershell
git switch feat/historico-conversas
```

## Antes de cada Pull Request

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
git diff --cached
git ls-files
```

Revisar os arquivos incluídos, a presença de dados pessoais e quaisquer valores de autenticação. `.env.example` contém somente configuração de exemplo e nenhuma credencial. Senhas fictícias em testes não podem ser reutilizadas como credenciais reais. Dados reais devem ficar fora do repositório, mesmo privado. Não usar `git add -f` para incluir arquivos ignorados.

```powershell
git add <arquivos-de-codigo-revisados>
git commit -m "feat: descreve a funcionalidade"
git push -u origin feat/nome-da-funcionalidade
```

Abra um Pull Request com destino à `main` pelo GitHub, descreva a mudança e os resultados dos testes, e aguarde a revisão e aprovação do usuário. Não fazer merge automático nem ativar auto-merge. O template de PR registra os itens de revisão; o workflow executa novamente os testes em cada Pull Request. Nenhum workflow faz deploy ou merge.

## Conflitos e histórico

Não usar force push, reset destrutivo, rebase de histórico publicado ou exclusão de arquivos/dados para eliminar conflitos sem autorização. Se o remoto tiver divergências, preservar ambos os históricos e informar o usuário. A preferência `pull.ff=only` impede merges locais inesperados durante o pull.

## Backups

O Git não contém o banco SQLite nem a chave de sessão. Faça backup separado da pasta de dados com o servidor parado, armazene-o com acesso restrito e siga a política de retenção da comunidade. Nunca envie esse backup ao GitHub. `.gitignore` é uma primeira barreira, não substitui a revisão de conteúdo.
