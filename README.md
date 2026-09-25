# Dexibo

**Lite fintech intelligence** — a small local assistant for finance questions, calculations, and learning.

Built to run on about **4GB of RAM** with a quantised 3B–7B model. Works in **mock mode** without a model (calculators + education still work).

> **Not financial advice.** Dexibo teaches and calculates. It does not recommend investments. Any market quotes are delayed, unofficial, and labelled.

---

## What's new in v0.5

Tier 1 + Tier 2 upgrades for a more product-like local demo:

**Trust & answers**
1. **Compliance pack** — UK/EU jurisdiction banner, session disclaimer, refusal audit log (`data/audit/refusals.jsonl`), `GET /api/compliance`
2. **JSON mode** — stable `{type, data, disclaimer, citations}` replies via `DEXIBO_JSON_MODE` or `"json": true` / CLI `/json on`
3. **Persistent sessions** — saved under `data/sessions/`, resume on web load, export Markdown or CSV
4. **Eval harness** — `python scripts/run_evals.py` (mock pipeline, no GGUF needed)

**Tools & web**
5. **Lite RAG v2** — better tokenisation, title/bigram boosts, more UK fintech notes (FCA, emergency fund, credit score, FX spread, auto-enrolment)
6. **Scenario studio** — savings goal, mortgage stress, inflation drag (`POST /api/scenarios/{name}`, CLI `/scenario`, web drawer)
7. **API key + rate limits** — optional `DEXIBO_API_KEY`, `DEXIBO_RATE_LIMIT` (default 60/min/IP)
8. **Streaming polish** — Stop, Regenerate, Copy, citation chips under assistant replies

Still fits ~**4GB** RAM. No heavier default model. Pure Python + existing deps.

See `examples/upgrades.md` for curl demos.

## Quick start

```bash
git clone https://github.com/RoninGrk1/Dexibo-LLM.git
cd Dexibo-LLM

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -U pip
pip install -e .
```

**Chat in the terminal**

```bash
python -m dexibo
```

**Open the web UI**

```bash
python -m dexibo web
# then visit http://127.0.0.1:8787
```

**One-line test**

```bash
python -m dexibo once "What is an ISA?"
```

---

## What Dexibo can do

| Feature | What it means for you |
|--------|------------------------|
| **Chat** | Ask fintech questions in the terminal or browser |
| **Calculators** | Compound interest, loans, returns, CAGR, simple risk stats — real maths, not guesses |
| **Knowledge (RAG)** | Pulls short UK/Europe notes (ISA, SIPP, Open Banking, KYC/AML, and more) into answers |
| **Guardrails** | Blocks scam / fraud / “evade KYC” asks; softens “you should buy X” style advice |
| **Quotes** | Optional delayed prices (e.g. `/quote AAPL`) — labelled unofficial |
| **Watchlist** | Configurable symbols on the web strip + `/watch` (delayed) |
| **Streaming** | Live token streaming in the browser (SSE) |
| **Web UI** | Clean dark fintech chat at port `8787` |

---

## Optional: add a real LLM (~2GB download)

Without a model file, Dexibo runs in **mock mode** (still useful for learning and calcs).

1. Install the local LLM library (needs a C++ toolchain; can take a few minutes):

```bash
pip install -e ".[llm]"
```

2. Download the recommended ~2GB model:

```bash
python scripts/download_model.py
```

| Option | Model | Size | Notes |
|--------|--------|------|--------|
| **0 (default)** | Qwen2.5-3B Instruct Q4 | ~2.0 GB | Best fit for ~4GB machines |
| 1 | Phi-3.1 mini Q4 | ~2.4 GB | Strong small alternative |
| 2 | Qwen2.5-7B Instruct Q4 | ~4.7 GB | Heavier — may be tight on 4GB |

```bash
python scripts/download_model.py --list
python scripts/download_model.py --choice 1
```

3. Copy settings (optional):

```bash
cp .env.example .env
```

---

## Terminal commands

| Command | What it does |
|---------|----------------|
| `/help` | Show help |
| `/clear` | Clear chat history |
| `/model` | Show backend and model info |
| `/calc …` | Run a calculator |
| `/concept <name>` | Look up a short educational note |
| `/concepts` | List all concepts |
| `/rag <query>` | Show retrieved knowledge chunks |
| `/quote <symbol>` | Delayed unofficial quote |
| `/watch` | Markets watchlist table |
| `/upgrades` | List built-in upgrades |
| `/disclaimer` | Show the short disclaimer |
| `/quit` | Exit |

**Calc examples**

```text
/calc compound 10000 5 10
/calc loan 200000 4.5 25
/calc cagr 10000 15000 5
```

**Other examples**

```text
/concept ISA
/rag open banking
/quote AAPL
```

---

## Web UI

Modern dark chat: navy background, cyan accents, markets watchlist strip, live streaming replies, and quick-action chips (ISA, compound calc, AAPL quote, Open Banking).

```bash
python -m dexibo web
```

Opens on **http://127.0.0.1:8787** by default.

Useful API routes:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/health` | Version, backend, feature flags |
| `POST` | `/api/chat` | `{ "message": "..." }` → reply |
| `POST` | `/api/chat/stream` | Same body → SSE tokens (`token` / `done` / `error`) |
| `GET` | `/api/watchlist` | Quotes for `DEXIBO_WATCHLIST` symbols |
| `GET` | `/api/quote/{symbol}` | Delayed quote helper |

Change host/port with `DEXIBO_WEB_HOST` and `DEXIBO_WEB_PORT` (see `.env.example`).

---

## Settings (common)

| Env var | Default | Meaning |
|---------|---------|---------|
| `DEXIBO_FORCE_MOCK` | off | Force mock mode (no GGUF) |
| `DEXIBO_MODEL_PATH` | `models/…gguf` | Path to your model file |
| `DEXIBO_N_GPU_LAYERS` | `0` | CPU by default; raise if you have GPU |
| `DEXIBO_N_CTX` | `4096` | Context size (lower = less RAM) |
| `DEXIBO_RAG` | on | Knowledge retrieval |
| `DEXIBO_GUARDRAILS` | on | Safety checks |
| `DEXIBO_QUOTES` | on | Delayed quotes |
| `DEXIBO_WATCHLIST` | `AAPL,MSFT,VWRL.L,BTC-USD` | Symbols for web strip + `/watch` |
| `DEXIBO_DEFAULT_CURRENCY` | `GBP` | Example currency framing |

---

## Project layout

```text
dexibo/          # Python package (chat, tools, RAG, web API)
web/             # Browser UI (HTML / CSS / JS)
knowledge/       # Short markdown notes for RAG
scripts/         # Model download + web launcher
models/          # Put GGUF files here (not committed)
examples/        # Sample sessions + upgrade demos
evals/           # Golden JSONL cases
data/            # Sessions + refusal audit (gitkept)
```

---

## Requirements

- Python **3.11+**
- About **4GB free RAM** for a small quantised model (mock mode needs far less)
- Optional: C++ build tools for `llama-cpp-python`
- Optional: network for delayed quotes

---

## Disclaimer

Dexibo is for **education and illustration** only. It is not financial, investment, tax, or legal advice. Quotes (when enabled) are unofficial and delayed. Check important decisions with official sources or a regulated adviser.

---

## Licence

MIT
