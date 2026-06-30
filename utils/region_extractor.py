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

# ---------------------------------------------------------------------------
# 경로 설정
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_EVENTS_PATH = _REPO_ROOT / "data" / "processed" / "disaster_db" / "disaster_events.csv"
_FREQ_DIR = _REPO_ROOT / "data" / "results" / "frequency"
_FREQ_PATH = _FREQ_DIR / "region_frequency.csv"

# ---------------------------------------------------------------------------
# 연안 지역 위경도 하드코딩 dict (Nominatim 호출 없이 즉시 반환)
# ---------------------------------------------------------------------------
COASTAL_COORDS: dict[str, tuple[float, float]] = {
    "통영": (34.8544, 128.4333),
    "여수": (34.7604, 127.6622),
    "부산": (35.1796, 129.0756),
    "거제": (34.8797, 128.6211),
    "완도": (34.3114, 126.7552),
    "고흥": (34.6042, 127.2756),
    "남해": (34.8378, 127.8925),
    "사천": (35.0036, 128.0644),
    "창원": (35.2279, 128.6811),
    "포항": (36.0190, 129.3435),
    "울산": (35.5384, 129.3114),
    "목포": (34.8118, 126.3922),
    "진도": (34.4867, 126.2636),
    "강진": (34.6414, 126.7672),
    "해남": (34.5739, 126.5990),
    "신안": (34.8396, 126.1069),
    "보성": (34.7711, 127.0800),
    "장흥": (34.6817, 126.9078),
    "순천": (34.9506, 127.4874),
    "광양": (34.9408, 127.6961),
    "하동": (35.0672, 127.7514),
    "고성": (34.9733, 128.3231),
    "마산": (35.1836, 128.5742),
    "진해": (35.1456, 128.6611),
    "울진": (36.9929, 129.4003),
    "영덕": (36.4153, 129.3650),
    "경주": (35.8562, 129.2247),
    "동해": (37.5247, 129.1144),
    "강릉": (37.7519, 128.8760),
    "속초": (38.2070, 128.5919),
    "삼척": (37.4499, 129.1650),
    "태안": (36.7456, 126.2983),
    "서산": (36.7848, 126.4500),
    "보령": (36.3331, 126.6128),
    "군산": (35.9678, 126.7368),
    "부안": (35.7317, 126.7331),
    "영광": (35.2772, 126.5122),
    "인천": (37.4563, 126.7052),
    "안산": (37.3219, 126.8309),
    "평택": (36.9921, 127.1128),
    "제주": (33.4996, 126.5312),
    "서귀포": (33.2541, 126.5600),
    "울릉도": (37.4845, 130.9057),
    "독도": (37.2426, 131.8647),
    "홍도": (34.6867, 125.1869),
    "흑산도": (34.6827, 125.4344),
}

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

    print(f"[region_extractor] {_EVENTS_PATH} not found -> using sample data ({len(_SAMPLE_EVENTS)} rows)")
    return pd.DataFrame(_SAMPLE_EVENTS, columns=["date", "location", "keyword", "title", "url"])


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
