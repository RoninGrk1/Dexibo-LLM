# Dexibo

**lite fintech intelligence** — a local LLM assistant for fintech Q&A, analysis, and education, designed to run on ~4GB RAM/VRAM with quantised 3B–7B instruct models.

> **Not financial advice.** Dexibo educates and calculates. It does not provide personalised investment recommendations. Delayed unofficial quotes (when enabled) are labelled and are not advice.

## What you get

- Local chat REPL branded as **Dexibo**
- GGUF inference via **llama-cpp-python** (optional; mock mode works without it)
- Fintech calculators: compound interest, loan amortisation, % returns, CAGR, simple risk metrics
- Curated educational concepts (ISA, APR, ETF, KYC/AML, Open Banking, …)
- CPU-friendly defaults (`n_gpu_layers=0`, `n_ctx=4096`)
- **v0.2 upgrades:** RAG, structured tool-calling, guardrails, delayed quotes
- **v0.3 Web UI:** single-page FastAPI chat at `http://127.0.0.1:8787`

## Upgrades (v0.2)

Exactly four high-value LLM upgrades ship in this release:

### 1. Fintech RAG retrieval (`dexibo/rag/`)

Curated UK/Europe-leaning markdown under `knowledge/` (ISA, SIPP, APR/AER, ETF, KYC/AML, Open Banking, SEPA, Basel III, volatility/Sharpe, diversification, bonds/gilts, inflation — 12 short docs). Lightweight retrieval with **no heavy ML deps**: tokenise + TF-IDF (pure Python / stdlib) over those docs plus existing `market_knowledge` concepts.

- `retrieve(query, k=3)` → scored chunks
- Wired into `ChatSession.ask` — top chunks injected as `[Retrieved context]` before `model.generate` (mock and GGUF)
- CLI: `/rag <query>` · flags: `DEXIBO_RAG=1`, `DEXIBO_RAG_TOP_K=3`

### 2. Structured calculator tool-calling (`dexibo/tools/registry.py`)

Tool schema registry for `compound_interest`, `loan_amortisation`, `percent_return`, `cagr`, `risk_metrics`.

- Detects calc intent in the chat pipeline
- For LlamaCpp: appends tool instructions and parses a fenced JSON call  
  `` ```tool\n{"name":"cagr","arguments":{...}}\n``` ``
- Executes deterministically in Python, then feeds the result back for a natural-language reply (or formats cleanly in mock)
- `MockModel` prefers the registry (`detect_and_run_from_text`) — **never invents calculator numbers**

### 3. Compliance / advice guardrails (`dexibo/guardrails.py`)

- **Pre-check** user input: refuse/redirect fraud, money-laundering how-tos, market manipulation, “help me evade KYC”
- **Post-check** assistant output: soften personalised advice patterns (“you should buy”, “guaranteed returns”, stock tips framed as advice) and force `DISCLAIMER_SHORT`
- Always ensure investment-related replies end with the short disclaimer if missing
- Flag: `DEXIBO_GUARDRAILS=1` (default on) · applied in `ChatSession.ask` around generate

### 4. Optional live market quotes (`dexibo/tools/quotes.py`)

Delayed quotes via the public Yahoo Finance chart endpoint using **stdlib urllib only** (no yfinance).

- `get_quote(symbol) -> dict` with `price`, `currency`, `as_of`, `source` labelled **delayed / unofficial**
- Hard-fails gracefully offline
- CLI: `/quote AAPL` or `/quote VWRL.L`
- Wired so “what’s the price of AAPL” can call quotes when `DEXIBO_QUOTES=1` (default on)
- System prompt: live quotes **are allowed** when the tool returns data, but must be labelled delayed and not advice

See also `examples/upgrades.md` for short demos of each.

## Requirements

- Python **3.11+**
- ~4GB free RAM for a Q4 3B model (more headroom is better)
- Optional: C++ build tools if installing `llama-cpp-python` from source
- Optional network for delayed quotes (`DEXIBO_QUOTES=1`)

## Install

