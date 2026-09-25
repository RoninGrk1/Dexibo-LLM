#!/usr/bin/env python3
"""Download a recommended GGUF model into models/ for Dexibo (~4GB class)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dexibo.config import PROJECT_ROOT, RECOMMENDED_MODELS  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download a quantised GGUF instruct model suitable for Dexibo "
            "(~2–4.7 GB weights; target ~4GB systems)."
        )
    )
    parser.add_argument(
        "--choice",
        type=int,
        default=0,
        help="Index into recommended list (default 0 = Qwen2.5-3B Q4_K_M).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List recommended models and exit.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=PROJECT_ROOT / "models",
        help="Destination directory (default: models/).",
    )
    args = parser.parse_args()

    if args.list or args.choice < 0 or args.choice >= len(RECOMMENDED_MODELS):
        print("Recommended GGUF models for Dexibo (~4GB RAM/VRAM class):\n")
        for i, m in enumerate(RECOMMENDED_MODELS):
            print(f"  [{i}] {m['id']}")
            print(f"      file:  {m['filename']}")
            print(f"      size:  {m['approx_size']}")
            print(f"      notes: {m['notes']}\n")
        if args.list:
            return 0
        if args.choice < 0 or args.choice >= len(RECOMMENDED_MODELS):
            print(f"Invalid --choice {args.choice}", file=sys.stderr)
            return 1

    model = RECOMMENDED_MODELS[args.choice]
    outdir: Path = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    dest = outdir / model["local_name"]

    print(f"Dexibo model download")
    print(f"  repo:     {model['id']}")
    print(f"  file:     {model['filename']}")
    print(f"  size:     {model['approx_size']} (approx)")
    print(f"  save as:  {dest}")
    print()

    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print(
            "huggingface-hub is required. Install with: pip install huggingface-hub",
            file=sys.stderr,
        )
        return 1

    path = hf_hub_download(
        repo_id=model["id"],
        filename=model["filename"],
        local_dir=str(outdir),
        local_dir_use_symlinks=False,
    )
    downloaded = Path(path)

    # Normalise to the expected local_name if HF kept original casing
    if downloaded.resolve() != dest.resolve():
        if dest.exists():
            dest.unlink()
        downloaded.rename(dest)
        final = dest
    else:
        final = downloaded

    size_mb = final.stat().st_size / (1024 * 1024)
    print(f"\nDone. Saved {final} ({size_mb:.0f} MiB).")
    print("Set DEXIBO_MODEL_PATH if needed, then: python -m dexibo")
    print(
        "\nNote: runtime RAM/VRAM is higher than file size "
        "(context, KV cache, Python). Prefer Q4_K_M 3B on tight 4GB boxes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
