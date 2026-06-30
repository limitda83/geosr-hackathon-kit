import streamlit as st
import pandas as pd
from pathlib import Path
from utils.style import apply
from utils.chat_widget import inject

st.set_page_config(page_title="Report", page_icon="📄", layout="wide")
apply()
inject()
st.title("📄 Report — 최종 분석 결과")

REGION_FREQ = Path("data/results/frequency/region_frequency.csv")
SUMMARY_DIR = Path("data/results/summary")

@st.cache_data
def load_summary():
    f = SUMMARY_DIR / "summary.csv"
    if f.exists():
        return pd.read_csv(f)
    return pd.DataFrame([
        {"region": "통영", "news_count": 23, "hot28_grids": 142, "max_cum": 18, "max_streak": 7},
        {"region": "여수", "news_count": 19, "hot28_grids": 98,  "max_cum": 14, "max_streak": 5},
        {"region": "부산", "news_count": 15, "hot28_grids": 76,  "max_cum": 11, "max_streak": 4},
    ])

df = load_summary()

# 핵심 지표 카드
st.subheader("🎯 핵심 지표")
col1, col2, col3, col4 = st.columns(4)
top = df.iloc[0] if not df.empty else {}
col1.metric("Top 관심지역", top.get("region", "-"))
col2.metric("고수온 지속 격자 수", f"{top.get('hot28_grids', '-')}개")
col3.metric("누적 빈도 최고 지역", top.get("region", "-"), f"{top.get('max_cum', '-')}일")
col4.metric("최대 연속 고수온", f"{top.get('max_streak', '-')}일")

st.markdown("---")

# 관심지역별 분석 결과
st.subheader("📊 관심지역별 분석 결과")
st.dataframe(df.rename(columns={
    "region": "지역",
    "news_count": "뉴스 건수",
    "hot28_grids": "28도↑ 격자 수",
    "max_cum": "최대 누적일",
    "max_streak": "최대 연속일",
}), use_container_width=True)

st.markdown("---")

# 재난 빈도 - 고수온 연계 해석
st.subheader("🔗 재난 빈도 & 고수온 연계 해석")
for _, row in df.iterrows():
    st.markdown(f"- **{row['region']}**: 재난 뉴스 {row['news_count']}건 발생, 28도↑ 격자 {row['hot28_grids']}개 / 최대 {row['max_streak']}일 연속 고수온 확인")

st.markdown("---")

# 결과 이미지
st.subheader("🖼️ 결과 이미지")
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
            st.info(f"{caption}\n(분석 후 표시)")

st.markdown("---")

# 다운로드
st.subheader("📥 결과 다운로드")
col1, col2 = st.columns(2)
with col1:
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📊 분석 결과 CSV 다운로드", csv,
                       file_name="고수온_분석결과.csv", mime="text/csv")
with col2:
    report_path = SUMMARY_DIR / "report.docx"
    if report_path.exists():
        with open(report_path, "rb") as f:
            st.download_button("📄 보고서 DOCX 다운로드", f,
                               file_name="고수온_분석보고서.docx",
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    else:
        st.info("보고서 생성 후 다운로드 가능")
