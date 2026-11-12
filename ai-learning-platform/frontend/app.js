/* AI Learning Platform - vanilla JS single page app (hash router). No build step. */
const S = {
  token: localStorage.getItem("token"),
  user: JSON.parse(localStorage.getItem("user") || "null"),
  track: localStorage.getItem("track") || "FULL",
  chat: {},
};
const app = document.getElementById("app");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const md = (t) => DOMPurify.sanitize(marked.parse(t || ""));
const spinner = (msg) => `<div class="flex items-center gap-3 text-slate-400 py-10 justify-center"><span class="spinner"></span>${esc(msg)}</div>`;
const errBox = (msg) => `<div class="bg-red-950/50 border border-red-800 text-red-200 rounded-lg p-4 my-4">${esc(msg)}</div>`;
const cls = {
  card: "bg-slate-900 border border-slate-800 rounded-xl",
  btn: "px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-sm font-medium disabled:opacity-50",
  btn2: "px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm",
  input: "w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-sky-500",
};

function toast(msg) {
  const t = document.getElementById("toast");
  t.innerHTML = `<div class="bg-slate-800 border border-slate-600 px-4 py-2 rounded-lg shadow-lg text-sm">${esc(msg)}</div>`;
  setTimeout(() => (t.innerHTML = ""), 3500);
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json" };
  if (S.token) headers.Authorization = "Bearer " + S.token;
  const r = await fetch(path, { method: opts.method || "GET", headers, body: opts.body ? JSON.stringify(opts.body) : undefined });
  let data = null;
  try { data = await r.json(); } catch (e) { /* empty body */ }
  if (r.status === 401 && S.token) { logout(); throw new Error("Please sign in again"); }
  if (!r.ok) {
    const d = data && (data.detail || data.error);
    throw new Error(typeof d === "string" ? d : JSON.stringify(d) || r.statusText);
  }
  return data;
}

function logout() {
  S.token = null; S.user = null;
  localStorage.removeItem("token"); localStorage.removeItem("user");
  location.hash = "#/login";
  renderUser();
}
function renderUser() {
  const box = document.getElementById("userbox");
  box.innerHTML = S.user
    ? `<span class="text-slate-400 mr-3">${esc(S.user.name)}</span><button id="logout" class="${cls.btn2}">Log out</button>`
    : "";
  const b = document.getElementById("logout");
  if (b) b.onclick = logout;
}

/* ---------------------------------------------------------------- router */
async function route() {
  renderUser();
  const h = location.hash || "#/";
  if (!S.token && h !== "#/login") { location.hash = "#/login"; return; }
  const parts = h.slice(2).split("/");
  try {
    if (parts[0] === "login") return viewLogin();
    if (parts[0] === "roadmap") return await viewRoadmap(parts[1]);
    if (parts[0] === "module") return await viewModule(parts[1]);
    return await viewHome();
  } catch (e) {
    app.innerHTML = errBox(e.message) + `<a href="#/" class="${cls.btn2}">Back home</a>`;
  }
}
window.addEventListener("hashchange", route);

/* ---------------------------------------------------------------- login */
function viewLogin() {
  let mode = "login";
  const draw = () => {
    app.innerHTML = `
    <div class="max-w-md mx-auto ${cls.card} p-6 mt-10">
      <h1 class="text-2xl font-bold mb-1">${mode === "login" ? "Welcome back" : "Create your account"}</h1>
      <p class="text-slate-400 text-sm mb-4">Learn anything from Class 6 to PhD, on a fast track or the full path.</p>
      <form id="f" class="space-y-3">
        ${mode === "register" ? `<input id="name" class="${cls.input}" placeholder="Your name" required />` : ""}
        <input id="email" type="email" class="${cls.input}" placeholder="Email" required />
        <input id="pw" type="password" class="${cls.input}" placeholder="Password (min 6 chars)" required />
        <div id="err"></div>
        <button class="${cls.btn} w-full">${mode === "login" ? "Log in" : "Sign up"}</button>
      </form>
      <button id="sw" class="text-sky-400 text-sm mt-3">${mode === "login" ? "New here? Create an account" : "Have an account? Log in"}</button>
    </div>`;
    document.getElementById("sw").onclick = () => { mode = mode === "login" ? "register" : "login"; draw(); };
    document.getElementById("f").onsubmit = async (ev) => {
      ev.preventDefault();
      try {
        const $v = (i) => document.getElementById(i).value;
        const body = { email: $v("email"), password: $v("pw") };
        if (mode === "register") body.name = $v("name");
        const d = await api(`/api/auth/${mode}`, { method: "POST", body });
        S.token = d.token; S.user = d.user;
        localStorage.setItem("token", d.token); localStorage.setItem("user", JSON.stringify(d.user));
        location.hash = "#/";
      } catch (e) { document.getElementById("err").innerHTML = errBox(e.message); }
    };
  };
  draw();
}

