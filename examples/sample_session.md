# Sample Dexibo session

Illustrative transcript (mock mode). Not financial advice.

```
$ cd /workspace/dexibo
$ pip install -e .
$ python -m dexibo
```

```
╭─ Dexibo — lite fintech intelligence ─────────────────────────╮
│ v0.1.0  ·  backend: mock                                     │
│ Educational only — not financial advice. …                   │
│ Type /help for commands, or just ask a fintech question.     │
╰──────────────────────────────────────────────────────────────╯
you> hello
```

Dexibo greets you as **Dexibo**, explains mock mode, and suggests `/calc` or concept questions.

```
you> /calc compound 10000 5 10
```

Shows future value of £10,000 at 5% for 10 years (monthly compounding by default).

```
you> What is an ISA?
```

Returns the curated UK ISA educational note plus the short disclaimer.

```
you> /concept APR
you> /model
you> /quit
```

With a GGUF downloaded (`python scripts/download_model.py`), the banner shows
`backend: llama.cpp (Qwen2.5-3B-Instruct-Q4_K_M.gguf)` and free-form answers
come from the local instruct model instead of the mock router.
