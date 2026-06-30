#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ocean SST collection helpers.

KOSC API로 SST 데이터를 수집한다. API 키가 없거나 요청 실패 시 에러를 반환한다.
"""

from __future__ import annotations

import csv
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


def _parse_date(value: str) -> date:
    return datetime.strptime(value, DATE_FMT).date()


def _daterange(start: date, end: date) -> Iterable[date]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def _resolve_api_key() -> Optional[str]:
    key = os.environ.get("KOSC_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
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
        import requests
    except ImportError as exc:
        raise RuntimeError("KOSC collection requires `requests`.") from exc

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
            rows.append({
                "date": str(item.get("date") or item.get("datetime", "")),
                "lat": round(float(item.get("lat", lat)), 4),
                "lon": round(float(item.get("lon", lon)), 4),
                "sst": round(float(item.get("sst") or item.get("sst_celsius")), 2),
                "source": "KOSC",
            })
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
    if not api_key:
        return {"success": False, "error": "KOSC_API_KEY not set", "data": []}

    try:
        rows = _fetch_kosc(api_key, lat, lon, radius_km, start_d, end_d)
    except Exception as exc:
        return {"success": False, "error": str(exc), "data": []}

    if not rows:
        return {"success": False, "error": "KOSC API returned empty response", "data": []}

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
        "source": "KOSC",
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
