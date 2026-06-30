# 구글 뉴스 한국어 크롤러 (사용법)

키워드로 **구글 뉴스**를 검색해 기사의 **제목 · 언론사 · 발행일 · 진짜 기사주소 · 본문**을
모아 **CSV(엑셀)** 로 저장하는 작은 프로그램입니다. 초보자용으로 주석을 한글로 달았습니다.

## 1. 설치 (처음 한 번만)

```bash
pip install -r requirements.txt
```

## 2. 웹 화면으로 쓰기 (추천)

```bash
streamlit run src/app.py
```

브라우저가 열리면:
1. **검색 키워드**(예: `기후변화`) 입력
2. **기사 수** 선택
3. **[검색 실행]** 클릭
4. 결과 표 확인 후 **[CSV 다운로드]** 클릭 → 엑셀에서 바로 열림

## 3. 터미널(명령창)로만 쓰기

```bash
python src/news_crawler.py
```

키워드와 기사 수를 물어본 뒤 `news_YYYYMMDD_HHMMSS.csv` 파일을 만들어 줍니다.

## 4. 다른 코드에서 함수로 쓰기

```python
from news_crawler import crawl, save_csv

rows = crawl("기후변화", 10)   # dict 리스트 반환
save_csv(rows, "result.csv")  # 엑셀용 CSV(utf-8-sig)로 저장
```

각 결과(dict)의 키: `title, press, published, url, google_link, body, note`

## 어떻게 동작하나요? (3단계)

1. **RSS 검색** — `feedparser` 로 구글 뉴스 RSS(`hl=ko&gl=KR&ceid=KR:ko`)에서 기사 목록을 가져옵니다.
2. **링크 복원** — 피드의 링크는 구글 리다이렉트 링크라서, `googlenewsdecoder` 로 진짜 언론사 URL 로 바꿉니다.
   (복원 실패해도 구글 링크를 그대로 보관하고 `note` 에 사유를 남깁니다.)
3. **본문 추출** — `trafilatura` 로 본문 텍스트만 깔끔히 뽑습니다. 한글(EUC-KR/CP949/UTF-8) 자동 감지.

## 알아두면 좋은 점

- 기사마다 잠깐(약 1초) 쉬면서 가져옵니다. 사이트 차단(429)을 피하기 위한 **예의**입니다.
- 한 기사에서 오류가 나도 **전체가 멈추지 않고** 그 기사만 메모를 남기고 넘어갑니다.
- 구글 RSS 는 보통 **최대 100건** 정도까지만 줍니다(전체 아카이브가 아님).
- 자바스크립트로만 본문을 그리는 일부 포털/앱뷰는 본문이 비어 있을 수 있습니다(`note` 확인).
- 수집 자료는 **robots.txt/이용약관**을 존중하고, 개인정보·대외비는 마스킹하세요.
