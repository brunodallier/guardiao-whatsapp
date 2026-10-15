# Etapa 02 — Histórico e Inteligência da Comunidade

Esta etapa roda no mesmo FastAPI e SQLite da Etapa 01. A inicialização cria tabelas adicionais sem remover ou renomear cadastros, usuários, afiliados, regras ou mensagens do simulador. Os módulos anteriores e sua identidade visual permanecem disponíveis. Não é necessário instalar dependências novas.

## Usar o histórico

1. Abra `http://127.0.0.1:8000` e faça login com sua conta.
2. Entre em **Histórico de conversas**. Escolha conscientemente a retenção desejada antes de importar dados antigos.
3. Clique em **Importar TXT**, escolha o grupo já cadastrado e selecione a exportação sem mídias.
4. Confira o formato das datas: dia/mês/ano por padrão; mês/dia/ano quando necessário. O fuso padrão é UTC−03, informado como −180 minutos. Ajuste para outros fusos ou arquivos históricos de horário de verão.
5. Gere a prévia. Confira datas, acentos, pseudônimos, conteúdo minimizado, duplicações, erros e mensagens fora da retenção. A amostra mostra até 20 mensagens novas; os contadores consideram o arquivo completo.
6. Marque a confirmação e importe. Sem essa confirmação, nenhuma mensagem é gravada. Cancelar descarta a prévia.

O TXT original não é salvo, nem mesmo em arquivo temporário de upload. O corpo é lido com limite em memória; a prévia minimizada expira em dez minutos, vinculada à sessão. Uma manutenção a cada cinco segundos remove as prévias vencidas da RAM mesmo sem novas requisições (portanto a limpeza pode ocorrer até cinco segundos após a expiração). Reiniciar o servidor invalida as prévias; selecione o arquivo novamente. Há limite de duas prévias por sessão e cinco no processo. Use um processo de aplicação nesta etapa: múltiplos workers exigiriam armazenamento coordenado de prévias.

Os limites são **10 MiB e 25.000 mensagens por arquivo**, com até 10.000 caracteres por mensagem. Aceita UTF-8 com ou sem BOM, UTF-16 com BOM e Windows-1252 (com aviso). Não abre ZIP, imagens ou vídeos, não acessa links e não segue redirecionamentos.

## Formatos de exportação

Exemplos fictícios reconhecidos:

```text
14/10/2026, 09:01 - Pessoa Fictícia A: Como faço para sacar na HUB?
Esta é uma continuação da mensagem.
[14/10/2026, 09:02:03] Pessoa Fictícia B: Como funciona o saque da HUB?
10/14/26, 2:05 PM - Pessoa Fictícia C: Pergunta em exportação mês/dia/ano.
```

Há arquivos fictícios em `tests/fixtures`. Também são tratados cabeçalhos com ano de dois dígitos, segundos opcionais, horários AM/PM e marcadores direcionais comuns das exportações. Mensagens de sistema e indicadores de mídia omitida recebem tipos próprios. Conteúdo de sistema é substituído por um marcador de privacidade; mídia omitida não permite inferir o conteúdo original, a identidade da imagem ou se imagens são iguais. Legendas com texto podem ser analisadas.

Datas inválidas, cabeçalhos incompatíveis e mensagens grandes geram diagnósticos por número de linha, sem incluir texto ou autor no erro. Linhas fora de uma mensagem são contadas como ignoradas. Um cabeçalho de data inválida interrompe a mensagem anterior, sem anexar conteúdo inválido a ela. Se um texto multilinha imitar exatamente um cabeçalho válido, poderá ser interpretado como nova mensagem: o TXT não possui IDs estruturados que permitam resolver todos os casos.

O formato de datas é explícito porque `03/04` pode significar março ou abril. Não se tenta adivinhar silenciosamente o calendário ou o horário de verão. Arquivos com formatos misturados devem ser separados ou ajustados localmente. Datas mais de cinco minutos à frente do relógio do servidor são ignoradas e contadas separadamente.

## Privacidade e arquivos

