import re
import streamlit as st
import pandas as pd
from pathlib import Path
from utils.style import apply
from utils.chat_widget import inject

st.set_page_config(page_title="Heat Analysis", page_icon="🌡️", layout="wide")
# 공통 스타일/챗 위젯 (secrets.toml 미설정 등으로 실패해도 페이지는 계속 동작)
try:
    apply()
except Exception:
    pass
try:
    inject()
except Exception:
    pass
st.title("🌡️ Heat Analysis — 해수면온도 분석")

# ── 실제 산출물 경로 (src/sst_*.py 파이프라인 출력 위치) ──────────────
RAW_NC_DIR   = Path("data/input/khoa_sst")                       # 원천 일별 SST
SST_ANALYSIS = Path("data/results/sst_analysis")
HOT_NC_DIR   = SST_ANALYSIS / "sst_over28"                       # 28도↑ 고수온 NC
HOT_IMG_DIR  = SST_ANALYSIS / "sst_over28" / "img"               # 일별 28도↑ 지도(62장)
PERSIST_DIR  = SST_ANALYSIS / "persistence"                      # 누적빈도/연속 NC·지도
REGION_FREQ  = Path("data/results/frequency/region_frequency.csv")


@st.cache_data
def load_region_list():
    if REGION_FREQ.exists():
        df = pd.read_csv(REGION_FREQ)
        return df["location"].tolist()
    return ["통영", "여수", "부산", "거제", "완도"]


def latest_png(d: Path, pattern: str):
    """폴더에서 패턴에 맞는 가장 최근 PNG 경로 (없으면 None)."""
    if not d.exists():
        return None
    files = sorted(d.glob(pattern))
    return files[-1] if files else None


def list_daily_images(img_dir: Path):
    """일별 고수온 이미지들을 {'YYYY-MM-DD': 경로} 로 (날짜순)."""
    out = {}
    if img_dir.exists():
        for p in sorted(img_dir.glob("*_HOT*.png")):
            m = re.search(r"(\d{8})", p.name)
            if m:
                d = m.group(1)
                out[f"{d[:4]}-{d[4:6]}-{d[6:]}"] = p
    return out


def show_img(path, title: str, expected: str = ""):
    """이미지가 있으면 표시, 없으면 안내. (Streamlit 버전별 폭 인자 호환 처리)"""
    if path and Path(path).exists():
        try:
            st.image(str(path), caption=title, use_container_width=True)
        except TypeError:                       # 구버전: use_column_width 사용
            st.image(str(path), caption=title, use_column_width=True)
    else:
        st.info(f"분석 결과 없음 — 수집·전처리 스크립트 실행 후 표시됩니다.\n\n"
                f"예상 경로: `{expected or path}`")


regions = load_region_list()
selected_region = st.selectbox("분석 대상 지역 선택", regions)

st.markdown("---")

# ── 파일 상태 (실제 산출물 개수) ──────────────────────────────────
st.subheader("📁 파일 상태")
col1, col2, col3 = st.columns(3)
with col1:
    n_raw = len(list(RAW_NC_DIR.glob("*.nc"))) if RAW_NC_DIR.exists() else 0
    st.metric("원천 SST NC", f"{n_raw}개")
    st.caption(f"`{RAW_NC_DIR}/`")
with col2:
    n_hot = len(list(HOT_NC_DIR.glob("*_HOT*.nc"))) if HOT_NC_DIR.exists() else 0
    st.metric("28도↑ 고수온 NC", f"{n_hot}개")
    st.caption(f"`{HOT_NC_DIR}/`")
with col3:
    n_ana = len(list(PERSIST_DIR.glob("*.nc"))) if PERSIST_DIR.exists() else 0
    st.metric("분석 NC (누적·연속)", f"{n_ana}개")
    st.caption(f"`{PERSIST_DIR}/`")

st.markdown("---")

# ── 전처리 결과 요약 ──────────────────────────────────────────────
st.subheader("⚙️ 전처리 결과 요약")
col1, col2, col3 = st.columns(3)
col1.success("✅ EPSG:4326 (WGS84) 적용")
col2.success("✅ 유효 범위 필터링 (0~40°C)")
col3.info("🌊 배경지도: Natural Earth 해안선")

st.markdown("---")

# ── 분석 결과 지도 (실제 산출물 연결) ─────────────────────────────
tab1, tab2, tab3 = st.tabs(["28도↑ 격자 (일별)", "2일↑ 누적 빈도", "최대 연속 지속일수"])

with tab1:
    imgs = list_daily_images(HOT_IMG_DIR)
    if imgs:
        days = list(imgs.keys())
        sel_day = st.select_slider("날짜 선택", options=days, value=days[-1])
        show_img(imgs[sel_day], f"{sel_day} · 28°C 이상 고수온 영역")
        st.caption(f"일별 28도↑ 지도 {len(imgs)}장 · 자료: `{HOT_IMG_DIR}/`")
    else:
        show_img(None, "", expected=f"{HOT_IMG_DIR}/*_HOT28.png")

with tab2:
    show_img(latest_png(PERSIST_DIR, "SST_HOTFREQ_28C_*.png"),
             "2일 이상 누적 고수온 빈도 (분석기간 중 28°C 이상이었던 누적 일수)",
             expected=f"{PERSIST_DIR}/SST_HOTFREQ_28C_*.png")

with tab3:
    show_img(latest_png(PERSIST_DIR, "SST_MAXCONSEC_28C_*.png"),
             "동일격자 28°C 최대 연속 지속일수 (3일↑ 연속 고수온 공간분포)",
             expected=f"{PERSIST_DIR}/SST_MAXCONSEC_28C_*.png")
