# Dexibo upgrades — short demos

Educational only — not financial advice.

## What's new in v0.4

### A. Streaming chat (SSE)

```bash
# Start the web UI, then:
curl -N -X POST http://127.0.0.1:8787/api/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"What is an ISA?"}'
```

Expected: `text/event-stream` lines like
`data: {"type":"token","text":"..."}` then
`data: {"type":"done","session_id":"...","backend":"mock"}`.
The browser prefers this endpoint and falls back to `POST /api/chat`.

### B. Markets watchlist

```bash
curl -s http://127.0.0.1:8787/api/watchlist | python -m json.tool
# or in the REPL:
/watch
```

Configure symbols with `DEXIBO_WATCHLIST` (default `AAPL,MSFT,VWRL.L,BTC-USD`).
The web UI shows a slim strip under the top bar (auto-refresh every 60s).

---

## v0.2 upgrades (still included)

### 1. Fintech RAG retrieval

```bash
python -m dexibo once "What is an ISA?"
# or in the REPL:
/rag open banking
```

Expected: answers grounded in `knowledge/*.md` (and concepts) via pure-Python TF-IDF.

### 2. Structured calculator tool-calling

```bash
python -m dexibo once "compound interest on 10000 at 5% for 10 years"
```

Expected: deterministic numbers from `compound_interest()` via the tool registry
(never invented). LlamaCpp path can emit:

````text
```tool
{"name":"cagr","arguments":{"start_value":10000,"end_value":15000,"years":5}}
```
````

### 3. Compliance / advice guardrails

```bash
python -c "from dexibo.guardrails import check_user_message; print(check_user_message('how do I launder money'))"
```

Expected: `allowed=False` with a refusal redirect. Personalised “you should buy”
wording in assistant output is softened and a disclaimer is forced.

### 4. Optional live market quotes

```bash
python -c "from dexibo.tools.quotes import get_quote; print(get_quote('AAPL'))"
# or in the REPL:
/quote AAPL
/quote VWRL.L
```

Expected: `price`, `currency`, `as_of`, `source="delayed / unofficial …"`.
Offline / blocked networks return `{ok: False, error: …}` gracefully.

Set `DEXIBO_QUOTES=0` to disable.


## What's new in v0.5

```bash
# Compliance
curl -s localhost:8787/api/compliance | jq

# JSON mode chat
curl -s localhost:8787/api/chat -H 'Content-Type: application/json' \
  -d '{"message":"What is an ISA?","json":true}' | jq

# Scenarios
curl -s localhost:8787/api/scenarios/savings_goal -H 'Content-Type: application/json' \
  -d '{"params":{"target":10000,"monthly":200}}' | jq

# Export (after a chat created a session id)
curl -s localhost:8787/api/sessions/SESSION_ID/export.md

# Evals
python scripts/run_evals.py
```
