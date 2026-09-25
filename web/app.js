/**
 * Dexibo web client — single-page chat UI
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

  let sessionId = null;
  let busy = false;

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

  function appendMessage(role, content, { html = false, typing = false } = {}) {
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
    transcript.appendChild(wrap);
    transcript.scrollTop = transcript.scrollHeight;
    return wrap;
  }

  function setBusy(on) {
    busy = on;
    sendBtn.disabled = on;
    input.disabled = on;
  }

  function autoResize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 140) + "px";
  }

  async function loadHealth() {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error("health " + res.status);
      const data = await res.json();
      const backend = data.backend || "unknown";
      backendLabel.textContent = backend;
      backendLabelMobile.textContent = backend;
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
      backendLabel.textContent = "offline";
      backendLabelMobile.textContent = "offline";
      console.warn("health check failed", err);
    }
  }

  async function sendMessage(raw) {
    const text = (raw || "").trim();
    if (!text || busy) return;

    appendMessage("user", text);
    input.value = "";
    autoResize();
    setBusy(true);
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
      if (data.backend) {
        backendLabel.textContent = data.backend;
        backendLabelMobile.textContent = data.backend;
      }
      appendMessage("assistant", data.reply || "(empty reply)");
    } catch (err) {
      thinking.remove();
      appendMessage(
        "assistant",
        `I couldn't reach the Dexibo API. Is the server running?\n\n\`${String(err)}\``
      );
    } finally {
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

  // Empty state welcome
  appendMessage("assistant", WELCOME);
  loadHealth();
  input.focus();
})();
