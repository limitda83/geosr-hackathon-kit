"""크롤링 오케스트레이션: 수집 → 파싱(날짜·위치) → DB 누적 → 빈도 → AOI."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import config
from . import aoi as aoi_mod
from .bigkinds import read_bigkinds
from .parse import extract_event_date, resolve_location, strip_tags
from .sources import (NaverNewsSource, PublicDataNewsSource, RssSource,
                      SeedSource)
from .store import EventRecord, EventStore, canonical_url


def _iso(d) -> str | None:
    if d is None:
        return None
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def crawl(keywords, max_items=100, allow_seed=True, force_seed=False,
          since=None, until=None, search_field="제목"):
    """소스 우선순위: (강제시드) → 공공데이터(한국언론진흥재단) → 네이버 → RSS → 시드."""
    if force_seed:
        arts = SeedSource(config.SEED_CSV).fetch(max_items=10000)
        return arts, ("seed" if arts else "none")

    pub = PublicDataNewsSource(config.PUBLIC_DATA_API_KEY, search_field=search_field)
    if pub.available():
        primary = pub
    else:
        primary = NaverNewsSource(config.NAVER_CLIENT_ID, config.NAVER_CLIENT_SECRET)
        if not primary.available():
            primary = RssSource()

    articles, seen = [], set()
    for kw in keywords:
        try:
            got = primary.fetch(kw, max_items=max_items, since=since, until=until)
        except Exception:
            got = []
        for a in got:
            k = canonical_url(a.link) or a.title.strip()
            if not k or k in seen:
                continue
            seen.add(k)
            articles.append(a)

    if articles:
        return articles, primary.name
    if allow_seed:
        arts = SeedSource(config.SEED_CSV).fetch(max_items=10000)
        return arts, ("seed" if arts else "none")
    return [], "none"


def _to_records(articles, disaster_type, now):
    records, n_located = [], 0
    for a in articles:
        loc = resolve_location(a.title, a.description, a.location_hint)
        ev_date = extract_event_date(strip_tags(a.title or ""), a.pub_date)
        if loc.normalized_region:
            n_located += 1
        records.append(EventRecord(
            disaster_type=disaster_type, event_date=ev_date,
            raw_location_text=loc.raw_location_text,
            normalized_sido=loc.sido, normalized_sigungu=loc.sigungu,
            normalized_region=loc.normalized_region,
            lat=loc.lat, lon=loc.lon,
            geocode_confidence=loc.confidence, geocode_source=loc.geocode_source,
            source_title=strip_tags(a.title), source_url=a.link,
            source_name=a.source_name, pub_date=a.pub_date,
            origin=a.origin, crawled_at=now,
        ))
    return records, n_located


@dataclass
class RunReport:
    n_fetched: int
    n_new: int
    n_located: int
    source_used: str
    aois: list


def run_pipeline(disaster_type="고수온", keywords=None, max_items=100,
                 since=None, until=None, top_n=3,
                 db_path=None, aoi_path=None,
                 allow_seed=True, force_seed=False, search_field="제목") -> RunReport:
    config.ensure_dirs()
    keywords = keywords or [disaster_type]
    db_path = db_path or config.EVENTS_DB
    aoi_path = aoi_path or config.AOI_JSON

    articles, source_used = crawl(keywords, max_items=max_items,
                                  allow_seed=allow_seed, force_seed=force_seed,
                                  since=_iso(since), until=_iso(until),
                                  search_field=search_field)
    now = datetime.now(timezone.utc).isoformat()
    records, n_located = _to_records(articles, disaster_type, now)

    store = EventStore(db_path)
    n_new = store.upsert_many(records)

    df = store.query(disaster_type=disaster_type, since=_iso(since),
                     until=_iso(until), located_only=True)
    aois = aoi_mod.compute_aois(df, top_n=top_n)
    aoi_mod.save_aoi(
        aoi_mod.to_payload(aois, disaster_type=disaster_type,
                           since=_iso(since), until=_iso(until)),
        aoi_path)
    export_team_csv(db_path)
    return RunReport(len(articles), n_new, n_located, source_used, aois)


def get_events_df(disaster_type=None, since=None, until=None, db_path=None):
    store = EventStore(db_path or config.EVENTS_DB)
    return store.query(disaster_type=disaster_type, since=_iso(since),
                       until=_iso(until), located_only=False)


# --- 팀 멀티페이지 앱(pages/2_Disaster_Areas.py) 연동용 CSV 내보내기 ---
TEAM_EVENTS_CSV = config.DATA_DIR / "processed" / "disaster_db" / "disaster_events.csv"
TEAM_FREQ_CSV = config.DATA_DIR / "results" / "frequency" / "region_frequency.csv"


def _short_loc(sigungu) -> str:
    s = str(sigungu or "")
    return s[:-1] if s.endswith(("시", "군", "구")) else s


def export_team_csv(db_path=None):
    """SQLite → 팀 페이지가 읽는 두 CSV(disaster_events / region_frequency)로 내보내기."""
    store = EventStore(db_path or config.EVENTS_DB)
    df = store.query(located_only=False)
    if df.empty:
        return None, None

    ev = df.copy()
    ev["location"] = ev["normalized_sigungu"].map(_short_loc)
    ev = ev.rename(columns={"event_date": "date", "disaster_type": "keyword",
                            "source_title": "title", "source_url": "url"})
    TEAM_EVENTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    ev[["date", "location", "keyword", "title", "url"]].to_csv(
        TEAM_EVENTS_CSV, index=False, encoding="utf-8")

    loc = df.dropna(subset=["normalized_sigungu", "lat", "lon"]).copy()
    loc["location"] = loc["normalized_sigungu"].map(_short_loc)
    freq = (loc.groupby("location")
               .agg(count=("id", "count"), lat=("lat", "first"),
                    lon=("lon", "first"))
               .reset_index().sort_values("count", ascending=False))
    TEAM_FREQ_CSV.parent.mkdir(parents=True, exist_ok=True)
    freq.to_csv(TEAM_FREQ_CSV, index=False, encoding="utf-8")
    return TEAM_EVENTS_CSV, TEAM_FREQ_CSV


def ingest_bigkinds(path, disaster_type="고수온", keyword=None,
                    since=None, until=None, top_n=3,
                    db_path=None, aoi_path=None) -> RunReport:
    """빅카인즈 엑셀/CSV를 읽어 DB에 누적하고 AOI를 재계산(2025 등 과거 실데이터).

    keyword 지정 시 제목/본문에 포함된 기사만 적재(관련성 필터).
    """
    config.ensure_dirs()
    db_path = db_path or config.EVENTS_DB
    aoi_path = aoi_path or config.AOI_JSON

    articles = read_bigkinds(path)
    if keyword:
        kw = keyword.strip()
        articles = [a for a in articles
                    if kw in (a.title or "") or kw in (a.description or "")]

    now = datetime.now(timezone.utc).isoformat()
    records, n_located = _to_records(articles, disaster_type, now)
    store = EventStore(db_path)
    n_new = store.upsert_many(records)

    df = store.query(disaster_type=disaster_type, since=_iso(since),
                     until=_iso(until), located_only=True)
    aois = aoi_mod.compute_aois(df, top_n=top_n)
    aoi_mod.save_aoi(
        aoi_mod.to_payload(aois, disaster_type=disaster_type,
                           since=_iso(since), until=_iso(until)),
        aoi_path)
    export_team_csv(db_path)
    return RunReport(len(articles), n_new, n_located, "bigkinds", aois)
