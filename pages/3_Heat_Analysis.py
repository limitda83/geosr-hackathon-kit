import streamlit as st
import pandas as pd
from pathlib import Path
from utils.style import apply
from utils.chat_widget import inject

st.set_page_config(page_title="Heat Analysis", page_icon="🌡️", layout="wide")
apply()
inject()
st.title("🌡️ Heat Analysis — 해수면온도 분석")

REGION_FREQ = Path("data/results/frequency/region_frequency.csv")
NC_CLEAN_DIR = Path("data/processed/nc_clean")
NC_HOT28_DIR = Path("data/processed/nc_hot28")
RESULTS_DIR = Path("data/results")

@st.cache_data
def load_region_list():
    if REGION_FREQ.exists():
        df = pd.read_csv(REGION_FREQ)
        return df["location"].tolist()
    return ["통영", "여수", "부산", "거제", "완도"]

regions = load_region_list()
selected_region = st.selectbox("분석 대상 지역 선택", regions)

st.markdown("---")

# 파일 상태
st.subheader("📁 파일 상태")
col1, col2, col3 = st.columns(3)
with col1:
    nc_raw = list(Path("data/raw/nc").glob("*.nc")) if Path("data/raw/nc").exists() else []
    st.metric("원천 NC 파일", f"{len(nc_raw)}개")
    st.caption("data/raw/nc/")
with col2:
    nc_clean = list(NC_CLEAN_DIR.glob("*.nc")) if NC_CLEAN_DIR.exists() else []
    st.metric("전처리 NC 파일", f"{len(nc_clean)}개")
    st.caption("data/processed/nc_clean/")
with col3:
    nc_hot = list(NC_HOT28_DIR.glob("*.nc")) if NC_HOT28_DIR.exists() else []
    st.metric("28도↑ NC 파일", f"{len(nc_hot)}개")
    st.caption("data/processed/nc_hot28/")

st.markdown("---")

# 전처리 결과 요약
st.subheader("⚙️ 전처리 결과 요약")
col1, col2, col3 = st.columns(3)
col1.success("✅ EPSG:4326 (WGS84) 적용")
col2.success("✅ 유효 범위 필터링 (0~40°C)")
col3.info("📊 분석 격자 수: 데이터 로드 후 표시")

st.markdown("---")

# 분석 결과 지도
tab1, tab2, tab3 = st.tabs(["28도↑ 격자", "2일↑ 누적 빈도", "3일↑ 연속 고수온"])

def show_map_or_image(image_path: Path, title: str):
    if image_path.exists():
        st.image(str(image_path), caption=title, use_container_width=True)
    else:
        st.info(f"분석 결과 없음 — 수집·전처리 스크립트 실행 후 표시됩니다.\n\n예상 경로: `{image_path}`")

with tab1:
    show_map_or_image(RESULTS_DIR / "heatmap" / "map_hot28.png", "28°C 이상 격자 분포")

with tab2:
    show_map_or_image(RESULTS_DIR / "frequency" / "map_cum2.png", "2일 이상 누적 고수온 빈도")

with tab3:
    show_map_or_image(RESULTS_DIR / "heatmap" / "map_streak3.png", "3일 이상 연속 고수온 영역")
