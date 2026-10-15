"use strict";
const $ = (selector, parent = document) => parent.querySelector(selector);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
const split = (value) =>
  String(value || "")
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
const date = (value) =>
  new Date(value * 1000).toLocaleString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
const names = {
  permitida: "Permitida",
  suspeita: "Suspeita",
  critica: "Crítica",
};
const paths = {
  painel: "Visão geral",
  grupos: "Grupos",
  afiliados: "Links e afiliados",
  regras: "Regras de moderação",
  simulador: "Simulador",
  ocorrencias: "Ocorrências",
  conversas: "Histórico de conversas",
  inteligencia: "Inteligência da comunidade",
};
const iconPaths = {
  painel: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  grupos:
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M16 3a4 4 0 0 1 0 8 M22 21v-2a4 4 0 0 0-3-3.87 M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
  afiliados:
    "M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-2 2 M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l2-2",
  regras: "M4 7h16 M4 17h16 M8 4v6 M16 14v6",
  simulador: "m8 5 11 7-11 7z",
  ocorrencias: "M12 3 2 21h20z M12 9v5 M12 17h.01",
  conversas: "M4 4h16v13H8l-4 4z M8 8h8 M8 12h6",
  inteligencia: "M4 20h16 M7 16V9 M12 16V4 M17 16v-5",
  plus: "M12 5v14 M5 12h14",
  arrow: "M5 12h14 M13 6l6 6-6 6",
};
const icon = (key) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${iconPaths[key] || iconPaths.arrow}"/></svg>`;
const badge = (status, label) =>
  `<span class="badge ${esc(status)}">${esc(label || names[status] || status)}</span>`;
let csrf = "",
  username = "",
  setupRequired = false,
  currentPage = "",
  navigationVersion = 0,
  groups = [],
  affiliates = [],
  historyPage = 1,
  toastTimer;

async function api(path, options = {}) {
  const response = await fetch("/api" + path, {
    credentials: "same-origin",
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf,
      ...options.headers,
    },
  });
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error("O servidor não respondeu corretamente.");
  }
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/auth")) {
      await boot();
    }
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "Não foi possível concluir. Revise os campos.",
    );
  }
  return body;
}
function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (element.hidden = true), 4500);
}
function pageHead(eyebrow, title, description, action = "") {
  return `<div class="page-head"><div><p class="eyebrow">${eyebrow}</p><h1>${title}</h1><p class="muted small">${description}</p></div>${action}</div>`;
}
function empty(title, text, action = "") {
  return `<div class="empty"><h3>${title}</h3><p>${text}</p>${action}</div>`;
}
function openDialog(title, content) {
  $("#dialog-content").innerHTML =
    `<div class="dialog-body"><div class="dialog-head"><h2>${title}</h2><button class="close" data-action="close" aria-label="Fechar">×</button></div>${content}</div>`;
  $("#dialog").showModal();
}
function selectGroups(selected = "", activeOnly = false) {
  return groups
    .filter((g) => !activeOnly || g.active)
    .map(
      (g) =>
        `<option value="${g.id}" ${String(selected) === String(g.id) ? "selected" : ""}>${esc(g.name)}</option>`,
    )
    .join("");
}
async function submit(form, task) {
  const button = $("button[type=submit]", form);
  if (button) button.disabled = true;
  const error = $(".error", form);
  if (error) error.textContent = "";
  try {
    await task();
  } catch (e) {
    if (error) error.textContent = e.message;
    else toast(e.message);
  } finally {
    if (button) button.disabled = false;
  }
}

