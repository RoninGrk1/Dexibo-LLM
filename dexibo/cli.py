"""Rich REPL CLI for Dexibo."""

from __future__ import annotations

import json
import sys
from typing import Any, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dexibo import __version__
from dexibo.chat import ChatSession
from dexibo.config import RECOMMENDED_MODELS, DexiboConfig, load_config
from dexibo.model import load_model
from dexibo.rag import retrieve
from dexibo.system_prompt import DISCLAIMER_SHORT
from dexibo.tools.calculator import (
    cagr,
    compound_interest,
    loan_amortisation,
    percent_return,
    risk_metrics,
)
from dexibo.tools.market_knowledge import CONCEPTS, lookup_concept, search_concepts
from dexibo.tools.quotes import format_quote, get_quote, get_watchlist
from dexibo.tools.scenarios import run_scenario

app = typer.Typer(
    name="dexibo",
    help="Dexibo — lite fintech intelligence",
    add_completion=False,
    invoke_without_command=True,
)
console = Console()


HELP_TEXT = """\
[bold]Slash commands[/bold]
  /help              Show this help
  /clear             Clear conversation history
  /model             Show model / backend info
  /calc ...          Run a calculator (see /calc help)
  /concept <name>    Look up an educational fintech concept
  /concepts          List curated concepts
  /rag <query>       Show TF-IDF retrieved knowledge chunks
  /quote <symbol>    Delayed unofficial market quote (Yahoo)
  /watch             Markets watchlist table (DEXIBO_WATCHLIST)
  /scenario ...      Run a scenario (savings|mortgage|inflation)
  /json on|off       Toggle structured JSON replies
  /upgrades          List product upgrades (v0.2–v0.5)
  /disclaimer        Show the short disclaimer
  /quit  /exit       Leave the REPL

[bold]Calc usage[/bold]
  /calc help
  /calc compound <principal> <rate%> <years> [compounds_per_year]
  /calc loan <principal> <rate%> <years> [payments_per_year]
  /calc return <start> <end>
  /calc cagr <start> <end> <years>
  /calc risk <r1,r2,r3,...>   (returns as % or decimals)

[bold]Scenario usage[/bold]
  /scenario savings target=<n> monthly=<n> [rate=<pct>] [years=<n>] [starting=<n>]
  /scenario mortgage principal=<n> rate=<pct> years=<n> [shock=<pct>]
  /scenario inflation amount=<n> years=<n> [inflation=<pct>] [return=<pct>]

Anything else is sent to the assistant (mock or GGUF).
"""

UPGRADES_TEXT = """\
[bold cyan]Dexibo upgrades[/bold cyan]

[bold]v0.2[/bold]
1. Fintech RAG · 2. Calculator tools · 3. Guardrails · 4. Delayed quotes

[bold]v0.3[/bold]
Web chat UI (FastAPI) at port 8787

[bold]v0.4[/bold]
A. Streaming chat (SSE) · B. Markets watchlist

[bold cyan]v0.5 — what's new[/bold cyan]
1. [bold]Trust & compliance[/bold] — jurisdiction banner, refusal audit log, `/api/compliance`
2. [bold]JSON mode[/bold] — stable structured replies (`DEXIBO_JSON_MODE`, `/json on`)
3. [bold]Persistent sessions[/bold] — disk history + markdown/CSV export
4. [bold]Eval harness[/bold] — `python scripts/run_evals.py`
5. [bold]Lite RAG v2[/bold] — better scoring + more UK fintech notes
6. [bold]Scenario studio[/bold] — savings / mortgage stress / inflation drag
7. [bold]API key + rate limits[/bold] — `DEXIBO_API_KEY`, `DEXIBO_RATE_LIMIT`
8. [bold]Streaming polish[/bold] — stop, regenerate, copy, citation chips
"""


