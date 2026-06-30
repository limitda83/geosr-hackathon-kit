# 고수온 연안재해 모니터링 웹 시스템 기획서

## 프로젝트 개요

**목적**: 재난 뉴스 기반 관심지역 도출 → 해수면온도 분석 → 고수온 이상 탐지 → 보고서 자동 생성

**시연 데이터**: 2025년 6월 ~ 8월 고수온 사례

**기술 스택**
- 웹: Streamlit
- 에이전트: LangGraph + Claude API
- 데이터: 국립해양조사원 API, 뉴스 크롤링
- 분석: pandas, xarray, folium
- 보고서: Anthropic docx 스킬

---

## 전체 흐름

```
뉴스 크롤링
    ↓
관심지역 추출 (LLM)
    ↓
위경도 변환
    ↓
국립해양조사원 API 수온 데이터 수집
    ↓
전처리 (EPSG:4326, 0~40도 필터)
    ↓
고수온 분석 (28도 이상 격자)
    ↓
누적 빈도 / 연속 발생 분석
    ↓
이상 알림 서비스
    ↓
보고서 자동 생성
```

---

## 폴더 구조

```
C:\team-gvidia
├─ app.py                         메인 진입점
├─ pages/
│  ├─ 1_Home.py
│  ├─ 2_Disaster_Areas.py
│  ├─ 3_Heat_Analysis.py
│  ├─ 4_Report.py
│  └─ 5_AI_Chat.py
├─ data/
│  ├─ raw/
│  │  ├─ news/                    크롤링 원본
│  │  └─ nc/                      수온 NC 원본
│  ├─ processed/
│  │  ├─ disaster_db/             정제 뉴스 DB
│  │  ├─ nc_clean/                전처리 NC
│  │  └─ nc_hot28/                28도 이상 NC
│  └─ results/
│     ├─ heatmap/                 수온 지도 이미지
│     ├─ frequency/               빈도 분석 결과
│     └─ summary/                 최종 요약
├─ utils/
│  ├─ crawler.py                  뉴스 크롤링
│  ├─ nc_preprocess.py            NC 전처리
│  ├─ analysis.py                 고수온 분석
│  ├─ viz.py                      시각화
│  └─ chatbot.py                  LLM 챗봇 RAG
├─ agents/
│  ├─ main_agent.py               메인 에이전트 (조율)
│  ├─ news_agent.py               뉴스 수집 서브에이전트
│  ├─ collection_agent.py         API 수집 서브에이전트
│  └─ report_agent.py             보고서 생성 서브에이전트
├─ submit/                        제출물
├─ .streamlit/
│  └─ secrets.toml                API 키
└─ requirements.txt
```

---

## 파일명 규칙

| 파일 | 규칙 |
|------|------|
| 뉴스 원천 | `news_raw_YYYYMMDD.csv` |
| 정제 뉴스 DB | `disaster_events.csv` |
| 지역 집계 | `region_frequency.csv` |
| 수온 원천 NC | `sst_raw_YYYYMMDD.nc` |
| 전처리 NC | `sst_clean_YYYYMMDD.nc` |
| 28도 이상 NC | `sst_hot28_YYYYMMDD.nc` |
| 2일 누적 결과 | `sst_hot28_cum2.nc` |
| 3일 연속 결과 | `sst_hot28_streak3.nc` |
| 지도 이미지 | `map_hot28.png`, `map_cum2.png`, `map_streak3.png` |

---

## 컬럼명 규칙

**뉴스 데이터**
- `date` — 발생일
- `location` — 발생위치
- `keyword` — 재난키워드
- `title` — 기사 제목
- `url` — 원문 URL

**분석 데이터**
- `lat` — 위도
- `lon` — 경도
- `value` — 수온값
- `time` — 시간
- `region_id` — 지역 ID

---

## 페이지별 상세 설계

### Page 1 — Home

**목적**: 프로젝트 전체 소개

**구성**
- 제목 + 한 줄 소개
- 전체 흐름도
- 데이터 소스 요약
- 핵심 성과 카드 4개

**핵심 성과 카드**
```
[재난 뉴스 분석]  [수온 수집]  [고수온 격자]  [이상 탐지]
    47건           1,247건       23일           3지역
```

---

### Page 2 — Disaster Areas

**목적**: 재난 뉴스 크롤링 결과 + 관심지역 확인

**구성**
```
[기간 필터] 2025.06 ~ 2025.08   [키워드] 고수온 ▾

뉴스 기사 테이블
┌────────────┬──────┬────────┬────────────────────┐
│ 날짜       │ 지역 │ 유형   │ 제목               │
├────────────┼──────┼────────┼────────────────────┤
│ 2025.08.14 │ 통영 │ 고수온 │ 고수온 피해... │