const $ = (id) => document.getElementById(id);
let DEMO = { alerts: [] };
let HEALTH = { writes_enabled: false, memory: "", llm: "", mode: "" };

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
));

function banner(text, kind) {
  const el = $("banner");
  if (!text) { el.hidden = true; el.textContent = ""; el.className = "banner"; return; }
  el.hidden = false;
  el.textContent = text;
  el.className = "banner " + (kind || "warn");
}

function describeMemory(name) {
  if (name === "hindsight") return "memory: Hindsight (live bank)";
  if (name === "fake-offline") return "memory: fake store (demo, resets per process)";
  return "memory: " + (name || "unknown");
}

function describeLlm(name) {
  if (name === "groq") return "llm: Groq (live)";
  if (name === "offline-template") return "llm: offline template";
  return "llm: " + (name || "unknown");
}

async function getJson(url, options) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 45000);
  try {
    const r = await fetch(url, { ...(options || {}), signal: controller.signal });
    const text = await r.text();
    let body = null;
    try { body = text ? JSON.parse(text) : null; } catch { body = { error: text }; }
    if (!r.ok) {
      const msg = body && body.error ? body.error : "HTTP " + r.status;
      throw new Error(msg);
    }
    return body;
  } finally {
    clearTimeout(timer);
  }
}

async function boot() {
  try {
    HEALTH = await getJson("/api/health");
    $("b-mem").textContent = describeMemory(HEALTH.memory);
    $("b-mem").className = "badge " + (HEALTH.memory === "hindsight" ? "live" : "off");
    $("b-llm").textContent = describeLlm(HEALTH.llm);
    $("b-llm").className = "badge " + (HEALTH.llm === "groq" ? "live" : "off");
    $("memlabel").textContent = HEALTH.memory === "hindsight"
      ? "Memory ON (Hindsight recall + retain)"
      : "Memory ON (demo store recall + retain)";
    if (HEALTH.mode === "offline") {
      banner("Offline demo: synthetic incident data and a fake in-process memory store. Answers come from the offline template, not a live model.", "info");
    }
    if (!HEALTH.writes_enabled) {
      $("resolve").disabled = true;
      $("savepref").disabled = true;
      $("write-note").textContent = "Write endpoints are locked on this deployment. Set RECURRENCE_WRITE_TOKEN to enable them.";
    }
    DEMO = await getJson("/api/demo");
    $("engineer").innerHTML = DEMO.engineers.map((e) => `<option>${esc(e)}</option>`).join("");
    $("service").innerHTML = DEMO.services.map((s) => `<option>${esc(s)}</option>`).join("");
    $("demo").innerHTML = `<option value="">(type your own)</option>` + DEMO.alerts
      .map((a, i) => `<option value="${i}">${esc(a.id)} · ${esc(a.label)}</option>`).join("");
  } catch (e) {
    banner("Could not load the console: " + e.message, "warn");
    $("answer").textContent = "The API is not reachable. Check the server logs.";
  }
}

$("demo").onchange = () => {
  const a = DEMO.alerts[$("demo").value];
  if (!a) return;
  $("alert").value = a.alert;
  $("engineer").value = a.engineer;
  $("service").value = a.service;
};

$("memory").onchange = () => {
  $("memlabel").textContent = $("memory").checked
    ? (HEALTH.memory === "hindsight" ? "Memory ON (Hindsight recall + retain)" : "Memory ON (demo store recall + retain)")
    : "Memory OFF (stateless LLM)";
};

function memCard(m) {
  const kind = (m.metadata && m.metadata.kind) || m.type || "memory";
  const id = (m.metadata && m.metadata.incident_id) || m.document_id || "";
  const ago = m.days_ago == null ? "" : (m.days_ago === 0 ? "today" : `${m.days_ago} days ago`);
  return `<div class="mem ${esc(kind)}"><div class="meta"><span class="chip">${esc(ago)}</span><span>${esc(kind)}</span><span>${esc(id)}</span></div>${esc(m.text)}</div>`;
}

$("ask").onclick = async () => {
  $("ask").disabled = true;
  $("answer").textContent = "Thinking…";
  $("answer").className = "";
  const a = DEMO.alerts[$("demo").value];
  const body = {
    alert: $("alert").value,
    engineer: $("engineer").value,
    service: $("service").value,
    memory_on: $("memory").checked,
    now: a ? a.now : null,
  };
  try {
    const j = await getJson("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    $("answer").textContent = j.answer;
    $("mode").textContent = j.memory_on ? `with memory · ${j.memories.length} recalled` : "no memory";
    $("mode").className = "badge " + (j.memory_on ? "live" : "off");
    $("prefs").innerHTML = (j.preferences || []).map(memCard).join("");
    $("mems").innerHTML = j.memory_on
      ? (j.memories.map(memCard).join("") || `<div class="empty">Nothing similar in memory yet.</div>`)
      : `<div class="empty">Memory is off. The agent sees only this page.</div>`;
    $("trace").textContent = JSON.stringify({ tool_trace: j.tool_trace, memory_errors: j.memory_errors, backend: j.backend }, null, 2);
    if ((j.memory_errors || []).length) {
      banner("Memory reported an error on this page. Some recalled items may be missing. See Tool calls and errors.", "warn");
    } else if (HEALTH.mode === "offline") {
      banner("Offline demo: synthetic incident data and a fake in-process memory store. Answers come from the offline template, not a live model.", "info");
    }
  } catch (e) {
    $("answer").textContent = "Error: " + e.message;
  }
  $("ask").disabled = false;
};

function writeHeaders() {
  const token = $("write-token").value.trim();
  return token ? { "Content-Type": "application/json", "X-Recurrence-Token": token } : { "Content-Type": "application/json" };
}

$("resolve").onclick = async () => {
  const body = {
    service: $("service").value,
    engineer: $("engineer").value,
    summary: $("r-summary").value,
    root_cause: $("r-root").value,
    fix: $("r-fix").value,
    did_not_work: $("r-dnw").value,
  };
  try {
    const j = await getJson("/api/resolve", { method: "POST", headers: writeHeaders(), body: JSON.stringify(body) });
    $("r-msg").textContent = `retained ${j.retained} memories`;
  } catch (e) {
    $("r-msg").textContent = "retain failed: " + e.message;
  }
};

$("savepref").onclick = async () => {
  try {
    await getJson("/api/preference", {
      method: "POST",
      headers: writeHeaders(),
      body: JSON.stringify({ engineer: $("engineer").value, text: $("pref").value }),
    });
    $("r-msg").textContent = "preference retained";
  } catch (e) {
    $("r-msg").textContent = "retain failed: " + e.message;
  }
};

boot();
