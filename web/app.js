/**
 * Dexibo web client — streaming chat + markets watchlist
 */
(function () {
  "use strict";

  const WELCOME =
    "Hi — I'm **Dexibo**, lite fintech intelligence.\n\n" +
    "Ask about ISAs, Open Banking, ETFs, compounding, or delayed quotes. " +
    "I educate and calculate; I don't give personalised financial advice.\n\n" +
    "_Educational only — not financial advice._";

  const transcript = document.getElementById("transcript");
  const composer = document.getElementById("composer");
  const input = document.getElementById("messageInput");
  const sendBtn = document.getElementById("sendBtn");
  const backendLabel = document.getElementById("backendLabel");
  const backendLabelMobile = document.getElementById("backendLabelMobile");
  const versionLabel = document.getElementById("versionLabel");
  const marketsRow = document.getElementById("marketsRow");
  const marketsLabel = document.getElementById("marketsLabel");
  const marketsRefresh = document.getElementById("marketsRefresh");

  let sessionId = null;
  let busy = false;
  let abortController = null;
  let lastUserMessage = null;
  let apiKey = localStorage.getItem('dexibo_api_key') || '';
  let watchTimer = null;

  function apiHeaders(extra = {}) {
    const h = { Accept: 'application/json', ...extra };
    if (apiKey) h['Authorization'] = 'Bearer ' + apiKey;
    return h;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /** Lightweight markdown-ish → HTML (bold, italic, code, lists, paragraphs). */
  function renderMarkdown(src) {
    let text = escapeHtml(src);

    // Fenced code blocks
    text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_m, _lang, code) => {
      return `<pre><code>${code.replace(/^\n|\n$/g, "")}</code></pre>`;
    });

    // Inline code
    text = text.replace(/`([^`\n]+)`/g, "<code>$1</code>");

    // Bold then italic
    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
    text = text.replace(/(^|[^_])_([^_\n]+)_(?!_)/g, "$1<em>$2</em>");

    const lines = text.split("\n");
    const out = [];
    let listType = null; // "ul" | "ol" | null

    function closeList() {
      if (listType) {
        out.push(listType === "ul" ? "</ul>" : "</ol>");
        listType = null;
      }
    }

    for (const line of lines) {
      const ul = line.match(/^\s*[-*]\s+(.+)$/);
      const ol = line.match(/^\s*\d+\.\s+(.+)$/);
      if (ul) {
        if (listType !== "ul") {
          closeList();
          out.push("<ul>");
          listType = "ul";
        }
        out.push(`<li>${ul[1]}</li>`);
      } else if (ol) {
        if (listType !== "ol") {
          closeList();
          out.push("<ol>");
          listType = "ol";
        }
        out.push(`<li>${ol[1]}</li>`);
      } else if (line.trim() === "") {
        closeList();
        out.push("");
      } else if (line.startsWith("<pre>")) {
        closeList();
        out.push(line);
      } else {
        closeList();
        out.push(`<p>${line}</p>`);
      }
    }
    closeList();

    // Collapse empty separators between paragraphs
    return out.filter((x, i, a) => !(x === "" && (a[i - 1] === "" || !a[i - 1]))).join("\n");
  }

  function attachAssistantActions(wrap, rawText) {
    if (!wrap || wrap.querySelector(".msg-actions")) return;
    const actions = document.createElement("div");
    actions.className = "msg-actions";
    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(rawText || "");
        copyBtn.textContent = "Copied";
        setTimeout(() => (copyBtn.textContent = "Copy"), 1200);
      } catch (_) {
        copyBtn.textContent = "Failed";
      }
    });
    const regenBtn = document.createElement("button");
    regenBtn.type = "button";
    regenBtn.textContent = "Regenerate";
    regenBtn.addEventListener("click", () => {
      if (lastUserMessage) sendMessage(lastUserMessage, { regenerate: true });
    });
    actions.appendChild(copyBtn);
    actions.appendChild(regenBtn);
    wrap.appendChild(actions);
  }

  function renderCitations(wrap, citations) {
    if (!wrap || !citations || !citations.length) return;
    let row = wrap.querySelector(".citation-chips");
    if (!row) {
      row = document.createElement("div");
      row.className = "citation-chips";
      wrap.appendChild(row);
    }
    row.innerHTML = "";
    for (const c of citations) {
      const chip = document.createElement("span");
      chip.className = "citation-chip";
      const score = c.score != null ? ` · ${Number(c.score).toFixed(2)}` : "";
      chip.textContent = `${c.title || c.doc_id || "source"}${score}`;
      chip.title = c.doc_id || "";
      row.appendChild(chip);
    }
  }

  function appendMessage(role, content, { html = false, typing = false, citations = null } = {}) {
    const wrap = document.createElement("div");
    wrap.className = `msg ${role}`;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (typing) {
      bubble.innerHTML =
        '<div class="typing" aria-label="Dexibo is thinking"><span></span><span></span><span></span></div>';
    } else if (html) {
      bubble.innerHTML = content;
    } else {
      bubble.innerHTML = renderMarkdown(content);
    }
    wrap.appendChild(bubble);
    if (role === "assistant" && !typing) {
      attachAssistantActions(wrap, typeof content === "string" ? content : bubble.innerText);
      renderCitations(wrap, citations);
    }
    transcript.appendChild(wrap);
    transcript.scrollTop = transcript.scrollHeight;
    return wrap;
  }

  function startStreamingBubble() {
    const wrap = document.createElement("div");
    wrap.className = "msg assistant streaming";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = '<span class="stream-cursor" aria-hidden="true"></span>';
    wrap.appendChild(bubble);
    transcript.appendChild(wrap);
    transcript.scrollTop = transcript.scrollHeight;
    return { wrap, bubble, raw: "" };
  }

  function updateStreamingBubble(state, chunk) {
    state.raw += chunk;
    state.bubble.innerHTML =
      renderMarkdown(state.raw) +
      '<span class="stream-cursor" aria-hidden="true"></span>';
    transcript.scrollTop = transcript.scrollHeight;
  }

  function finishStreamingBubble(state, citations) {
    state.wrap.classList.remove("streaming");
    state.bubble.innerHTML = renderMarkdown(state.raw || "(empty reply)");
    attachAssistantActions(state.wrap, state.raw || "");
    renderCitations(state.wrap, citations || state.citations || null);
  }

  function setBusy(on) {
    busy = on;
    sendBtn.disabled = on;
    input.disabled = on;
    const stopBtn = document.getElementById('stopBtn');
    if (stopBtn) stopBtn.classList.toggle('hidden', !on);
  }

  function autoResize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 140) + "px";
  }

  function setBackend(backend) {
    if (!backend) return;
    backendLabel.textContent = backend;
    backendLabelMobile.textContent = backend;
  }

  async function loadHealth() {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error("health " + res.status);
      const data = await res.json();
      setBackend(data.backend || "unknown");
      if (data.version) versionLabel.textContent = data.version;
      const flags = data.flags || {};
      document.querySelectorAll(".pill").forEach((el) => {
        const key = el.getAttribute("data-flag");
        let on = false;
        if (key === "tools") on = true;
        else if (key === "rag") on = !!flags.rag;
        else if (key === "guardrails") on = !!flags.guardrails;
        else if (key === "quotes") on = !!flags.quotes;
        el.classList.toggle("on", on);
      });
    } catch (err) {
      setBackend("offline");
      console.warn("health check failed", err);
    }
  }

  function formatPrice(q) {
    if (!q || !q.ok) return "—";
    const n = Number(q.price);
    if (!Number.isFinite(n)) return "—";
    if (n >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
    if (n >= 1) return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
    return n.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }

  function formatPct(q) {
    if (!q || !q.ok || q.change_pct == null) return null;
    const n = Number(q.change_pct);
    if (!Number.isFinite(n)) return null;
    const sign = n > 0 ? "+" : "";
    return { text: `${sign}${n.toFixed(2)}%`, up: n >= 0 };
  }

  function renderWatchlist(data) {
    if (!marketsRow) return;
    if (data && data.label && marketsLabel) {
      marketsLabel.textContent = data.label;
    }
    const quotes = (data && data.quotes) || [];
    if (!quotes.length) {
      marketsRow.innerHTML =
        '<span class="markets-loading">No quotes (check DEXIBO_QUOTES / network)</span>';
      return;
    }
    marketsRow.innerHTML = "";
    for (const q of quotes) {
      const card = document.createElement("div");
      card.className = "market-chip" + (q.ok ? "" : " is-err");
      card.setAttribute("role", "listitem");
      const sym = escapeHtml(q.symbol || "?");
      if (!q.ok) {
        card.innerHTML =
          `<span class="m-sym">${sym}</span>` +
          `<span class="m-price muted">n/a</span>`;
        card.title = q.error || "quote unavailable";
      } else {
        const pct = formatPct(q);
        let pctHtml = "";
        if (pct) {
          pctHtml = `<span class="m-pct ${pct.up ? "up" : "down"}">${escapeHtml(
            pct.text
          )}</span>`;
        }
        const cur = q.currency ? `<span class="m-cur">${escapeHtml(q.currency)}</span>` : "";
        card.innerHTML =
          `<span class="m-sym">${sym}</span>` +
          `<span class="m-price">${escapeHtml(formatPrice(q))}</span>` +
          cur +
          pctHtml;
        card.title = `${q.symbol} · ${q.source || "delayed"} · as of ${q.as_of || "—"}`;
      }
      marketsRow.appendChild(card);
    }
  }

  async function loadWatchlist() {
    if (!marketsRow) return;
    try {
      if (marketsRefresh) marketsRefresh.classList.add("spinning");
      const res = await fetch("/api/watchlist");
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        marketsRow.innerHTML =
          '<span class="markets-loading">Watchlist unavailable</span>';
        return;
      }
      renderWatchlist(data);
    } catch (err) {
      console.warn("watchlist failed", err);
      marketsRow.innerHTML =
        '<span class="markets-loading">Watchlist offline</span>';
    } finally {
      if (marketsRefresh) marketsRefresh.classList.remove("spinning");
    }
  }

  function scheduleWatchlist() {
    if (watchTimer) clearInterval(watchTimer);
    watchTimer = setInterval(() => {
      if (document.visibilityState === "visible") loadWatchlist();
    }, 60000);
  }

  async function sendViaStream(text) {
    abortController = new AbortController();
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      signal: abortController.signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    });
    if (!res.ok || !res.body) {
      const errBody = await res.json().catch(() => ({}));
      const detail = errBody.detail || res.statusText || "stream failed";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }

    const state = startStreamingBubble();
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let sawDone = false;
    let errorMsg = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const block of parts) {
        const lines = block.split("\n");
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const raw = line.slice(5).trim();
          if (!raw || raw === "[DONE]") continue;
          let evt;
          try {
            evt = JSON.parse(raw);
          } catch {
            continue;
          }
          if (evt.type === "token" && evt.text) {
            updateStreamingBubble(state, evt.text);
          } else if (evt.type === "done") {
            sawDone = true;
            if (evt.session_id) sessionId = evt.session_id;
            if (evt.backend) setBackend(evt.backend);
            state.citations = evt.citations || null;
          } else if (evt.type === "error") {
            errorMsg = evt.message || "stream error";
          }
        }
      }
    }

    if (errorMsg) {
      state.wrap.remove();
      throw new Error(errorMsg);
    }
    if (!state.raw && !sawDone) {
      state.wrap.remove();
      throw new Error("empty stream");
    }
    finishStreamingBubble(state, state.citations);
  }

  async function sendViaJson(text) {
    const thinking = appendMessage("assistant", "", { typing: true });
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      });
      const data = await res.json().catch(() => ({}));
      thinking.remove();
      if (!res.ok) {
        const detail = data.detail || res.statusText || "Request failed";
        appendMessage("assistant", `Sorry — something went wrong: ${detail}`);
        return;
      }
      if (data.session_id) sessionId = data.session_id;
      if (data.backend) setBackend(data.backend);
      appendMessage("assistant", data.reply || "(empty reply)", {
        citations: data.citations || null,
      });
    } catch (err) {
      thinking.remove();
      throw err;
    }
  }

  async function sendMessage(raw, { regenerate = false } = {}) {
    const text = (raw || "").trim();
    if (!text || busy) return;

    lastUserMessage = text;
    if (!regenerate) appendMessage("user", text);
    input.value = "";
    autoResize();
    setBusy(true);

    try {
      try {
        await sendViaStream(text);
      } catch (streamErr) {
        console.warn("stream failed, falling back to /api/chat", streamErr);
        await sendViaJson(text);
      }
    } catch (err) {
      appendMessage(
        "assistant",
        `I couldn't reach the Dexibo API. Is the server running?\n\n\`${String(err)}\``
      );
    } finally {
      abortController = null;
      setBusy(false);
      input.focus();
    }
  }

  composer.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(input.value);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input.value);
    }
  });

  input.addEventListener("input", autoResize);

  document.querySelectorAll(".chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const prompt = btn.getAttribute("data-prompt");
      if (prompt) sendMessage(prompt);
    });
  });

  if (marketsRefresh) {
    marketsRefresh.addEventListener("click", () => loadWatchlist());
  }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") loadWatchlist();
  });

  // Empty state welcome
  appendMessage("assistant", WELCOME);
  loadHealth();
  loadWatchlist();
  scheduleWatchlist();
  input.focus();

  // ---- v0.5: sessions, stop, scenarios, compliance ----
  async function resumeLatestSession() {
    try {
      const res = await fetch('/api/sessions/latest', { headers: apiHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      const sess = data.session;
      if (!sess || !sess.id || !(sess.messages || []).length) return;
      sessionId = sess.id;
      transcript.innerHTML = '';
      for (const m of sess.messages) {
        if (m.role === 'user' || m.role === 'assistant') {
          appendMessage(m.role, m.content || '', {
            citations: (m.meta && m.meta.citations) || null,
          });
        }
      }
    } catch (err) {
      console.warn('resume session failed', err);
    }
  }

  async function newChat() {
    try {
      const res = await fetch('/api/sessions/new', {
        method: 'POST',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
      });
      const data = await res.json().catch(() => ({}));
      sessionId = (data.session && data.session.id) || null;
      transcript.innerHTML = '';
      appendMessage('assistant', WELCOME);
    } catch (err) {
      console.warn('new chat failed', err);
      sessionId = null;
      transcript.innerHTML = '';
      appendMessage('assistant', WELCOME);
    }
  }

  function exportMarkdown() {
    if (!sessionId) {
      alert('No session to export yet — send a message first.');
      return;
    }
    window.open('/api/sessions/' + encodeURIComponent(sessionId) + '/export.md', '_blank');
  }

  function toggleScenarios(force) {
    const drawer = document.getElementById('scenarioDrawer');
    const btn = document.getElementById('scenariosBtn');
    if (!drawer) return;
    const open = force != null ? force : drawer.hasAttribute('hidden');
    if (open) drawer.removeAttribute('hidden');
    else drawer.setAttribute('hidden', '');
    if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  async function runScenarioForm(form) {
    const name = form.getAttribute('data-scenario');
    const params = {};
    for (const el of form.querySelectorAll('input[name]')) {
      const v = el.value;
      params[el.name] = v === '' ? null : Number(v);
    }
    const out = document.getElementById('scenarioResult');
    if (out) out.textContent = 'Running…';
    try {
      const res = await fetch('/api/scenarios/' + encodeURIComponent(name), {
        method: 'POST',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ params }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || res.statusText);
      if (out) out.textContent = JSON.stringify(data.result, null, 2);
    } catch (err) {
      if (out) out.textContent = 'Error: ' + err;
    }
  }

  const stopBtn = document.getElementById('stopBtn');
  if (stopBtn) {
    stopBtn.addEventListener('click', () => {
      if (abortController) abortController.abort();
    });
  }
  const newChatBtn = document.getElementById('newChatBtn');
  if (newChatBtn) newChatBtn.addEventListener('click', () => newChat());
  const exportMdBtn = document.getElementById('exportMdBtn');
  if (exportMdBtn) exportMdBtn.addEventListener('click', () => exportMarkdown());
  const scenariosBtn = document.getElementById('scenariosBtn');
  if (scenariosBtn) scenariosBtn.addEventListener('click', () => toggleScenarios());
  const closeScenariosBtn = document.getElementById('closeScenariosBtn');
  if (closeScenariosBtn) closeScenariosBtn.addEventListener('click', () => toggleScenarios(false));
  document.querySelectorAll('.scenario-form').forEach((form) => {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      runScenarioForm(form);
    });
  });

  loadCompliance();
  resumeLatestSession();

})();
