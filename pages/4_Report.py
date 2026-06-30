import io
import textwrap
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.style import apply
from utils.chat_widget import inject

st.set_page_config(page_title="Report", page_icon="📄", layout="wide")
apply()
inject()

st.title("📄 Report · 최종 분석 결과")

# ── 경로 상수 ─────────────────────────────────────────────
DISASTER_DB   = Path("data/processed/disaster_db/disaster_events.csv")
REGION_FREQ   = Path("data/results/frequency/region_frequency.csv")
SST_DIR       = Path("data")
SST_HOT_IMG   = Path("data/sst/hot/img")
SST_PERS_DIR  = Path("data/sst/persistence")
SST_TS_DIR    = Path("data/sst/timeseries")


# ── 데이터 로드 ──────────────────────────────────────────
@st.cache_data
def load_data():
    df = pd.read_csv(DISASTER_DB, encoding="utf-8", parse_dates=["date"])
    freq = pd.read_csv(REGION_FREQ, encoding="utf-8") if REGION_FREQ.exists() else pd.DataFrame()

    # SST 지역별 CSV
    sst_frames = {}
    for f in sorted(SST_DIR.glob("*_2025*.csv")):
        region = f.stem.split("_")[0]
        if region in ("geocode", "regions", "Tongyeong"):
            continue
        tmp = pd.read_csv(f, encoding="utf-8", parse_dates=["date"])
        if "sst" in tmp.columns and tmp.get("source", pd.Series([""])).iloc[0] == "KHOA_OPeNDAP":
            sst_frames[region] = tmp

    # SST 일평균 시계열
    ts_csvs = sorted(SST_TS_DIR.glob("SST_daily_mean_*.csv")) if SST_TS_DIR.exists() else []
    ts_df = pd.read_csv(ts_csvs[0], encoding="utf-8-sig", parse_dates=["date"]) if ts_csvs else None

    return df, freq, sst_frames, ts_df


df, freq_df, sst_frames, ts_df = load_data()

# 지역별 요약
summary = (
    df["location"].dropna().value_counts()
    .reset_index().rename(columns={"index": "location", "location": "뉴스 건수", "count": "뉴스 건수"})
)
if not freq_df.empty and "lat" in freq_df.columns:
    summary = summary.merge(freq_df[["location", "lat", "lon"]], on="location", how="left")

# SST 통계 (28°C 기준)
THRESHOLD = 28.0
sst_stats = []
for region, rdf in sst_frames.items():
    hot = rdf["sst"] >= THRESHOLD
    cur = max_c = 0
    for v in hot:
        cur = cur + 1 if v else 0
        max_c = max(max_c, cur)
    sst_stats.append({
        "지역": region,
        "평균SST(°C)": round(rdf["sst"].mean(), 2),
        "최고SST(°C)": round(rdf["sst"].max(), 2),
        f"고수온일수(≥{THRESHOLD}°C)": int(hot.sum()),
        "최장연속(일)": max_c,
    })
sst_stat_df = pd.DataFrame(sst_stats).sort_values("고수온일수(≥28.0°C)", ascending=False) if sst_stats else pd.DataFrame()

# ── 핵심 지표 ────────────────────────────────────────────
st.subheader("📌 핵심 지표")
c1, c2, c3, c4 = st.columns(4)
top_region = summary.iloc[0]["location"] if not summary.empty else "-"
c1.metric("최다 언급 지역", top_region)
c2.metric("총 뉴스 기사", f"{len(df):,}건")
c3.metric("분석 지역 수", f"{len(sst_frames)}개")
if ts_df is not None:
    c4.metric("분석 기간 평균 SST", f"{ts_df['mean_sst'].mean():.1f}°C")
else:
    c4.metric("수집 기간", "2025-06-01 ~ 08-31")

st.markdown("---")

# ── 지역별 집계 ──────────────────────────────────────────
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("📰 뉴스 기사 지역별 빈도")
    st.dataframe(summary.rename(columns={"location": "지역", "count": "뉴스 건수"}).head(15),
                 use_container_width=True, height=320)

with col_b:
    st.subheader("🌡️ 지역별 SST 통계")
    if not sst_stat_df.empty:
        st.dataframe(sst_stat_df, use_container_width=True, height=320)
    else:
        st.info("SST 데이터 없음")

st.markdown("---")

# ── 분석 이미지 ──────────────────────────────────────────
st.subheader("🗺️ 분석 결과 이미지")

img_tab1, img_tab2, img_tab3 = st.tabs(["누적 빈도", "최장 연속", "일평균 SST"])

with img_tab1:
    imgs = sorted(SST_PERS_DIR.glob("SST_HOTFREQ*.png"))
    if imgs:
        st.image(str(imgs[0]), use_container_width=True)
    else:
        st.info("이미지 없음")

with img_tab2:
    imgs = sorted(SST_PERS_DIR.glob("SST_MAXCONSEC*.png"))
    if imgs:
        st.image(str(imgs[0]), use_container_width=True)
    else:
        st.info("이미지 없음")