def _banner(config: DexiboConfig, backend: str) -> None:
    title = Text()
    title.append(config.name, style="bold cyan")
    title.append(" — ", style="dim")
    title.append(config.tagline, style="italic")
    from dexibo.compliance import jurisdiction_banner, session_compliance_footer

    flags = (
        f"rag={'on' if config.enable_rag else 'off'}  "
        f"guardrails={'on' if config.enable_guardrails else 'off'}  "
        f"quotes={'on' if config.enable_quotes else 'off'}  "
        f"json={'on' if config.json_mode else 'off'}  "
        f"jurisdiction={config.jurisdiction}"
    )
    body = (
        f"[dim]v{__version__}[/dim]  ·  backend: [green]{backend}[/green]\n"
        f"[dim]{flags}[/dim]\n"
        f"[dim]{jurisdiction_banner(config.jurisdiction)}[/dim]\n"
        f"[dim]{session_compliance_footer()}[/dim]\n"
        "Type [bold]/help[/bold] or [bold]/upgrades[/bold], or just ask a fintech question."
    )
    console.print(Panel(body, title=title, border_style="cyan"))


def _print_result(obj: dict[str, Any]) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column("Value")
    for key, value in obj.items():
        if key == "schedule_preview":
            table.add_row(key, json.dumps(value, indent=2))
        elif isinstance(value, float):
            table.add_row(key, f"{value:,.6g}")
        else:
            table.add_row(key, str(value))
    console.print(table)


def _handle_calc(args: list[str]) -> None:
    if not args or args[0] in {"help", "-h", "--help"}:
        console.print(
            Markdown(
                """
### Calculator
- `compound <principal> <rate%> <years> [n]` — compound interest
- `loan <principal> <rate%> <years> [payments/year]` — amortisation
- `return <start> <end>` — simple % return
- `cagr <start> <end> <years>` — CAGR
- `risk <r1,r2,...>` — mean, vol, max drawdown proxy
"""
            )
        )
        return

    cmd = args[0].lower()
    try:
        if cmd == "compound":
            if len(args) < 4:
                raise ValueError("usage: /calc compound <principal> <rate%> <years> [n]")
            n = int(args[4]) if len(args) > 4 else 12
            _print_result(
                compound_interest(float(args[1]), float(args[2]), float(args[3]), n)
            )
        elif cmd == "loan":
            if len(args) < 4:
                raise ValueError("usage: /calc loan <principal> <rate%> <years> [ppy]")
            ppy = int(args[4]) if len(args) > 4 else 12
            _print_result(
                loan_amortisation(float(args[1]), float(args[2]), int(float(args[3])), ppy)
            )
        elif cmd in {"return", "pct", "percent"}:
            if len(args) < 3:
                raise ValueError("usage: /calc return <start> <end>")
            _print_result(percent_return(float(args[1]), float(args[2])))
        elif cmd == "cagr":
            if len(args) < 4:
                raise ValueError("usage: /calc cagr <start> <end> <years>")
            _print_result(cagr(float(args[1]), float(args[2]), float(args[3])))
        elif cmd == "risk":
            if len(args) < 2:
                raise ValueError("usage: /calc risk <r1,r2,r3,...>")
            raw = " ".join(args[1:]).replace(" ", "")
            returns = [float(x) for x in raw.split(",") if x]
            _print_result(risk_metrics(returns))
        else:
            console.print(f"[red]Unknown calc command:[/red] {cmd}. Try /calc help.")
    except (ValueError, ZeroDivisionError) as exc:
        console.print(f"[red]Calc error:[/red] {exc}")


def _handle_rag(args: list[str], config: DexiboConfig) -> None:
    if not args:
        console.print("[yellow]Usage:[/yellow] /rag <query>")
        return
    query = " ".join(args)
    chunks = retrieve(query, k=config.rag_top_k)
    if not chunks:
        console.print(f"[yellow]No chunks retrieved for[/yellow] {query!r}")
        return
    for i, c in enumerate(chunks, 1):
        console.print(
            Panel(
                f"{c['text'][:1200]}{'…' if len(c['text']) > 1200 else ''}\n\n"
                f"[dim]source={c['source']}  doc_id={c['doc_id']}  score={c['score']}[/dim]",
                title=f"({i}) {c['title']}",
                border_style="green",
            )
        )


