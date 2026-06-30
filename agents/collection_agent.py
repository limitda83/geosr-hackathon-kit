"""Collection automation agent."""

from __future__ import annotations

import math

from utils.ocean_api import collect_ocean_data


def _has_coord(value) -> bool:
    """lat/lon 이 수집 가능한 유효 좌표인지 검사 (None/NaN/비숫자 방어)."""
    if value is None:
        return False
    try:
        return not math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def run(regions: list[dict], start: str, end: str) -> list[dict]:
    results: list[dict] = []
    for region in regions:
        name = region.get("location")
        lat = region.get("lat")
        lon = region.get("lon")

        # 위경도가 미해결(None/NaN)인 지역은 건너뛴다.
        # (collect_ocean_data 의 좌표 비교에서 TypeError 로 전체가 죽는 것을 방지)
        if not name or not _has_coord(lat) or not _has_coord(lon):
            print(f"  [skip] {name}: 위경도 미해결(lat/lon 없음) → 수집 건너뜀")
            results.append(
                {"region": name, "success": False, "error": "missing lat/lon", "count": 0, "data": []}
            )
            continue

        result = collect_ocean_data(
            region=name,
            lat=lat,
            lon=lon,
            radius_km=50,
            start=start,
            end=end,
        )
        results.append({"region": name, **result})
        status = "[ok]" if result["success"] else "[err]"
        print(f"  {status} {name}: {result.get('count', 0)} rows")
    return results