with img_tab3:
    imgs = sorted(SST_TS_DIR.glob("SST_daily_mean_*.png")) if SST_TS_DIR.exists() else []
    if imgs:
        st.image(str(imgs[0]), use_container_width=True)
    else:
        st.info("이미지 없음")

st.markdown("---")

# ── 최근 재난 뉴스 ──────────────────────────────────────
st.subheader("📰 주요 재난 뉴스")
show_df = df.sort_values("date", ascending=False).head(30)
show_df["date"] = show_df["date"].dt.strftime("%Y-%m-%d")
st.dataframe(show_df[["date", "location", "keyword", "title"]].rename(columns={
    "date": "날짜", "location": "지역", "keyword": "키워드", "title": "제목"
}), use_container_width=True, height=300)

st.markdown("---")

# ── 다운로드 ────────────────────────────────────────────
st.subheader("⬇️ 보고서 다운로드")

# ── 커스텀 옵션 ──────────────────────────────────────────
with st.expander("⚙️ 보고서 커스텀 옵션", expanded=True):
    r_title = st.text_input("보고서 제목", value="고수온 연안재해 분석 보고서")
    r_threshold = st.slider("고수온 기준(°C)", 24.0, 32.0, 28.0, 0.5)
    r_top_n = st.slider("뉴스 기사 포함 수", 5, 50, 20, 5)
    r_fmt = st.radio("출력 형식", ["docx", "pdf", "both"], horizontal=True)
    r_use_ai = st.checkbox("AI 분석 내러티브 포함 (ANTHROPIC_API_KEY 필요)", value=True)

    SECTION_LABELS = {
        "overview":   "📋 개요",
        "timeseries": "📈 시계열 (필수)",
        "hotmap":     "🗺️ 일별 고수온 지도",
        "freq_map":   "🟠 누적 빈도 지도",
        "consec_map": "🔴 최장 연속 지도",
        "sst_stats":  "🌡️ 지역별 SST 통계",
        "news":       "📰 주요 뉴스",
    }
    st.markdown("**포함 섹션 선택**")
    sec_cols = st.columns(4)
    selected_sections = ["timeseries"]  # 항상 포함
    for i, (key, label) in enumerate(SECTION_LABELS.items()):
        if key == "timeseries":
            sec_cols[i % 4].checkbox(label, value=True, disabled=True)
            continue
        if sec_cols[i % 4].checkbox(label, value=True):
            selected_sections.append(key)

# ── 다운로드 버튼 ────────────────────────────────────────
dl_col1, dl_col2 = st.columns([1, 2])

with dl_col1:
    csv_bytes = summary.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 집계 CSV 다운로드",
        csv_bytes,
        file_name=f"region_summary_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

with dl_col2:
    if st.button("🚀 보고서 생성 (서브에이전트)", type="primary", use_container_width=True):
        with st.spinner("보고서 생성 중... (시각화 자료 포함, 잠시 기다려 주세요)"):
            try:
                from agents.report_agent import run as agent_run
                result = agent_run(
                    title=r_title,
                    threshold=r_threshold,
                    include_sections=selected_sections,
                    top_n_regions=r_top_n,
                    fmt=r_fmt,
                    use_ai=r_use_ai,
                )
                # bytes를 session_state에 저장해 rerun 후에도 다운로드 가능
                st.session_state["report_result"] = result
                st.success("보고서 생성 완료!")
            except Exception as e:
                st.error(f"보고서 생성 오류: {e}")
                import traceback; st.code(traceback.format_exc())

# session_state에 결과가 있으면 다운로드 버튼 표시 (rerun 이후에도 유지)
if "report_result" in st.session_state:
    result = st.session_state["report_result"]
    st.info("보고서가 준비되었습니다. 아래 버튼으로 다운로드하세요.")
    btn_col1, btn_col2 = st.columns(2)
    stem = result.get("filename_stem", "report")
    if result.get("pdf") and result["pdf"].get("bytes"):
        btn_col1.download_button(
            "⬇️ PDF 다운로드",
            result["pdf"]["bytes"],
            file_name=f"{stem}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    if result.get("docx") and result["docx"].get("bytes"):
        btn_col2.download_button(
            "⬇️ Word 다운로드",
            result["docx"]["bytes"],
            file_name=f"{stem}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

# ── 기존 보고서 목록 ────────────────────────────────────
st.markdown("---")
st.subheader("📂 기존 보고서 목록")

SUMMARY_DIR = Path("data/results/summary")
existing = sorted(SUMMARY_DIR.glob("report_*.*"), reverse=True) if SUMMARY_DIR.exists() else []

if existing:
    for f in existing:
        mime = (
            "application/pdf"
            if f.suffix == ".pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        col1, col2 = st.columns([4, 1])
        col1.text(f"{f.name}  ({f.stat().st_size // 1024} KB)")
        col2.download_button(
            "⬇️ 다운로드",
            f.read_bytes(),
            file_name=f.name,
            mime=mime,
            key=str(f),
            use_container_width=True,
        )
else:
    st.info("생성된 보고서가 없습니다. 위에서 보고서를 생성하세요.")
