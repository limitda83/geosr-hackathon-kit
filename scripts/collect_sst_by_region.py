# -*- coding: utf-8 -*-
"""
collect_sst_by_region.py — 크롤링 결과 기반 지역 추출 → KHOA SST 실데이터 수집

흐름:
  1) data/processed/disaster_db/disaster_events.csv (뉴스 크롤링 결과)에서 지역명 추출
  2) data/results/frequency/region_frequency.csv (지오코딩 결과)에서 위경도 매핑
  3) 각 지역 좌표 ±0.2° 박스 평균 SST 를 KHOA OPeNDAP ASCII 로 수집
  4) data/{지역명}_{start}_{end}.csv 저장 (이전 더미 파일 교체)

사용:
  python scripts/collect_sst_by_region.py
  python scripts/collect_sst_by_region.py --start 2025-06-01 --end 2025-08-31
  python scripts/collect_sst_by_region.py --top 5   # 빈도 상위 N개 지역만
"""

import argparse
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE = "https://nosc.go.kr/opendap/hyrax/CONJUGATE/KHOA_SST"
HEADERS = {"User-Agent": "Mozilla/5.0 (KHOA-SST-collector/2.0; research)"}
TIMEOUT = 20
SLEEP = 0.3
BOX_DEG = 0.2        # 지역 좌표 ±0.2° 박스
FILL_VAL = -999.0

DATA_DIR = Path("data")
DISASTER_CSV = DATA_DIR / "processed" / "disaster_db" / "disaster_events.csv"
FREQ_CSV     = DATA_DIR / "results" / "frequency" / "region_frequency.csv"
GEOCODE_CSV  = DATA_DIR / "regions_geocoded.csv"


def load_regions_from_crawl(top: int = None) -> pd.DataFrame:
    """크롤링 결과(disaster_events)에서 지역 추출 → 지오코딩 좌표 매핑.

    Returns: DataFrame[location, lat, lon, news_count]
    """
    events = pd.read_csv(DISASTER_CSV, encoding="utf-8")
    counts = events["location"].dropna().value_counts().reset_index()
    counts.columns = ["location", "news_count"]

    # 좌표 소스: region_frequency(지오코딩 포함) > regions_geocoded
    freq = pd.read_csv(FREQ_CSV, encoding="utf-8")[["location", "lat", "lon"]]
    geo  = pd.read_csv(GEOCODE_CSV, encoding="utf-8")[["region", "lat", "lon"]]
    geo  = geo.rename(columns={"region": "location"})
    coords = pd.concat([freq, geo]).drop_duplicates("location").dropna(subset=["lat", "lon"])

    merged = counts.merge(coords, on="location", how="inner")
    merged = merged.sort_values("news_count", ascending=False).reset_index(drop=True)

    if top:
        merged = merged.head(top)

    print(f"[지역 추출] 크롤링 결과 기반 {len(merged)}개 지역 선정")
    for _, r in merged.iterrows():
        print(f"  {r['location']}  뉴스 {r['news_count']}건  ({r['lat']:.4f}N, {r['lon']:.4f}E)")
    return merged


def lat2idx(lat: float) -> int:
    return round((lat - 20.0) / 0.01)

def lon2idx(lon: float) -> int:
    return round((lon - 117.0) / 0.01)

def box_indices(lat: float, lon: float, box: float = BOX_DEG):
    step = round(box / 0.01)
    return (
        lat2idx(lat) - step, lat2idx(lat) + step,
        lon2idx(lon) - step, lon2idx(lon) + step,
    )

def fetch_sst(d: date, lat: float, lon: float) -> float | None:
    """해당 날짜·지역의 박스 평균 SST (°C) 반환. 실패 또는 전부 결측이면 None."""
    li, la, lo, hi = box_indices(lat, lon)
    li = max(0, li); la = min(3300, la)
    lo = max(0, lo); hi = min(3300, hi)

    fname = f"KHOA_SST_L4_Z003_D01_WGS001K_U{d.strftime('%Y%m%d')}.nc"
    url = (f"{BASE}/{d.year}/{d.month:02d}/{fname}.ascii"
           f"?sst[0][{li}:{la}][{lo}:{hi}]")
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException:
        return None

    vals = []
    for line in r.text.splitlines():
        if not line.startswith("sst.sst"):
            continue
        parts = line.split(",")[1:]
        for p in parts:
            try:
                v = float(p.strip())
                if v != FILL_VAL and not np.isnan(v):
                    vals.append(v)
            except ValueError:
                pass

    return round(float(np.mean(vals)), 4) if vals else None


def daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def collect_region(region: str, lat: float, lon: float,
                   start: date, end: date, out_dir: Path) -> Path:
    rows = []
    days = list(daterange(start, end))
    print(f"\n[{region}] {lat:.4f}N {lon:.4f}E  ({len(days)}일)")

    for i, d in enumerate(days, 1):
        sst = fetch_sst(d, lat, lon)
        status = f"{sst:.2f}°C" if sst is not None else "결측"
        print(f"  ({i:3d}/{len(days)}) {d}  {status}")
        rows.append({
            "date": d.isoformat(),
            "lat": lat,
            "lon": lon,
            "sst": sst,
            "source": "KHOA_OPeNDAP",
        })
        time.sleep(SLEEP)

    df = pd.DataFrame(rows)
    start_tag = start.strftime("%Y%m%d")
    end_tag = end.strftime("%Y%m%d")
    out_path = out_dir / f"{region}_{start_tag}_{end_tag}.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    valid = df["sst"].notna().sum()
    print(f"  → 저장: {out_path}  (유효 {valid}/{len(days)}일)")
    return out_path


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="크롤링 기반 KHOA SST 지역별 수집기")
    p.add_argument("--start",   default="2025-06-01")
    p.add_argument("--end",     default="2025-08-31")
    p.add_argument("--out",     default=str(DATA_DIR))
    p.add_argument("--top",     type=int, default=None, help="뉴스 빈도 상위 N개 지역만 수집")
    p.add_argument("--regions", nargs="*", help="특정 지역명 지정(미입력 시 크롤링 결과 전체)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    start = date.fromisoformat(args.start)
    end   = date.fromisoformat(args.end)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 크롤링 결과에서 지역 추출
    regions_df = load_regions_from_crawl(top=args.top)
    if args.regions:
        regions_df = regions_df[regions_df["location"].isin(args.regions)]

    if regions_df.empty:
        print("수집할 지역이 없습니다.")
        sys.exit(1)

    print(f"\n=== KHOA SST 수집 시작 ===")
    print(f"기간: {start} ~ {end}")
    print(f"지역: {regions_df['location'].tolist()}")

    # 기존 더미/이전 파일 삭제
    for _, row in regions_df.iterrows():
        region = row["location"]
        for old in out_dir.glob(f"{region}_*.csv"):
            print(f"  [삭제] 이전 파일: {old.name}")
            old.unlink()

    saved = []
    for _, row in regions_df.iterrows():
        path = collect_region(
            region=row["location"],
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            start=start,
            end=end,
            out_dir=out_dir,
        )
        saved.append(path)

    print(f"\n=== 완료 ===  {len(saved)}개 파일 저장")
    for p in saved:
        print(f"  {p}")


if __name__ == "__main__":
    main()
