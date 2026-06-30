from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from agents.alert_agent import get_active_alerts
from utils.alert_widget import inject_alerts
from utils.chat_widget import inject
from utils.style import apply

st.set_page_config(page_title="Heat Analysis", page_icon="🌡️", layout="wide")
apply()
inject()
inject_alerts(get_active_alerts())

st.title("🌡️ 해수면온도 분석")
st.caption("실제 수집된 SST CSV를 바탕으로 지역별 추세와 시각자료를 함께 확인합니다.")

DATA_DIR = Path("data")
DEFAULT_THRESHOLD = 28.0
CONSEC_MIN = 3
FREQ_MIN = 2
TS_DIR = Path("data/sst/timeseries")
HOT_IMG_DIR = Path("data/sst/hot/img")


@st.cache_data(ttl=300)
def load_region_freq() -> pd.DataFrame:
    freq_path = Path("data/results/frequency/region_frequency.csv")
    return pd.read_csv(freq_path, encoding="utf-8") if freq_path.exists() else pd.DataFrame()


@st.cache_data(ttl=300)
def load_sst_by_region() -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    for f in sorted(DATA_DIR.glob("*_2025*.csv")):
        region = f.stem.split("_")[0]
        if region in {"geocode", "regions", "Tongyeong"}:
            continue
        df = pd.read_csv(f, encoding="utf-8", parse_dates=["date"])
        if {"date", "sst", "source"}.issubset(df.columns) and not df.empty:
            if str(df["source"].iloc[0]) == "KHOA_OPeNDAP":
                result[region] = df.sort_values("date").reset_index(drop=True)
    return result


def calc_hot_stats(df: pd.DataFrame, threshold: float) -> dict:
    sst = df["sst"].values
    hot_mask = sst >= threshold
    hot_freq = int(hot_mask.sum())
    max_consec = 0
    cur = 0
    for v in hot_mask:
        cur = cur + 1 if v else 0
        max_consec = max(max_consec, cur)
    return {
        "avg": float(pd.Series(sst).mean()),
        "max": float(pd.Series(sst).max()),
        "hot_freq": hot_freq,
        "max_consec": max_consec,
        "persist2": hot_freq >= FREQ_MIN,
        "persist3": max_consec >= CONSEC_MIN,
    }


freq_df = load_region_freq()
sst_data = load_sst_by_region()

if not sst_data:
    st.warning("수집된 SST CSV가 없습니다. 먼저 `data/*_2025*.csv` 파일을 생성하세요.")
    st.stop()

regions = sorted(sst_data.keys())
selected = st.multiselect("분석 대상 지역", regions, default=regions[: min(3, len(regions))])
threshold = st.slider("고수온 기준(℃)", 24.0, 32.0, DEFAULT_THRESHOLD, 0.5)

if not selected:
    st.info("분석할 지역을 하나 이상 선택하세요.")
    st.stop()

stats = {r: calc_hot_stats(sst_data[r], threshold) for r in selected}

summary_cols = st.columns(len(selected))
for col, region in zip(summary_cols, selected):
    s = stats[region]
    col.metric(region, f"평균 {s['avg']:.1f}℃", f"최고 {s['max']:.1f}℃")
    col.caption(f"고수온 {s['hot_freq']}일 · 최장 연속 {s['max_consec']}일")

flags = st.columns(2)
flags[0].success(f"누적 {FREQ_MIN}일 이상 지역: {sum(1 for r in selected if stats[r]['persist2'])}개")
flags[1].warning(f"연속 {CONSEC_MIN}일 이상 지역: {sum(1 for r in selected if stats[r]['persist3'])}개")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["분석결과", "지역빈도", "시각자료"])

