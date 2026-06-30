"""
뉴스 수집 서브에이전트
disaster_events.csv 로드 → 관심지역 추출 → region_frequency.csv 저장
"""
from utils.region_extractor import load_disaster_events, extract_regions


def run(keyword: str, start: str, end: str) -> list[dict]:
    df = load_disaster_events()
    if "keyword" in df.columns and keyword:
        df = df[df["keyword"].str.contains(keyword, na=False)]

    regions_df = extract_regions(df)
    regions = regions_df.to_dict("records")
    print(f"  → 관심지역 {len(regions)}개 추출")
    return regions
