#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Project-level SST collection CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.ocean_api import collect_ocean_data, generate_collection_script  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect ocean SST data")
    parser.add_argument("--region", required=True, help="Region name, e.g. Tongyeong")
    parser.add_argument("--lat", type=float, required=True, help="Latitude")
    parser.add_argument("--lon", type=float, required=True, help="Longitude")
    parser.add_argument("--radius", type=float, required=True, help="Search radius in km")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--gen-script", action="store_true", help="Write a reusable wrapper into data/scripts/")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = collect_ocean_data(
        args.region,
        args.lat,
        args.lon,
        args.radius,
        args.start,
        args.end,
    )
    if not result["success"]:
        print(f"[error] {result['error']}", file=sys.stderr)
        return 1

    print(f"[ok] source={result.get('source', 'unknown')} rows={result['count']}")
    print(f"[ok] saved -> {result['filepath']}")

    if args.gen_script:
        script_path = generate_collection_script(
            args.region,
            args.lat,
            args.lon,
            args.radius,
            args.start,
            args.end,
        )
        print(f"[ok] wrapper -> {script_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
