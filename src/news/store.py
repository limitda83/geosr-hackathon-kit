"""재난 이벤트 SQLite 저장소 — 누적·중복제거·조회."""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd

_SCHEMA = """
CREATE TABLE IF NOT EXISTS disaster_events (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    disaster_type      TEXT    NOT NULL,
    event_date         TEXT,
    raw_location_text  TEXT,
    normalized_sido    TEXT,
    normalized_sigungu TEXT,
    normalized_region  TEXT,
    lat                REAL,
    lon                REAL,
    geocode_confidence REAL,
    geocode_source     TEXT,
    source_title       TEXT,
    source_url         TEXT    NOT NULL,
    source_name        TEXT,
    pub_date           TEXT,
    origin             TEXT    NOT NULL,
    crawled_at         TEXT    NOT NULL,
    content_hash       TEXT    NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_events_hash   ON disaster_events(content_hash);
CREATE INDEX        IF NOT EXISTS ix_events_region ON disaster_events(normalized_region);
CREATE INDEX        IF NOT EXISTS ix_events_date   ON disaster_events(event_date);
CREATE INDEX        IF NOT EXISTS ix_events_type   ON disaster_events(disaster_type);
"""


@dataclass
class EventRecord:
    disaster_type: str
    event_date: str | None
    raw_location_text: str | None
    normalized_sido: str | None
    normalized_sigungu: str | None
    normalized_region: str | None
    lat: float | None
    lon: float | None
    geocode_confidence: float
    geocode_source: str
    source_title: str | None
    source_url: str
    source_name: str | None
    pub_date: str | None
    origin: str
    crawled_at: str

    def content_hash(self) -> str:
        """기사 단위 중복키: 정규화한 URL의 sha1."""
        canon = canonical_url(self.source_url)
        return hashlib.sha1(canon.encode("utf-8")).hexdigest()


_TRACKING_KEYS = {"fbclid", "gclid", "spm", "outurl", "utm_source",
                  "utm_medium", "utm_campaign", "utm_term", "utm_content"}


def canonical_url(url: str) -> str:
    """프래그먼트·추적 파라미터(utm_ 등)만 제거. 식별 쿼리(newsId 등)는 유지.

    공공데이터 기사 URL은 ?newsId= 로만 구분되므로 쿼리를 통째로 버리면 안 된다.
    """
    if not url:
        return ""
    p = urlsplit(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if k.lower() not in _TRACKING_KEYS and not k.lower().startswith("utm_")]
    q.sort()
    path = p.path.rstrip("/")
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path,
                       urlencode(q), "")).lower()


class EventStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path, check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init_schema(self) -> None:
        with self._connect() as con:
            con.executescript(_SCHEMA)

    def upsert_many(self, records: list[EventRecord]) -> int:
        """INSERT OR IGNORE — 새로 들어간 행 수를 반환."""
        if not records:
            return 0
        cols = list(asdict(records[0]).keys()) + ["content_hash"]
        placeholders = ",".join("?" * len(cols))
        sql = (f"INSERT OR IGNORE INTO disaster_events ({','.join(cols)}) "
               f"VALUES ({placeholders})")
        rows = [tuple(asdict(r).values()) + (r.content_hash(),) for r in records]
        with self._connect() as con:
            before = con.total_changes
            con.executemany(sql, rows)
            return con.total_changes - before

    def query(self, *, disaster_type: str | None = None,
              since: str | None = None, until: str | None = None,
              located_only: bool = False) -> pd.DataFrame:
        clauses, params = [], []
        if disaster_type:
            clauses.append("disaster_type = ?")
            params.append(disaster_type)
        if since:
            clauses.append("event_date >= ?")
            params.append(since)
        if until:
            clauses.append("event_date <= ?")
            params.append(until)
        if located_only:
            clauses.append("normalized_region IS NOT NULL AND lat IS NOT NULL")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = "SELECT * FROM disaster_events" + where + " ORDER BY event_date DESC"
        with self._connect() as con:
            return pd.read_sql_query(sql, con, params=params)

    def stats(self) -> dict:
        with self._connect() as con:
            total = con.execute("SELECT COUNT(*) FROM disaster_events").fetchone()[0]
            located = con.execute(
                "SELECT COUNT(*) FROM disaster_events "
                "WHERE normalized_region IS NOT NULL").fetchone()[0]
        return {
            "total": total,
            "located": located,
            "unlocated_rate": round(1 - located / total, 3) if total else 0.0,
        }
