"""Lightweight fintech helper tools for Dexibo."""

from dexibo.tools.calculator import (
    cagr,
    compound_interest,
    loan_amortisation,
    percent_return,
    risk_metrics,
)
from dexibo.tools.market_knowledge import CONCEPTS, lookup_concept, search_concepts
from dexibo.tools.quotes import (
    detect_quote_symbol,
    format_quote,
    get_quote,
    get_watchlist,
    parse_watchlist_symbols,
)
from dexibo.tools.registry import (
    TOOL_SCHEMAS,
    detect_and_run_from_text,
    execute_tool,
    format_tool_result,
    needs_calculator,
    parse_tool_call,
    tool_instructions_block,
)

__all__ = [
    "cagr",
    "compound_interest",
    "loan_amortisation",
    "percent_return",
    "risk_metrics",
    "CONCEPTS",
    "lookup_concept",
    "search_concepts",
    "get_quote",
    "format_quote",
    "detect_quote_symbol",
    "get_watchlist",
    "parse_watchlist_symbols",
    "TOOL_SCHEMAS",
    "needs_calculator",
    "tool_instructions_block",
    "parse_tool_call",
    "execute_tool",
    "format_tool_result",
    "detect_and_run_from_text",
]

from dexibo.tools.scenarios import (
    inflation_drag,
    mortgage_stress,
    run_scenario,
    savings_goal,
)

__all__ += [
    "savings_goal",
    "mortgage_stress",
    "inflation_drag",
    "run_scenario",
]
