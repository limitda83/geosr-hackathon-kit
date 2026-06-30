"""프로젝트 전역 설정 — 경로와 .env 키를 한 곳에서 관리."""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv 미설치 시에도 동작
    load_dotenv = None

# --- 경로 ---
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
NEWS_DIR = DATA_DIR / "news"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
HIGHTEMP_DIR = DATA_DIR / "hightemp"
PERSISTENCE_DIR = DATA_DIR / "persistence"

EVENTS_DB = DATA_DIR / "events.sqlite"
AOI_JSON = DATA_DIR / "aoi.json"
SEED_CSV = NEWS_DIR / "seed_events.csv"

# --- .env 로드 ---
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")


def _get(key: str, default: str = "") -> str:
    v = os.environ.get(key, default)
    return v.strip() if isinstance(v, str) else v


# --- 키 (없으면 빈 문자열 → 키리스 폴백) ---
NAVER_CLIENT_ID = _get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = _get("NAVER_CLIENT_SECRET")
PUBLIC_DATA_API_KEY = _get("PUBLIC_DATA_API_KEY")  # 공공데이터포털 디코딩 인증키
VWORLD_KEY = _get("VWORLD_KEY")
KAKAO_KEY = _get("KAKAO_KEY")

# --- 기본값 ---
DEFAULT_KEYWORDS = ["고수온", "고수온 양식장", "고수온 적조"]
# 한국 연안 대략 범위 (minlon, minlat, maxlon, maxlat)
KOREA_COAST_BBOX = (124.5, 32.5, 132.0, 38.7)


def has_public_data() -> bool:
    """공공데이터포털 인증키가 있으면 True (한국언론진흥재단 메타데이터)."""
    return bool(PUBLIC_DATA_API_KEY)


def has_naver() -> bool:
    """네이버 검색 API 키(Client ID + Secret)가 모두 있으면 True."""
    return bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)


def ensure_dirs() -> None:
    for d in (DATA_DIR, NEWS_DIR, RAW_DIR, PROCESSED_DIR,
              HIGHTEMP_DIR, PERSISTENCE_DIR):
        d.mkdir(parents=True, exist_ok=True)