/* ---------------------------------------------------------------- home */
async function viewHome() {
  app.innerHTML = spinner("Loading roadmaps...");
  const [rms, levels] = await Promise.all([api("/api/roadmaps"), api("/api/levels")]);
  const lvlOpts = levels.map((l) => `<option value="${l.key}">${esc(l.label)}</option>`).join("");
  app.innerHTML = `
    <h1 class="text-2xl font-bold mb-1">Your learning roadmaps</h1>
    <p class="text-slate-400 text-sm mb-5">Pick a roadmap, or let AI build one for any topic at any level.</p>
    <div class="${cls.card} p-4 mb-6">
      <h2 class="font-semibold mb-2">Generate a roadmap with AI</h2>
      <form id="gen" class="grid md:grid-cols-12 gap-3">
        <input id="topic" class="${cls.input} md:col-span-5" placeholder="e.g. Photosynthesis, Organic Chemistry, Quantum Mechanics" required />
        <select id="level" class="${cls.input} md:col-span-3">${lvlOpts}</select>
        <input id="count" type="number" min="5" max="14" value="8" class="${cls.input} md:col-span-1" title="Number of modules" />
        <button id="genbtn" class="${cls.btn} md:col-span-3">Generate roadmap</button>
      </form>
      <div id="generr"></div>
    </div>
    <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
      ${rms.map((r) => `
        <a href="#/roadmap/${r.slug}" class="${cls.card} p-4 hover:border-sky-600 block">
          <span class="text-xs px-2 py-0.5 rounded-full bg-sky-950 text-sky-300 border border-sky-800">${esc(r.level_label)}</span>
          <h3 class="font-semibold mt-2">${esc(r.title)}</h3>
          <p class="text-sm text-slate-400 mt-1 line-clamp-3">${esc(r.description)}</p>
          <div class="mt-3 h-2 bg-slate-800 rounded"><div class="h-2 bg-emerald-500 rounded" style="width:${(100 * r.mastered / Math.max(1, r.module_count)).toFixed(0)}%"></div></div>
          <div class="text-xs text-slate-500 mt-1">${r.mastered}/${r.module_count} modules mastered</div>
        </a>`).join("")}
    </div>`;
  document.getElementById("gen").onsubmit = async (ev) => {
    ev.preventDefault();
    const b = document.getElementById("genbtn");
    b.disabled = true; b.innerHTML = '<span class="spinner"></span> Generating...';
    try {
      const gv = (i) => document.getElementById(i).value;
      const d = await api("/api/roadmaps/generate", { method: "POST", body: { topic: gv("topic"), level: gv("level"), count: +gv("count") } });
      location.hash = "#/roadmap/" + d.slug;
    } catch (e) {
      document.getElementById("generr").innerHTML = errBox(e.message);
      b.disabled = false; b.textContent = "Generate roadmap";
    }
  };
}

/* ---------------------------------------------------------------- roadmap */
const STATUS = {
  locked: ["Locked", "bg-slate-800 text-slate-400"],
  available: ["Ready", "bg-sky-950 text-sky-300"],
  in_progress: ["In progress", "bg-amber-950 text-amber-300"],
  mastered: ["Mastered", "bg-emerald-950 text-emerald-300"],
};
const badge = (label, val, color) => `<span class="text-xs px-2 py-0.5 rounded-md ${color}">${label}: <b>${val}</b></span>`;

