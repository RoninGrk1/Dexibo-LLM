#!/usr/bin/env python3
"""Run Dexibo golden evals against the mock pipeline (no GGUF required)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _contains_any(text: str, needles: list[str]) -> bool:
    low = (text or "").lower()
    return any(n.lower() in low for n in needles)


def run_case(case: dict, session) -> tuple[bool, str]:
    expect = case.get("expect") or {}
    result = session.ask_result(case["input"])
    text = result.text or ""
    errors: list[str] = []

    type_in = expect.get("type_in") or []
    if type_in and result.type not in type_in:
        # soft: allow text when optional quote fails offline
        if not (expect.get("optional") and result.type == "text"):
            errors.append(f"type={result.type!r} not in {type_in}")

    want_refuse = bool(expect.get("refuse"))
    if want_refuse and not result.refused:
        errors.append("expected refusal")
    if not want_refuse and result.refused:
        errors.append("unexpected refusal")

    needles = expect.get("contains_any") or []
    if needles and not _contains_any(text, needles):
        if expect.get("optional"):
            pass  # quote may be offline
        else:
            errors.append(f"missing any of {needles}")

    ok = not errors
    detail = "; ".join(errors) if errors else "ok"
    return ok, detail


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file",
        default=str(ROOT / "evals" / "golden.jsonl"),
        help="Path to golden JSONL",
    )
    args = parser.parse_args()

    from dexibo.chat import ChatSession
    from dexibo.config import load_config
    from dexibo.model import load_model

    cfg = load_config()
    # Force mock for speed / no GGUF
    object.__setattr__(cfg, "force_mock", True) if False else None
    # DexiboConfig is frozen — use env override via force by loading model mock
    import os

    os.environ["DEXIBO_FORCE_MOCK"] = "1"
    cfg = load_config()
    model = load_model(cfg)
    session = ChatSession(model=model, config=cfg)

    path = Path(args.file)
    cases = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    passed = failed = 0
    print(f"Running {len(cases)} golden cases against backend={model.backend_name}…")
    for case in cases:
        # fresh history per case
        session.clear()
        ok, detail = run_case(case, session)
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  [{status}] {case.get('id', '?')}: {detail}")

    print(f"\n{passed} passed, {failed} failed, {len(cases)} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
