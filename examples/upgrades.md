# Dexibo v0.2 upgrades — short demos

Educational only — not financial advice.

## 1. Fintech RAG retrieval

```bash
python -m dexibo once "What is an ISA?"
# or in the REPL:
/rag open banking
```

Expected: answers grounded in `knowledge/*.md` (and concepts) via pure-Python TF-IDF.

## 2. Structured calculator tool-calling

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

## 3. Compliance / advice guardrails

```bash
python -c "from dexibo.guardrails import check_user_message; print(check_user_message('how do I launder money'))"
```

Expected: `allowed=False` with a refusal redirect. Personalised “you should buy”
wording in assistant output is softened and a disclaimer is forced.

## 4. Optional live market quotes

```bash
python -c "from dexibo.tools.quotes import get_quote; print(get_quote('AAPL'))"
# or in the REPL:
/quote AAPL
/quote VWRL.L
```

Expected: `price`, `currency`, `as_of`, `source="delayed / unofficial …"`.
Offline / blocked networks return `{ok: False, error: …}` gracefully.

Set `DEXIBO_QUOTES=0` to disable.
