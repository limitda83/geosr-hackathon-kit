"""빅카인즈 '엑셀 다운로드'(.xlsx)/CSV 적재 → RawArticle 목록.

빅카인즈 분석결과(NewsResult) 표준 컬럼을 매핑한다. 컬럼명이 버전마다
조금씩 달라서 후보 목록으로 견고하게 탐지한다. 위치/인물/기관 개체명과
일자(YYYYMMDD)가 이미 추출돼 있어 그대로 활용한다.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .sources import RawArticle

# 필드 → 가능한 컬럼명 후보(공백/대소문자 무시 비교)
_COLS: dict[str, list[str]] = {
    "title": ["제목"],
    "date": ["일자", "날짜"],
    "url": ["URL", "원문주소", "주소", "링크"],
    "newsid": ["뉴스 식별자", "뉴스식별자", "newsId"],
    "provider": ["언론사"],
    "location": ["위치", "개체명(위치)", "개체명(지역)"],
    "keyword": ["키워드"],
    "body": ["본문", "본문(요약)"],
    "byline": ["기고자"],
}


def _norm(s: str) -> str:
    return str(s).replace(" ", "").lower()


def _build_index(columns) -> dict[str, str]:
    norm_cols = {_norm(c): c for c in columns}
    idx: dict[str, str] = {}
    for field, cands in _COLS.items():
        for cand in cands:
            if _norm(cand) in norm_cols:
                idx[field] = norm_cols[_norm(cand)]
                break
    return idx


def _val(row, idx: dict, field: str, default: str = "") -> str:
    col = idx.get(field)
    if not col:
        return default
    v = row.get(col, default)
    return "" if v is None else str(v)


def _parse_date(v: str) -> str | None:
    """'20250801' / '2025-08-01' / '2025.08.01' → '2025-08-01'."""
    s = str(v).strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    if len(s) >= 10 and s[4] in "-./":
        return s[:10].replace(".", "-").replace("/", "-")
    return None


def read_bigkinds(path) -> list[RawArticle]:
    """빅카인즈 엑셀/CSV → RawArticle 목록."""
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(p, dtype=str)
    else:
        df = pd.read_csv(p, dtype=str)
    df = df.fillna("")

    idx = _build_index(df.columns)
    if "title" not in idx:
        raise ValueError(
            "빅카인즈 형식이 아닙니다('제목' 컬럼을 찾을 수 없음). "
            f"발견된 컬럼: {list(df.columns)[:15]}")

    out: list[RawArticle] = []
    for _, row in df.iterrows():
        link = _val(row, idx, "url")
        if not link:
            nid = _val(row, idx, "newsid")
            link = f"bigkinds://{nid}" if nid else ""
        body = _val(row, idx, "body")
        kw = _val(row, idx, "keyword")
        prov = _val(row, idx, "provider") or "빅카인즈"
        out.append(RawArticle(
            title=_val(row, idx, "title"),
            link=link,
            description=(body or kw)[:300],
            pub_date=_parse_date(_val(row, idx, "date")),
            source_name=prov + "/bigkinds",
            origin="bigkinds",
            location_hint=_val(row, idx, "location"),
        ))
    return out
