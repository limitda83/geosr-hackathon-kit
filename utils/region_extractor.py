"""
region_extractor.py
-------------------
재해 이벤트 CSV 에서 연안 지역명 빈도를 집계하고 위경도를 부여하는 모듈.

주요 함수
  load_disaster_events() -> pd.DataFrame
  extract_regions(df)    -> pd.DataFrame
  get_top_regions(n=5)   -> list[dict]
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from src.news.gazetteer import GAZETTEER, build_alias_index

# ---------------------------------------------------------------------------
# 경로 설정
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_EVENTS_PATH = _REPO_ROOT / "data" / "processed" / "disaster_db" / "disaster_events.csv"
_FREQ_DIR = _REPO_ROOT / "data" / "results" / "frequency"
_FREQ_PATH = _FREQ_DIR / "region_frequency.csv"

# gazetteer 기반 별칭→위경도 인덱스 (하드코딩 제거)
_ALIAS_INDEX = build_alias_index()
COASTAL_COORDS: dict[str, tuple[float, float]] = {}
for alias, key in _ALIAS_INDEX:
    info = GAZETTEER[key]
    if alias not in COASTAL_COORDS:
        COASTAL_COORDS[alias] = (info.lat, info.lon)

# ---------------------------------------------------------------------------
# 샘플 데이터 (disaster_events.csv 없을 때 fallback)
# ---------------------------------------------------------------------------
_SAMPLE_EVENTS = [
    {
        "date": "2025-07-10",
        "location": "통영",
        "keyword": "고수온",
        "title": "통영 해상 고수온 경보 발령",
        "url": "https://example.com/1",
    },
    {
        "date": "2025-07-15",
        "location": "여수",
        "keyword": "고수온",
        "title": "여수 양식장 고수온 피해 급증",
        "url": "https://example.com/2",
    },
    {
        "date": "2025-07-20",
        "location": "부산",
        "keyword": "고수온",
        "title": "부산 기장 해역 수온 이상 관측",
        "url": "https://example.com/3",
    },
    {
        "date": "2025-08-02",
        "location": "거제",
        "keyword": "고수온",
        "title": "거제 굴 양식장 고수온 피해",
        "url": "https://example.com/4",
    },
    {
        "date": "2025-08-08",
        "location": "완도",
        "keyword": "고수온",
        "title": "완도 전복 폐사 잇따라...고수온 원인",
        "url": "https://example.com/5",
    },
    {
        "date": "2025-08-10",
        "location": "통영",
        "keyword": "고수온",
        "title": "통영 고수온 피해 어가 지원 촉구",
        "url": "https://example.com/6",
    },
    {
        "date": "2025-08-15",
        "location": "여수",
        "keyword": "고수온",
        "title": "여수·고흥 연안 수온 29도 돌파",
        "url": "https://example.com/7",
    },
]

# ---------------------------------------------------------------------------
# 공개 함수
# ---------------------------------------------------------------------------

def load_disaster_events() -> pd.DataFrame:
    """
    data/processed/disaster_db/disaster_events.csv 를 로드한다.
    파일이 없으면 샘플 데이터(연안 고수온 기사 7건)를 DataFrame 으로 반환한다.

    Returns
    -------
    pd.DataFrame
        컬럼: date, location, keyword, title, url
    """
    if _EVENTS_PATH.exists():
        df = pd.read_csv(_EVENTS_PATH, encoding="utf-8")
        print(f"[region_extractor] loaded {len(df)} rows from {_EVENTS_PATH}")
        return df

    raise FileNotFoundError(f"{_EVENTS_PATH} not found")


def extract_regions(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame 의 location 컬럼에서 지역명 빈도를 집계하고 위경도를 부여한다.
    결과를 data/results/frequency/region_frequency.csv 에 저장 후 반환한다.

    Parameters
    ----------
    df : pd.DataFrame
        load_disaster_events() 반환값 (location 컬럼 필수)

    Returns
    -------
    pd.DataFrame
        컬럼: location, count, lat, lon
        - lat/lon 이 None 인 행은 연안 화이트리스트에 없는 지역(미해결).
    """
    if "location" not in df.columns:
        raise ValueError("DataFrame must have a 'location' column")

    freq = (
        df["location"]
        .dropna()
        .value_counts()
        .reset_index()
    )
    freq.columns = ["location", "count"]

    # 위경도 부여 (COASTAL_COORDS 하드코딩 기반)
    freq["lat"] = freq["location"].map(lambda x: COASTAL_COORDS.get(x, (None, None))[0])
    freq["lon"] = freq["location"].map(lambda x: COASTAL_COORDS.get(x, (None, None))[1])

    # 미해결 지역 보고
    unresolved = freq[freq["lat"].isna()]
    if not unresolved.empty:
        print(f"[region_extractor] unresolved regions: {unresolved['location'].tolist()}")

    # 저장
    _FREQ_DIR.mkdir(parents=True, exist_ok=True)
    freq.to_csv(_FREQ_PATH, index=False, encoding="utf-8")
    print(f"[region_extractor] saved -> {_FREQ_PATH} ({len(freq)} rows)")

    return freq


def get_top_regions(n: int = 5) -> list[dict]:
    """
    region_frequency.csv 에서 언급 빈도 상위 N 개 지역을 반환한다.
    CSV 가 없으면 load_disaster_events() + extract_regions() 를 자동 실행한다.

    Parameters
    ----------
    n : int
        반환할 상위 지역 수 (기본값 5)

    Returns
    -------
    list[dict]
        [{"location": str, "count": int, "lat": float, "lon": float}, ...]
        lat/lon 이 없는 항목(미해결)도 포함되며 해당 값은 None.
    """
    if not _FREQ_PATH.exists():
        print("[region_extractor] region_frequency.csv not found -> running extract_regions()")
        df = load_disaster_events()
        extract_regions(df)

    freq = pd.read_csv(_FREQ_PATH, encoding="utf-8")
    freq = freq.sort_values("count", ascending=False).head(n)

    result = []
    for _, row in freq.iterrows():
        result.append(
            {
                "location": row["location"],
                "count": int(row["count"]),
                "lat": float(row["lat"]) if pd.notna(row.get("lat")) else None,
                "lon": float(row["lon"]) if pd.notna(row.get("lon")) else None,
            }
        )
    return result


# ---------------------------------------------------------------------------
# 직접 실행 시 동작 확인
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    df = load_disaster_events()
    print(f"\nloaded: {len(df)} rows")
    print(df.head())

    print("\n--- extract_regions ---")
    freq_df = extract_regions(df)
    print(freq_df)

    print("\n--- top 5 regions ---")
    for r in get_top_regions(5):
        lat_str = f"{r['lat']:.4f}" if r["lat"] else "N/A"
        lon_str = f"{r['lon']:.4f}" if r["lon"] else "N/A"
        print(f"  {r['location']:6s} | count={r['count']} | lat={lat_str}, lon={lon_str}")