async function boot() {
  const session = await api("/auth/session");
  csrf = session.csrf;
  username = session.username;
  setupRequired = session.setup_required;
  $("#auth-screen").hidden = !!username;
  $("#app-shell").hidden = !username;
  $("#auth-title").textContent = setupRequired
    ? "Seu primeiro acesso."
    : "Bem-vindo de volta.";
  $("#auth-description").textContent = setupRequired
    ? "Crie a conta que vai administrar sua comunidade. Escolha uma senha com pelo menos 10 caracteres."
    : "Entre para acompanhar sua comunidade e revisar os alertas.";
  $("#auth-submit").textContent = setupRequired
    ? "Criar conta e começar"
    : "Entrar no painel";
  $("input[name=password]", $("#auth-form")).autocomplete = setupRequired
    ? "new-password"
    : "current-password";
  if (username) {
    $("#account-name").textContent = username;
    $("#today").textContent = new Date().toLocaleDateString("pt-BR", {
      timeZone: "America/Sao_Paulo",
      day: "2-digit",
      month: "long",
    });
    await navigate();
  }
}
$("#auth-form").addEventListener("submit", (event) => {
  event.preventDefault();
  submit(event.target, async () => {
    const values = Object.fromEntries(new FormData(event.target));
    const session = await api(setupRequired ? "/auth/setup" : "/auth/login", {
      method: "POST",
      body: JSON.stringify(values),
    });
    csrf = session.csrf;
    event.target.reset();
    await boot();
  });
});
$("#logout").addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
    $("#dialog").close();
    await boot();
  } catch (error) {
    toast(error.message);
  }
});
$("#nav").innerHTML = Object.entries(paths)
  .map(
    ([key, label]) =>
      `<a class="nav-link" href="#${key}" data-page="${key}">${icon(key)}<span>${label}</span></a>`,
  )
  .join("");
window.addEventListener("hashchange", () => {
  if (username) navigate();
});

async function navigate() {
  const version = ++navigationVersion;
  currentPage = location.hash.slice(1).split("?")[0] || "painel";
  if (!paths[currentPage]) currentPage = "painel";
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.classList.toggle("active", link.dataset.page === currentPage);
    if (link.dataset.page === currentPage)
      link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  $("#breadcrumb").textContent = paths[currentPage];
  document.title = `${paths[currentPage]} · Guardião IA`;
  $("#main").innerHTML =
    '<div class="loading" role="status">Carregando seu espaço…</div>';
  try {
    groups = await api("/groups");
    const renderers = {
      painel: dashboard,
      grupos: groupPage,
      afiliados: affiliatePage,
      regras: rulesPage,
      simulador: simulatorPage,
      ocorrencias: historyPageView,
      conversas: () => Community.historyPage(),
      inteligencia: () => Community.intelligencePage(),
    };
    const html = await renderers[currentPage]();
    if (version !== navigationVersion) return;
    $("#main").innerHTML = html;
    wirePage();
    if (window.Community) Community.wire(currentPage);
  } catch (error) {
    if (version === navigationVersion)
      $("#main").innerHTML = empty(
        "Não foi possível carregar.",
        esc(error.message),
        '<button class="button" data-action="refresh">Tentar novamente</button>',
      );
  }
}

