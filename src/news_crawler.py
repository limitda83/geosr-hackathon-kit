# -*- coding: utf-8 -*-
"""
news_crawler.py — 한국어 구글 뉴스 크롤러 (핵심 모듈)

이 파일이 하는 일 (큰 그림 3단계):
  1) 구글 뉴스 RSS 검색 피드에서 키워드로 기사 목록을 가져온다. (feedparser)
  2) 피드 속 링크는 진짜 기사 주소가 아니라 '구글 리다이렉트 링크'라서,
     googlenewsdecoder 로 진짜 언론사 기사 URL 로 복원한다.
  3) 복원한 URL 에 접속해 본문 텍스트를 추출한다. (trafilatura)

초보자 안내:
  - 함수 crawl(keyword, limit) 하나만 알면 됩니다. 결과는 dict 리스트로 돌려줍니다.
  - app.py(스트림릿 화면)가 이 파일의 crawl 을 가져다 씁니다.
  - 이 파일만 단독 실행해도 됩니다(맨 아래 __main__ 참고): 키워드를 물어보고 CSV 로 저장.

필요 패키지:  pip install -r requirements.txt
"""

import csv
import time
import urllib.parse
from datetime import datetime

import feedparser            # RSS(XML) 피드를 파싱 (인코딩 자동 처리)
import requests              # 기사 페이지 HTTP 다운로드
import trafilatura           # 기사 '본문'만 깔끔하게 추출 (한글 인코딩 자동 감지)

# googlenewsdecoder 는 구글 리다이렉트 링크를 진짜 기사 URL 로 바꿔주는 패키지입니다.
# 혹시 설치가 안 돼 있어도 프로그램이 죽지 않도록 import 를 try 로 감쌉니다.
try:
    from googlenewsdecoder import gnewsdecoder
    _HAS_DECODER = True
except Exception:            # 패키지가 없거나 import 에러여도 계속 진행
    gnewsdecoder = None
    _HAS_DECODER = False


# ---------------------------------------------------------------------------
# 공통 설정값
# ---------------------------------------------------------------------------

# 실제 브라우저처럼 보이게 하는 User-Agent (없으면 일부 사이트가 차단함)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# 네트워크 요청이 너무 오래 걸리면 끊는 시간(초)
REQUEST_TIMEOUT = 15

# 기사 사이트에 예의를 지키기 위해 기사 사이 잠깐 쉬는 시간(초).
# 너무 빠르게 연속 요청하면 차단(429)될 수 있어서 둡니다.
SLEEP_BETWEEN_ARTICLES = 1.0


# ---------------------------------------------------------------------------
# 1) 구글 뉴스 RSS 검색 URL 만들기
# ---------------------------------------------------------------------------
def build_rss_url(keyword: str) -> str:
    """한국어 키워드로 구글 뉴스 RSS 검색 주소를 만든다.

    hl=ko  : 화면(인터페이스) 언어 = 한국어
    gl=KR  : 국가 = 대한민국
    ceid=KR:ko : 한국 에디션 + 한국어
    """
    # 한글/공백을 URL 에 안전하게 넣기 위해 인코딩 (예: "기후변화" -> %ED%95...)
    q = urllib.parse.quote(keyword)
    return (
        f"https://news.google.com/rss/search?q={q}"
        f"&hl=ko&gl=KR&ceid=KR:ko"
    )


# ---------------------------------------------------------------------------
# 2) 구글 리다이렉트 링크 -> 진짜 기사 URL
# ---------------------------------------------------------------------------
def decode_google_link(google_link: str) -> str:
    """구글 뉴스 리다이렉트 링크를 진짜 언론사 기사 URL 로 복원한다.

    성공하면 진짜 URL(문자열)을, 실패하면 빈 문자열("")을 돌려준다.
    (실패해도 호출한 쪽에서 원본 구글 링크를 그대로 보관하면 된다.)
    """
    if not _HAS_DECODER or gnewsdecoder is None:
        # 디코더 패키지가 없으면 복원 불가 -> 빈 문자열
        return ""

    try:
        # interval=1 : 내부적으로 1초 쉬며 호출 -> 429(과다요청) 차단 예방
        res = gnewsdecoder(google_link, interval=1)
    except Exception:
        # 디코더가 예외를 던져도 전체 크롤링은 멈추지 않게 한다
        return ""

    # 반환값은 문자열이 아니라 dict 입니다. 반드시 status 를 먼저 확인!
    if isinstance(res, dict) and res.get("status"):
        return res.get("decoded_url", "") or ""
    return ""


