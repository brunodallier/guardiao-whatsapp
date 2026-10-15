"use strict";
window.Community = (() => {
  let previewToken = null,
    pageNumber = 1,
    historyFilters = {},
    intelligenceFilters = { days: "7" },
    lastPeriod = null;
  const fullDate = (value) =>
    new Date(value * 1000).toLocaleString("pt-BR", {
      timeZone: "America/Sao_Paulo",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  const kinds = { text: "Texto", media: "Mídia omitida", system: "Sistema" };
  const query = (values) =>
    new URLSearchParams(
      Object.entries(values).filter(
        ([, v]) => v !== "" && v !== undefined && v !== null,
      ),
    );
  const metrics = (values) =>
    `<div class="community-metrics">${values.map(([label, value, foot]) => `<div class="metric"><div class="metric-label">${esc(label)}</div><div class="metric-value">${Number(value).toLocaleString("pt-BR")}</div><div class="metric-foot">${esc(foot || "")}</div></div>`).join("")}</div>`;
  function filters(values, id, analysis = false) {
    return `<form id="${id}" class="filters"><label>Grupo<select name="group_id"><option value="">Todos os grupos</option>${selectGroups(values.group_id)}</select></label>${analysis ? `<label>Período<select name="days">${[7, 15, 30].map((n) => `<option value="${n}" ${String(values.days) === String(n) ? "selected" : ""}>Últimos ${n} dias</option>`).join("")}</select></label>` : ""}<label>De<input type="date" name="since" value="${esc(values.since || "")}"></label><label>Até<input type="date" name="until" value="${esc(values.until || "")}"></label>${
      !analysis
        ? `<label class="search">Conteúdo<input name="q" value="${esc(values.q || "")}" placeholder="Buscar no texto minimizado"></label><label>Classificação<select name="status"><option value="">Todas</option>${Object.entries(
            names,
          )
            .map(
              ([key, label]) =>
                `<option value="${key}" ${values.status === key ? "selected" : ""}>${label}</option>`,
            )
            .join(
              "",
            )}</select></label><label>Tipo<select name="kind"><option value="">Todos</option>${Object.entries(
            kinds,
          )
            .map(
              ([key, label]) =>
                `<option value="${key}" ${values.kind === key ? "selected" : ""}>${label}</option>`,
            )
            .join("")}</select></label>`
        : ""
    }<button class="button" type="submit">Aplicar filtros</button><button class="button subtle" type="button" data-community="clear" data-mode="${analysis ? "analysis" : "history"}">Limpar</button></form>`;
  }
  async function historyPage() {
    const policy = await api("/conversations/policy");
    return (
      pageHead(
        "MEMÓRIA COM PRIVACIDADE",
        "Histórico de conversas",
        "Importe, encontre e entenda as conversas da sua comunidade.",
        `<button class="button primary" data-community="import">${icon("plus")}Importar TXT</button>`,
      ) +
      `<div class="notice">Processamento local. Autores recebem pseudônimos estáveis; telefones, e-mails e menções aos autores reconhecidos são minimizados. O original não é salvo. Confira a prévia: texto livre ainda pode conter informações pessoais.</div>` +
      `<section class="panel retention-panel"><div><h2>Retenção das conversas</h2><p class="small muted">Atualmente: <strong id="retention-current">${policy.retention_days} dias</strong>. Este controle é separado do histórico do simulador, que mantém sua configuração.</p></div><form id="conversation-policy"><label>Dias de retenção<input type="number" name="retention_days" min="1" max="365" value="${policy.retention_days}" required></label><label class="check-label small"><input type="checkbox" name="confirm_deletion">Confirmo a exclusão de dados vencidos se reduzir o prazo.</label><button type="submit" class="button">Salvar retenção</button><p class="error" role="alert"></p></form></section>` +
      `<section class="panel community-history"><div class="panel-head"><div><h2>Mensagens importadas</h2><p>Datas e filtros em horário de Brasília (UTC−03).</p></div><a class="link-button" href="#inteligencia">Ver inteligência ↗</a></div>${historyFilters.topic_key ? '<div class="notice">Assunto selecionado na análise. Use “Limpar” para ver outros assuntos.</div>' : ""}${filters(historyFilters, "conversation-filters")}<div id="conversation-results" aria-live="polite">Carregando…</div></section><section class="panel import-log"><div class="panel-head"><div><h2>Registro das importações</h2><p>Resultados agregados, sem nome do arquivo original. Até 50 operações recentes.</p></div></div><div id="import-results">Carregando…</div></section><div class="danger-zone"><div><h3>Excluir conversas</h3><p>Remova registros por grupo e período. Os cadastros e o simulador são preservados.</p></div><button class="button danger" data-community="delete-period">Excluir registros</button></div>`
    );
  }
  async function loadMessages() {
    const data = await api(
      "/conversations/messages?" +
        query({ ...historyFilters, page: pageNumber }),
    );
    if (currentPage !== "conversas" || !$("#conversation-results")) return;
    const pages = Math.max(1, Math.ceil(data.total / data.page_size));
    $("#conversation-results").innerHTML = data.items.length
      ? `<div class="table-wrap"><table><thead><tr><th>Data / autor</th><th>Mensagem</th><th>Grupo / assunto</th><th>Análise</th><th></th></tr></thead><tbody>${data.items.map((row) => `<tr><td><strong>${esc(fullDate(row.timestamp))}</strong><small>${esc(row.participant)} · ${kinds[row.kind]}</small></td><td><span class="conversation-excerpt">${esc(row.content)}</span></td><td>${esc(row.group_name)}<small>${esc(row.topic_label || "Sem assunto")}</small></td><td>${row.kind === "system" ? badge("neutral", "Sistema") : badge(row.status)}</td><td><button class="link-button" data-community="message" data-id="${row.id}">Detalhes ↗</button></td></tr>`).join("")}</tbody></table></div><div class="pagination"><span>${data.total} registros</span><div><button class="button" data-community="previous" ${pageNumber <= 1 ? "disabled" : ""}>←</button><span>${pageNumber} de ${pages}</span><button class="button" data-community="next" ${pageNumber >= pages ? "disabled" : ""}>→</button></div></div>`
      : empty(
          "As conversas começam aqui.",
          "Importe um TXT ou ajuste os filtros.",
          `<button class="button" data-community="import">Importar uma conversa</button>`,
        );
  }
  async function loadImports() {
    const rows = await api(
      "/conversations/imports?" + query({ group_id: historyFilters.group_id }),
    );
    if (!$("#import-results")) return;
    $("#import-results").innerHTML = rows.length
      ? `<div class="table-wrap"><table><thead><tr><th>Importação</th><th>Grupo</th><th>Salvas</th><th>Duplicadas</th><th>Fora da retenção</th><th>Erros</th><th></th></tr></thead><tbody>${rows.map((row) => `<tr><td>#${row.id}<small>${esc(fullDate(row.created_at))}</small></td><td>${esc(row.group_name)}</td><td>${row.result.inserted}</td><td>${row.result.duplicates + row.result.duplicates_at_confirmation}</td><td>${row.result.expired + row.result.expired_at_confirmation}</td><td>${row.result.errors}</td><td><button class="link-button" data-community="import-log" data-id="${row.id}">Detalhes ↗</button></td></tr>`).join("")}</tbody></table></div>`
      : empty(
          "Nenhuma importação por enquanto.",
          "Cada confirmação registra mensagens aceitas, ignoradas e erros.",
        );
  }
  function counters(s) {
    return (
      metrics([
        ["Prontas / salvas", s.inserted ?? s.ready, "Mensagens únicas"],
        [
          "Duplicadas",
          (s.duplicates || 0) + (s.duplicates_at_confirmation || 0),
          "Ignoradas",
        ],
        [
          "Fora do prazo",
          (s.expired || 0) + (s.expired_at_confirmation || 0),
          "Retenção atual",
        ],
        ["Erros", s.errors || 0, "Leitura do TXT"],
      ]) +
      `<p class="small muted">${s.total} mensagens reconhecidas · ${s.system || 0} de sistema · ${s.media || 0} com mídia omitida · ${s.future || 0} datas futuras ignoradas · ${s.ignored_lines || 0} linhas fora de mensagens ignoradas.</p>`
    );
  }
  function diagnostics(errors = [], warnings = []) {
    return (
      warnings
        .map((w) => `<div class="notice warning">${esc(w)}</div>`)
        .join("") +
      (errors.length
        ? `<details class="community-diagnostics"><summary>Ver erros de leitura (até 100)</summary><ul>${errors.map((e) => `<li>Linha ${e.line}: ${esc(e.reason)}</li>`).join("")}</ul></details>`
        : "")
    );
  }
  function importDialog() {
    if (!groups.length) {
      toast("Cadastre um grupo antes de importar.");
      return;
    }
    openDialog(
      "Importar conversa",
      `<form id="conversation-upload"><div class="notice">TXT exportado pelo WhatsApp, sem mídias. Até 10 MiB e 25.000 mensagens. Nenhum conteúdo será enviado a serviços externos.</div><div class="form-grid"><label class="full">Grupo da conversa<select name="group_id" required>${selectGroups()}</select></label><label>Formato de datas<select name="date_order"><option value="dmy">Dia / mês / ano (Brasil)</option><option value="mdy">Mês / dia / ano</option></select></label><label>Fuso do arquivo (minutos de UTC)<input name="utc_offset" type="number" min="-720" max="840" value="-180" required><small>Brasília atual: −180. Ajuste para outros fusos ou horário de verão histórico.</small></label><label class="full community-file">Arquivo TXT<input name="file" type="file" accept=".txt,text/plain" required><small>O original é processado em memória e descartado. Revise a prévia antes de salvar.</small></label></div><p class="error" role="alert"></p><div class="panel-actions"><button type="button" class="button" data-action="close">Cancelar</button><button type="submit" class="button primary">Gerar prévia</button></div></form>`,
    );
    $("#conversation-upload").addEventListener("submit", (event) => {
      event.preventDefault();
      submit(event.target, async () => {
        const form = event.target,
          file = $("[name=file]", form).files[0];
        if (!file || !file.name.toLowerCase().endsWith(".txt"))
          throw new Error("Selecione um arquivo .txt.");
        if (file.size > 10 * 1024 * 1024)
          throw new Error("O arquivo deve ter no máximo 10 MiB.");
        const v = Object.fromEntries(new FormData(form));
        const p = await api(
          "/conversations/preview?" +
            query({
              group_id: v.group_id,
              date_order: v.date_order,
              utc_offset: v.utc_offset,
            }),
          {
            method: "POST",
            headers: { "Content-Type": "text/plain" },
            body: file,
          },
        );
        previewToken = p.token;
        showPreview(p);
      });
    });
  }
  function showPreview(p) {
    openDialog(
      "Prévia da importação",
      `<p class="small muted">Confira autores, datas e conteúdo minimizado. A prévia expira em dez minutos.</p>${counters(p.summary)}<div class="notice">Retenção: ${p.retention_days} dias. Mensagens anteriores ao prazo não serão importadas. Para incluir um período maior, cancele e salve explicitamente outra retenção no histórico.</div>${diagnostics(p.errors, p.warnings)}<p class="small muted">Intervalo reconhecido: ${esc(fullDate(p.range.from))} a ${esc(fullDate(p.range.to))}. Codificação: ${esc(p.encoding)}.</p><div class="preview-messages">${p.samples.map((row) => `<article><strong>${esc(row.participant)}</strong><small>${esc(fullDate(row.timestamp))} · ${kinds[row.kind]}</small><p>${esc(row.content)}</p></article>`).join("") || '<p class="muted">Sem mensagens novas dentro da retenção. A confirmação registrará o resultado da tentativa.</p>'}</div><form id="confirm-conversation-import"><label class="check-label"><input type="checkbox" name="confirmed" required>Revisei a prévia e autorizo salvar os registros minimizados.</label><p class="error" role="alert"></p><div class="panel-actions"><button type="button" class="button" data-action="close">Cancelar</button><button type="submit" class="button primary">Confirmar importação</button></div></form>`,
    );
    $("#confirm-conversation-import").addEventListener("submit", (event) => {
      event.preventDefault();
      submit(event.target, async () => {
        const result = await api("/conversations/import", {
          method: "POST",
          body: JSON.stringify({ token: previewToken, confirmed: true }),
        });
        previewToken = null;
        openDialog(
          "Importação concluída",
          `${counters(result)}${diagnostics(result.errors_detail, result.warnings)}<div class="notice">Análise histórica concluída. Nenhuma notificação de emergência ou punição foi executada.</div><div class="panel-actions"><button class="button" data-action="close">Fechar</button><a class="button primary" href="#inteligencia" data-community="open-intelligence">Ver inteligência ↗</a></div>`,
        );
        await Promise.all([loadMessages(), loadImports()]);
        toast(`${result.inserted} mensagens importadas.`);
      });
    });
  }
  async function messageDialog(id) {
    const [row, topics] = await Promise.all([
      api("/conversations/messages/" + id),
      api("/conversations/topics"),
    ]);
    openDialog(
      "Detalhes da conversa",
      `<p class="small muted">${esc(row.group_name)} · ${esc(fullDate(row.timestamp))}<br>${esc(row.participant)} · ${kinds[row.kind]}</p>${badge(row.status)}<div class="message-block">${esc(row.content)}</div>${(row.analysis.findings || []).map((f) => `<div class="finding"><strong>${esc(f.label)}</strong><p>${esc(f.reason)}</p></div>`).join("")}<p class="hint">Registro histórico, sem alertas emergenciais ou punições.</p>${
        row.kind !== "system"
          ? `<form id="conversation-correction"><h3>Revisar a interpretação</h3><label>Agrupamento<select name="topic_key">${topics.map((t) => `<option value="${esc(t.key)}" ${t.key === row.topic_key ? "selected" : ""}>${esc(t.label)}</option>`).join("")}</select></label><label>Ou criar um assunto<input name="new_topic_label" minlength="3" maxlength="100" placeholder="Ex.: Saques pendentes na HUB"><small>Evite dados pessoais no título.</small></label><label class="check-label"><input type="checkbox" name="reset_topic">Restaurar o assunto automático</label>${
              row.question
                ? `<label>Situação da pergunta<select name="answer_state">${[
                    ["auto", "Avaliação automática"],
                    ["answered", "Resposta confirmada por mim"],
                    ["unanswered", "Manter como pendente"],
                  ]
                    .map(
                      ([key, label]) =>
                        `<option value="${key}" ${row.answer_state === key ? "selected" : ""}>${label}</option>`,
                    )
                    .join("")}</select></label>`
                : ""
            }<p class="error" role="alert"></p><div class="panel-actions"><button type="submit" class="button primary">Salvar revisão</button></div></form>`
          : ""
      }<div class="panel-actions"><button class="button danger" data-community="delete-one" data-id="${row.id}">Excluir registro</button><button class="button" data-action="close">Fechar</button></div>`,
    );
    if ($("#conversation-correction"))
      $("#conversation-correction").addEventListener("submit", (event) => {
        event.preventDefault();
        submit(event.target, async () => {
          const form = event.target,
            v = Object.fromEntries(new FormData(form)),
            payload = {};
          if ($("[name=reset_topic]", form).checked) payload.reset_topic = true;
          else if (v.new_topic_label.trim())
            payload.new_topic_label = v.new_topic_label.trim();
          else if (v.topic_key !== row.topic_key)
            payload.topic_key = v.topic_key;
          if (v.answer_state) payload.answer_state = v.answer_state;
          await api(`/conversations/messages/${row.id}/correction`, {
            method: "PUT",
            body: JSON.stringify(payload),
          });
          $("#dialog").close();
          toast("Interpretação revisada.");
          await refresh();
        });
      });
  }
  function deletionDialog(id = null) {
    openDialog(
      id ? "Excluir esta mensagem?" : "Excluir histórico de conversas",
      `<form id="delete-conversations"><div class="notice warning">Exclusão permanente dos registros selecionados. Não remove cópias de backup fora do aplicativo.</div>${id ? "" : `<div class="form-grid"><label class="full">Grupo<select name="group_id"><option value="">Todos os grupos</option>${selectGroups(historyFilters.group_id)}</select></label><label>De<input type="date" name="since" value="${esc(historyFilters.since || "")}"></label><label>Até<input type="date" name="until" value="${esc(historyFilters.until || "")}"></label></div><p class="hint">Sem datas: exclui todo o histórico do grupo, incluindo logs de importação. A busca por conteúdo não limita a exclusão.</p>`}<label>Digite EXCLUIR para confirmar<input name="confirmation" required pattern="EXCLUIR" autocomplete="off"></label><p class="error" role="alert"></p><div class="panel-actions"><button type="button" class="button" data-action="close">Cancelar</button><button type="submit" class="button danger">Excluir definitivamente</button></div></form>`,
    );
    $("#delete-conversations").addEventListener("submit", (event) => {
      event.preventDefault();
      submit(event.target, async () => {
        const v = Object.fromEntries(new FormData(event.target)),
          payload = { confirmation: v.confirmation };
        if (v.group_id) payload.group_id = Number(v.group_id);
        if (v.since) payload.since = v.since;
        if (v.until) payload.until = v.until;
        const result = await api(
          "/conversations/messages" + (id ? "/" + id : ""),
          { method: "DELETE", body: JSON.stringify(payload) },
        );
        $("#dialog").close();
        toast(`${result.deleted} registros excluídos.`);
        await refresh();
      });
    });
  }
  async function intelligencePage() {
    return (
      pageHead(
        "DAS CONVERSAS AO CUIDADO",
        "Inteligência da comunidade",
        "Padrões locais para orientar o suporte. O contexto continua com você.",
        `<a class="button" href="#conversas">${icon("conversas")}Histórico de conversas</a>`,
      ) +
      `<div class="notice">Vocabulário, sinônimos e similaridade de termos locais. Os agrupamentos e possíveis perguntas sem resposta são hipóteses revisáveis, sem promessa de identificação semântica perfeita.</div><section class="panel intelligence-filters">${filters(intelligenceFilters, "intelligence-filters", true)}<p class="hint">Datas preenchidas definem um intervalo personalizado e têm prioridade sobre “últimos dias”.</p></section><div id="intelligence-results" aria-live="polite">Carregando análise…</div>`
    );
  }
  function ranking(title, description, items, review = false) {
    const max = Math.max(1, ...items.map((i) => i.count));
    return `<section class="panel"><div class="panel-head"><div><h2>${title}</h2><p>${description}</p></div></div>${
      items.length
        ? items
            .slice(0, 8)
            .map(
              (item) =>
                `<div class="community-ranking"><div><strong>${esc(item.label)}</strong><span>${item.count}</span></div><meter min="0" max="${max}" value="${item.count}" aria-label="${esc(item.label)}: ${item.count}"></meter>${item.unanswered ? `<small>${item.unanswered} possivelmente sem resposta</small>` : ""}${review && item.key ? `<div class="community-row-actions"><button class="link-button" data-community="topic-messages" data-key="${esc(item.key)}">Ver mensagens ↗</button><button class="link-button" data-community="topic-review" data-key="${esc(item.key)}">Revisar assunto</button></div>` : ""}</div>`,
            )
            .join("")
        : empty("Ainda sem dados.", "Importe conversas ou ajuste o período.")
    }</section>`;
  }
  async function loadIntelligence() {
    const d = await api("/intelligence?" + query(intelligenceFilters));
    lastPeriod = d.period;
    if (currentPage !== "inteligencia" || !$("#intelligence-results")) return;
    const t = d.totals,
      max = Math.max(1, ...d.hours.map((i) => i.count));
    const chart = `<svg viewBox="0 0 480 135" width="100%" height="135" role="img" aria-label="Atividade por hora em Brasília">${d.hours.map((r, i) => `<g><title>${r.hour}h: ${r.count} mensagens</title><rect x="${i * 20 + 2}" y="${110 - Math.max((r.count / max) * 100, 2)}" height="${Math.max((r.count / max) * 100, 2)}" width="13" rx="3" fill="#a8c18e"/>${i % 4 === 0 ? `<text x="${i * 20 + 2}" y="130" fill="#758078" font-size="10">${r.hour}h</text>` : ""}</g>`).join("")}</svg>`;
    $("#intelligence-results").innerHTML =
      metrics([
        [
          "Mensagens analisadas",
          t.analyzed,
          `${t.system} registros de sistema à parte`,
        ],
        ["Dúvidas", t.questions, "Mensagens permitidas"],
        ["Reclamações", t.complaints, "Indícios por vocabulário"],
        ["Possíveis pendências", t.unanswered, "Revise o contexto"],
        [
          "Sinais de spam",
          t.suspect + t.critical,
          `${t.critical} críticas · apenas histórico`,
        ],
      ]) +
      `<p class="small muted">Retenção: ${d.retention_days} dias. Dados no período: ${d.period.available_from ? esc(fullDate(d.period.available_from)) + " a " + esc(fullDate(d.period.available_to)) : "nenhum"}. ${Number(intelligenceFilters.days || 7) > d.retention_days ? "O período solicitado é maior que a retenção: o relatório usará apenas os dados disponíveis." : ""}</p>` +
      `<div class="columns"><section class="panel"><div class="panel-head"><div><h2>O ritmo da comunidade</h2><p>Atividade por hora · UTC−03</p></div></div>${chart}<div class="community-weekdays">${d.weekdays.map((r) => `<div><span>${r.label}</span><strong>${r.count}</strong></div>`).join("")}</div></section><section class="panel"><div class="panel-head"><div><h2>Atividade por grupo</h2><p>Texto, mídia e sistema</p></div></div>${d.activity.map((g) => `<div class="group-row"><div class="group-copy"><strong>${esc(g.name)}</strong><small>${g.total} mensagens · ${g.spam} suspeitas ou críticas</small></div>${badge("neutral", g.total + " registros")}</div>`).join("") || empty("Nenhum grupo no período.", "Ajuste os filtros ou importe conversas.")}</section></div>` +
      `<div class="columns">${ranking("Assuntos recorrentes", "Agrupamentos sugeridos, com revisão humana.", d.topics, true)}<section class="panel"><div class="panel-head"><div><h2>Plataformas nas conversas</h2><p>Menções e problemas em mensagens permitidas.</p></div></div>${d.platforms.length ? `<div class="table-wrap"><table><thead><tr><th>Plataforma</th><th>Menções</th><th>Reclamações</th></tr></thead><tbody>${d.platforms.map((r) => `<tr><td>${esc(r.label)}</td><td>${r.count}</td><td>${r.complaints}</td></tr>`).join("")}</tbody></table></div>` : empty("Sem menções identificadas.", "Vocabulário inicial: HUB, Mimix, Crowtado, Kgen, Flambra e plataformas cadastradas.")}</section></div>` +
      `<div class="columns">${ranking("Principais dúvidas", "Perguntas relacionadas ao mesmo assunto.", d.questions, true)}${ranking("Principais reclamações", "Sinais para acompanhar no suporte.", d.complaints, true)}</div>` +
      `<section class="panel community-section"><div class="panel-head"><div><h2>Possíveis perguntas sem resposta</h2><p>Hipótese por assunto e janela de seis horas. Revise o contexto.</p></div></div>${
        d.unanswered.length
          ? d.unanswered
              .slice(0, 50)
              .map(
                (r) =>
                  `<article class="community-question"><div><strong>${esc(r.topic || "Dúvida")}</strong><small>${esc(r.group)} · ${esc(fullDate(r.timestamp))}${r.manual ? " · Revisão humana" : ""}</small><p>${esc(r.content)}</p></div><button class="button subtle" data-community="message" data-id="${r.id}">Revisar ↗</button></article>`,
              )
              .join("")
          : empty(
              "Nenhuma pendência identificada.",
              "Isso não garante que todas as dúvidas tenham uma resposta satisfatória.",
            )
      }</section>` +
      `<div class="columns">${ranking("Ocorrências de spam", "Motor da Etapa 01. Nenhuma notificação.", d.spam)}<section class="panel"><div class="panel-head"><div><h2>Ideias para melhorar o suporte</h2><p>Sugestões derivadas das conversas, sem IA.</p></div></div>${d.suggestions.map((r) => `<div class="finding"><h3>${esc(r.topic)}</h3><p>${esc(r.tutorial)}.</p><p>${esc(r.pinned_message)}.</p><p>${esc(r.future_bot_response)}.</p></div>`).join("") || empty("As ideias aparecem com as conversas.", "Importe dúvidas para gerar sugestões locais.")}</section></div>` +
      `<section class="panel community-section"><div class="panel-head"><div><h2>Relatório da comunidade</h2><p>Agregados e sugestões; sem mensagens individuais ou pseudônimos.</p></div></div><div class="community-export">${[
        ["md", "Markdown"],
        ["jsonl", "JSONL"],
        ["csv", "CSV"],
      ]
        .map(
          ([f, label]) =>
            `<button class="button" data-community="export" data-format="${f}">Baixar ${label} ↗</button>`,
        )
        .join(
          "",
        )}</div><p class="hint">Usa o grupo e o período selecionados, conforme os dados disponíveis. Dados excluídos não são recuperados.</p></section>`;
  }
  async function topicDialog(key) {
    const topics = await api("/conversations/topics"),
      topic = topics.find((t) => t.key === key);
    if (!topic)
      throw new Error("Agrupamento não encontrado. Atualize a análise.");
    openDialog(
      "Revisar agrupamento",
      `<div class="notice">A revisão se aplica a todas as mensagens deste agrupamento, em todos os grupos. Nenhuma mensagem será apagada.</div><form id="review-topic"><label>Nome do assunto<input name="label" value="${esc(topic.label)}" minlength="3" maxlength="100" required></label><label class="check-label"><input name="reviewed" type="checkbox" checked>Marcar agrupamento como revisado</label><p class="error" role="alert"></p><div class="panel-actions"><button class="button primary" type="submit">Salvar assunto</button></div></form>${
        topics.length > 1
          ? `<hr><form id="merge-topics"><h3>Mesclar com outro assunto</h3><label>Assunto de destino<select name="target">${topics
              .filter((t) => t.key !== key)
              .map(
                (t) => `<option value="${esc(t.key)}">${esc(t.label)}</option>`,
              )
              .join(
                "",
              )}</select></label><label class="check-label"><input type="checkbox" required>Confirmo mover todas as mensagens para o destino escolhido.</label><p class="error" role="alert"></p><div class="panel-actions"><button class="button" type="submit">Mesclar agrupamentos</button></div></form>`
          : ""
      }<div class="panel-actions"><button class="button" data-action="close">Fechar</button></div>`,
    );
    $("#review-topic").addEventListener("submit", (event) => {
      event.preventDefault();
      submit(event.target, async () => {
        await api("/conversations/topics/" + key, {
          method: "PUT",
          body: JSON.stringify({
            label: $("[name=label]", event.target).value,
            reviewed: $("[name=reviewed]", event.target).checked,
          }),
        });
        $("#dialog").close();
        toast("Agrupamento revisado.");
        await loadIntelligence();
      });
    });
    if ($("#merge-topics"))
      $("#merge-topics").addEventListener("submit", (event) => {
        event.preventDefault();
        submit(event.target, async () => {
          await api("/conversations/topics/merge", {
            method: "POST",
            body: JSON.stringify({
              source: key,
              target: $("[name=target]", event.target).value,
            }),
          });
          $("#dialog").close();
          toast("Agrupamentos mesclados.");
          await loadIntelligence();
        });
      });
  }
  async function download(format) {
    const response = await fetch(
      "/api/intelligence/report?" + query({ ...intelligenceFilters, format }),
      { credentials: "same-origin" },
    );
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.detail || "Falha ao gerar relatório.");
    }
    const url = URL.createObjectURL(await response.blob()),
      a = document.createElement("a");
    a.href = url;
    a.download = `guardiao-comunidade.${format}`;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    toast("Relatório agregado gerado.");
  }
  async function refresh() {
    if (currentPage === "conversas")
      await Promise.all([loadMessages(), loadImports()]);
    if (currentPage === "inteligencia") await loadIntelligence();
  }
  function wire(page) {
    if (page === "conversas") {
      $("#conversation-filters").addEventListener("submit", (e) => {
        e.preventDefault();
        const key = historyFilters.topic_key;
        historyFilters = Object.fromEntries(new FormData(e.target));
        if (key) historyFilters.topic_key = key;
        pageNumber = 1;
        refresh().catch((err) => toast(err.message));
      });
      $("#conversation-policy").addEventListener("submit", (e) => {
        e.preventDefault();
        submit(e.target, async () => {
          const f = e.target,
            r = await api("/conversations/policy", {
              method: "PUT",
              body: JSON.stringify({
                retention_days: Number($("[name=retention_days]", f).value),
                confirm_deletion: $("[name=confirm_deletion]", f).checked,
              }),
            });
          $("#retention-current").textContent = r.retention_days + " dias";
          toast(
            `Retenção salva explicitamente. ${r.deleted} registros vencidos excluídos.`,
          );
          await refresh();
        });
      });
      refresh().catch((e) => toast(e.message));
    }
    if (page === "inteligencia") {
      $("#intelligence-filters").addEventListener("submit", (e) => {
        e.preventDefault();
        intelligenceFilters = Object.fromEntries(new FormData(e.target));
        loadIntelligence().catch((err) => toast(err.message));
      });
      loadIntelligence().catch((e) => toast(e.message));
    }
  }
  document.addEventListener("click", async (e) => {
    const button = e.target.closest("[data-community]");
    if (!button) return;
    const { community: action, id, key, format, mode } = button.dataset;
    try {
      if (action === "import") importDialog();
      if (action === "message") await messageDialog(id);
      if (action === "delete-one") deletionDialog(id);
      if (action === "delete-period") deletionDialog();
      if (action === "previous" || action === "next") {
        pageNumber += action === "previous" ? -1 : 1;
        await loadMessages();
      }
      if (action === "clear") {
        if (mode === "history") {
          historyFilters = {};
          pageNumber = 1;
        } else intelligenceFilters = { days: "7" };
        await navigate();
      }
      if (action === "topic-review") await topicDialog(key);
      if (action === "topic-messages") {
        historyFilters = { ...intelligenceFilters, topic_key: key };
        if (!historyFilters.since && lastPeriod?.from) {
          const day = new Date(lastPeriod.from * 1000);
          historyFilters.since = new Intl.DateTimeFormat("en-CA", {
            timeZone: "America/Sao_Paulo",
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
          }).format(day);
        }
        delete historyFilters.days;
        pageNumber = 1;
        location.hash = "conversas";
      }
      if (action === "open-intelligence") $("#dialog").close();
      if (action === "export") await download(format);
      if (action === "import-log") {
        const rows = await api("/conversations/imports"),
          r = rows.find((item) => item.id === Number(id));
        if (!r) throw new Error("Importação não encontrada.");
        openDialog(
          "Resultado da importação",
          `<p class="small muted">#${r.id} · ${esc(r.group_name)} · ${esc(fullDate(r.created_at))}</p>${counters(r.result)}${diagnostics(r.result.errors_detail, r.result.warnings)}<p class="hint">Datas: ${r.result.date_order === "mdy" ? "mês/dia/ano" : "dia/mês/ano"} · Fuso: ${r.result.utc_offset} minutos de UTC.</p><div class="panel-actions"><button class="button" data-action="close">Fechar</button></div>`,
        );
      }
    } catch (error) {
      toast(error.message);
    }
  });
  $("#dialog").addEventListener("close", () => {
    if (previewToken) {
      const t = previewToken;
      previewToken = null;
      api("/conversations/preview/" + encodeURIComponent(t), {
        method: "DELETE",
      }).catch(() => {});
    }
  });
  return { historyPage, intelligencePage, wire };
})();