async function dashboard() {
  const data = await api("/dashboard"),
    s = data.stats;
  const metrics = [
    ["Grupos cadastrados", s.groups, "Registros locais", ""],
    ["Mensagens analisadas", s.analyzed, `${s.allowed} permitidas`, ""],
    ["Suspeitas de spam", s.suspicious, "Aguardam contexto", ""],
    ["Infrações críticas", s.critical, "Lista de domínios", "critical"],
    ["Alertas pendentes", s.pending, "Sua revisão faz a diferença", "pending"],
  ];
  const max = Math.max(...data.activity.map((b) => b.total), 1);
  const chart = `<svg viewBox="0 0 480 125" width="100%" height="125" role="img" aria-label="Mensagens e alertas por hora nas últimas 12 horas"><path d="M0 120H480 M0 80H480 M0 40H480" stroke="#edf0e8"/>${data.activity.map((bucket, i) => `<g><title>${date(bucket.end)}: ${bucket.total} mensagens, ${bucket.alerts} alertas</title><rect x="${i * 40 + 9}" y="${120 - Math.max((bucket.total / max) * 100, 2)}" width="17" height="${Math.max((bucket.total / max) * 100, 2)}" rx="3" fill="#c9d9bc"/><rect x="${i * 40 + 28}" y="${120 - Math.max((bucket.alerts / max) * 100, 2)}" width="7" height="${Math.max((bucket.alerts / max) * 100, 2)}" rx="2" fill="#d9a672"/></g>`).join("")}</svg>`;
  return (
    pageHead(
      "SEU CENTRO DE CUIDADO",
      "Visão geral",
      "Um olhar atento para o que acontece na sua comunidade.",
      `<a class="button primary" href="#simulador">${icon("plus")}Simular mensagem</a>`,
    ) +
    `<section class="hero"><div><p class="eyebrow">CUIDADO COM A COMUNIDADE</p><h2>Boas conversas merecem espaço.</h2><p>${s.pending ? `Há ${s.pending} alertas esperando seu olhar. Explore as ocorrências e decida o próximo passo.` : "Todos os alertas foram revisados. Seu espaço está pronto para novas conversas."} Este painel usa apenas mensagens fictícias e simuladas.</p></div><div class="hero-art"><img src="/static/mark.svg" alt="Escudo Guardião IA"></div></section>` +
    `<section class="metrics" aria-label="Indicadores">${metrics.map(([label, value, foot, type]) => `<div class="metric ${type}"><div class="metric-label">${esc(label)}</div><div class="metric-value">${value.toLocaleString("pt-BR")}</div><div class="metric-foot">${esc(foot)}</div></div>`).join("")}</section>` +
    `<div class="columns"><section class="panel"><div class="panel-head"><div><h2>O ritmo das conversas</h2><p>Mensagens analisadas por hora</p></div><span class="badge neutral">Últimas 12 horas</span></div>${chart}<div class="chart-axis"><span>12 horas atrás</span><span>6 horas atrás</span><span>Agora</span></div><div class="legend"><span><i></i>Mensagens</span><span><i class="alert"></i>Alertas</span></div></section><section class="panel"><div class="panel-head"><div><h2>Seus grupos</h2><p>Registros locais da comunidade</p></div><a class="link-button" href="#grupos">Gerenciar ↗</a></div>${
      data.groups
        .slice(0, 3)
        .map(
          (g, i) =>
            `<div class="group-row"><div class="group-icon">${String(i + 1).padStart(2, "0")}</div><div class="group-copy"><strong>${esc(g.name)}</strong><small>${g.participant_count} participantes · ${g.analyzed} análises</small></div>${badge(g.pending ? "suspeita" : "neutral", g.pending ? `${g.pending} alertas` : g.active ? "Ativo" : "Pausado")}</div>`,
        )
        .join("") ||
      empty("Seu primeiro grupo", "Cadastre um grupo para começar.")
    }</section></div>` +
    `<section class="panel"><div class="panel-head"><div><h2>Ocorrências recentes</h2><p>Contexto primeiro. Ações sempre sob sua revisão.</p></div><a class="link-button" href="#ocorrencias">Ver todas ↗</a></div>${occurrenceTable(data.recent)}</section><p class="small muted">Os indicadores consideram o histórico retido, incluindo a demonstração. Exclusão automática após ${data.retention_days} dias.</p>`
  );
}
function occurrenceTable(items) {
  return items.length
    ? `<div class="table-wrap"><table><thead><tr><th>Participante / mensagem</th><th>Grupo</th><th>Classificação</th><th>Revisão</th><th></th></tr></thead><tbody>${items.map((item) => `<tr><td><strong>${esc(item.participant)}</strong><span class="preview">${esc(item.content)}</span><small>${date(item.created_at)} ${item.source === "demo" ? "· demonstração" : ""}</small></td><td>${esc(item.group_name)}</td><td>${badge(item.status)}</td><td>${item.status === "permitida" ? '<span class="muted">—</span>' : badge(item.reviewed ? "neutral" : "suspeita", item.reviewed ? "Revisado" : "Pendente")}</td><td><button class="link-button" data-action="detail" data-id="${item.id}">Detalhes ↗</button></td></tr>`).join("")}</tbody></table></div>`
    : empty(
        "Tudo em ordem por aqui.",
        "Nenhum registro corresponde a esta seleção.",
      );
}
async function groupPage() {
  return (
    pageHead(
      "A BASE DA COMUNIDADE",
      "Seus grupos",
      "Identifique cada espaço e organize a moderação.",
      `<button class="button primary" data-action="group">${icon("plus")}Cadastrar grupo</button>`,
    ) +
    `<div class="notice">Os nomes e participantes da demonstração são fictícios. Os grupos cadastrados ainda não estão conectados ao WhatsApp.</div><div class="grid-cards">${groups.map((g, i) => `<section class="panel group-card"><div class="card-top"><div class="group-icon">${String(i + 1).padStart(2, "0")}</div>${badge(g.active ? "permitida" : "neutral", g.active ? "Ativo para simulação" : "Pausado")}</div><h2>${esc(g.name)}</h2><p class="card-description">${esc(g.description || "Sem descrição.")}</p><div class="card-stats"><div><strong>${g.participant_count}</strong><small>participantes informados</small></div><div><strong>${String(g.id).padStart(2, "0")}</strong><small>identificação local</small></div></div><button class="button subtle" data-action="group" data-id="${g.id}">Editar grupo ↗</button></section>`).join("")}</div>${groups.length ? "" : empty("Um espaço para começar.", "Cadastre os grupos da sua comunidade.")}`
  );
}
function groupDialog(id) {
  const g = groups.find((item) => item.id === Number(id)) || {
    name: "",
    description: "",
    participant_count: 0,
    active: true,
  };
  openDialog(
    id ? "Editar grupo" : "Cadastrar grupo",
    `<form id="group-form" class="form-grid"><label class="full">Nome do grupo<input name="name" value="${esc(g.name)}" minlength="2" maxlength="100" required></label><label class="full">Descrição<textarea name="description" maxlength="500">${esc(g.description)}</textarea></label><label>Participantes informados<input name="participant_count" type="number" min="0" max="100000" value="${g.participant_count}" required></label><label class="check-label"><input name="active" type="checkbox" ${g.active ? "checked" : ""}>Ativo para simulação</label><p class="error full" role="alert"></p><div class="panel-actions full"><button type="button" class="button" data-action="close">Cancelar</button><button type="submit" class="button primary">Salvar grupo</button></div></form>`,
  );
  $("#group-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submit(event.target, async () => {
      const v = Object.fromEntries(new FormData(event.target));
      v.participant_count = Number(v.participant_count);
      v.active = $("[name=active]", event.target).checked;
      await api(id ? `/groups/${id}` : "/groups", {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(v),
      });
      $("#dialog").close();
      toast("Grupo salvo.");
      await navigate();
    });
  });
}
async function affiliatePage() {
  affiliates = await api("/affiliates");
  return (
    pageHead(
      "INDICAÇÕES COM IDENTIDADE",
      "Links e afiliados",
      "Seus links autorizados, organizados por plataforma.",
      `<button class="button primary" data-action="affiliate">${icon("plus")}Cadastrar plataforma</button>`,
    ) +
    `<div class="notice">Nenhum código ou link real foi preenchido por você ainda? Cadastre-os quando estiver pronto. A comparação considera os parâmetros de indicação e, opcionalmente, o caminho do link.</div><section class="panel">${affiliates.length ? `<div class="table-wrap"><table><thead><tr><th>Plataforma</th><th>Domínio</th><th>Identificação</th><th>Permissões</th><th></th></tr></thead><tbody>${affiliates.map((a) => `<tr><td><strong>${esc(a.platform)}</strong><small>${a.referral_url ? "Link de indicação cadastrado" : "Sem link próprio"}</small></td><td>${esc(a.domain)}</td><td>${a.affiliate_code ? esc(a.affiliate_code) : "Não informado"}<small>${esc(a.affiliate_parameters.join(", ") || "Parâmetros globais")}</small></td><td>${a.allowed_links.length} links · ${a.allowed_domains.length} domínios</td><td><button class="link-button" data-action="affiliate" data-id="${a.id}">Editar ↗</button></td></tr>`).join("")}</tbody></table></div>` : empty("Sua indicação tem lugar aqui.", "Cadastre sua plataforma e os identificadores autorizados. Nenhum afiliado fictício foi adicionado.", `<button class="button" data-action="affiliate">Cadastrar primeira plataforma</button>`)}</section>`
  );
}
function affiliateDialog(id) {
  const a = affiliates.find((item) => item.id === Number(id)) || {
    platform: "",
    domain: "",
    referral_url: "",
    affiliate_code: "",
    affiliate_parameters: [],
    affiliate_path_prefix: "",
    allowed_links: [],
    allowed_domains: [],
  };
  openDialog(
    id ? "Editar plataforma" : "Cadastrar plataforma",
    `<form id="affiliate-form" class="form-grid"><label>Nome da plataforma<input name="platform" required minlength="2" maxlength="100" value="${esc(a.platform)}" placeholder="Nome da plataforma"></label><label>Domínio<input name="domain" required value="${esc(a.domain)}" placeholder="plataforma.example"><small>Sem https:// ou caminho.</small></label><label class="full">Link completo de indicação<input name="referral_url" value="${esc(a.referral_url)}" placeholder="https://plataforma.example/?ref=SEU_CODIGO"><small>Opcional. O domínio deve pertencer à plataforma.</small></label><label>Código de afiliado<input name="affiliate_code" maxlength="200" value="${esc(a.affiliate_code)}"></label><label>Parâmetros de afiliado<input name="affiliate_parameters" value="${esc(a.affiliate_parameters.join(", "))}" placeholder="ref, invite_code"><small>Separe por vírgulas. Somados aos parâmetros globais.</small></label><label class="full">Prefixo de indicação no caminho (opcional)<input name="affiliate_path_prefix" value="${esc(a.affiliate_path_prefix)}" placeholder="/convite/"><small>Para links como /convite/SEU_CODIGO. Caminhos diferentes ficam suspeitos.</small></label><label>Links exatos autorizados<textarea name="allowed_links" placeholder="Um link por linha">${esc(a.allowed_links.join("\n"))}</textarea></label><label>Domínios autorizados<textarea name="allowed_domains" placeholder="Um domínio por linha">${esc(a.allowed_domains.join("\n"))}</textarea><small>Inclui todos os subdomínios. Não ignora indicações de terceiros na plataforma.</small></label><p class="error full" role="alert"></p><div class="panel-actions full">${id ? `<button type="button" class="button danger" data-action="affiliate-delete" data-id="${id}">Excluir</button>` : ""}<button type="button" class="button" data-action="close">Cancelar</button><button type="submit" class="button primary">Salvar plataforma</button></div></form>`,
  );
  $("#affiliate-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submit(event.target, async () => {
      const v = Object.fromEntries(new FormData(event.target));
      ["affiliate_parameters", "allowed_links", "allowed_domains"].forEach(
        (key) => (v[key] = split(v[key])),
      );
      await api(id ? `/affiliates/${id}` : "/affiliates", {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(v),
      });
      $("#dialog").close();
      toast("Plataforma salva.");
      await navigate();
    });
  });
}

