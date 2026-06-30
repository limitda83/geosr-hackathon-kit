from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from agents.alert_agent import get_active_alerts
from utils.alert_widget import inject_alerts
from utils.chat_widget import inject
from utils.style import apply

st.set_page_config(page_title="Report", page_icon="📄", layout="wide")
apply()
inject()
inject_alerts(get_active_alerts())

st.title("📄 보고서 생성")
st.caption("실제 데이터와 보고서 생성 agent를 연결해 Word/PDF 보고서를 만듭니다.")

DISASTER_DB = Path("data/processed/disaster_db/disaster_events.csv")
REGION_FREQ = Path("data/results/frequency/region_frequency.csv")
SUMMARY_DIR = Path("data/results/summary")


@st.cache_data
def load_data():
    if not DISASTER_DB.exists():
        raise FileNotFoundError(f"{DISASTER_DB} not found")
    news_df = pd.read_csv(DISASTER_DB, encoding="utf-8", parse_dates=["date"])
    freq_df = pd.read_csv(REGION_FREQ, encoding="utf-8") if REGION_FREQ.exists() else pd.DataFrame()
    return news_df, freq_df


news_df, freq_df = load_data()

col1, col2, col3, col4 = st.columns(4)
top_region = news_df["location"].value_counts().index[0] if not news_df.empty else "-"
col1.metric("최다 언급 지역", top_region)
col2.metric("전체 기사", f"{len(news_df):,}건")
col3.metric("지역 수", f"{news_df['location'].nunique():,}개")
col4.metric("생성 시각", datetime.now().strftime("%H:%M"))

st.markdown("---")

left, right = st.columns([1.2, 0.8])
with left:
    st.subheader("기사 요약")
    st.dataframe(
        news_df.sort_values("date", ascending=False)[["date", "location", "keyword", "title"]].head(20),
        use_container_width=True,
        height=420,
    )
with right:
    st.subheader("지역 빈도")
    if not freq_df.empty:
        st.dataframe(freq_df.sort_values("count", ascending=False).head(10), use_container_width=True, height=420)
    else:
        st.info("지역 빈도 파일이 없습니다.")

st.markdown("---")
st.subheader("보고서 생성")

col_a, col_b = st.columns([1, 1])
with col_a:
    title = st.text_input("보고서 제목", value="예보사업부 AI·AX 해커톤 보고서")
    threshold = st.slider("고수온 기준(℃)", 24.0, 32.0, 28.0, 0.5)
    top_n = st.slider("기사 포함 개수", 5, 50, 20, 5)
with col_b:
    fmt = st.radio("출력 형식", ["both", "docx", "pdf"], horizontal=True)
    use_ai = st.checkbox("AI 서술 포함", value=True)
    st.caption("보고서 생성 agent는 `agents.report_agent.run()`을 직접 호출합니다.")

selected_sections = ["overview", "timeseries", "hotmap", "freq_map", "consec_map", "sst_stats", "news"]

if st.button("보고서 생성", type="primary", use_container_width=True):
    try:
        from agents.report_agent import run as report_run

        with st.spinner("보고서 생성 agent 실행 중..."):
            result = report_run(
                title=title,
                threshold=threshold,
                include_sections=selected_sections,
                top_n_regions=top_n,
                fmt=fmt,
                output_dir=str(SUMMARY_DIR),
                use_ai=use_ai,
            )
        st.session_state["report_result"] = result
        st.success("보고서 생성이 완료되었습니다.")
    except Exception as e:
        st.error(f"보고서 생성 실패: {e}")

if "report_result" in st.session_state:
    result = st.session_state["report_result"]
    stem = result.get("filename_stem", "report")
    st.markdown("---")
    st.subheader("다운로드")
    d1, d2 = st.columns(2)
    if result.get("docx") and result["docx"].get("bytes"):
        d1.download_button(
            "Word 다운로드",
            result["docx"]["bytes"],
            file_name=f"{stem}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    if result.get("pdf") and result["pdf"].get("bytes"):
        d2.download_button(
            "PDF 다운로드",
            result["pdf"]["bytes"],
            file_name=f"{stem}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

st.markdown("---")
st.subheader("생성된 보고서 파일")
existing = sorted(SUMMARY_DIR.glob("report_*.*"), reverse=True) if SUMMARY_DIR.exists() else []
if existing:
    for f in existing[:10]:
        cols = st.columns([4, 1])
        cols[0].write(f"{f.name} ({f.stat().st_size // 1024} KB)")
        cols[1].download_button(
            "다운로드",
            f.read_bytes(),
            file_name=f.name,
            mime="application/pdf" if f.suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f.name,
            use_container_width=True,
        )
else:
    st.info("생성된 보고서가 아직 없습니다.")