async function viewRoadmap(slug) {
  app.innerHTML = spinner("Loading roadmap...");
  const d = await api(`/api/roadmaps/${slug}?track=${S.track}`);
  const phases = {};
  d.modules.forEach((m) => (phases[m.phase] = phases[m.phase] || []).push(m));
  const tbtn = (t, label) =>
    `<button data-t="${t}" class="px-4 py-2 text-sm rounded-lg ${S.track === t ? "bg-sky-600 text-white" : "bg-slate-800 text-slate-300"}">${label}</button>`;
  app.innerHTML = `
    <a href="#/" class="text-sky-400 text-sm">&larr; All roadmaps</a>
    <div class="flex flex-wrap items-start justify-between gap-4 mt-2 mb-5">
      <div><span class="text-xs px-2 py-0.5 rounded-full bg-sky-950 text-sky-300 border border-sky-800">${esc(d.roadmap.level_label)}</span>
        <h1 class="text-2xl font-bold mt-2">${esc(d.roadmap.title)}</h1>
        <p class="text-slate-400 text-sm max-w-2xl">${esc(d.roadmap.description)}</p></div>
      <div class="text-right">
        <div class="inline-flex gap-1 bg-slate-900 p-1 rounded-xl border border-slate-800">${tbtn("FULL", "Full Roadmap")}${tbtn("ACCELERATED", "Accelerated")}</div>
        <div class="text-xs text-slate-500 mt-1">Showing ${d.visible_modules} of ${d.total_modules} modules ${S.track === "ACCELERATED" ? "(weightage &ge; 70% or future scope &ge; 8)" : ""}</div>
      </div>
    </div>
    ${Object.entries(phases).map(([ph, mods]) => `
      <h2 class="text-sm uppercase tracking-wider text-slate-500 mt-6 mb-2">${esc(ph)}</h2>
      <div class="space-y-3">${mods.map(nodeHtml).join("")}</div>`).join("")}
    <div class="${cls.card} p-4 mt-8">
      <h2 class="font-semibold mb-2">Skill-gap radar</h2>
      <div id="skills" class="max-w-xl mx-auto">${spinner("Loading skills...")}</div>
    </div>`;
  app.querySelectorAll("[data-t]").forEach((b) => (b.onclick = () => { S.track = b.dataset.t; localStorage.setItem("track", S.track); viewRoadmap(slug); }));
  app.querySelectorAll("[data-open]").forEach((a) => (a.onclick = (e) => {
    if (a.dataset.locked) { e.preventDefault(); toast("Locked. Pass the prerequisite quizzes (80%+) first."); }
  }));
  drawSkills(slug);
}

function nodeHtml(m) {
  const [label, color] = STATUS[m.status];
  const mt = m.metrics;
  return `<a data-open="1" ${m.status === "locked" ? 'data-locked="1"' : ""} href="#/module/${m.module_id}"
    class="${cls.card} p-4 block hover:border-sky-600 ${m.status === "locked" ? "opacity-60" : ""}">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="font-semibold">${m.order}. ${esc(m.title)}</div>
      <span class="text-xs px-2 py-0.5 rounded-full ${color}">${label}${m.best_score ? ` &middot; best ${m.best_score}%` : ""}</span>
    </div>
    <div class="flex flex-wrap gap-2 mt-2">
      ${badge("Exam/Interview", mt.interview_weightage, "bg-violet-950 text-violet-300")}
      ${badge("Theory", mt.theoretical_importance + "/10", "bg-blue-950 text-blue-300")}
      ${badge("Future scope", mt.future_scope + "/10", "bg-teal-950 text-teal-300")}
      ${badge("Time", mt.estimated_time_minutes + " min", "bg-slate-800 text-slate-300")}
    </div></a>`;
}

async function drawSkills(slug) {
  const box = document.getElementById("skills");
  try {
    const s = await api(`/api/roadmaps/${slug}/skills`);
    box.innerHTML = `<canvas id="radar"></canvas><p class="text-sm text-slate-400 mt-3">${
      s.weak_phases.length ? "Needs work: " + s.weak_phases.map(esc).join(", ") : "No weak areas. Nice."}</p>`;
    new Chart(document.getElementById("radar"), {
      type: "radar",
      data: { labels: s.phases.map((p) => p.phase), datasets: [{ label: "Avg best score (%)", data: s.phases.map((p) => p.score),
        backgroundColor: "rgba(56,189,248,.25)", borderColor: "#38bdf8", pointBackgroundColor: "#38bdf8" }] },
      options: { scales: { r: { min: 0, max: 100, ticks: { color: "#94a3b8", backdropColor: "transparent" }, grid: { color: "#334155" },
        angleLines: { color: "#334155" }, pointLabels: { color: "#cbd5e1" } } }, plugins: { legend: { labels: { color: "#cbd5e1" } } } },
    });
  } catch (e) { box.innerHTML = errBox(e.message); }
}