- Autores recebem pseudônimos estáveis, como `Pessoa-a1b2c3d4e5f6`, por HMAC com chave local. Não existe tabela de correspondência de nomes ou telefones originais.
- A chave fica em `data/privacy.key` (ao lado do banco configurado), independente da chave de sessão. Não é enviada ao GitHub. Preserve-a em um backup protegido: perdê-la altera a identificação e a deduplicação em futuras importações.
- Conteúdo reconhecível como e-mail, telefone, CPF e parâmetros de autenticação de URLs é ocultado. Menções a autores conhecidos no próprio arquivo também são substituídas. Conteúdo de sistema e nomes de anexos reconhecidos não são preservados.
- A deduplicação usa HMAC sobre grupo, instante, identidade normalizada do autor, tipo e texto original. O original não é guardado. Reimportar arquivos sobrepostos não duplica as mensagens já presentes. Dois envios realmente idênticos do mesmo autor, no mesmo instante e grupo, podem ser indistinguíveis no TXT; mensagens com precisão de minuto e de segundo podem não corresponder se os instantes diferirem.
- Não se guardam o nome do TXT nem o arquivo original. O registro da importação guarda somente contadores, diagnósticos de linha, opções de datas/fuso e uma impressão HMAC do arquivo.
- Acesso e exportação exigem autenticação. Importação, correções, retenção e exclusão também exigem CSRF. Consultas do módulo e tokens de prévia são retirados dos logs de acesso do Uvicorn. Não habilite logs de corpo das requisições no proxy ou em ferramentas externas.

**Pseudonimização não é anonimização completa.** Endereços, nomes não reconhecidos, detalhes sensíveis em texto livre ou dados inseridos manualmente em títulos podem permanecer. Revise a prévia e remova trechos privados do TXT local antes de importar quando necessário. Não inclua nomes ou informações pessoais nos títulos de agrupamentos. O aplicativo não envia conversas para serviços externos e não criptografa o SQLite em repouso: restrinja permissões da pasta de dados e use a proteção de disco/backup apropriada ao computador.

## Retenção e exclusão

A retenção inicial das conversas é **sete dias**, em configuração separada. A regra atual de sete dias do simulador não é alterada. É possível escolher de 1 a 365 dias e salvar explicitamente. Aumentar o prazo não recupera dados excluídos. Reduzir exige confirmação e exclui os registros vencidos imediatamente.

O prazo das mensagens usa a data da conversa, não o momento do upload; mensagens anteriores são ignoradas na prévia e conferidas novamente na confirmação. Os logs agregados de importação seguem o mesmo prazo em dias, contado da operação. A limpeza roda na inicialização, a cada hora e nos acessos ao módulo. Agrupamentos sem mensagens são removidos. Mudar retenção, regras ou afiliados invalida a confirmação de uma prévia antiga, exigindo uma nova conferência.

Pode excluir uma mensagem, um grupo/período ou todo o módulo com a palavra **EXCLUIR**. Sem datas, a exclusão completa também remove os logs de importação do escopo. Exclusão por período preserva esses logs agregados. Cadastros e ocorrências do simulador permanecem intactos. Exclusão não apaga backups nem garante remoção forense de bytes do SQLite/WAL.

## Inteligência local e revisão humana

**Inteligência da comunidade** usa somente as conversas importadas. Inclui indicadores, atividade por grupo, horário e dia da semana, plataformas mencionadas, reclamações por plataforma, assuntos, dúvidas, possíveis pendências, regras de spam e sugestões para suporte. Filtre por grupo e últimos 7, 15 ou 30 dias, ou informe datas explícitas. Os períodos usam dias de calendário em Brasília, incluindo o dia final. Datas explícitas têm prioridade. Sem dados suficientes, o período é apresentado com sua disponibilidade real.

O PLN é local e transparente: normalização de caixa/acentos, remoção de palavras comuns, vocabulário de plataformas e tópicos, sinônimos e similaridade de Jaccard (limiar 0,65) para textos sem um tópico conhecido. “Sacar”, “saque” e “retirar dinheiro” na HUB são agrupados como **Saque na HUB**. Não há download de modelos ou promessa de compreensão semântica perfeita. Textos fora do vocabulário podem aparecer como **Outros assuntos**. A lista de plataformas inclui HUB, Mimix, Crowtado, Kgen, Flambra e as plataformas cadastradas nos afiliados.

Nos cards, **Revisar assunto** permite renomear, marcar como revisado e mesclar agrupamentos. A alteração global afeta todos os grupos. Nos detalhes de uma mensagem, pode movê-la para outro assunto, criar um assunto ou restaurar a sugestão automática. Correções manuais são preservadas na reimportação.