# ---------------------------------------------------------------------------
# 3) 기사 본문 텍스트 추출
# ---------------------------------------------------------------------------
def extract_body(url: str) -> str:
    """기사 URL 에서 본문 텍스트만 추출한다. 실패하면 빈 문자열("")을 돌려준다.

    포인트(한글 깨짐 방지): requests 로 받은 '바이트(resp.content)'를 그대로
    trafilatura 에 넘긴다. 그래야 EUC-KR/CP949/UTF-8 을 자동 감지해 한글이
    깨지지 않는다. (resp.text 를 쓰면 인코딩 추측이 틀려 깨질 수 있음)
    """
    if not url:
        return ""

    # (1) 먼저 우리가 직접 다운로드 시도 (User-Agent + timeout 지정 가능)
    html_bytes = None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        html_bytes = resp.content          # 반드시 .content (바이트!) 사용
    except requests.RequestException:
        html_bytes = None                  # 다운로드 실패 -> 아래 대체경로로

    text = None
    if html_bytes is not None:
        try:
            text = trafilatura.extract(
                html_bytes,
                favor_recall=True,         # 본문을 최대한 많이 가져오기 (한글 뉴스에 적합)
                include_comments=False,    # 댓글 제외
                include_tables=False,      # 표 제외
                url=url,                   # 메타/상대링크 처리에 도움
            )
        except Exception:
            text = None

    # (2) 위에서 본문을 못 얻었으면, trafilatura 자체 다운로더로 한 번 더 시도
    if not text:
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(
                    downloaded,
                    favor_recall=True,
                    include_comments=False,
                )
        except Exception:
            text = None

    return text or ""                      # 실패하면 빈 문자열