def _handle_quote(args: list[str]) -> None:
    if not args:
        console.print("[yellow]Usage:[/yellow] /quote AAPL   or   /quote VWRL.L")
        return
    symbol = args[0]
    with console.status(f"[cyan]Fetching delayed quote for {symbol}…[/cyan]"):
        q = get_quote(symbol)
    console.print(Markdown(format_quote(q)))
    console.print(f"[dim]{DISCLAIMER_SHORT}[/dim]")



def _handle_watch(config: DexiboConfig) -> None:
    """Print the configured markets watchlist as a Rich table."""
    if not config.enable_quotes:
        console.print("[yellow]Quotes are disabled[/yellow] (DEXIBO_QUOTES=0).")
        return
    symbols = list(config.watchlist)
    with console.status("[cyan]Fetching watchlist…[/cyan]"):
        quotes = get_watchlist(symbols)
    table = Table(title="Markets watchlist · Delayed · unofficial", show_lines=False)
    table.add_column("Symbol", style="bold cyan")
    table.add_column("Price", justify="right")
    table.add_column("Change %", justify="right")
    table.add_column("Currency")
    table.add_column("As of (UTC)")
    table.add_column("Status")
    for q in quotes:
        if q.get("ok"):
            pct = q.get("change_pct")
            if pct is None:
                pct_s = "—"
            else:
                sign = "+" if pct >= 0 else ""
                style = "green" if pct >= 0 else "red"
                pct_s = f"[{style}]{sign}{pct:.2f}%[/{style}]"
            table.add_row(
                str(q.get("symbol", "?")),
                f"{q['price']:,.4g}",
                pct_s,
                str(q.get("currency") or "—"),
                str(q.get("as_of") or "—")[:19],
                "[green]ok[/green]",
            )
        else:
            table.add_row(
                str(q.get("symbol", "?")),
                "—",
                "—",
                "—",
                "—",
                f"[red]{q.get('error', 'fail')[:40]}[/red]",
            )
    console.print(table)
    console.print(f"[dim]Symbols from DEXIBO_WATCHLIST · {DISCLAIMER_SHORT}[/dim]")


def _parse_kv_args(args: list[str]) -> dict[str, float]:
    """Parse key=value pairs (and bare numbers as positional fallbacks)."""
    out: dict[str, float] = {}
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            out[k.strip().lower().replace("-", "_")] = float(v)
        else:
            # ignore bare tokens that aren't key=value
            continue
    return out


