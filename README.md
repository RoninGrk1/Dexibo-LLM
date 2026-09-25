# Dexibo

**Lite fintech intelligence** — local assistant for finance questions, calcs, and learning.

Runs on about **4GB RAM** (small quantised model). Works in **mock mode** with no model file.

> **Not financial advice.** Quotes are delayed and unofficial when shown.

---

## Quick start

```bash
git clone https://github.com/RoninGrk1/Dexibo-LLM.git
cd Dexibo-LLM
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

| Do this | Command |
|---------|---------|
| Terminal chat | `python -m dexibo` |
| Web UI | `python -m dexibo web` → http://127.0.0.1:8787 |
| Quick test | `python -m dexibo once "What is an ISA?"` |
| Run evals | `python scripts/run_evals.py` |

---

## Features

- Chat (terminal + dark web UI) with **streaming**
- **Calculators** — compound, loan, CAGR, returns, risk (real maths)
- **RAG** — short UK/EU fintech notes grounded in answers
- **Guardrails** + refusal audit
- **Delayed quotes** + markets **watchlist**
- **Scenarios** — savings / mortgage stress / inflation
- **Sessions** — save, resume, export Markdown/CSV
- Optional **JSON mode**, **API key**, rate limits

Still capped for **≤4GB** — default model path is 3B Q4 (~2GB), not 7B.

---

## Optional model (~2GB)

```bash
pip install -e ".[llm]"
python scripts/download_model.py          # Qwen2.5-3B Q4 (~2GB)
cp .env.example .env                      # optional
```

| Choice | Model | Size |
|--------|--------|------|
| 0 (default) | Qwen2.5-3B Instruct Q4 | ~2.0 GB |
| 1 | Phi-3.1 mini Q4 | ~2.4 GB |
| 2 | Qwen2.5-7B Q4 | ~4.7 GB (tight) |

---

## Useful commands

```text
/help   /calc compound 10000 5 10   /concept ISA
/rag open banking   /quote AAPL   /watch
/scenario savings|mortgage|inflation
/json on|off   /quit
```

Web: Stop · Regenerate · Copy · Export · Scenarios drawer.

---

## Settings (short)

| Env | Default | Meaning |
|-----|---------|---------|
| `DEXIBO_FORCE_MOCK` | off | No GGUF |
| `DEXIBO_MODEL_PATH` | `models/…gguf` | Model file |
| `DEXIBO_N_CTX` | `4096` | Lower = less RAM |
| `DEXIBO_WATCHLIST` | `AAPL,MSFT,VWRL.L,BTC-USD` | Quote symbols |
| `DEXIBO_API_KEY` | unset | Protect `/api/*` |
| `DEXIBO_RATE_LIMIT` | `60` | Req/min per IP |
| `DEXIBO_JSON_MODE` | off | Structured replies |
| `DEXIBO_JURISDICTION` | `UK` | Banner region |

More in `.env.example`.

---

## Layout

```text
dexibo/   web/   knowledge/   scripts/   models/   evals/   data/   examples/
```

**Needs:** Python 3.11+ · ~4GB RAM for a small model · optional C++ tools for `llama-cpp-python`

---

## Disclaimer

Educational only — not financial, tax, or legal advice. Verify with official sources or a regulated adviser.

## Licence

MIT
