# -*- coding: utf-8 -*-
"""
crawler_collection_agent.py — 크롤러(뉴스) → 지역 추출 → 수온 수집 연결 서브에이전트

이 모듈이 채우는 '빠진 고리':
  src/news_crawler.crawl(keyword, limit) 는 원시 기사 dict 리스트만 돌려준다.
    스키마: {title, press, published, url, google_link, body, note}  ← location/lat/lon 없음
  collection_agent.run(regions, ...) 은 region["location"], region["lat"], region["lon"] 을 기대한다.

  → 그래서 기사 텍스트(title+body)에서 연안 지역명을 탐지하고 위경도를 부여하는
    단계를 끼워 넣어 두 컴포넌트를 연결한다.

공개 함수:
  extract_regions_from_articles(articles) -> list[dict]   # 기사 → [{location,count,lat,lon}]
  collect_from_crawler(keyword, start, end, limit, articles=None) -> (regions, results)

라이브 크롤(feedparser/trafilatura/googlenewsdecoder 필요)이 불가능한 환경에서도
연결/검증이 가능하도록, articles 를 직접 주입할 수 있게 설계했다.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from utils.region_extractor import COASTAL_COORDS, extract_regions
from agents.collection_agent import run as run_collection

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src"


# ---------------------------------------------------------------------------
# 1) 기사 텍스트 → 관심지역(location/lat/lon)
# ---------------------------------------------------------------------------
def extract_regions_from_articles(
    articles: list[dict],
    text_keys: tuple[str, ...] = ("title", "body"),
) -> list[dict]:
    """크롤러 기사 dict 리스트에서 연안 지역명을 탐지해 빈도·위경도를 부여한다.

    한 기사가 같은 지역을 여러 번 언급해도 1회로 집계
    → count = 그 지역을 언급한 기사 수.
    COASTAL_COORDS 화이트리스트와 extract_regions() 를 재사용하므로
    출력 스키마는 기존 news_agent.run() 과 동일하다: {location, count, lat, lon}.
    """
    detected: list[dict] = []
    for art in articles or []:
        if not isinstance(art, dict):
            continue
        text = " ".join(str(art.get(k, "") or "") for k in text_keys)
        seen: set[str] = set()
        for name in COASTAL_COORDS:
            if name in text and name not in seen:
                detected.append({"location": name})
                seen.add(name)

    if not detected:
        print("[crawler_collection] 기사에서 탐지된 연안 지역이 없습니다.")
        return []

    df = pd.DataFrame(detected)
    print(f"[crawler_collection] 기사 {len(articles)}건에서 지역 언급 {len(detected)}건 탐지")
    # extract_regions: 빈도 집계 + 위경도 부여 + region_frequency.csv 저장 (기존 로직 재사용)
    freq_df = extract_regions(df)
    return freq_df.to_dict("records")


# ---------------------------------------------------------------------------
# 2) 라이브 크롤러 호출 (의존성 없으면 명확히 실패)
# ---------------------------------------------------------------------------
def _live_crawl(keyword: str, limit: int) -> list[dict]:
    """src/news_crawler.crawl 을 import 해 실행한다. 의존성 미설치 시 RuntimeError."""
    if str(_SRC_DIR) not in sys.path:
        sys.path.insert(0, str(_SRC_DIR))
    try:
        from news_crawler import crawl  # type: ignore
    except Exception as exc:  # feedparser/trafilatura/googlenewsdecoder 미설치 등
        raise RuntimeError(
            f"라이브 크롤러를 불러올 수 없습니다 ({exc}). "
            f"`pip install -r requirements.txt` 후 재시도하거나 articles 를 직접 주입하세요."
        ) from exc
    return crawl(keyword, limit)


# ---------------------------------------------------------------------------
# 3) 미해결 지역(위경도 None/NaN) 필터링 — collection 크래시 방지
# ---------------------------------------------------------------------------
def _is_valid_coord(value) -> bool:
    if value is None:
        return False
    try:
        return not math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def _filter_collectable(regions: list[dict]) -> tuple[list[dict], list[dict]]:
    """lat/lon 이 유효한 지역만 수집 대상으로 분리. (collectable, skipped)"""
    collectable, skipped = [], []
    for r in regions:
        if _is_valid_coord(r.get("lat")) and _is_valid_coord(r.get("lon")):
            collectable.append(r)
        else:
            skipped.append(r)
            print(f"  [skip] {r.get('location')}: 위경도 미해결(lat/lon 없음) → 수집 제외")
    return collectable, skipped


# ---------------------------------------------------------------------------
# 4) 연결: 크롤러 → 지역 추출 → 수온 수집
# ---------------------------------------------------------------------------
def collect_from_crawler(
    keyword: str = "고수온",
    start: str = "2025-06-01",
    end: str = "2025-08-31",
    limit: int = 20,
    articles: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """크롤러로 기사를 모아 관심지역을 뽑고, 각 지역의 수온 데이터를 data/ 에 적재한다.

    articles 를 주면 라이브 크롤을 건너뛰고 그 기사들을 사용한다(테스트/오프라인용).
    반환: (regions, results)  — results 는 collection_agent.run() 결과.
    """
    if articles is None:
        print(f"[1/2] 뉴스 크롤링 (keyword='{keyword}', limit={limit}) ...")
        articles = _live_crawl(keyword, limit)
    else:
        print(f"[1/2] 주입된 기사 {len(articles)}건 사용 (라이브 크롤 생략)")

    regions = extract_regions_from_articles(articles)
    print(f"  → 관심지역 {len(regions)}개 추출")

    collectable, _skipped = _filter_collectable(regions)
    print(f"[2/2] 수온 데이터 수집 ({len(collectable)}개 지역) ...")
    results = run_collection(collectable, start, end)
    return regions, results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="crawler → region → ocean collection")
    parser.add_argument("--keyword", default="고수온")
    parser.add_argument("--start", default="2025-06-01")
    parser.add_argument("--end", default="2025-08-31")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    regions, results = collect_from_crawler(
        keyword=args.keyword, start=args.start, end=args.end, limit=args.limit
    )
    ok = sum(1 for r in results if r.get("success"))
    print(f"\n[done] regions={len(regions)} collected_ok={ok}/{len(results)}")
