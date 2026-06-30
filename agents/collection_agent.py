"""Collection automation agent."""

from __future__ import annotations

from utils.ocean_api import collect_ocean_data


def run(regions: list[dict], start: str, end: str) -> list[dict]:
    results: list[dict] = []
    for region in regions:
        result = collect_ocean_data(
            region=region["location"],
            lat=region["lat"],
            lon=region["lon"],
            radius_km=50,
            start=start,
            end=end,
        )
        results.append({"region": region["location"], **result})
        status = "[ok]" if result["success"] else "[err]"
        print(f"  {status} {region['location']}: {result.get('count', 0)} rows")
    return results