with tab1:
    st.subheader("일별 SST 분석결과")
    fig = go.Figure()
    for region in selected:
        df = sst_data[region].sort_values("date")
        fig.add_trace(go.Scatter(x=df["date"], y=df["sst"], mode="lines", name=region))
    fig.add_hline(y=threshold, line_dash="dash", line_color="#ff6b35")
    fig.update_layout(
        xaxis_title="날짜",
        yaxis_title="SST (℃)",
        hovermode="x unified",
        height=360,
        margin=dict(t=10, b=20, l=20, r=10),
        legend=dict(orientation="h", y=-0.2),
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("관심 지역 빈도")
    if not freq_df.empty:
        top_freq = freq_df.sort_values("count", ascending=True).head(12)
        fig2 = px.bar(
            top_freq,
            x="count",
            y="location",
            orientation="h",
            labels={"count": "언급 수", "location": "지역"},
            color="count",
            color_continuous_scale=["#bfefff", "#00c2d4", "#005f6e"],
        )
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            height=320,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("지역 빈도 파일이 없습니다.")

with tab3:
    import datetime as _dt

    _WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]

    def _date_label(img_path) -> str:
        raw = img_path.stem.replace("KHOA_SST_L4_Z003_D01_WGS001K_U", "").replace("_HOT28", "")
        try:
            d = _dt.date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
            return f"{d.month}월 {d.day}일 ({_WEEKDAY_KO[d.weekday()]})"
        except Exception:
            return raw

    ts_imgs = sorted(TS_DIR.glob("SST_daily_mean_*.png"))
    hot_imgs = sorted(HOT_IMG_DIR.glob("*_HOT28.png"))
    ss_imgs = sorted(Path("data/results/HS28NLS26/south_sea").glob("*_region.png"))

    def _ss_label(p) -> str:
        raw = p.stem.replace("HOTLOWSAL_", "").replace("_region", "")
        try:
            d = _dt.date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
            return f"{d.month}월 {d.day}일 ({_WEEKDAY_KO[d.weekday()]})"
        except Exception:
            return raw

    vt1, vt2, vt3 = st.tabs(["고수온 분포 지도", "남해 고수온·저염분", "일평균 SST 시계열"])

    with vt1:
        if hot_imgs:
            hot_labels = [_date_label(p) for p in hot_imgs]

            if "hot_idx" not in st.session_state:
                st.session_state.hot_idx = len(hot_imgs) - 1

            nav_l, nav_slider, nav_r = st.columns([1, 8, 1])
            with nav_l:
                if st.button("◀", use_container_width=True) and st.session_state.hot_idx > 0:
                    st.session_state.hot_idx -= 1
            with nav_r:
                if st.button("▶", use_container_width=True) and st.session_state.hot_idx < len(hot_imgs) - 1:
                    st.session_state.hot_idx += 1
            with nav_slider:
                st.session_state.hot_idx = st.select_slider(
                    "날짜",
                    options=list(range(len(hot_imgs))),
                    value=st.session_state.hot_idx,
                    format_func=lambda i: hot_labels[i],
                    label_visibility="collapsed",
                )

            idx = st.session_state.hot_idx
            st.caption(f"28℃ 이상 고수온 구역 · {hot_labels[idx]} · {idx + 1}/{len(hot_imgs)}")
            _, img_col, _ = st.columns([1, 6, 1])
            with img_col:
                st.image(str(hot_imgs[idx]), use_container_width=True)
        else:
            st.info("고수온 분포 지도가 없습니다.")

    with vt2:
        if ss_imgs:
            ss_labels = [_ss_label(p) for p in ss_imgs]

            if "ss_idx" not in st.session_state:
                st.session_state.ss_idx = len(ss_imgs) - 1

            sl, ss_slider, sr = st.columns([1, 8, 1])
            with sl:
                if st.button("◀", key="ss_prev", use_container_width=True) and st.session_state.ss_idx > 0:
                    st.session_state.ss_idx -= 1
            with sr:
                if st.button("▶", key="ss_next", use_container_width=True) and st.session_state.ss_idx < len(ss_imgs) - 1:
                    st.session_state.ss_idx += 1
            with ss_slider:
                st.session_state.ss_idx = st.select_slider(
                    "날짜",
                    options=list(range(len(ss_imgs))),
                    value=st.session_state.ss_idx,
                    format_func=lambda i: ss_labels[i],
                    label_visibility="collapsed",
                    key="ss_date_slider",
                )

            sidx = st.session_state.ss_idx
            st.caption(f"남해 고수온(28℃↑)·저염분(26psu↓) 동시 발생 구역 · {ss_labels[sidx]} · {sidx + 1}/{len(ss_imgs)}")
            _, sc2, _ = st.columns([1, 6, 1])
            with sc2:
                st.image(str(ss_imgs[sidx]), use_container_width=True)
        else:
            st.info("남해 고수온·저염분 이미지가 없습니다. (`data/results/HS28NLS26/south_sea/`)")

    with vt3:
        if ts_imgs:
            _, c2, _ = st.columns([1, 6, 1])
            with c2:
                st.image(str(ts_imgs[0]), use_container_width=True)
        else:
            st.info("일평균 SST 결과가 없습니다.")