def _handle_scenario(args: list[str]) -> None:
    if not args or args[0] in {"help", "-h", "--help"}:
        console.print(
            Markdown(
                """
### Scenarios
- `savings target=10000 monthly=200 [rate=3] [years=5] [starting=0]`
- `mortgage principal=200000 rate=4.5 years=25 [shock=2]`
- `inflation amount=10000 years=10 [inflation=2.5] [return=0]`
"""
            )
        )
        return
    name = args[0].lower()
    kv = _parse_kv_args(args[1:])
    # Map friendly keys → scenario kwargs
    aliases = {
        "savings": "savings_goal",
        "mortgage": "mortgage_stress",
        "inflation": "inflation_drag",
    }
    scenario = aliases.get(name, name)
    params: dict[str, float] = {}
    try:
        if scenario == "savings_goal":
            if "target" not in kv or "monthly" not in kv:
                raise ValueError("need target= and monthly=")
            params = {
                "target": kv["target"],
                "monthly": kv["monthly"],
                "annual_rate_pct": kv.get("rate", kv.get("annual_rate_pct", 3.0)),
                "starting": kv.get("starting", 0.0),
            }
            if "years" in kv:
                params["years"] = kv["years"]
        elif scenario == "mortgage_stress":
            if "principal" not in kv or "rate" not in kv and "annual_rate_pct" not in kv:
                if "principal" not in kv or ("rate" not in kv and "annual_rate_pct" not in kv):
                    raise ValueError("need principal= and rate=")
            params = {
                "principal": kv["principal"],
                "annual_rate_pct": kv.get("rate", kv["annual_rate_pct"]),
                "years": int(kv.get("years", 25)),
                "rate_shock_pct": kv.get("shock", kv.get("rate_shock_pct", 2.0)),
            }
        elif scenario == "inflation_drag":
            if "amount" not in kv or "years" not in kv:
                raise ValueError("need amount= and years=")
            params = {
                "amount": kv["amount"],
                "years": kv["years"],
                "inflation_pct": kv.get("inflation", kv.get("inflation_pct", 2.5)),
                "nominal_return_pct": kv.get("return", kv.get("nominal_return_pct", 0.0)),
            }
        else:
            console.print(f"[red]Unknown scenario:[/red] {name}. Try /scenario help.")
            return
        result = run_scenario(scenario, params)
        _print_result(result)
        console.print(f"[dim]{DISCLAIMER_SHORT}[/dim]")
    except (ValueError, TypeError, KeyError) as exc:
        console.print(f"[red]Scenario error:[/red] {exc}")



def _handle_slash(line: str, session: ChatSession, config: DexiboConfig) -> bool:
    """Handle a slash command. Return False if the REPL should exit."""
    parts = line.strip().split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd in {"/quit", "/exit", "/q"}:
        console.print("[dim]Goodbye from Dexibo.[/dim]")
        return False

    if cmd in {"/help", "/h", "/?"}:
        console.print(Panel(HELP_TEXT, title="Help", border_style="blue"))
    elif cmd == "/clear":
        session.clear()
        console.print("[green]History cleared.[/green]")
    elif cmd == "/model":
        console.print(
            Panel(
                f"Name: {config.name}\n"
                f"Tagline: {config.tagline}\n"
                f"Backend: {session.model.backend_name}\n"
                f"Model path: {config.model_path}\n"
                f"Exists: {config.model_exists}\n"
                f"Mock: {config.use_mock}\n"
                f"n_ctx={config.n_ctx}  n_gpu_layers={config.n_gpu_layers}\n"
                f"temp={config.temperature}  max_tokens={config.max_tokens}\n"
                f"currency={config.default_currency}\n"
                f"rag={config.enable_rag}  top_k={config.rag_top_k}\n"
                f"guardrails={config.enable_guardrails}  quotes={config.enable_quotes}\n"
                f"watchlist={', '.join(config.watchlist)}",
                title="Model / config",
                border_style="magenta",
            )
        )
        table = Table(title="Recommended GGUFs (~4GB class)", show_lines=False)
        table.add_column("Repo / file")
        table.add_column("Size")
        table.add_column("Notes")
        for m in RECOMMENDED_MODELS:
            table.add_row(
                f"{m['id']}\n{m['filename']}",
                m["approx_size"],
                m["notes"],
            )
        console.print(table)
    elif cmd == "/calc":
        _handle_calc(args)
    elif cmd == "/rag":
        _handle_rag(args, config)
    elif cmd == "/quote":
        _handle_quote(args)
    elif cmd == "/watch":
        _handle_watch(config)
    elif cmd == "/upgrades":
        console.print(Panel(UPGRADES_TEXT, title="Upgrades", border_style="cyan"))
    elif cmd == "/concept":
        if not args:
            console.print("[yellow]Usage:[/yellow] /concept <name>")
        else:
            q = " ".join(args)
            hit = lookup_concept(q)
            if hit is None:
                hits = search_concepts(q)
                if hits:
                    hit = hits[0]
            if hit:
                console.print(
                    Panel(
                        f"{hit['summary']}\n\n[dim]Aliases: {', '.join(hit.get('aliases', []))}[/dim]",
                        title=hit["title"],
                        border_style="green",
                    )
                )
                console.print(f"[dim]{DISCLAIMER_SHORT}[/dim]")
            else:
                console.print(f"[yellow]No concept match for[/yellow] {q!r}")
    elif cmd == "/concepts":
        table = Table(title="Educational concepts")
        table.add_column("ID")
        table.add_column("Title")
        for c in CONCEPTS:
            table.add_row(c["id"], c["title"])
        console.print(table)
    elif cmd == "/disclaimer":
        console.print(Panel(DISCLAIMER_SHORT, border_style="yellow"))
    elif cmd == "/json":
        if not args or args[0].lower() not in {"on", "off", "1", "0", "true", "false"}:
            state = "on" if session.json_mode else "off"
            console.print(
                f"JSON mode is [bold]{state}[/bold]. Usage: /json on|off"
            )
        else:
            on = args[0].lower() in {"on", "1", "true"}
            session.json_mode = on
            console.print(f"[green]JSON mode {'on' if on else 'off'}.[/green]")
    elif cmd == "/scenario":
        _handle_scenario(args)
    else:
        console.print(f"[yellow]Unknown command[/yellow] {cmd}. Try /help.")
    return True