/* ---------------------------------------------------------------- module workspace */
async function viewModule(id) {
  app.innerHTML = spinner("Opening module (the first open generates the lesson with AI, ~15-30 s)...");
  const d = await api(`/api/modules/${id}?track=${S.track}`);
  const m = d.module, c = d.content || {}, rm = d.roadmap, mt = m.metrics;
  const accel = S.track === "ACCELERATED";
  const sb = c.sandbox || {};
  S.chat[id] = S.chat[id] || [];
  app.innerHTML = `
    <a href="#/roadmap/${rm.slug}" class="text-sky-400 text-sm">&larr; ${esc(rm.title)}</a>
    <h1 class="text-2xl font-bold mt-1">${esc(m.title)}</h1>
    <div class="flex flex-wrap gap-2 my-3">
      ${badge("Exam/Interview", mt.interview_weightage, "bg-violet-950 text-violet-300")}
      ${badge("Theory", mt.theoretical_importance + "/10", "bg-blue-950 text-blue-300")}
      ${badge("Future scope", mt.future_scope + "/10", "bg-teal-950 text-teal-300")}
      ${badge("Time", mt.estimated_time_minutes + " min", "bg-slate-800 text-slate-300")}
      ${badge("Track", S.track, "bg-slate-800 text-slate-300")}
    </div>
    <div class="grid lg:grid-cols-3 gap-5">
      <section class="lg:col-span-2">
        <div class="flex gap-2 mb-3" id="tabs">
          <button data-tab="learn" class="${cls.btn}">Learn</button>
          <button data-tab="videos" class="${cls.btn2}">Videos</button>
          <button data-tab="quiz" class="${cls.btn2}">Mastery quiz</button>
        </div>
        <div id="tabbody" class="${cls.card} p-5"></div>
        <div class="flex justify-between mt-4">
          ${d.prev ? `<a class="${cls.btn2}" href="#/module/${d.prev}">&larr; Previous</a>` : "<span></span>"}
          ${d.next ? `<a class="${cls.btn2}" href="#/module/${d.next}">Next &rarr;</a>` : ""}
        </div>
      </section>
      <aside class="${cls.card} p-4 flex flex-col h-[75vh] lg:sticky lg:top-20">
        <div class="flex items-center justify-between mb-2">
          <h2 class="font-semibold">AI Tutor</h2>
          <select id="mode" class="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs">
            <option value="normal">Explain</option><option value="socratic">Socratic</option></select>
        </div>
        <div id="msgs" class="flex-1 overflow-y-auto space-y-3 text-sm pr-1"></div>
        <form id="chatf" class="mt-3 flex gap-2">
          <input id="chatin" class="${cls.input}" placeholder="Ask about this module..." autocomplete="off" />
          <button class="${cls.btn}">Send</button>
        </form>
      </aside>
    </div>`;

  const body = document.getElementById("tabbody");
  const tabs = {
    learn: () => {
      body.innerHTML = `<div class="prose-md">
        ${accel ? `<div class="bg-sky-950/40 border border-sky-900 rounded-lg p-4 mb-4"><b>Fast-track summary</b>${md(c.accelerated_summary)}</div>
          <details class="mb-4"><summary class="cursor-pointer text-sky-400">Show full theory</summary>${md(c.theoretical_summary)}</details>`
          : md(c.theoretical_summary)}
        <h2>Worked examples</h2>${(c.examples || []).map((e) => `<div class="bg-slate-950 rounded-lg p-3 my-2">${md(e)}</div>`).join("")}
        <h2>Real-world scenarios</h2>${(c.real_world_scenarios || []).map((e) => `<div class="bg-slate-950 rounded-lg p-3 my-2">${md(e)}</div>`).join("")}
        ${sb.code ? `<h2>Sandbox: ${esc(sb.title)}</h2><pre><code>${esc(sb.code)}</code></pre>${md(sb.explanation)}` : ""}
      </div>`;
    },
    videos: () => loadVideos(body, id),
    quiz: () => quizStart(body, id),
  };
  document.querySelectorAll("#tabs button").forEach((b) => (b.onclick = () => {
    document.querySelectorAll("#tabs button").forEach((x) => (x.className = x === b ? cls.btn : cls.btn2));
    tabs[b.dataset.tab]();
  }));
  tabs.learn();
  initChat(id);
}

