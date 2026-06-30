"""뉴스 소스 — 공공데이터포털 한국언론진흥재단 메타데이터(우선, 기간검색 가능)
/ 네이버 검색 API / Google News RSS / 시드.

모든 소스의 fetch(query, max_items, since, until) 시그니처 통일.
since/until 은 'YYYY-MM-DD' 문자열. (네이버/RSS는 무시, 공공데이터/시드는 활용)
"""
from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import requests


@dataclass
class RawArticle:
    title: str
    link: str
    description: str
    pub_date: str | None
    source_name: str
    origin: str  # pubdata | naver_api | rss | seed
    location_hint: str = ""  # 사전추출된 지역 개체명(있으면 위치추출에 우선 활용)


class PublicDataNewsSource:
    """공공데이터포털 한국언론진흥재단 뉴스빅데이터 메타데이터 (odcloud).

    기간(일자)·키워드(제목/본문) 서버단 필터 지원 → 과거 기간 검색 가능.
    개체명(지역)이 사전추출되어 위치추출 정확도가 높다.
    """
    name = "pubdata"
    BASE = "https://api.odcloud.kr/api/{ds_id}/v1/{uddi}"
    DATASETS = {
        "폭염": ("15153440", "uddi:ee9aa29f-5229-47a4-811e-e2d22c8e270f"),
        "기후변화": ("15153229", "uddi:11966686-801c-457d-b785-e58a3f786c61"),
    }

    def __init__(self, service_key: str,
                 datasets: tuple[str, ...] = ("폭염", "기후변화"),
                 search_field: str = "제목", per_page: int = 100):
        self.service_key = service_key
        self.datasets = datasets
        self.search_field = search_field  # 제목(정밀) | 본문(폭넓게)
        self.per_page = per_page

    def available(self) -> bool:
        return bool(self.service_key)

    def fetch(self, query: str, max_items: int = 300,
              since: str | None = None, until: str | None = None) -> list[RawArticle]:
        if not self.available():
            return []
        out: list[RawArticle] = []
        for ds_name in self.datasets:
            ds_id, uddi = self.DATASETS[ds_name]
            url = self.BASE.format(ds_id=ds_id, uddi=uddi)
            page = 1
            while len(out) < max_items:
                params = {"serviceKey": self.service_key, "returnType": "JSON",
                          "page": page, "perPage": self.per_page}
                if query:
                    params[f"cond[{self.search_field}::LIKE]"] = query
                if since:
                    params["cond[일자::GTE]"] = since
                if until:
                    params["cond[일자::LTE]"] = until
                try:
                    r = requests.get(url, params=params, timeout=30)
                    if r.status_code != 200:
                        break
                    data = r.json().get("data", [])
                except (requests.RequestException, ValueError):
                    break
                if not data:
                    break
                for d in data:
                    out.append(self._to_article(d, ds_name))
                    if len(out) >= max_items:
                        break
                if len(data) < self.per_page:
                    break
                page += 1
        return out

    @staticmethod
    def _to_article(d: dict, ds_name: str) -> RawArticle:
        return RawArticle(
            title=d.get("제목", "") or "",
            link=d.get("주소", "") or "",
            description=(d.get("본문") or d.get("키워드") or "")[:300],
            pub_date=d.get("일자"),
            source_name=(d.get("언론사") or "언론사") + f"/{ds_name}",
            origin="pubdata",
            location_hint=d.get("개체명(지역)") or "",
        )


class NaverNewsSource:
    """네이버 뉴스 검색 API (최근 기사 위주, 기간검색 불가)."""
    name = "naver_api"
    ENDPOINT = "https://openapi.naver.com/v1/search/news.json"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    def available(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def fetch(self, query: str, max_items: int = 100,
              since: str | None = None, until: str | None = None) -> list[RawArticle]:
        if not self.available():
            return []
        headers = {"X-Naver-Client-Id": self.client_id,
                   "X-Naver-Client-Secret": self.client_secret}
        out: list[RawArticle] = []
        start = 1
        while start <= 1000 and len(out) < max_items:
            display = min(100, max_items - len(out))
            params = {"query": query, "display": display,
                      "start": start, "sort": "date"}
            r = requests.get(self.ENDPOINT, headers=headers,
                             params=params, timeout=20)
            r.raise_for_status()
            items = r.json().get("items", [])
            if not items:
                break
            for it in items:
                out.append(RawArticle(
                    title=it.get("title", ""),
                    link=it.get("originallink") or it.get("link", ""),
                    description=it.get("description", ""),
                    pub_date=it.get("pubDate"),
                    source_name="naver",
                    origin="naver_api",
                ))
            start += display
        return out


class RssSource:
    """Google News RSS 키워드 검색 — 키 불필요(최근 기사)."""
    name = "rss"

    def available(self) -> bool:
        return True

    def fetch(self, query: str, max_items: int = 100,
              since: str | None = None, until: str | None = None) -> list[RawArticle]:
        url = ("https://news.google.com/rss/search?q="
               + requests.utils.quote(query) + "&hl=ko&gl=KR&ceid=KR:ko")
        out: list[RawArticle] = []
        try:
            r = requests.get(url, timeout=20,
                             headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            root = ET.fromstring(r.content)
        except (requests.RequestException, ET.ParseError):
            return out
        for item in root.iter("item"):
            if len(out) >= max_items:
                break
            out.append(RawArticle(
                title=item.findtext("title", ""),
                link=item.findtext("link", ""),
                description=item.findtext("description", ""),
                pub_date=item.findtext("pubDate"),
                source_name=item.findtext("source") or "google_news",
                origin="rss",
            ))
        return out


class SeedSource:
    """오프라인 데모용 시드 CSV — 키/네트워크 불필요."""
    name = "seed"

    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)

    def available(self) -> bool:
        return self.csv_path.exists()

    def fetch(self, query: str = "", max_items: int = 1000,
              since: str | None = None, until: str | None = None) -> list[RawArticle]:
        if not self.available():
            return []
        out: list[RawArticle] = []
        with self.csv_path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                out.append(RawArticle(
                    title=row.get("title", ""),
                    link=row.get("link", ""),
                    description=row.get("description", ""),
                    pub_date=row.get("pubDate"),
                    source_name=row.get("source", "seed"),
                    origin="seed",
                ))
                if len(out) >= max_items:
                    break
        return out