def run_repl(config: DexiboConfig | None = None) -> None:
    """Interactive REPL entry."""
    cfg = config or load_config()
    with console.status("[cyan]Loading Dexibo…[/cyan]"):
        model = load_model(cfg)
    session = ChatSession(model=model, config=cfg, json_mode=cfg.json_mode)
    _banner(cfg, model.backend_name)

    load_err = getattr(model, "_load_error", None)
    if load_err:
        console.print(
            f"[yellow]GGUF load failed — using mock mode.[/yellow]\n[dim]{load_err}[/dim]"
        )

    while True:
        try:
            line = console.input("[bold cyan]you>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye from Dexibo.[/dim]")
            break

        if not line:
            continue

        if line.startswith("/"):
            if not _handle_slash(line, session, cfg):
                break
            continue

        with console.status("[cyan]Dexibo is thinking…[/cyan]"):
            reply = session.ask(line)
        console.print()
        console.print(Markdown(reply))
        console.print()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", help="Show version and exit."
    ),
) -> None:
    """Start the Dexibo REPL (default)."""
    if version:
        console.print(f"Dexibo {__version__}")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        run_repl()


@app.command("once")
def once(
    prompt: str = typer.Argument(..., help="Single prompt to answer then exit."),
) -> None:
    """Non-interactive one-shot query (useful for smoke tests)."""
    cfg = load_config()
    model = load_model(cfg)
    session = ChatSession(model=model, config=cfg, json_mode=cfg.json_mode)
    reply = session.ask(prompt)
    console.print(Markdown(reply))



@app.command("web")
def web(
    host: Optional[str] = typer.Option(
        None, "--host", help="Bind host (default: DEXIBO_WEB_HOST or 127.0.0.1)."
    ),
    port: Optional[int] = typer.Option(
        None, "--port", "-p", help="Bind port (default: DEXIBO_WEB_PORT or 8787)."
    ),
) -> None:
    """Start the Dexibo web UI (FastAPI + uvicorn)."""
    import os

    import uvicorn

    bind_host = host or os.getenv("DEXIBO_WEB_HOST", "127.0.0.1")
    bind_port = port if port is not None else int(os.getenv("DEXIBO_WEB_PORT", "8787"))
    console.print(
        f"[bold cyan]Dexibo[/bold cyan] web → "
        f"[green]http://{bind_host}:{bind_port}[/green]  "
        f"[dim](Ctrl+C to stop)[/dim]"
    )
    uvicorn.run(
        "dexibo.webapp:app",
        host=bind_host,
        port=bind_port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    app()