/* ---------------------------------------------------------------- chat */
function initChat(id) {
  const msgs = document.getElementById("msgs");
  const draw = () => {
    msgs.innerHTML = S.chat[id].length
      ? S.chat[id].map((h) => `<div class="${h.role === "user" ? "text-right" : ""}"><div class="inline-block max-w-[92%] text-left rounded-lg px-3 py-2 ${h.role === "user" ? "bg-sky-700" : "bg-slate-800"} prose-md">${h.role === "user" ? esc(h.content) : md(h.content)}</div></div>`).join("")
      : `<div class="text-slate-500">Ask anything about this module. Try Socratic mode to be guided instead of told.</div>`;
    msgs.scrollTop = msgs.scrollHeight;
  };
  draw();
  document.getElementById("chatf").onsubmit = async (ev) => {
    ev.preventDefault();
    const inp = document.getElementById("chatin");
    const text = inp.value.trim();
    if (!text) return;
    inp.value = "";
    const history = S.chat[id].slice();
    S.chat[id].push({ role: "user", content: text });
    draw();
    msgs.insertAdjacentHTML("beforeend", `<div id="typing" class="text-slate-500"><span class="spinner"></span> thinking...</div>`);
    try {
      const r = await api(`/api/modules/${id}/chat`, { method: "POST", body: { message: text, history, mode: document.getElementById("mode").value } });
      S.chat[id].push({ role: "assistant", content: r.answer });
    } catch (e) { S.chat[id].push({ role: "assistant", content: "Error: " + e.message }); }
    draw();
  };
}

/* ---------------------------------------------------------------- videos */
async function loadVideos(body, id) {
  body.innerHTML = spinner("Finding top tutorials...");
  try {
    const d = await api(`/api/modules/${id}/videos`);
    if (!d.videos.length) { body.innerHTML = "<p class='text-slate-400'>No videos found.</p>"; return; }
    body.innerHTML = `<div id="player"></div><h3 class="font-semibold mb-2">Recommended videos</h3>
      <div class="grid sm:grid-cols-2 gap-3">${d.videos.map((v) => `
        <button data-v="${v.id}" data-title="${esc(v.title)}" class="text-left ${cls.card} overflow-hidden hover:border-sky-600">
          <img src="${esc(v.thumbnail)}" class="w-full" alt="" />
          <div class="p-2"><div class="text-sm font-medium line-clamp-2">${esc(v.title)}</div>
          <div class="text-xs text-slate-500 mt-1">${esc(v.channel)} &middot; ${esc(v.duration)} &middot; ${v.views.toLocaleString()} views</div></div>
        </button>`).join("")}</div>`;
    body.querySelectorAll("[data-v]").forEach((b) => (b.onclick = () => playVideo(b.dataset.v, b.dataset.title)));
  } catch (e) { body.innerHTML = errBox(e.message); }
}

async function playVideo(vid, title) {
  const box = document.getElementById("player");
  const embed = (t) => `<iframe class="w-full aspect-video rounded-lg" src="https://www.youtube.com/embed/${vid}?rel=0${t ? "&start=" + t + "&autoplay=1" : ""}" allowfullscreen></iframe>`;
  box.innerHTML = `<div class="mb-4">${embed(0)}<div id="sum" class="mt-3">${spinner("Summarising video (transcript + AI)...")}</div></div>`;
  box.scrollIntoView({ behavior: "smooth" });
  for (let i = 0; i < 45; i++) {
    let r;
    try { r = await api(`/api/youtube/${vid}/summary?title=${encodeURIComponent(title)}`); }
    catch (e) { document.getElementById("sum").innerHTML = errBox(e.message); return; }
    if (!document.getElementById("sum")) return; // user navigated away
    if (r.status === "done") {
      const s = r.data;
      document.getElementById("sum").innerHTML = `
        <div class="prose-md"><h3>Summary</h3><p>${esc(s.executive_summary)}</p>
        <h3>Key takeaways</h3><ul>${s.takeaways.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>
        <h3>Chapters</h3></div>
        <div class="space-y-1">${s.chapters.map((c) => `<button data-t="${c.time_seconds}" class="block w-full text-left text-sm px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700"><span class="text-sky-400 mr-2">${esc(c.time)}</span>${esc(c.title)}</button>`).join("")}</div>`;
      document.querySelectorAll("#sum [data-t]").forEach((b) => (b.onclick = () => {
        box.querySelector("iframe").outerHTML = embed(b.dataset.t);
      }));
      return;
    }
    if (r.status === "error") { document.getElementById("sum").innerHTML = errBox(r.error); return; }
    await new Promise((res) => setTimeout(res, 3000));
  }
  document.getElementById("sum").innerHTML = errBox("Summary is taking too long. Try again in a minute.");
}

