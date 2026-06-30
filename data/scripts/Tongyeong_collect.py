#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproducible SST collection wrapper for Tongyeong."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.ocean_api import collect_ocean_data  # noqa: E402

REGION = "Tongyeong"
LAT = 34.85
LON = 128.43
RADIUS_KM = 10.0
START = "2025-06-01"
END = "2025-08-31"


def main() -> int:
    result = collect_ocean_data(REGION, LAT, LON, RADIUS_KM, START, END)
    if result["success"]:
        print(f"[ok] rows={result['count']}")
        print(f"[ok] saved -> {result['filepath']}")
        return 0
    print(f"[error] {result['error']}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
