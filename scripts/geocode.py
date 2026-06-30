#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
geocode.py — 뉴스 기사 -> 연안 지역명 추출 -> 위경도 지오코딩 + 캐싱 모듈

이 모듈은 '뉴스 기사 텍스트' 또는 '지역명 리스트'를 입력받아
연안 시군구 지명을 추출(extract_regions)하고, 각 지명을 위경도로
변환(geocode)하여 CSV에 캐싱한다. 분석 기능은 포함하지 않는다.

────────────────────────────────────────────────────────────────────
필요 pip 패키지:
    pip install requests
────────────────────────────────────────────────────────────────────
사용법(CLI):
    python scripts/geocode.py --text "통영과 거제 연안에서 적조가 관측됐다"
    python scripts/geocode.py --regions 통영,거제,포항
    python scripts/geocode.py --regions 통영,거제 --backend nominatim

지오코딩 백엔드 우선순위:
    1) 환경변수 KAKAO_REST_API_KEY 가 있으면 Kakao 사용
    2) 환경변수 VWORLD_KEY 가 있으면 VWorld 사용
    3) 그 외에는 OSM Nominatim(키 불필요) 사용
    * API 키는 절대 하드코딩하지 않고 os.environ 으로만 읽는다.

출력:
    - stdout 에 보정된 좌표 표
    - data/geocode_cache.csv  (캐시, append, 스키마: region,lat,lon,source,geocoded_at)
    - data/regions_geocoded.csv (이번 실행 결과, 스키마 동일)

규칙:
    - 지오코딩 실패/모호한 결과는 추정하지 않고 'UNRESOLVED'(미해결)로 표기.
    - 좌표 검증: lat -90~90, lon -180~180. 한국 근해 범위(33~39, 124~132)를
      벗어나면 경고를 출력(값은 유지하되 source 에 표시).