/* ---------------------------------------------------------------- quiz */
function quizStart(body, id) {
  body.innerHTML = `<h3 class="font-semibold mb-1">Mastery quiz</h3>
    <p class="text-sm text-slate-400 mb-3">60% real-world scenarios, 20% theory, 20% code/debugging. You need 80% to master this module and unlock what comes next.</p>
    <button id="qstart" class="${cls.btn}">Start new quiz</button><div id="qerr"></div>`;
  document.getElementById("qstart").onclick = async (ev) => {
    ev.target.disabled = true; ev.target.innerHTML = '<span class="spinner"></span> Generating quiz...';
    try {
      const q = await api(`/api/modules/${id}/quiz`, { method: "POST" });
      quizRender(body, id, q);
    } catch (e) { document.getElementById("qerr").innerHTML = errBox(e.message); ev.target.disabled = false; ev.target.textContent = "Start new quiz"; }
  };
}

function quizRender(body, id, q) {
  const tag = { scenario: "Scenario", theory: "Theory", code: "Code / debug" };
  body.innerHTML = `<form id="qf" class="space-y-5">
    ${q.questions.map((x, i) => `
      <div><div class="text-xs text-sky-400 mb-1">Q${i + 1} &middot; ${tag[x.type] || x.type}</div>
      <div class="font-medium mb-2 prose-md">${md(x.question)}</div>
      ${x.options.map((o, j) => `<label class="flex gap-2 items-start p-2 rounded hover:bg-slate-800 cursor-pointer text-sm">
        <input type="radio" name="q${i}" value="${j}" class="mt-1" /><span>${esc(o)}</span></label>`).join("")}</div>`).join("")}
    <button class="${cls.btn}">Submit answers</button><div id="qerr"></div></form>`;
  document.getElementById("qf").onsubmit = async (ev) => {
    ev.preventDefault();
    const answers = q.questions.map((_, i) => { const c = document.querySelector(`input[name=q${i}]:checked`); return c ? +c.value : null; });
    const btn = ev.target.querySelector("button"); btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Grading...';
    try {
      const r = await api(`/api/quiz/${q.quiz_id}/submit`, { method: "POST", body: { answers } });
      quizResult(body, id, r);
    } catch (e) { document.getElementById("qerr").innerHTML = errBox(e.message); btn.disabled = false; btn.textContent = "Submit answers"; }
  };
}

function quizResult(body, id, r) {
  body.innerHTML = `
    <div class="text-center mb-4">
      <div class="text-4xl font-bold ${r.passed ? "text-emerald-400" : "text-amber-400"}">${r.score}%</div>
      <div class="text-sm text-slate-400">${r.correct}/${r.total} correct &middot; ${r.passed ? "Module mastered! Next modules are unlocked." : `Need ${r.threshold}% to master this module`}</div>
      <div class="flex justify-center gap-3 mt-2 text-xs">${Object.entries(r.breakdown).map(([k, v]) => `<span class="px-2 py-1 rounded bg-slate-800">${esc(k)}: ${v.correct}/${v.total}</span>`).join("")}</div>
    </div>
    ${r.remediation ? `<div class="bg-amber-950/30 border border-amber-900 rounded-lg p-4 mb-4 prose-md"><b>Targeted remediation</b>${md(r.remediation)}</div>` : ""}
    <div class="space-y-3">${r.results.map((x, i) => `
      <div class="rounded-lg p-3 border ${x.correct ? "border-emerald-900 bg-emerald-950/20" : "border-red-900 bg-red-950/20"}">
        <div class="text-sm font-medium">Q${i + 1}. ${esc(x.question)}</div>
        <div class="text-xs mt-1">Your answer: ${x.your_index === null ? "(none)" : esc(x.options[x.your_index])}</div>
        ${x.correct ? "" : `<div class="text-xs text-emerald-300">Correct: ${esc(x.options[x.answer_index])}</div>`}
        <div class="text-xs text-slate-400 mt-1">${esc(x.explanation)}</div></div>`).join("")}</div>
    <div class="mt-4 flex gap-2"><button id="retry" class="${cls.btn}">Take a fresh quiz</button></div>`;
  document.getElementById("retry").onclick = () => quizStart(body, id);
}

route();
