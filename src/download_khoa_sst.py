# -*- coding: utf-8 -*-
"""
download_khoa_sst.py — KHOA(국립해양조사원) 일자별 SST(해수면온도) 자료 다운로더

데이터 출처(OPeNDAP/Hyrax):
  https://nosc.go.kr/opendap/CONJUGATE/KHOA_SST/contents.html

자료 구조 (실측으로 확인):
  - 경로 : /opendap/hyrax/CONJUGATE/KHOA_SST/{연}/{월2자리}/
  - 파일 : KHOA_SST_L4_Z003_D01_WGS001K_U{YYYYMMDD}.nc   (하루 1개, 약 42MB)
  - 내용 : 변수 sst(°C), 격자 위도 20~53N · 경도 117~150E (3301x3301, ~1km)
  - 형식 : NetCDF3 (파일 맨 앞 3바이트가 'CDF')

핵심:
  - 서버가 HEAD 요청은 막지만(403) GET 은 허용합니다 → requests.get 으로 받습니다.
  - 맨 .nc 주소를 GET 하면 '원본 파일'이 그대로 내려옵니다.

기본 동작:
  인자 없이 실행하면 2025-07-01 ~ 2025-08-31 자료를 ./data/input/khoa_sst 폴더에 받습니다.
  이미 받은(정상 크기) 파일은 건너뜁니다(이어받기). 오류(작은 HTML 등)는 자동 삭제 후 재시도 대상.

사용 예:
  python src/download_khoa_sst.py
  python src/download_khoa_sst.py --start 2025-07-01 --end 2025-08-31 --out ./data/input/khoa_sst
  python src/download_khoa_sst.py --overwrite      # 이미 있어도 다시 받기
"""

import argparse
import os
import sys
import time
from datetime import date, timedelta

import requests

# ---------------------------------------------------------------------------
# 설정값
# ---------------------------------------------------------------------------
BASE = "https://nosc.go.kr/opendap/hyrax/CONJUGATE/KHOA_SST"
# 파일 이름 틀: 날짜(YYYYMMDD)만 바뀜
NAME_TMPL = "KHOA_SST_L4_Z003_D01_WGS001K_U{ymd}.nc"

HEADERS = {"User-Agent": "Mozilla/5.0 (KHOA-SST-downloader/1.0; research)"}
REQUEST_TIMEOUT = 60          # 한 요청이 이 시간(초)을 넘기면 끊음
CHUNK = 1024 * 1024           # 1MB 씩 스트리밍 저장(메모리 절약)
RETRIES = 3                   # 파일당 재시도 횟수
SLEEP_BETWEEN = 0.5           # 파일 사이 잠깐 대기(서버 예의)
MIN_BYTES = 1_000_000         # 이보다 작으면 오류 페이지로 간주(정상 파일은 수십 MB)


def build_url(d: date):
    """해당 날짜의 (다운로드 URL, 파일이름) 튜플을 만든다."""
    ymd = d.strftime("%Y%m%d")
    name = NAME_TMPL.format(ymd=ymd)
    return f"{BASE}/{d.year}/{d.month:02d}/{name}", name


def daterange(start: date, end: date):
    """start ~ end(포함) 날짜를 하루씩 생성."""
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def is_valid_netcdf(path: str) -> bool:
    """받은 파일이 진짜 NetCDF3 인지 간단 검증.

    - 크기가 너무 작으면(오류 HTML 등) False
    - 맨 앞 3바이트가 b'CDF' 인지 확인
    """
    try:
        if os.path.getsize(path) < MIN_BYTES:
            return False
        with open(path, "rb") as f:
            return f.read(3) == b"CDF"
    except OSError:
        return False


def download_one(d: date, out_dir: str, overwrite: bool) -> str:
    """하루치 파일 1개를 받는다. 결과 상태 문자열을 돌려준다.

    반환: "skip"(이미 있음) / "ok"(받음) / "fail"(실패)
    """
    url, name = build_url(d)
    dst = os.path.join(out_dir, name)

    # 이미 정상 파일이 있으면 건너뛴다(이어받기)
    if not overwrite and is_valid_netcdf(dst):
        print(f"  [건너뜀] {name} (이미 있음)")
        return "skip"

    tmp = dst + ".part"          # 받는 중에는 .part 로 저장(중간 끊김 안전)
    for attempt in range(1, RETRIES + 1):
        try:
            with requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, stream=True) as r:
                r.raise_for_status()
                size = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=CHUNK):
                        if chunk:
                            f.write(chunk)
                            size += len(chunk)
            # 다 받은 뒤 검증
            if is_valid_netcdf(tmp):
                os.replace(tmp, dst)     # 검증 통과해야 최종 파일명으로 교체
                print(f"  [완료]   {name}  ({size/1_048_576:.1f} MB)")
                return "ok"
            else:
                print(f"  [경고]   {name} 받은 내용이 NetCDF가 아님(시도 {attempt}/{RETRIES})")
                if os.path.exists(tmp):
                    os.remove(tmp)
        except requests.RequestException as e:
            print(f"  [재시도] {name} 실패({attempt}/{RETRIES}): {e}")
            if os.path.exists(tmp):
                os.remove(tmp)
        time.sleep(SLEEP_BETWEEN * attempt)   # 재시도일수록 조금 더 쉼

    print(f"  [실패]   {name} — 건너뜀")
    return "fail"


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="KHOA 일자별 SST(NetCDF) 다운로더")
    p.add_argument("--start", default="2025-07-01", help="시작일 YYYY-MM-DD (기본 2025-07-01)")
    p.add_argument("--end", default="2025-08-31", help="종료일 YYYY-MM-DD (기본 2025-08-31)")
    p.add_argument("--out", default="./data/input/khoa_sst", help="저장 폴더 (기본 ./data/input/khoa_sst)")
    p.add_argument("--overwrite", action="store_true", help="이미 있어도 다시 받기")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end)
    except ValueError:
        print("날짜 형식이 잘못됐습니다. 예: --start 2025-07-01 --end 2025-08-31")
        sys.exit(1)
    if end < start:
        print("종료일이 시작일보다 빠릅니다.")
        sys.exit(1)

    os.makedirs(args.out, exist_ok=True)
    days = list(daterange(start, end))
    print(f"=== KHOA SST 다운로드 ===")
    print(f"기간: {start} ~ {end}  ({len(days)}일)")
    print(f"저장: {os.path.abspath(args.out)}")
    print(f"예상 용량: 약 {len(days)*42/1024:.1f} GB (파일당 ~42MB)\n")

    counts = {"ok": 0, "skip": 0, "fail": 0}
    failed_days = []
    for i, d in enumerate(days, 1):
        print(f"({i}/{len(days)}) {d}")
        status = download_one(d, args.out, args.overwrite)
        counts[status] += 1
        if status == "fail":
            failed_days.append(d.isoformat())
        time.sleep(SLEEP_BETWEEN)

    print("\n=== 요약 ===")
    print(f"  받음 {counts['ok']} / 건너뜀 {counts['skip']} / 실패 {counts['fail']}")
    if failed_days:
        print("  실패한 날짜(다시 실행하면 이어받기 됩니다):")
        print("   ", ", ".join(failed_days))


if __name__ == "__main__":
    main()