"""

import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("[ERROR] 'requests' 패키지가 필요합니다. 설치: pip install requests", file=sys.stderr)
    sys.exit(1)


# ───────────────────────── 경로/상수 ─────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CACHE_PATH = os.path.join(DATA_DIR, "geocode_cache.csv")
OUTPUT_PATH = os.path.join(DATA_DIR, "regions_geocoded.csv")

CSV_HEADER = ["region", "lat", "lon", "source", "geocoded_at"]
UNRESOLVED = "UNRESOLVED"  # 미해결 표기

# 한국 근해 대략 범위(경고용)
KR_LAT_MIN, KR_LAT_MAX = 33.0, 39.0
KR_LON_MIN, KR_LON_MAX = 124.0, 132.0

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "team-gvidia-hackathon-geocoder/1.0 (coastal region geocoding)"

# ──────────────────── 연안 시군구 화이트리스트 ────────────────────
# 추후 LLM 추출로 교체 가능. 지금은 대표 연안 지명 사전 매칭으로 구현.
# (동해/남해/서해/제주 권역 대표 연안 시군구 중심)
COASTAL_WHITELIST = [
    # 동해안
    "강릉", "속초", "동해", "삼척", "양양", "고성", "울진", "영덕", "포항", "경주",
    # 남해안
    "부산", "울산", "통영", "거제", "고성", "남해", "사천", "여수", "광양", "순천",
    "마산", "진해", "창원", "기장",
    # 서해안
    "인천", "안산", "화성", "당진", "서산", "태안", "보령", "서천", "군산", "부안",
    "고창", "영광", "신안", "목포", "무안", "해남", "완도", "진도", "보성", "강진",
    # 제주
    "제주", "서귀포",
]
# 중복 제거(고성 등). 길이 긴 지명부터 매칭하여 부분문자열 충돌 최소화.
COASTAL_WHITELIST = sorted(set(COASTAL_WHITELIST), key=len, reverse=True)


# ───────────────────────── 핵심 함수 ─────────────────────────
def extract_regions(text):
    """
    기사 텍스트에서 연안 시군구 지명을 추출한다.

    현재 구현: 연안 시군구 화이트리스트 사전 매칭(부분 문자열 검색).
    추후 LLM 추출(예: Claude/GPT 로 지명 NER)으로 교체 가능.

    Returns: 원문 등장 순서를 보존한 중복 없는 지역명 리스트.
    """
    if not text:
        return []
    found = []
    seen = set()
    # 등장 위치 기준 정렬을 위해 (위치, 지명) 수집
    hits = []
    for region in COASTAL_WHITELIST:
        idx = text.find(region)
        if idx != -1:
            hits.append((idx, region))
    for _, region in sorted(hits, key=lambda x: x[0]):
        if region not in seen:
            seen.add(region)
            found.append(region)
    return found


def _validate_coords(lat, lon):
    """좌표 유효성 검사. (is_valid_global, is_in_korea) 반환."""
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return False, False
    valid_global = (-90.0 <= lat <= 90.0) and (-180.0 <= lon <= 180.0)
    in_korea = (KR_LAT_MIN <= lat <= KR_LAT_MAX) and (KR_LON_MIN <= lon <= KR_LON_MAX)
    return valid_global, in_korea


def _geocode_kakao(region, api_key):
    """Kakao 로컬 검색 API 백엔드(골격). 키는 인자로 전달받는다."""
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": "KakaoAK {}".format(api_key)}
    params = {"query": region}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        docs = resp.json().get("documents", [])
        if not docs:
            return None, None, "kakao"
        # Kakao: x=경도(lon), y=위도(lat)
        lon = float(docs[0]["x"])
        lat = float(docs[0]["y"])
        return lat, lon, "kakao"
    except Exception as e:  # noqa: BLE001
        print("[WARN] Kakao 지오코딩 실패({}): {}".format(region, e), file=sys.stderr)
        return None, None, "kakao"


def _geocode_vworld(region, api_key):
    """VWorld 지오코딩 API 백엔드(골격). 키는 인자로 전달받는다."""
    url = "https://api.vworld.kr/req/search"
    params = {
        "service": "search",
        "request": "search",
        "version": "2.0",
        "size": "1",
        "query": region,
        "type": "place",
        "format": "json",
        "key": api_key,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        result = resp.json().get("response", {}).get("result", {})
        items = result.get("items", [])
        if not items:
            return None, None, "vworld"
        point = items[0]["point"]  # {x: lon, y: lat}
        lon = float(point["x"])
        lat = float(point["y"])
        return lat, lon, "vworld"
    except Exception as e:  # noqa: BLE001
        print("[WARN] VWorld 지오코딩 실패({}): {}".format(region, e), file=sys.stderr)
        return None, None, "vworld"


def _geocode_nominatim(region):
    """OSM Nominatim 백엔드(키 불필요). User-Agent 헤더 필수."""
    headers = {"User-Agent": USER_AGENT}
    params = {
        "q": "{}, South Korea".format(region),
        "format": "json",
        "limit": 1,
        "countrycodes": "kr",
    }
    try:
        resp = requests.get(NOMINATIM_URL, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None, None, "nominatim"
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        return lat, lon, "nominatim"
    except Exception as e:  # noqa: BLE001
        print("[WARN] Nominatim 지오코딩 실패({}): {}".format(region, e), file=sys.stderr)
        return None, None, "nominatim"


def geocode(region, backend=None):
    """
    지역명 하나를 위경도로 변환한다.

    백엔드 우선순위(backend 인자가 None 일 때):
        KAKAO_REST_API_KEY > VWORLD_KEY > nominatim
    API 키는 os.environ 으로만 읽는다(하드코딩 금지).

    Returns: dict(region, lat, lon, source, geocoded_at)
             실패/모호 시 lat=lon='' , source 에 사유, region 은 미해결로 표시.
    """
    kakao_key = os.environ.get("KAKAO_REST_API_KEY")
    vworld_key = os.environ.get("VWORLD_KEY")

    # 사용할 백엔드 결정
    if backend is None:
        if kakao_key:
            backend = "kakao"
        elif vworld_key:
            backend = "vworld"
        else:
            backend = "nominatim"

    if backend == "kakao" and kakao_key:
        lat, lon, source = _geocode_kakao(region, kakao_key)
    elif backend == "vworld" and vworld_key:
        lat, lon, source = _geocode_vworld(region, vworld_key)
    else:
        lat, lon, source = _geocode_nominatim(region)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 실패/모호 → 미해결
    if lat is None or lon is None:
        return {
            "region": region,
            "lat": "",
            "lon": "",
            "source": "{}:{}".format(source, UNRESOLVED.lower()),
            "geocoded_at": ts,
        }

    valid_global, in_korea = _validate_coords(lat, lon)
    if not valid_global:
        print("[WARN] {} 좌표 범위 이상(lat={}, lon={}) → 미해결".format(region, lat, lon),
              file=sys.stderr)
        return {
            "region": region,
            "lat": "",
            "lon": "",
            "source": "{}:{}".format(source, UNRESOLVED.lower()),
            "geocoded_at": ts,
        }

    source_label = source
    if not in_korea:
        print("[WARN] {} 좌표가 한국 근해 범위(위 33~39, 경 124~132)를 벗어남"
              "(lat={}, lon={}).".format(region, lat, lon), file=sys.stderr)
        source_label = "{}:out_of_kr_range".format(source)

    return {
        "region": region,
        "lat": round(float(lat), 6),
        "lon": round(float(lon), 6),
        "source": source_label,
        "geocoded_at": ts,
    }


def load_cache():
    """data/geocode_cache.csv 를 읽어 {region: row dict} 로 반환."""
    cache = {}
    if not os.path.exists(CACHE_PATH):
        return cache
    try:
        with open(CACHE_PATH, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                region = row.get("region")
                if region:
                    cache[region] = row
    except Exception as e:  # noqa: BLE001
        print("[WARN] 캐시 로드 실패: {}".format(e), file=sys.stderr)
    return cache


def save_cache(row):
    """단일 결과 dict 를 캐시 CSV 에 append (헤더 없으면 생성)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    file_exists = os.path.exists(CACHE_PATH) and os.path.getsize(CACHE_PATH) > 0
    with open(CACHE_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        if not file_exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in CSV_HEADER})