# ---------------------------------------------------------------------------
# 메인 함수: crawl
# ---------------------------------------------------------------------------
def crawl(keyword: str, limit: int = 10) -> list:
    """키워드로 구글 뉴스를 검색해 기사 목록을 만든다.

    매개변수:
        keyword : 검색할 한국어 키워드 (예: "기후변화")
        limit   : 가져올 기사 개수 (구글 RSS 는 최대 100개 안팎)

    반환값:
        dict 의 리스트. 각 dict 의 키:
            title        : 기사 제목
            press        : 언론사 이름
            published    : 발행일(문자열)
            url          : 진짜 기사 URL (복원 실패 시 구글 링크)
            google_link  : 원본 구글 리다이렉트 링크
            body         : 본문 텍스트 (실패 시 "")
            note         : 처리 메모 (성공/실패 사유 등)
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return []

    # limit 이 이상한 값이어도 죽지 않게 안전 처리
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    if limit < 1:
        limit = 1

    rss_url = build_rss_url(keyword)
    # RSS 피드도 직접 내려받아 timeout 을 건다.
    # (feedparser.parse(url) 은 타임아웃이 없어, 구글이 응답을 끌면 무한 대기할 수 있음)
    try:
        rss_resp = requests.get(rss_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        rss_resp.raise_for_status()
        feed = feedparser.parse(rss_resp.content)   # 바이트를 넘겨도 인코딩 자동 처리
    except requests.RequestException:
        # 피드 자체를 못 가져오면 빈 결과 (전체가 멈추지 않게)
        return []

    results = []
    entries = feed.entries[:limit]         # 필요한 개수만큼만 자르기

    for index, entry in enumerate(entries, start=1):
        # --- try/except 로 기사 1건을 통째로 감싼다 ---
        # 한 기사에서 에러가 나도 전체 크롤링이 멈추지 않도록!
        try:
            title = entry.get("title", "").strip()
            google_link = entry.get("link", "").strip()

            # 언론사 이름: entry.source.title 에 들어있는 경우가 많음
            press = ""
            source = entry.get("source")
            if isinstance(source, dict):
                press = source.get("title", "")
            elif source is not None:
                # feedparser 객체일 수도 있어 title 속성을 시도
                press = getattr(source, "title", "") or ""

            published = entry.get("published", "") or entry.get("updated", "")

            note = ""

            # 1) 진짜 기사 URL 복원
            real_url = decode_google_link(google_link)
            if real_url:
                url = real_url
            else:
                # 복원 실패 -> 구글 링크라도 남긴다 (요구사항)
                url = google_link
                note = "URL 복원 실패(구글 링크 유지)"

            # 2) 본문 추출 (복원 성공한 진짜 URL 일 때 시도)
            body = ""
            if real_url:
                body = extract_body(real_url)
                if not body:
                    # 본문 추출 실패해도 행은 유지 (빈 본문 + 메모)
                    note = (note + " / " if note else "") + "본문 추출 실패"

            results.append({
                "title": title,
                "press": press,
                "published": published,
                "url": url,
                "google_link": google_link,
                "body": body,
                "note": note,
            })

        except Exception as exc:
            # 예상 못한 에러가 나도 그 기사만 메모를 남기고 넘어간다
            results.append({
                "title": entry.get("title", "") if hasattr(entry, "get") else "",
                "press": "",
                "published": "",
                "url": entry.get("link", "") if hasattr(entry, "get") else "",
                "google_link": entry.get("link", "") if hasattr(entry, "get") else "",
                "body": "",
                "note": f"처리 중 오류: {exc}",
            })

        # 마지막 기사 뒤에는 굳이 안 쉬어도 되지만, 코드 단순화를 위해 항상 쉰다.
        # (사이트에 예의를 지키고 차단을 피하기 위한 짧은 대기)
        if index < len(entries):
            time.sleep(SLEEP_BETWEEN_ARTICLES)

    return results


# ---------------------------------------------------------------------------
# CSV 저장 도우미
# ---------------------------------------------------------------------------
# CSV 의 열 순서 (한 곳에서 관리)
CSV_FIELDS = ["title", "press", "published", "url", "google_link", "body", "note"]


def save_csv(rows: list, filename: str) -> str:
    """결과(dict 리스트)를 CSV 파일로 저장한다.

    encoding="utf-8-sig" 로 저장하면 엑셀에서 한글이 깨지지 않고 잘 열린다.
    반환값: 저장한 파일 경로.
    """
    # newline="" 은 윈도우에서 줄바꿈이 두 번 들어가는 문제를 막는다.
    with open(filename, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            # 혹시 없는 키가 있어도 안전하게 빈 값으로
            writer.writerow({key: row.get(key, "") for key in CSV_FIELDS})
    return filename


# ---------------------------------------------------------------------------
# 단독 실행(CLI): 이 파일을 직접 실행하면 키워드를 물어보고 CSV 로 저장
#   사용법:  python news_crawler.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== 구글 뉴스 한국어 크롤러 ===")
    kw = input("검색할 키워드를 입력하세요: ").strip()

    cnt_raw = input("가져올 기사 수를 입력하세요 (기본 10): ").strip()
    try:
        cnt = int(cnt_raw) if cnt_raw else 10
    except ValueError:
        print("숫자가 아니라서 기본값 10으로 진행합니다.")
        cnt = 10

    print(f"\n'{kw}' 로 검색 중... (기사 {cnt}건)\n")
    data = crawl(kw, cnt)

    print(f"총 {len(data)}건 수집 완료.")
    for i, row in enumerate(data, start=1):
        flag = "본문O" if row["body"] else "본문X"
        print(f"  [{i}] ({flag}) {row['press']} | {row['title']}")

    # 파일명은 영문/타임스탬프로 (한글 파일명은 일부 환경에서 깨질 수 있음)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"news_{stamp}.csv"
    save_csv(data, out_name)
    print(f"\nCSV 저장 완료 -> {out_name} (엑셀에서 바로 열려요)")
