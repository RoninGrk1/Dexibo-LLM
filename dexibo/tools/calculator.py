"""Educational finance calculators (illustrative — not advice)."""

from __future__ import annotations

import math
from typing import Any


def compound_interest(
    principal: float,
    annual_rate_pct: float,
    years: float,
    compounds_per_year: int = 12,
) -> dict[str, Any]:
    """Future value with compound interest.

    FV = P * (1 + r/n)^(n*t)
    """
    if principal < 0:
        raise ValueError("principal must be non-negative")
    if compounds_per_year < 1:
        raise ValueError("compounds_per_year must be >= 1")
    if years < 0:
        raise ValueError("years must be non-negative")

    r = annual_rate_pct / 100.0
    n = compounds_per_year
    t = years
    fv = principal * (1 + r / n) ** (n * t)
    interest = fv - principal
    return {
        "principal": principal,
        "annual_rate_pct": annual_rate_pct,
        "years": years,
        "compounds_per_year": n,
        "future_value": round(fv, 2),
        "interest_earned": round(interest, 2),
        "note": "Illustrative only — ignores fees, tax, and inflation.",
    }


def loan_amortisation(
    principal: float,
    annual_rate_pct: float,
    years: int,
    payments_per_year: int = 12,
) -> dict[str, Any]:
    """Fixed-rate loan payment and total interest.

    Payment = P * r(1+r)^N / ((1+r)^N - 1) where r is periodic rate.
    """
    if principal <= 0:
        raise ValueError("principal must be positive")
    if years < 1:
        raise ValueError("years must be >= 1")
    if payments_per_year < 1:
        raise ValueError("payments_per_year must be >= 1")

    n = years * payments_per_year
    periodic = (annual_rate_pct / 100.0) / payments_per_year

    if periodic == 0:
        payment = principal / n
    else:
        factor = (1 + periodic) ** n
        payment = principal * (periodic * factor) / (factor - 1)

    total_paid = payment * n
    total_interest = total_paid - principal

    # First few schedule rows for transparency
    balance = principal
    schedule_preview: list[dict[str, float]] = []
    for i in range(1, min(4, n + 1)):
        interest_i = balance * periodic
        principal_i = payment - interest_i
        balance = max(0.0, balance - principal_i)
        schedule_preview.append(
            {
                "period": float(i),
                "payment": round(payment, 2),
                "interest": round(interest_i, 2),
                "principal": round(principal_i, 2),
                "balance": round(balance, 2),
            }
        )

    return {
        "principal": principal,
        "annual_rate_pct": annual_rate_pct,
        "years": years,
        "payments_per_year": payments_per_year,
        "periods": n,
        "payment": round(payment, 2),
        "total_paid": round(total_paid, 2),
        "total_interest": round(total_interest, 2),
        "schedule_preview": schedule_preview,
        "note": "Illustrative fixed-rate amortisation — not a product quote.",
    }


def percent_return(start_value: float, end_value: float) -> dict[str, Any]:
    """Simple percentage return between two values."""
    if start_value == 0:
        raise ValueError("start_value must be non-zero")
    change = end_value - start_value
    pct = (change / start_value) * 100.0
    return {
        "start_value": start_value,
        "end_value": end_value,
        "absolute_change": round(change, 4),
        "percent_return": round(pct, 4),
        "note": "Simple return — not annualised.",
    }


def cagr(start_value: float, end_value: float, years: float) -> dict[str, Any]:
    """Compound annual growth rate."""
    if start_value <= 0 or end_value <= 0:
        raise ValueError("start_value and end_value must be positive")
    if years <= 0:
        raise ValueError("years must be positive")
    rate = (end_value / start_value) ** (1.0 / years) - 1.0
    return {
        "start_value": start_value,
        "end_value": end_value,
        "years": years,
        "cagr_pct": round(rate * 100.0, 4),
        "note": "Past growth is not a guarantee of future results.",
    }


def risk_metrics(returns: list[float]) -> dict[str, Any]:
    """Simple risk stats from a list of period returns (e.g. decimal or %).

    Pass returns as percentages (e.g. 1.2 for +1.2%) or decimals —
    results are scaled consistently with the input units for mean/vol.
    """
    if len(returns) < 2:
        raise ValueError("need at least 2 return observations")

    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(variance)

    # Downside deviation (below 0)
    downside = [min(0.0, r - 0.0) for r in returns]
    down_var = sum(d**2 for d in downside) / (n - 1)
    downside_dev = math.sqrt(down_var)

    # Max drawdown on cumulative equity curve
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    # Treat returns as percentages if typical magnitudes look like %
    as_pct = max(abs(r) for r in returns) > 1.0
    for r in returns:
        factor = 1.0 + (r / 100.0 if as_pct else r)
        equity *= factor
        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak else 0.0
        max_dd = max(max_dd, dd)

    sharpe_proxy = (mean / std) if std > 0 else float("nan")

    return {
        "observations": n,
        "mean_return": round(mean, 6),
        "volatility": round(std, 6),
        "downside_deviation": round(downside_dev, 6),
        "max_drawdown_pct": round(max_dd * 100.0, 4),
        "sharpe_proxy": round(sharpe_proxy, 4) if std > 0 else None,
        "input_looks_like_percent": as_pct,
        "note": (
            "Educational sample stats only — not VaR, not annualised, "
            "and not a substitute for proper risk systems."
        ),
    }