async function simulatorPage() {
  return (
    pageHead(
      "TESTE ANTES DE AGIR",
      "Simulador de mensagens",
      "Observe como as regras respondem a uma conversa fictícia.",
    ) +
    `<div class="notice">Nenhuma mensagem será enviada ao WhatsApp. Exclusões, advertências e remoções são recomendações simuladas.</div><div class="simulator-grid"><section class="panel"><div class="panel-head"><div><h2>Uma mensagem de teste</h2><p>Use o mesmo participante para testar repetição e frequência.</p></div>${badge("neutral", "SIMULAÇÃO")}</div>${groups.some((g) => g.active) ? `<form id="simulate-form"><div class="form-grid"><label>Grupo<select name="group_id" required>${selectGroups("", true)}</select></label><label>Participante fictício<input name="participant" required minlength="2" maxlength="100" value="Participante de teste"></label><label class="full">Mensagem<textarea name="content" required maxlength="10000" placeholder="Escreva a mensagem que deseja analisar…"></textarea></label></div><span class="hint">Experimente um cenário:</span><div class="examples"><button class="example" type="button" data-example="conversa">Conversa normal</button><button class="example" type="button" data-example="cassino">Cassino de demonstração</button><button class="example" type="button" data-example="loja">Marketplace</button><button class="example" type="button" data-example="encurtado">Link encurtado</button></div><p class="error" role="alert"></p><button class="button primary" type="submit">${icon("simulador")}Analisar mensagem</button></form>` : empty("Ative um grupo para testar.", "Cadastre ou ative um grupo na área de grupos.", `<a class="button" href="#grupos">Ir para grupos</a>`)}</section><section class="panel" id="simulation-result" aria-live="polite"><div class="panel-head"><h2>Resultado da análise</h2></div><div class="result-placeholder"><img src="/static/mark.svg" alt=""><h3>O contexto faz a diferença.</h3><p>Envie uma mensagem de teste para ver as regras acionadas e a ação recomendada.</p></div></section></div><p class="small muted">Nesta etapa, a análise recebe apenas texto e URLs. Imagens e vídeos serão avaliados em uma etapa futura.</p>`
  );
}
function analysisResult(item) {
  return `<p class="eyebrow">${item.source === "demo" ? "DEMONSTRAÇÃO FICTÍCIA" : "ANÁLISE SIMULADA"}</p><div class="result-status">${esc(names[item.status])}</div>${badge(item.status)}<div class="message-block">${esc(item.content)}</div>${item.findings.length ? item.findings.map((f) => `<div class="finding"><h3>${esc(f.label)}</h3><p>${esc(f.reason)}</p><span class="hint">Regra: ${esc(f.rule)}</span></div>`).join("") : '<p class="muted small">Nenhuma regra de infração foi acionada. Menções a assuntos ou plataformas são permitidas.</p>'}<div class="action-box"><strong>AÇÃO RECOMENDADA</strong>${esc(item.recommendation)}</div><p class="hint">Nenhuma ação foi executada contra participantes ou mensagens.</p>`;
}
async function rulesPage() {
  const r = await api("/rules");
  const labels = {
    casino: ["Cassinos e apostas", "Somente URLs de domínios cadastrados."],
    affiliate: ["Afiliados de terceiros", "Compara a identidade de indicação."],
    marketplace: [
      "Propaganda comercial",
      "Links de lojas precisam de contexto.",
    ],
    unknown_link: [
      "Links desconhecidos e encurtados",
      "Revisão manual, sem abrir endereços.",
    ],
    repeat: ["Mensagens repetidas", "Mesmo texto, participante e grupo."],
    burst: ["Frequência de mensagens", "Muitos envios em poucos segundos."],
    link_burst: [
      "Frequência de links",
      "Quantidade de links por participante e grupo.",
    ],
  };
  return (
    pageHead(
      "POLÍTICAS DA COMUNIDADE",
      "Regras de moderação",
      "Ajuste as regras ao seu contexto. Sem inteligência artificial nesta etapa.",
    ) +
    `<div class="notice warning">A lista inicial de cassinos contém apenas domínios fictícios .example. Adicione domínios confirmados antes de qualquer uso real. O classificador não oferece cobertura universal de spam.</div><form id="rules-form"><div class="rules-grid"><section class="panel"><h2>Regras ativas</h2>${Object.entries(
      labels,
    )
      .map(
        ([key, [label, desc]]) =>
          `<label class="rule-toggle"><span>${label}<small>${desc}</small></span><input type="checkbox" name="enabled_${key}" ${r.enabled[key] ? "checked" : ""}></label>`,
      )
      .join(
        "",
      )}<h3 class="rules-section">Limites e janelas de tempo</h3><div class="form-grid">${[
      ["repeat", "Repetição"],
      ["burst", "Mensagens"],
      ["link_burst", "Links"],
    ]
      .map(
        ([key, label]) =>
          `<label>${label}: limite<input type="number" name="${key}_threshold" min="2" max="1000" value="${r[key + "_threshold"]}" required></label><label>Janela (segundos)<input type="number" name="${key}_window_seconds" min="1" max="86400" value="${r[key + "_window_seconds"]}" required></label>`,
      )
      .join(
        "",
      )}<label class="full">Reter histórico por quantos dias?<input type="number" name="retention_days" min="1" max="365" required value="${r.retention_days}"><small>Reduzir este prazo exclui imediatamente os registros vencidos.</small></label></div></section><section class="panel"><h2>Endereços e identificadores</h2><p class="small muted">Um item por linha. Domínios incluem seus subdomínios.</p>${[
      ["casino_domains", "Cassinos e apostas confirmados"],
      ["marketplace_domains", "Marketplaces"],
      ["shortener_domains", "Encurtadores e redirecionadores"],
      ["allowed_domains", "Domínios globais autorizados"],
      ["allowed_links", "Links exatos autorizados"],
      ["affiliate_parameters", "Parâmetros de indicação globais"],
    ]
      .map(
        ([key, label]) =>
          `<label class="rules-section">${label}<textarea name="${key}">${esc(r[key].join("\n"))}</textarea></label>`,
      )
      .join(
        "",
      )}<p class="hint">Domínios de cassino confirmados e encurtadores têm prioridade sobre autorizações. Parâmetros diferentes dos seus continuam suspeitos mesmo em um domínio autorizado.</p></section></div><p class="error" role="alert"></p><div class="panel-actions"><button class="button primary" type="submit">Salvar regras</button></div></form><section class="danger-zone"><div><h3>Exclusão de histórico</h3><p>Apague mensagens, resultados e alertas armazenados, preservando os cadastros e as regras.</p></div><button class="button danger" data-action="history-delete">Excluir histórico</button></section>`
  );
}
async function historyPageView() {
  historyPage = 1;
  return (
    pageHead(
      "CONTEXTO PARA DECIDIR",
      "Ocorrências e histórico",
      "Encontre mensagens, entenda as regras e revise os alertas.",
    ) +
    `<section class="panel"><form id="history-filters" class="filters"><label class="search">Buscar<input name="q" placeholder="Mensagem ou participante"></label><label>Grupo<select name="group_id"><option value="">Todos os grupos</option>${selectGroups()}</select></label><label>Classificação<select name="status"><option value="ocorrencias">Todas as ocorrências</option><option value="">Todas as mensagens</option><option value="suspeita">Suspeita</option><option value="critica">Crítica</option><option value="permitida">Permitida</option></select></label><label>Revisão<select name="reviewed"><option value="">Qualquer situação</option><option value="false">Pendente</option><option value="true">Revisado</option></select></label><button class="button" type="submit">Filtrar</button></form><div id="history-results" aria-live="polite">Carregando…</div></section>`
  );
}
async function loadHistory() {
  const v = Object.fromEntries(new FormData($("#history-filters")));
  const params = new URLSearchParams(
    Object.entries(v).filter(([, value]) => value !== ""),
  );
  params.set("page", historyPage);
  const data = await api("/history?" + params);
  if (currentPage !== "ocorrencias") return;
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  $("#history-results").innerHTML =
    occurrenceTable(data.items) +
    `<div class="pagination"><span>${data.total} registros encontrados</span><div><button class="button" data-action="history-prev" ${historyPage <= 1 ? "disabled" : ""}>←</button><span>Página ${historyPage} de ${pages}</span><button class="button" data-action="history-next" ${historyPage >= pages ? "disabled" : ""}>→</button></div></div>`;
}
function wirePage() {
  const form = $("#simulate-form");
  if (form)
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submit(form, async () => {
        const v = Object.fromEntries(new FormData(form));
        v.group_id = Number(v.group_id);
        const result = await api("/simulate", {
          method: "POST",
          body: JSON.stringify(v),
        });
        $("#simulation-result").innerHTML =
          `<div class="panel-head"><h2>Resultado da análise</h2><span class="badge neutral">#${result.id}</span></div>${analysisResult(result)}<a class="link-button" href="#ocorrencias">Ver no histórico ↗</a>`;
        toast("Mensagem analisada e salva no histórico.");
      });
    });
  const rules = $("#rules-form");
  if (rules)
    rules.addEventListener("submit", (event) => {
      event.preventDefault();
      submit(rules, async () => {
        const values = Object.fromEntries(new FormData(rules)),
          payload = { enabled: {} };
        Object.keys(values)
          .filter((k) => !k.startsWith("enabled_"))
          .forEach(
            (key) =>
              (payload[key] =
                key.includes("threshold") ||
                key.includes("seconds") ||
                key === "retention_days"
                  ? Number(values[key])
                  : split(values[key])),
          );
        [
          "casino",
          "affiliate",
          "marketplace",
          "unknown_link",
          "repeat",
          "burst",
          "link_burst",
        ].forEach(
          (key) =>
            (payload.enabled[key] = $(`[name=enabled_${key}]`, rules).checked),
        );
        const result = await api("/rules", {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast(
          `Regras salvas.${result.deleted ? " " + result.deleted + " registros vencidos excluídos." : ""}`,
        );
      });
    });
  const filters = $("#history-filters");
  if (filters) {
    filters.addEventListener("submit", (event) => {
      event.preventDefault();
      historyPage = 1;
      loadHistory().catch((e) => toast(e.message));
    });
    loadHistory().catch((e) => toast(e.message));
  }
}

document.addEventListener("click", async (event) => {
  const example = event.target.closest("[data-example]");
  if (example) {
    const samples = {
      conversa:
        "Alguém sabe como começar no HUB? Vi uma conversa sobre Shopee e BET, mas minha dúvida é sobre treinamento de IA.",
      cassino: "Entre agora: https://cassino-demo.example/bonus",
      loja: "Oferta do dia: https://shopee.com.br/oferta-demo",
      encurtado: "Confira este link: https://bit.ly/demo-guardiao",
    };
    $("[name=content]", $("#simulate-form")).value =
      samples[example.dataset.example];
    return;
  }
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const { action, id } = button.dataset;
  try {
    if (action === "close") $("#dialog").close();
    if (action === "refresh") await navigate();
    if (action === "group") groupDialog(id);
    if (action === "affiliate") affiliateDialog(id);
    if (action === "affiliate-delete") {
      const profile = affiliates.find((a) => a.id === Number(id));
      openDialog(
        "Excluir plataforma?",
        `<p class="muted">Remover ${esc(profile.platform)} e suas autorizações? O histórico existente será preservado.</p><div class="panel-actions"><button class="button" data-action="close">Cancelar</button><button class="button danger" data-action="affiliate-delete-confirm" data-id="${id}">Excluir plataforma</button></div>`,
      );
    }
    if (action === "affiliate-delete-confirm") {
      await api("/affiliates/" + id, { method: "DELETE" });
      $("#dialog").close();
      toast("Plataforma excluída.");
      await navigate();
    }
    if (action === "detail") {
      const item = await api("/history/" + id);
      openDialog(
        "Detalhes da ocorrência",
        `<p class="small muted">${esc(item.group_name)} · ${esc(item.participant)}<br>${date(item.created_at)}${item.reviewed_at ? " · Revisado em " + date(item.reviewed_at) : ""}</p>${analysisResult(item)}<div class="panel-actions">${item.status !== "permitida" && !item.reviewed ? `<button class="button primary" data-action="review" data-id="${id}">Marcar como revisado</button>` : badge("neutral", item.reviewed ? "Alerta revisado" : "Nenhum alerta pendente")}<button class="button" data-action="close">Fechar</button></div>`,
      );
    }
    if (action === "review") {
      await api(`/history/${id}/review`, { method: "POST" });
      $("#dialog").close();
      toast("Alerta marcado como revisado.");
      if (currentPage === "ocorrencias") await loadHistory();
      else await navigate();
    }
    if (action === "history-prev" || action === "history-next") {
      historyPage += action === "history-prev" ? -1 : 1;
      await loadHistory();
    }
    if (action === "history-delete") {
      openDialog(
        "Excluir histórico",
        `<p class="muted small">Esta ação apaga os registros selecionados de forma permanente. Os dados não podem ser recuperados pelo painel.</p><form id="delete-form"><label>Escopo<select name="group_id"><option value="">Todo o histórico</option>${selectGroups()}</select></label><label>Digite EXCLUIR para confirmar<input name="confirmation" required pattern="EXCLUIR" autocomplete="off"></label><p class="error" role="alert"></p><div class="panel-actions"><button type="button" class="button" data-action="close">Cancelar</button><button type="submit" class="button danger">Excluir definitivamente</button></div></form>`,
      );
      $("#delete-form").addEventListener("submit", (event) => {
        event.preventDefault();
        submit(event.target, async () => {
          const v = Object.fromEntries(new FormData(event.target));
          v.group_id = v.group_id ? Number(v.group_id) : null;
          const result = await api("/history", {
            method: "DELETE",
            body: JSON.stringify(v),
          });
          $("#dialog").close();
          toast(`${result.deleted} registros excluídos.`);
        });
      });
    }
  } catch (error) {
    toast(error.message);
  }
});
$("#dialog").addEventListener("click", (event) => {
  if (event.target === $("#dialog")) {
    const rect = $("#dialog").getBoundingClientRect();
    if (
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom
    )
      $("#dialog").close();
  }
});
document.addEventListener("DOMContentLoaded", () => {
  boot().catch((error) => {
    $("#auth-screen").hidden = false;
    $("#auth-error").textContent =
      "Não foi possível acessar o servidor: " + error.message;
  });
});
