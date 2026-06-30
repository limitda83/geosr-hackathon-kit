import streamlit as st
import pandas as pd
from pathlib import Path
from utils.style import apply
from utils.chat_widget import inject

st.set_page_config(page_title="Report", page_icon="📄", layout="wide")
apply()
inject()

st.title("📄 Report · 최종 분석 결과")

REGION_FREQ = Path("data/results/frequency/region_frequency.csv")
DISASTER_DB = Path("data/processed/disaster_db/disaster_events.csv")
RESULTS_DIR = Path("data/results")


@st.cache_data
def load_disaster_db():
    if not DISASTER_DB.exists():
        raise FileNotFoundError(f"{DISASTER_DB} not found")
    return pd.read_csv(DISASTER_DB)


@st.cache_data
def load_region_freq():
    if REGION_FREQ.exists():
        return pd.read_csv(REGION_FREQ)
    df = load_disaster_db()
    freq = (
        df["location"]
        .dropna()
        .value_counts()
        .reset_index()
    )
    freq.columns = ["location", "count"]
    return freq


df = load_disaster_db()
freq_df = load_region_freq()
summary = (
    df.groupby("location")
    .size()
    .reset_index(name="news_count")
    .merge(freq_df, on="location", how="left")
    .fillna(0)
    .sort_values("news_count", ascending=False)
    .rename(columns={"count": "region_mentions"})
)

st.subheader("📌 핵심 지표")
col1, col2, col3, col4 = st.columns(4)
top = summary.iloc[0] if not summary.empty else {}
col1.metric("Top 지역", top.get("location", "-"))
col2.metric("뉴스 수", f"{int(top.get('news_count', 0)):,}")
col3.metric("언급 빈도", f"{int(top.get('region_mentions', 0)):,}")
col4.metric("전체 기사", f"{len(df):,}")

st.markdown("---")

st.subheader("📊 지역별 집계")
st.dataframe(
    summary.rename(columns={
        "location": "지역",
        "news_count": "뉴스 수",
        "region_mentions": "지역 언급 수",
    }),
    use_container_width=True,
)

st.markdown("---")

st.subheader("📰 재난 뉴스 요약")
for _, row in df.head(20).iterrows():
    st.markdown(f"- **{row['location']}**: {row['title']}")

st.markdown("---")

st.subheader("🗺️ 결과 이미지")
images = [
    ("data/results/heatmap/map_hot28.png", "28°C 이상 격자"),
    ("data/results/frequency/map_cum2.png", "2일↑ 누적 빈도"),
    ("data/results/heatmap/map_streak3.png", "3일↑ 연속 고수온"),
]
cols = st.columns(3)
for i, (path, caption) in enumerate(images):
    with cols[i]:
        p = Path(path)
        if p.exists():
            st.image(str(p), caption=caption, use_container_width=True)
        else:
            st.info(f"{caption}\n(이미지 없음)")

st.markdown("---")

st.subheader("⬇️ 다운로드")
col1, col2 = st.columns(2)
with col1:
    csv = summary.to_csv(index=False).encode("utf-8-sig")
    st.download_button("지역별 집계 CSV 다운로드", csv, file_name="region_summary.csv", mime="text/csv")
with col2:
    st.info("현재는 실제 파일 기반 집계만 사용합니다.")