```bash
cd /workspace/dexibo
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Or with requirements:

```bash
pip install -r requirements.txt
pip install -e .
```

### LLM backend (optional but recommended)

`llama-cpp-python` can take several minutes to build. If the install fails or is too heavy, Dexibo still runs in **mock mode** (calculators + educational knowledge + RAG + guardrails).

```bash
pip install "llama-cpp-python>=0.2.90"
# or
pip install -e ".[llm]"
```

On some platforms you may need:

```bash
CMAKE_ARGS="-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS" pip install llama-cpp-python
```

## Download a model (~2–4.7 GB)

Recommended default for ~4GB systems:

| Choice | Hugging Face repo | File | Approx size |
|--------|-------------------|------|-------------|
| **0 (default)** | `Qwen/Qwen2.5-3B-Instruct-GGUF` | `qwen2.5-3b-instruct-q4_k_m.gguf` | **~2.0 GB** |
| 1 | `bartowski/Phi-3.1-mini-4k-instruct-GGUF` | `Phi-3.1-mini-4k-instruct-Q4_K_M.gguf` | ~2.4 GB |
| 2 | `Qwen/Qwen2.5-7B-Instruct-GGUF` | `qwen2.5-7b-instruct-q4_k_m.gguf` | ~4.7 GB (tight on 4GB) |

```bash
python scripts/download_model.py --list
python scripts/download_model.py          # downloads choice 0 into models/
python scripts/download_model.py --choice 1
```

Weights land in `models/`. Runtime memory is **higher** than file size (context + KV cache + Python). Prefer the 3B Q4_K_M on constrained boxes.

Copy env defaults:

```bash
cp .env.example .env
# edit DEXIBO_MODEL_PATH / DEXIBO_N_GPU_LAYERS if needed
```

## Run

```bash
python -m dexibo
# or
dexibo
```

One-shot smoke test:

```bash
python -m dexibo once "hello"
```

### Slash commands

| Command | Purpose |
|---------|---------|
| `/help` | Help |
| `/clear` | Clear history |
| `/model` | Backend + recommended GGUFs |
| `/calc …` | Calculators |
| `/concept <name>` | Educational lookup |
| `/concepts` | List concepts |
| `/rag <query>` | TF-IDF retrieved chunks |
| `/quote <symbol>` | Delayed unofficial quote |
| `/upgrades` | List the four v0.2 upgrades |
| `/disclaimer` | Short disclaimer |
| `/quit` | Exit |

Examples:

```text
/calc compound 10000 5 10
/calc loan 200000 4.5 25
/calc cagr 10000 15000 5
/concept ISA
/rag open banking
/quote AAPL
/upgrades
```


## Web UI (v0.3)

A small, modern single-page chat app (vanilla HTML/CSS/JS + FastAPI) with a futuristic fintech look: deep navy/charcoal, cyan/teal accents, glass panels, Inter/system sans.

**Screenshot description:** Left slim rail with a geometric **D** mark, Dexibo name, backend badge (`mock` / `llama…`), and feature pills (RAG · Tools · Guardrails · Quotes). Main column shows a welcome bubble from Dexibo, user messages right-aligned, assistant left-aligned with soft glass bubbles; bottom composer with quick-action chips (Ask ISA · Compound calc · Quote AAPL · What is Open Banking), Send button, and educational disclaimer footer. On phone the rail collapses into a compact top bar.

### Run

```bash
cd /workspace/dexibo
source .venv/bin/activate
pip install -e .          # pulls fastapi + uvicorn
python -m dexibo web      # http://127.0.0.1:8787
# or
python scripts/run_web.py
```

Env (see `.env.example`): `DEXIBO_WEB_HOST` (default `127.0.0.1`), `DEXIBO_WEB_PORT` (default `8787`).

### API

| Method | Path | Body / notes |
|--------|------|----------------|
| `GET` | `/` | Serves `web/index.html` |
| `GET` | `/api/health` | version, backend, feature flags |
| `POST` | `/api/chat` | `{ "message": "...", "session_id": "optional" }` → reply + session_id + backend |
| `GET` | `/api/quote/{symbol}` | Convenience delayed quote (when quotes enabled) |

Sessions are in-memory (fine for local demo). The chat pipeline is the same as the CLI: RAG inject, tools, guardrails, quotes.

## Hardware notes

- **Default:** CPU only (`DEXIBO_N_GPU_LAYERS=0`) — friendly for laptops without a large GPU.
- Raise `DEXIBO_N_GPU_LAYERS` if you have VRAM and a CUDA/Metal build of llama-cpp-python.
- Keep `DEXIBO_N_CTX` at 2048–4096 on 4GB systems; larger context costs RAM.
- Mock mode (`DEXIBO_FORCE_MOCK=1` or missing GGUF) needs only tens of MB.

## Project layout

```text
dexibo/
  __init__.py
  __main__.py
  config.py
  system_prompt.py
  model.py          # llama-cpp + mock fallback
  chat.py           # RAG + tools + guardrails + quotes pipeline
  cli.py            # REPL + `web` command
  webapp.py         # FastAPI app factory (v0.3)
  guardrails.py
  rag/
    retriever.py    # pure-Python TF-IDF
  tools/
    calculator.py
    market_knowledge.py
    registry.py     # structured tool schemas
    quotes.py       # delayed Yahoo quotes (urllib)
web/                # static SPA (index.html, styles.css, app.js, favicon.svg)
knowledge/          # curated markdown for RAG
scripts/download_model.py
scripts/run_web.py  # uvicorn launcher
models/             # GGUF files (gitignored content)
examples/sample_session.md
examples/upgrades.md
```

## Disclaimer

Dexibo is an **educational** assistant. It does **not** provide financial, investment, tax, or legal advice. Delayed quotes (when enabled) are unofficial and must not be treated as a live trading feed. Verify important decisions with official sources or a regulated adviser. You are responsible for compliance with laws in your jurisdiction.

## Licence

MIT
