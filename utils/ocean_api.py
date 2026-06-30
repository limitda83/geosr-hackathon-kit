#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ocean SST collection helpers.

This module provides the reusable collection/ingestion path for the project:
- `collect_ocean_data(...)` downloads SST data when the KOSC API is configured.
- It falls back to deterministic sample data when API access is unavailable.
- `generate_collection_script(...)` writes a reproducible region-specific wrapper
  into `data/scripts/` so the collection step can be rerun later.

The goal is a stable, end-to-end data acquisition slice that downstream analysis
can consume without depending on the UI.
"""

from __future__ import annotations

import csv
import hashlib
import os
import sys
import textwrap
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DATE_FMT = "%Y-%m-%d"
CSV_HEADER = ["date", "lat", "lon", "sst", "source"]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SCRIPTS_DIR = DATA_DIR / "scripts"

DEFAULT_KOSC_URL = os.environ.get(
    "KOSC_API_URL",
    "https://www.nosc.go.kr/openapi/sstService",
)

MONTHLY_SST_PARAMS: Dict[int, tuple[float, float]] = {
    1: (8.0, 3.0),
    2: (7.5, 3.0),
    3: (9.5, 3.0),
    4: (13.0, 3.0),
    5: (17.5, 3.0),
    6: (21.5, 3.5),
    7: (25.0, 3.5),
    8: (27.5, 3.0),
    9: (24.5, 3.0),
    10: (20.0, 3.0),
    11: (15.0, 3.0),
    12: (10.5, 3.0),
}

REGION_OFFSET: Dict[str, float] = {
    "Tongyeong": 1.0,
    "Yeosu": 0.8,
    "Busan": 0.5,
}


def _parse_date(value: str) -> date:
    return datetime.strptime(value, DATE_FMT).date()


def _daterange(start: date, end: date) -> Iterable[date]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def _deterministic_noise(lat: float, lon: float, day: date) -> float:
    key = f"{lat:.4f}_{lon:.4f}_{day.isoformat()}".encode("utf-8")
    digest = hashlib.sha256(key).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _fallback_sst(lat: float, lon: float, day: date, region: str) -> float:
    base, rng = MONTHLY_SST_PARAMS.get(day.month, (18.0, 3.0))
    if day.month == 8 and 10 <= day.day <= 20:
        base += 1.5
    offset = REGION_OFFSET.get(region, 0.0)
    noise = _deterministic_noise(lat, lon, day)
    return round(base + offset + (noise * rng) - (rng / 2), 2)


def _generate_fallback_rows(
    region: str,
    lat: float,
    lon: float,
    start: date,
    end: date,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for day in _daterange(start, end):
        rows.append(
            {
                "date": day.strftime(DATE_FMT),
                "lat": round(lat, 4),
                "lon": round(lon, 4),
                "sst": _fallback_sst(lat, lon, day, region),
                "source": "fallback_sample",
            }
        )
    return rows


def _resolve_api_key() -> Optional[str]:
    key = os.environ.get("KOSC_API_KEY")
    if key:
        return key
    try:
        import streamlit as st  # type: ignore

        return st.secrets.get("KOSC_API_KEY")
    except Exception:
        return None


def _fetch_kosc(
    api_key: str,
    lat: float,
    lon: float,
    radius_km: float,
    start: date,
    end: date,
) -> List[Dict[str, Any]]:
    try:
        import requests  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError("KOSC collection requires `requests`. Install it first.") from exc

    params = {
        "serviceKey": api_key,
        "startDate": start.strftime("%Y%m%d"),
        "endDate": end.strftime("%Y%m%d"),
        "lat": lat,
        "lon": lon,
        "radius": radius_km,
        "ResultType": "json",
    }
    resp = requests.get(DEFAULT_KOSC_URL, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    items: list = []
    if isinstance(payload, dict):
        items = (
            payload.get("items")
            or payload.get("data")
            or payload.get("response", {}).get("body", {}).get("items", [])
            or []
        )
    elif isinstance(payload, list):
        items = payload

    rows: List[Dict[str, Any]] = []
    for item in items:
        try:
            rows.append(
                {
                    "date": str(item.get("date") or item.get("datetime", "")),
                    "lat": round(float(item.get("lat", lat)), 4),
                    "lon": round(float(item.get("lon", lon)), 4),
                    "sst": round(float(item.get("sst") or item.get("sst_celsius")), 2),
                    "source": "KOSC",
                }
            )
        except (TypeError, ValueError):
            continue
    return rows


def collect_ocean_data(
    region: str,
    lat: float,
    lon: float,
    radius_km: float,
    start: str,
    end: str,
) -> dict:
    errors = []
    if not region or not region.strip():
        errors.append("region is required")
    if not (-90.0 <= lat <= 90.0):
        errors.append(f"lat out of range: {lat}")
    if not (-180.0 <= lon <= 180.0):
        errors.append(f"lon out of range: {lon}")
    if radius_km <= 0:
        errors.append(f"radius_km must be positive: {radius_km}")

    try:
        start_d = _parse_date(start)
    except Exception:
        errors.append(f"start must use YYYY-MM-DD: {start}")
        start_d = None
    try:
        end_d = _parse_date(end)
    except Exception:
        errors.append(f"end must use YYYY-MM-DD: {end}")
        end_d = None
    if start_d and end_d and end_d < start_d:
        errors.append("end must be on or after start")
    if errors:
        return {"success": False, "error": "; ".join(errors), "data": []}

    assert start_d is not None and end_d is not None

    api_key = _resolve_api_key()
    used_fallback = False
    rows: List[Dict[str, Any]] = []

    if api_key:
        try:
            rows = _fetch_kosc(api_key, lat, lon, radius_km, start_d, end_d)
            if not rows:
                print("[ocean_api] KOSC response empty, switching to fallback", file=sys.stderr)
                used_fallback = True
        except Exception as exc:
            print(f"[ocean_api] KOSC request failed ({exc}); switching to fallback", file=sys.stderr)
            used_fallback = True
    else:
        print("[ocean_api] KOSC_API_KEY not set; using fallback sample data", file=sys.stderr)
        used_fallback = True

    if used_fallback:
        rows = _generate_fallback_rows(region, lat, lon, start_d, end_d)

    if not rows:
        return {"success": False, "error": "no rows returned", "data": []}

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"{region}_{start.replace('-', '')}_{end.replace('-', '')}.csv"
    file_path = DATA_DIR / file_name
    with file_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)

    return {
        "success": True,
        "count": len(rows),
        "filepath": str(file_path),
        "data": rows,
        "source": "fallback_sample" if used_fallback else "KOSC",
    }


def generate_collection_script(
    region: str,
    lat: float,
    lon: float,
    radius_km: float,
    start: str,
    end: str,
) -> str:
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    script_path = SCRIPTS_DIR / f"{region}_collect.py"

    script_body = textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        # -*- coding: utf-8 -*-
        \"\"\"Reproducible collection wrapper for {region}.\"\"\"

        from pathlib import Path
        import sys

        PROJECT_ROOT = Path(__file__).resolve().parents[2]
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))

        from utils.ocean_api import collect_ocean_data

        REGION = {region!r}
        LAT = {lat!r}
        LON = {lon!r}
        RADIUS_KM = {radius_km!r}
        START = {start!r}
        END = {end!r}


        def main() -> int:
            result = collect_ocean_data(REGION, LAT, LON, RADIUS_KM, START, END)
            if result["success"]:
                print(f"[ok] {{result['count']}} rows saved to {{result['filepath']}}")
                print(f"[ok] source={{result.get('source', 'unknown')}}")
                return 0
            print(f"[error] {{result['error']}}", file=sys.stderr)
            return 1


        if __name__ == "__main__":
            raise SystemExit(main())
        """
    )

    script_path.write_text(script_body, encoding="utf-8")
    return str(script_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ocean collection helper")
    parser.add_argument("--region", required=True)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--radius", type=float, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--gen-script", action="store_true")
    args = parser.parse_args()

    result = collect_ocean_data(args.region, args.lat, args.lon, args.radius, args.start, args.end)
    if not result["success"]:
        print(f"[error] {result['error']}", file=sys.stderr)
        raise SystemExit(1)

    print(f"[ok] count={result['count']} filepath={result['filepath']}")
    if args.gen_script:
        script_path = generate_collection_script(
            args.region, args.lat, args.lon, args.radius, args.start, args.end
        )
        print(f"[ok] script={script_path}")