Uma possível pergunta sem resposta é uma heurística: procura outra pessoa respondendo ao mesmo assunto, com termos de resposta, nas seis horas seguintes e dentro do conjunto filtrado. Não há dados estruturados de resposta/citação no TXT. Uma resposta fora do período selecionado, implícita ou sem os termos esperados pode não ser reconhecida. Marque manualmente **Resposta confirmada por mim** ou **Manter como pendente** nos detalhes. As listas mostram os agrupamentos mais frequentes e até 50 exemplos de pendências; não garantem cobertura semântica integral.

Textos suspeitos/críticos aparecem nos indicadores de spam, mas são excluídos das dúvidas, reclamações agrupadas e sugestões de suporte para reduzir contaminação por propaganda. Mídias sem legenda não geram assunto automático. Indicadores de atividade incluem eventos de sistema; “analisadas” conta mensagens de participantes, incluindo a avaliação das regras de frequência em eventos de mídia. Não há OCR ou análise visual.

## Antispam histórico

O classificador é o mesmo `app/moderation/engine.py` da Etapa 01. Links são classificados enquanto o conteúdo original está em memória, antes da minimização, para evitar confundir um código próprio numérico ocultado com indicação de terceiros. Somente achados minimizados são persistidos, sem lista de URLs no resultado.

Na confirmação, as regras temporais são calculadas por grupo e pseudônimo em ordem cronológica, incluindo mensagens anteriores já importadas. Reimportações fora de ordem recalculam as janelas do grupo. Tokens HMAC permitem comparar textos repetidos sem preservar os originais. Marcadores de mídia sem conteúdo não são considerados prova de mídias idênticas.

Os achados de URL preservam a análise feita na importação, já que o original é descartado. Janelas de repetição/frequência são recalculadas com as regras atuais em novas importações do grupo. Não se chama o serviço de notificações da Etapa 01. Não há alertas emergenciais nem ações de punição; ocorrências importadas não entram nos indicadores do simulador.

## Relatórios

Baixe **Markdown, JSONL ou CSV** no painel de inteligência, usando o grupo e o período selecionados. Incluem totais, frequência de assuntos, dúvidas, reclamações, spam, atividade, limitações e sugestões para tutoriais, mensagens fixadas e respostas futuras do bot. As sugestões são modelos locais derivados dos assuntos; não são respostas geradas por IA.

Os arquivos priorizam agregados: não incluem mensagens individuais, autores/pseudônimos, IDs de mensagens ou links originais. Títulos e nomes de grupos têm dados reconhecíveis minimizados. CSV neutraliza células iniciadas por marcadores de fórmula para reduzir risco ao abrir em planilhas. Relatórios são gerados sob demanda e não são salvos no servidor. Escolher 30 dias com retenção de sete não modifica a retenção nem inventa dados ausentes.

## Testes e arquitetura

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check app/static/app.js
node --check app/static/community.js
```

Os testes antigos continuam ativos. Os novos cobrem formatos, múltiplas linhas, datas/fusos, codificação, erros sem conteúdo privado, limites de upload, deduplicação/concorrência, pseudônimos, minimização, retenção, invalidação de prévias, agrupamentos, revisão humana, antispam sem notificações, relatórios agregados e CSV seguro. Usam bancos temporários e dados fictícios. Fixtures em `tests/fixtures` têm datas fixas para testar o parser; para uma demonstração em outra data, ajuste uma cópia local conforme a retenção.

O módulo está em `app/community`: parser, privacidade, migração aditiva, importador, PLN, agregações, relatórios e rotas. O frontend adicional está em `app/static/community.js` e `community.css`. Não foram adicionadas bibliotecas de IA, serviços de nuvem ou ferramentas de build ao runtime.

Antes de atualizar seu banco local, faça backup separado e protegido do SQLite e das chaves, preferencialmente com o servidor parado (ou usando a API de backup consistente do SQLite). Não envie esses arquivos ao GitHub. Para uma verificação em Docker, use a imagem local de teste e o script `tests/smoke_container.py`; nenhum deploy é necessário.

O desenvolvimento ocorre em `feat/historico-conversas`. A integração na `main` depende de Pull Request, testes e aprovação manual do usuário.
