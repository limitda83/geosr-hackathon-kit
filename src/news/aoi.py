"""빈도 집계 → 관심지역(AOI) 도출 및 JSON 입출력.

AOI는 뉴스 패키지와 수온(SST) 패키지의 유일한 연결고리(data/aoi.json)다.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import config


@dataclass
class AOI:
    rank: int
    region_name: str
    center_lat: float
    center_lon: float
    bbox: list  # [minlon, minlat, maxlon, maxlat]
    event_count: int


def _clamp(bbox: list) -> list:
    w, s, e, n = bbox
    W, S, E, N = config.KOREA_COAST_BBOX
    return [max(w, W), max(s, S), min(e, E), min(n, N)]


def region_frequency(df: pd.DataFrame) -> pd.DataFrame:
    """지역별 발생 빈도 + 대표 좌표(빈도 내림차순)."""
    cols = ["normalized_region", "event_count", "center_lat", "center_lon"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    g = (df.dropna(subset=["normalized_region", "lat", "lon"])
           .groupby("normalized_region")
           .agg(event_count=("id", "count"),
                center_lat=("lat", "mean"),
                center_lon=("lon", "mean"))
           .reset_index()
           .sort_values("event_count", ascending=False))
    return g[cols]


def daily_counts(df: pd.DataFrame) -> pd.DataFrame:
    """일자별 발생 건수 (일단위 누적 추이)."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["event_date", "count"])
    d = (df.dropna(subset=["event_date"])
           .groupby("event_date").size().reset_index(name="count")
           .sort_values("event_date"))
    return d


def compute_aois(df: pd.DataFrame, top_n: int = 3, pad_deg: float = 0.5,
                 min_count: int = 1) -> list[AOI]:
    freq = region_frequency(df)
    freq = freq[freq["event_count"] >= min_count].head(top_n)
    aois: list[AOI] = []
    for rank, (_, row) in enumerate(freq.iterrows(), start=1):
        clat, clon = float(row["center_lat"]), float(row["center_lon"])
        bbox = _clamp([clon - pad_deg, clat - pad_deg,
                       clon + pad_deg, clat + pad_deg])
        aois.append(AOI(rank, row["normalized_region"],
                        round(clat, 4), round(clon, 4),
                        [round(x, 4) for x in bbox], int(row["event_count"])))
    return aois


def aoi_from_region(df: pd.DataFrame, region_name: str,
                    pad_deg: float = 0.5) -> AOI | None:
    """특정 지역을 1순위 AOI로 직접 지정."""
    sub = df[df["normalized_region"] == region_name].dropna(subset=["lat", "lon"])
    if sub.empty:
        return None
    clat, clon = float(sub["lat"].mean()), float(sub["lon"].mean())
    bbox = _clamp([clon - pad_deg, clat - pad_deg, clon + pad_deg, clat + pad_deg])
    return AOI(1, region_name, round(clat, 4), round(clon, 4),
              [round(x, 4) for x in bbox], int(len(sub)))


def to_payload(aois: list[AOI], disaster_type: str,
               since: str | None = None, until: str | None = None) -> dict:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disaster_type": disaster_type,
        "window": {"since": since, "until": until},
        "grid_ref": {"crs": "EPSG:4326",
                     "coast_bbox": list(config.KOREA_COAST_BBOX)},
        "aois": [asdict(a) for a in aois],
    }


def save_aoi(payload: dict, path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_aoi(path) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as f:
        return json.load(f)
