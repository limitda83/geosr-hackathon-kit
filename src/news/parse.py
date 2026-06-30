"""기사 제목/요약에서 발생일과 발생위치를 추출."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from email.utils import parsedate_to_datetime

from .gazetteer import GAZETTEER, SIDO_ALIASES, RegionInfo, build_alias_index, region_label

_ALIAS_INDEX = build_alias_index()
_TAG_RE = re.compile(r"<[^>]+>")

_DATE_PATTERNS = [
    (re.compile(r"(\d{4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})"), "ymd"),
    (re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일"), "md"),
]


def strip_tags(s: str) -> str:
    """<b> 등 태그 제거 + HTML 엔티티 해제."""
    if not s:
        return ""
    return html.unescape(_TAG_RE.sub("", s)).strip()


def _parse_pub_date(pub_date: str | None) -> datetime | None:
    if not pub_date:
        return None
    try:
        return parsedate_to_datetime(pub_date)  # RFC822 (네이버 pubDate)
    except (TypeError, ValueError, IndexError):
        pass
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(pub_date.strip()[:10], fmt)
        except ValueError:
            continue
    return None


def extract_event_date(text: str, pub_date: str | None) -> str | None:
    """본문 내 날짜를 우선, 없으면 pub_date를 ISO(YYYY-MM-DD)로 반환."""
    pub = _parse_pub_date(pub_date)
    base_year = pub.year if pub else None
    pub_d = pub.date() if pub else None
    if text:
        for rx, kind in _DATE_PATTERNS:
            m = rx.search(text)
            if not m:
                continue
            try:
                if kind == "ymd":
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                else:
                    if base_year is None:
                        continue
                    y, mo, d = base_year, int(m.group(1)), int(m.group(2))
                cand = date(y, mo, d)
            except ValueError:
                continue
            # 발행일보다 미래의 본문 날짜는 '예정/계획'일 가능성 → 발행일 사용
            if pub_d and cand > pub_d:
                return pub_d.isoformat()
            return cand.isoformat()
    return pub_d.isoformat() if pub_d else None


@dataclass
class LocationResult:
    normalized_region: str | None
    sido: str | None
    sigungu: str | None
    lat: float | None
    lon: float | None
    confidence: float
    raw_location_text: str | None
    geocode_source: str = "gazetteer"


def _sido_mentioned(info: RegionInfo, text: str) -> bool:
    if info.sido in text:
        return True
    for short, full in SIDO_ALIASES.items():
        if full == info.sido and short in text:
            return True
    return False


def _score(cand: dict, text: str) -> float:
    info = GAZETTEER[cand["key"]]
    s = len(cand["alias"]) * 2.0           # 긴 표면형 우선 (통영시 > 통영)
    if cand.get("in_head"):
        s += 5.0
    if cand.get("in_hint"):
        s += 8.0                           # 사전추출 지역 개체명에 등장 → 강한 신호
    if _sido_mentioned(info, text):
        s += 10.0                          # 시도 동시언급 → 동명이지(고성 등) 해소
    s -= cand["pos"] * 0.001               # 앞쪽 등장 우선(미세)
    return s


def resolve_location(headline: str, description: str = "",
                     location_hint: str = "") -> LocationResult:
    """연안 지명사전으로 위치 추출. 사전추출 지역(개체명) 있으면 우선 활용. 키 불필요."""
    head = strip_tags(headline or "")
    desc = strip_tags(description or "")
    hint = location_hint or ""
    text = head + " " + desc + " " + hint

    candidates: list[dict] = []
    for alias, key in _ALIAS_INDEX:
        pos = text.find(alias)
        if pos == -1:
            continue
        candidates.append({"alias": alias, "key": key, "in_head": alias in head,
                           "in_hint": alias in hint, "pos": pos})
    if not candidates:
        return LocationResult(None, None, None, None, None, 0.0, None)

    best = max(candidates, key=lambda c: _score(c, text))
    info = GAZETTEER[best["key"]]

    conf = 0.85 if best.get("in_hint") else (0.75 if best["in_head"] else 0.60)
    if _sido_mentioned(info, text):
        conf = min(0.97, conf + 0.12)
    if best["alias"].endswith(("시", "군", "구")):
        conf = min(0.97, conf + 0.05)

    return LocationResult(
        normalized_region=region_label(info),
        sido=info.sido, sigungu=info.sigungu,
        lat=info.lat, lon=info.lon,
        confidence=round(conf, 2),
        raw_location_text=best["alias"],
    )
