"""Structured calculator tool schemas + detection / parsing / execution."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from dexibo.tools.calculator import (
    cagr,
    compound_interest,
    loan_amortisation,
    percent_return,
    risk_metrics,
)

ToolFn = Callable[..., dict[str, Any]]

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "compound_interest": {
        "name": "compound_interest",
        "description": "Future value with compound interest.",
        "parameters": {
            "principal": {"type": "number", "required": True},
            "annual_rate_pct": {"type": "number", "required": True},
            "years": {"type": "number", "required": True},
            "compounds_per_year": {"type": "integer", "required": False, "default": 12},
        },
    },
    "loan_amortisation": {
        "name": "loan_amortisation",
        "description": "Fixed-rate loan payment and total interest.",
        "parameters": {
            "principal": {"type": "number", "required": True},
            "annual_rate_pct": {"type": "number", "required": True},
            "years": {"type": "integer", "required": True},
            "payments_per_year": {"type": "integer", "required": False, "default": 12},
        },
    },
    "percent_return": {
        "name": "percent_return",
        "description": "Simple percentage return between two values.",
        "parameters": {
            "start_value": {"type": "number", "required": True},
            "end_value": {"type": "number", "required": True},
        },
    },
    "cagr": {
        "name": "cagr",
        "description": "Compound annual growth rate.",
        "parameters": {
            "start_value": {"type": "number", "required": True},
            "end_value": {"type": "number", "required": True},
            "years": {"type": "number", "required": True},
        },
    },
    "risk_metrics": {
        "name": "risk_metrics",
        "description": "Mean, volatility, max drawdown proxy from period returns.",
        "parameters": {
            "returns": {
                "type": "array",
                "items": "number",
                "required": True,
                "description": "List of period returns (%% or decimals).",
            },
        },
    },
}

_HANDLERS: dict[str, ToolFn] = {
    "compound_interest": compound_interest,
    "loan_amortisation": loan_amortisation,
    "percent_return": percent_return,
    "cagr": cagr,
    "risk_metrics": risk_metrics,
}

# Natural-language calc intent
_CALC_HINT = re.compile(
    r"\b("
    r"compound(?:\s+interest)?|amorti[sz]e|amortisation|amortization|"
    r"loan\s+payment|mortgage|cagr|percent(?:age)?\s+return|"
    r"risk\s+metrics?|sharpe|volatility\s+of\s+returns|"
    r"future\s+value|interest\s+on\s+[\d,.]+"
    r")\b",
    re.I,
)

_TOOL_FENCE = re.compile(
    r"```(?:tool|json\s*tool)?\s*\n?\s*(\{.*?\})\s*\n?```",
    re.I | re.S,
)

_BARE_TOOL_JSON = re.compile(
    r'\{\s*"name"\s*:\s*"(?:'
    + "|".join(TOOL_SCHEMAS.keys())
    + r')"\s*,\s*"arguments"\s*:\s*\{.*?\}\s*\}',
    re.S,
)


def needs_calculator(user_message: str) -> bool:
    """Heuristic: does the user message look like a calc request?"""
    text = (user_message or "").strip()
    if not text:
        return False
    if _CALC_HINT.search(text):
        return True
    # Numbers + rate/years patterns
    if re.search(r"[\d,]+\.?\d*.{0,40}\d+\s*%", text) and re.search(
        r"\b(year|years|yr|yrs|month|months)\b", text, re.I
    ):
        return True
    return False


def tool_instructions_block() -> str:
    """Append to system prompt when calc tools may be needed."""
    names = ", ".join(TOOL_SCHEMAS.keys())
    example = (
        '```tool\n'
        '{"name":"cagr","arguments":{"start_value":10000,"end_value":15000,"years":5}}\n'
        "```"
    )
    return (
        "## Calculator tools\n"
        f"When the user needs a numerical calculation, emit ONE fenced tool call "
        f"using one of: {names}.\n"
        "Format exactly:\n"
        f"{example}\n"
        "Do not invent calculator results — wait for the deterministic tool output. "
        "After you receive a tool result, explain it in clear educational language."
    )


def parse_tool_call(text: str) -> dict[str, Any] | None:
    """Extract a tool call dict {name, arguments} from model output, or None."""
    if not text:
        return None
    m = _TOOL_FENCE.search(text)
    raw = None
    if m:
        raw = m.group(1)
    else:
        m2 = _BARE_TOOL_JSON.search(text)
        if m2:
            raw = m2.group(0)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    name = data.get("name")
    args = data.get("arguments", data.get("args", {}))
    if name not in TOOL_SCHEMAS or not isinstance(args, dict):
        return None
    return {"name": name, "arguments": args}


def execute_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run a registered calculator; never invent numbers."""
    if name not in _HANDLERS:
        raise ValueError(f"unknown tool: {name}")
    schema = TOOL_SCHEMAS[name]
    args = dict(arguments or {})
    # Apply defaults
    for pname, pmeta in schema["parameters"].items():
        if pname not in args and "default" in pmeta:
            args[pname] = pmeta["default"]
    # Coerce types lightly
    if name == "loan_amortisation" and "years" in args:
        args["years"] = int(args["years"])
    if name == "risk_metrics" and "returns" in args:
        rets = args["returns"]
        if isinstance(rets, str):
            rets = [float(x) for x in rets.replace(" ", "").split(",") if x]
        args["returns"] = [float(x) for x in rets]
    fn = _HANDLERS[name]
    result = fn(**args)
    return {"tool": name, "arguments": args, "result": result}