def _write_output(rows):
    """이번 실행 결과를 data/regions_geocoded.csv 로 저장(덮어쓰기)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in CSV_HEADER})


def _print_table(rows):
    """stdout 에 결과 표 출력."""
    widths = {"region": 10, "lat": 12, "lon": 12, "source": 24, "geocoded_at": 22}
    header = "  ".join(h.ljust(widths[h]) for h in CSV_HEADER)
    print(header)
    print("-" * len(header))
    for row in rows:
        line = "  ".join(str(row.get(h, "")).ljust(widths[h]) for h in CSV_HEADER)
        print(line)


def resolve_regions(regions, backend=None):
    """
    지역명 리스트를 캐시/지오코딩으로 해석.
    Returns: (rows, hit_count, new_count)
    """
    cache = load_cache()
    rows = []
    hit_count = 0
    new_count = 0
    for region in regions:
        if region in cache:
            cached = cache[region]
            rows.append({k: cached.get(k, "") for k in CSV_HEADER})
            hit_count += 1
            print("[CACHE] {} (적중)".format(region), file=sys.stderr)
            continue
        # 신규 호출
        result = geocode(region, backend=backend)
        save_cache(result)
        rows.append(result)
        new_count += 1
        print("[API]   {} (신규 호출, source={})".format(region, result["source"]),
              file=sys.stderr)
        # Nominatim 사용정책: 1초 1회 권장 → 신규 호출 사이 지연
        if (backend in (None, "nominatim")) and not os.environ.get("KAKAO_REST_API_KEY") \
                and not os.environ.get("VWORLD_KEY"):
            time.sleep(1.1)
    return rows, hit_count, new_count


# ───────────────────────── CLI ─────────────────────────
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="뉴스 기사/지역명 → 연안 지역 좌표 지오코딩 + 캐싱")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="기사 텍스트(여기서 연안 지명을 추출)")
    group.add_argument("--regions", help="쉼표로 구분한 지역명(예: 통영,거제,포항)")
    parser.add_argument("--backend", choices=["nominatim", "kakao", "vworld"],
                        default=None, help="지오코딩 백엔드 강제 지정(기본: 자동)")
    args = parser.parse_args(argv)

    if args.text:
        regions = extract_regions(args.text)
        if not regions:
            print("[INFO] 화이트리스트에서 추출된 연안 지명이 없습니다.", file=sys.stderr)
            return 0
        print("[INFO] 추출된 지명: {}".format(", ".join(regions)), file=sys.stderr)
    else:
        regions = [r.strip() for r in args.regions.split(",") if r.strip()]

    rows, hit_count, new_count = resolve_regions(regions, backend=args.backend)

    _print_table(rows)
    _write_output(rows)

    unresolved = sum(1 for r in rows if r.get("lat") == "")
    print("", file=sys.stderr)
    print("[SUMMARY] 총 {}건 | 캐시적중 {} | 신규호출 {} | 미해결 {}".format(
        len(rows), hit_count, new_count, unresolved), file=sys.stderr)
    print("[SUMMARY] 결과 저장: {}".format(OUTPUT_PATH), file=sys.stderr)
    print("[SUMMARY] 캐시 파일: {}".format(CACHE_PATH), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
