"""Deterministic scenario studio — savings, mortgage stress, inflation drag."""

from __future__ import annotations

from typing import Any

from dexibo.system_prompt import DISCLAIMER_SHORT
from dexibo.tools.calculator import compound_interest, loan_amortisation


def savings_goal(
    *,
    target: float,
    monthly: float,
    annual_rate_pct: float = 3.0,
    years: float | None = None,
    starting: float = 0.0,
) -> dict[str, Any]:
    """Project savings toward a goal with regular monthly contributions."""
    if target <= 0:
        raise ValueError("target must be positive")
    if monthly < 0:
        raise ValueError("monthly must be non-negative")
    if starting < 0:
        raise ValueError("starting must be non-negative")

    r_month = (annual_rate_pct / 100.0) / 12.0

    def fv_at(months: int) -> float:
        bal = starting * ((1 + r_month) ** months) if months else starting
        if monthly == 0:
            return bal
        if r_month == 0:
            return bal + monthly * months
        annuity = monthly * (((1 + r_month) ** months) - 1) / r_month
        return bal + annuity

    if years is not None:
        if years < 0:
            raise ValueError("years must be non-negative")
        months = int(round(years * 12))
        projected = fv_at(months)
        shortfall = max(0.0, target - projected)
        return {
            "scenario": "savings_goal",
            "target": target,
            "starting": starting,
            "monthly": monthly,
            "annual_rate_pct": annual_rate_pct,
            "years": years,
            "months": months,
            "projected_value": round(projected, 2),
            "shortfall": round(shortfall, 2),
            "on_track": projected >= target,
            "note": "Illustrative savings projection — ignores fees, tax, and inflation.",
            "disclaimer": DISCLAIMER_SHORT,
        }

    if monthly == 0 and (starting <= 0 or annual_rate_pct <= 0):
        return {
            "scenario": "savings_goal",
            "target": target,
            "starting": starting,
            "monthly": monthly,
            "annual_rate_pct": annual_rate_pct,
            "months_needed": None,
            "years_needed": None,
            "reachable": False,
            "note": "Cannot reach target without contributions or growth.",
            "disclaimer": DISCLAIMER_SHORT,
        }

    lo, hi = 0, 50 * 12
    if fv_at(hi) < target:
        return {
            "scenario": "savings_goal",
            "target": target,
            "starting": starting,
            "monthly": monthly,
            "annual_rate_pct": annual_rate_pct,
            "months_needed": None,
            "years_needed": None,
            "reachable": False,
            "projected_at_50y": round(fv_at(hi), 2),
            "note": "Target not reached within 50 years under these assumptions.",
            "disclaimer": DISCLAIMER_SHORT,
        }
    while lo < hi:
        mid = (lo + hi) // 2
        if fv_at(mid) >= target:
            hi = mid
        else:
            lo = mid + 1
    months_needed = lo
    return {
        "scenario": "savings_goal",
        "target": target,
        "starting": starting,
        "monthly": monthly,
        "annual_rate_pct": annual_rate_pct,
        "months_needed": months_needed,
        "years_needed": round(months_needed / 12.0, 2),
        "projected_value": round(fv_at(months_needed), 2),
        "reachable": True,
        "note": "Illustrative — contribution timing and rates are simplified.",
        "disclaimer": DISCLAIMER_SHORT,
    }


def mortgage_stress(
    *,
    principal: float,
    annual_rate_pct: float,
    years: int,
    rate_shock_pct: float = 2.0,
    payments_per_year: int = 12,
) -> dict[str, Any]:
    """Compare base mortgage payment vs +rate-shock payment."""
    base = loan_amortisation(principal, annual_rate_pct, years, payments_per_year)
    stressed_rate = annual_rate_pct + rate_shock_pct
    stressed = loan_amortisation(principal, stressed_rate, years, payments_per_year)
    delta = stressed["payment"] - base["payment"]
    return {
        "scenario": "mortgage_stress",
        "principal": principal,
        "years": years,
        "payments_per_year": payments_per_year,
        "base_rate_pct": annual_rate_pct,
        "stressed_rate_pct": stressed_rate,
        "rate_shock_pct": rate_shock_pct,
        "base_payment": base["payment"],
        "stressed_payment": stressed["payment"],
        "payment_increase": round(delta, 2),
        "payment_increase_pct": round((delta / base["payment"]) * 100.0, 2)
        if base["payment"]
        else None,
        "base_total_interest": base["total_interest"],
        "stressed_total_interest": stressed["total_interest"],
        "note": "Illustrative stress test — not a lender affordability assessment.",
        "disclaimer": DISCLAIMER_SHORT,
    }


def inflation_drag(
    *,
    amount: float,
    years: float,
    inflation_pct: float = 2.5,
    nominal_return_pct: float = 0.0,
) -> dict[str, Any]:
    """Show purchasing-power erosion and optional real growth."""
    if amount < 0:
        raise ValueError("amount must be non-negative")
    if years < 0:
        raise ValueError("years must be non-negative")

    infl = inflation_pct / 100.0
    nom = nominal_return_pct / 100.0
    real_cash = amount / ((1 + infl) ** years) if years else amount
    nominal_end = amount * ((1 + nom) ** years) if years else amount
    real_end = nominal_end / ((1 + infl) ** years) if years else amount
    compound_note = None
    if nominal_return_pct != 0:
        compound_note = compound_interest(amount, nominal_return_pct, years, 1)

    lost = amount - real_cash
    return {
        "scenario": "inflation_drag",
        "amount": amount,
        "years": years,
        "inflation_pct": inflation_pct,
        "nominal_return_pct": nominal_return_pct,
        "purchasing_power_if_cash": round(real_cash, 2),
        "purchasing_power_lost_if_cash": round(lost, 2),
        "nominal_ending_value": round(nominal_end, 2),
        "real_ending_value": round(real_end, 2),
        "compound_reference": compound_note,
        "note": "Illustrative inflation maths — actual CPI paths vary.",
        "disclaimer": DISCLAIMER_SHORT,
    }


SCENARIO_HANDLERS = {
    "savings_goal": savings_goal,
    "mortgage_stress": mortgage_stress,
    "inflation_drag": inflation_drag,
}

_ALIASES = {
    "savings": "savings_goal",
    "mortgage": "mortgage_stress",
    "inflation": "inflation_drag",
}


def run_scenario(name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    key = (name or "").strip().lower().replace("-", "_")
    key = _ALIASES.get(key, key)
    if key not in SCENARIO_HANDLERS:
        raise ValueError(
            f"unknown scenario: {name!r}. Choose from: {', '.join(SCENARIO_HANDLERS)}"
        )
    return SCENARIO_HANDLERS[key](**(params or {}))


__all__ = [
    "savings_goal",
    "mortgage_stress",
    "inflation_drag",
    "run_scenario",
    "SCENARIO_HANDLERS",
]