def format_tool_result(payload: dict[str, Any]) -> str:
    """Human-readable formatting of an execute_tool payload."""
    name = payload.get("tool", "tool")
    result = payload.get("result", {})
    lines = [f"**Tool result: `{name}`** (deterministic)", ""]
    for key, value in result.items():
        if key.startswith("_"):
            continue
        label = key.replace("_", " ").title()
        if isinstance(value, float):
            if abs(value) < 1 and value != 0:
                lines.append(f"- {label}: {value:,.6g}")
            else:
                lines.append(f"- {label}: {value:,.4g}" if abs(value) < 100 else f"- {label}: {value:,.2f}")
        elif isinstance(value, list):
            lines.append(f"- {label}: {json.dumps(value)}")
        else:
            lines.append(f"- {label}: {value}")
    return "\n".join(lines)


def detect_and_run_from_text(user_message: str) -> dict[str, Any] | None:
    """Best-effort NL → registry execution for mock / fallback paths."""
    lower = (user_message or "").lower()
    text = user_message or ""

    m = re.search(
        r"compound(?:\s+interest)?\s+(?:on\s+)?([\d,.]+)\s+(?:at\s+)?([\d.]+)%?\s+"
        r"(?:for\s+)?([\d.]+)\s*y",
        lower,
    )
    if m:
        p, r, y = (float(m.group(i).replace(",", "")) for i in (1, 2, 3))
        return execute_tool(
            "compound_interest",
            {"principal": p, "annual_rate_pct": r, "years": y},
        )

    m = re.search(
        r"(?:loan|mortgage|amorti[sz]e)\s+([\d,.]+)\s+(?:at\s+)?([\d.]+)%?\s+"
        r"(?:over\s+)?([\d.]+)\s*y",
        lower,
    )
    if not m:
        m = re.search(
            r"(?:loan|mortgage|amorti[sz]ation|amorti[sz]e)\s+(?:for\s+)?([\d,.]+)\s+"
            r"(?:at\s+)?([\d.]+)\s*%\s+(?:over|for|across)\s+([\d.]+)\s*y",
            lower,
        )
    if m:
        p, r, y = (float(m.group(i).replace(",", "")) for i in (1, 2, 3))
        return execute_tool(
            "loan_amortisation",
            {"principal": p, "annual_rate_pct": r, "years": int(y)},
        )

    m = re.search(
        r"cagr\s+(?:from\s+)?([\d,.]+)\s+(?:to\s+)?([\d,.]+)\s+(?:over\s+)?([\d.]+)\s*y",
        lower,
    )
    if m:
        s, e, y = (float(m.group(i).replace(",", "")) for i in (1, 2, 3))
        return execute_tool(
            "cagr",
            {"start_value": s, "end_value": e, "years": y},
        )

    m = re.search(
        r"(?:percent(?:age)?\s+)?return\s+(?:from\s+)?([\d,.]+)\s+(?:to\s+)?([\d,.]+)",
        lower,
    )
    if m:
        s, e = (float(m.group(i).replace(",", "")) for i in (1, 2))
        return execute_tool("percent_return", {"start_value": s, "end_value": e})

    m = re.search(r"risk(?:\s+metrics?)?\s+([\d.\-,\s]+)", lower)
    if m:
        raw = m.group(1).replace(" ", "")
        returns = [float(x) for x in raw.split(",") if x]
        if len(returns) >= 2:
            return execute_tool("risk_metrics", {"returns": returns})

    # Also accept fenced tool JSON typed by the user
    parsed = parse_tool_call(text)
    if parsed:
        return execute_tool(parsed["name"], parsed["arguments"])

    return None


__all__ = [
    "TOOL_SCHEMAS",
    "needs_calculator",
    "tool_instructions_block",
    "parse_tool_call",
    "execute_tool",
    "format_tool_result",
    "detect_and_run_from_text",
]
