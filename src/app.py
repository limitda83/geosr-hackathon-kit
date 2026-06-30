# -*- coding: utf-8 -*-
"""
app.py — 구글 뉴스 한국어 크롤러 웹 화면 (Streamlit)

실행 방법(터미널에서):
    streamlit run app.py

화면 구성:
  - 검색 키워드 입력칸
  - 가져올 기사 수 입력칸
  - [검색 실행] 버튼
  - 결과 표(테이블)
  - CSV 다운로드 버튼 (엑셀에서 한글이 안 깨지게 utf-8-sig)

핵심 로직은 옆 파일 news_crawler.py 에 있고, 여기서는 그 함수를 불러다 씁니다.
"""

import io
import csv
from datetime import datetime

import pandas as pd
import streamlit as st

# 같은 폴더의 news_crawler.py 에서 함수들을 가져온다
from news_crawler import crawl, CSV_FIELDS


# ---------------------------------------------------------------------------
# 결과(dict 리스트) -> CSV 바이트 만들기
# ---------------------------------------------------------------------------
def make_csv_bytes(rows: list) -> bytes:
    """다운로드 버튼에 넘길 CSV 데이터를 '바이트'로 만든다.

    st.download_button 은 문자열이 아니라 바이트(bytes)를 받는 게 안전하다.
    encoding="utf-8-sig" 로 인코딩해야 엑셀에서 한글이 안 깨진다.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in CSV_FIELDS})
    # 문자열을 utf-8-sig 바이트로 변환 (맨 앞 BOM 덕분에 엑셀이 UTF-8 로 인식)
    return buffer.getvalue().encode("utf-8-sig")


# ---------------------------------------------------------------------------
# 화면(UI) 만들기
# ---------------------------------------------------------------------------
st.set_page_config(page_title="구글 뉴스 한국어 크롤러", page_icon=None)

st.title("구글 뉴스 한국어 크롤러")
st.caption("키워드로 구글 뉴스를 검색해 제목·언론사·발행일·기사주소·본문을 모아 CSV 로 내려받습니다.")

# 입력칸들 (가로로 두 칸 배치)
col1, col2 = st.columns([3, 1])
with col1:
    keyword = st.text_input("검색 키워드", value="", placeholder="예: 기후변화")
with col2:
    limit = st.number_input("기사 수", min_value=1, max_value=50, value=10, step=1)

st.caption("기사 1건당 약 1~2초 걸립니다(링크 복원+본문 추출). 처음엔 10건 정도로 시작하세요.")

run = st.button("검색 실행", type="primary")

# 결과를 새로고침 후에도 유지하기 위해 세션 상태에 저장
if "rows" not in st.session_state:
    st.session_state["rows"] = None
if "keyword" not in st.session_state:
    st.session_state["keyword"] = ""

# [검색 실행] 버튼을 눌렀을 때
if run:
    if not keyword.strip():
        st.warning("검색 키워드를 입력해 주세요.")
    else:
        # 크롤링은 시간이 걸리므로 진행 표시(spinner)를 보여준다
        with st.spinner(f"'{keyword}' 검색 중입니다... (기사 사이마다 잠깐 쉬어요)"):
            rows = crawl(keyword.strip(), int(limit))
        st.session_state["rows"] = rows
        st.session_state["keyword"] = keyword.strip()

# 결과가 있으면 표와 다운로드 버튼을 보여준다
rows = st.session_state["rows"]
if rows is not None:
    if len(rows) == 0:
        st.info("검색 결과가 없습니다. 키워드를 바꿔서 다시 시도해 보세요.")
    else:
        # 본문이 추출된 기사 수를 알려준다
        ok_body = sum(1 for r in rows if r.get("body"))
        st.success(f"총 {len(rows)}건 수집 완료 (본문 추출 성공 {ok_body}건).")

        # 표로 보여주기 — 본문은 길어서 미리보기만 잘라서 표시
        table_rows = []
        for r in rows:
            body = r.get("body", "") or ""
            preview = (body[:120] + "...") if len(body) > 120 else body
            table_rows.append({
                "제목": r.get("title", ""),
                "언론사": r.get("press", ""),
                "발행일": r.get("published", ""),
                "기사주소": r.get("url", ""),
                "본문(미리보기)": preview,
                "메모": r.get("note", ""),
            })
        df = pd.DataFrame(table_rows)
        st.dataframe(df, use_container_width=True)

        # CSV 다운로드 버튼 (바이트 전달, 파일명은 .csv 로 끝남)
        csv_bytes = make_csv_bytes(rows)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        kw_for_name = st.session_state["keyword"]
        # 파일명에 한글이 들어가도 대부분 OK 지만, 안전하게 타임스탬프를 같이 붙인다
        file_name = f"news_{stamp}.csv"
        st.download_button(
            label="CSV 다운로드",
            data=csv_bytes,                      # 반드시 bytes
            file_name=file_name,                 # .csv 로 끝남
            mime="text/csv",
        )

        st.caption(f"검색어: {kw_for_name}  /  엑셀에서 바로 열 수 있어요(utf-8-sig).")
else:
    st.info("위에 키워드를 넣고 [검색 실행]을 눌러 주세요.")
