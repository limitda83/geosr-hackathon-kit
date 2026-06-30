import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from utils.style import apply
from utils.chat_widget import inject

st.set_page_config(page_title="Heat Analysis", page_icon="🌡️", layout="wide")
apply()
inject()

st.title("🌡️ Heat Analysis — 해수면온도 분석")

DATA_DIR = Path("data")
DEFAULT_THRESHOLD = 28.0
CONSEC_MIN = 3   # 연속 고수온 기준일 (sst_persistence.py 와 동일)
FREQ_MIN   = 2   # 누적 빈도 기준일  (sst_frequency.py 와 동일)


# ── 데이터 로드 ──────────────────────────────────────────
@st.cache_data
def load_all_sst() -> dict[str, pd.DataFrame]:
    result = {}
    for f in sorted(DATA_DIR.glob("*_2025*.csv")):
        region = f.stem.split("_")[0]
        if region in ("geocode", "regions", "Tongyeong"):
            continue
        df = pd.read_csv(f, encoding="utf-8", parse_dates=["date"])
        if "sst" in df.columns and "source" in df.columns:
            if df["source"].iloc[0] == "KHOA_OPeNDAP":
                result[region] = df.sort_values("date").reset_index(drop=True)
    return result


def calc_hot_stats(df: pd.DataFrame, threshold: float) -> dict:
    """sst_frequency.py / sst_persistence.py 와 동일한 로직을 CSV 단위로 계산."""
    sst = df["sst"].values

    # 누적 빈도 (sst_frequency.py: hot_freq)
    hot_mask = sst >= threshold
    hot_freq = int(hot_mask.sum())

    # 연속 지속일수 (sst_persistence.py: max_consec)
    max_consec = 0
    cur = 0
    for v in hot_mask:
        cur = cur + 1 if v else 0
        max_consec = max(max_consec, cur)

    # 2일↑ 누적 (FREQ_MIN)
    persist2 = hot_freq >= FREQ_MIN

    # 3일↑ 연속 (CONSEC_MIN)
    persist3 = max_consec >= CONSEC_MIN

    return {
        "avg": float(np.nanmean(sst)),
        "max": float(np.nanmax(sst)),
        "hot_freq": hot_freq,
        "max_consec": max_consec,
        "persist2": persist2,   # 2일↑ 누적 고수온 여부
        "persist3": persist3,   # 3일↑ 연속 고수온 여부
        "total_days": len(df),
    }


sst_data = load_all_sst()

if not sst_data:
    st.warning("수집된 SST 데이터가 없습니다. `scripts/collect_sst_by_region.py` 를 먼저 실행하세요.")
    st.stop()

regions = list(sst_data.keys())

# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.subheader("필터")
    selected = st.multiselect("분석 지역", regions, default=regions)
    threshold = st.slider("고수온 기준 (°C)", 24.0, 32.0, DEFAULT_THRESHOLD, 0.5)
    st.caption(f"누적 기준: {FREQ_MIN}일↑ / 연속 기준: {CONSEC_MIN}일↑")

if not selected:
    st.info("왼쪽에서 지역을 하나 이상 선택하세요.")
    st.stop()

stats = {r: calc_hot_stats(sst_data[r], threshold) for r in selected}

# ── 요약 메트릭 ───────────────────────────────────────────
st.subheader("📊 지역별 요약")
cols = st.columns(len(selected))
for col, region in zip(cols, selected):
    s = stats[region]
    badges = []
    if s["persist2"]:
        badges.append(f"🟠 누적 {FREQ_MIN}일↑")
    if s["persist3"]:
        badges.append(f"🔴 연속 {CONSEC_MIN}일↑")
    col.metric(f"🌊 {region}", f"평균 {s['avg']:.1f}°C", f"최고 {s['max']:.1f}°C")
    col.caption(f"고수온 {s['hot_freq']}일  |  최장연속 {s['max_consec']}일")
    if badges:
        col.markdown(" ".join(badges))

st.markdown("---")

# ── 시계열 + 28°C 감지 강조 ──────────────────────────────
st.subheader("📈 일별 해수면온도 추이")

fig = go.Figure()

for region in selected:
    df = sst_data[region]
    hot = df["sst"] >= threshold

    # 고수온 구간 배경 음영
    fig.add_trace(go.Scatter(
        x=pd.concat([df["date"], df["date"][::-1]]),
        y=pd.concat([df["sst"].where(hot, threshold), pd.Series([threshold] * len(df))]),
        fill="toself", fillcolor="rgba(255,80,0,0.12)",
        line=dict(width=0), showlegend=False, hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["sst"],
        mode="lines", name=region,
        hovertemplate=f"{region}<br>%{{x|%Y-%m-%d}}<br>%{{y:.2f}}°C<extra></extra>",
    ))

    # 고수온 감지 마커
    hot_df = df[hot]
    if not hot_df.empty:
        fig.add_trace(go.Scatter(
            x=hot_df["date"], y=hot_df["sst"],
            mode="markers", name=f"{region} 고수온",
            marker=dict(color="red", size=5, symbol="circle"),
            hovertemplate=f"{region} 고수온<br>%{{x|%Y-%m-%d}}<br>%{{y:.2f}}°C<extra></extra>",
            showlegend=False,
        ))

fig.add_hline(
    y=threshold, line_dash="dash", line_color="red", line_width=1.5,
    annotation_text=f"고수온 기준 {threshold}°C",
    annotation_position="top left",
)
fig.update_layout(
    xaxis_title="날짜", yaxis_title="SST (°C)",
    legend_title="지역", hovermode="x unified",
    height=440, margin=dict(t=20, b=40),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── 분석 결과 이미지 (sst_processing / sst_frequency / sst_persistence 출력) ──
SST_HOT_DIR   = Path("data/sst/hot")
SST_PERS_DIR  = Path("data/sst/persistence")

def show_images(paths: list[Path], cols: int = 2):
    if not paths:
        return False
    rows = [paths[i:i+cols] for i in range(0, len(paths), cols)]
    for row in rows:
        cs = st.columns(len(row))
        for c, p in zip(cs, row):
            c.image(str(p), caption=p.stem, use_container_width=True)
    return True

SST_TS_DIR = Path("data/sst/timeseries")

tab1, tab2, tab3, tab4 = st.tabs(["🗺️ 일별 고수온 지도", "🟠 누적 빈도 지도", "🔴 최장 연속 지도", "📈 일평균 SST 추이"])

with tab1:
    imgs = sorted((SST_HOT_DIR / "img").glob("*.png")) if (SST_HOT_DIR / "img").exists() else []
    if imgs:
        # 날짜 슬라이더로 탐색
        dates = [p.stem.split("_U")[-1].replace("_HOT28", "") for p in imgs]
        dates_fmt = [f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in dates]
        idx = st.select_slider("날짜 선택", options=range(len(dates_fmt)),
                               format_func=lambda i: dates_fmt[i], value=0)
        st.image(str(imgs[idx]), caption=f"{dates_fmt[idx]} 고수온(28°C↑) 분포",
                 use_container_width=True)
        st.caption(f"총 {len(imgs)}일치 이미지 — 슬라이더로 날짜를 이동하세요.")
    else:
        st.info("분석 결과 이미지가 없습니다.\n\n"
                "```bash\npython src/run_pipeline.py data/khoa_sst data/sst/hot data/sst/persistence\n```")

with tab2:
    imgs = sorted(SST_PERS_DIR.glob("SST_HOTFREQ*.png"))
    if not show_images(imgs, cols=1):
        st.info("누적 빈도 지도가 없습니다. `run_pipeline.py` 실행 후 표시됩니다.")

with tab3:
    imgs = sorted(SST_PERS_DIR.glob("SST_MAXCONSEC*.png"))
    if not show_images(imgs, cols=1):
        st.info("최장 연속 지도가 없습니다. `run_pipeline.py` 실행 후 표시됩니다.")

with tab4:
    ts_png = sorted(SST_TS_DIR.glob("SST_daily_mean_*.png")) if SST_TS_DIR.exists() else []
    ts_csv = sorted(SST_TS_DIR.glob("SST_daily_mean_*.csv")) if SST_TS_DIR.exists() else []
    if ts_png:
        st.image(str(ts_png[0]), caption="일평균 SST 추이 (2025-07-01 ~ 08-31)",
                 use_container_width=True)
    if ts_csv:
        ts_df = pd.read_csv(ts_csv[0])
        with st.expander("원본 CSV 보기"):
            st.dataframe(ts_df, use_container_width=True)
    if not ts_png and not ts_csv:
        st.info("시계열 데이터가 없습니다. `src/sst_timeseries.py` 실행 후 표시됩니다.")

st.markdown("---")

# ── 고수온 감지 달력 히트맵 ──────────────────────────────
st.subheader("🗓️ 지역별 고수온 감지 달력")

calendar_rows = []
for region in selected:
    df = sst_data[region].copy()
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["hot"] = (df["sst"] >= threshold).astype(int)
    for month, grp in df.groupby("month"):
        calendar_rows.append({
            "지역": region, "월": month,
            "고수온 일수": int(grp["hot"].sum()),
            "평균SST": round(grp["sst"].mean(), 1),
        })

cal_df = pd.DataFrame(calendar_rows)
if not cal_df.empty:
    pivot = cal_df.pivot(index="지역", columns="월", values="고수온 일수")
    fig_cal = px.imshow(
        pivot, color_continuous_scale="YlOrRd", zmin=0,
        text_auto=True,
        labels={"color": f"고수온 일수 (≥{threshold}°C)"},
    )
    fig_cal.update_layout(height=80 + 55 * len(selected), margin=dict(t=10, b=20))
    st.plotly_chart(fig_cal, use_container_width=True)

st.markdown("---")

# ── 고수온 ∩ 저염분 공통지역 (hot_lowsal.py 결과) ─────────
st.subheader("🧪 고수온 ∩ 저염분 공통지역 분석")

HOTLOWSAL_DIR = Path("data/results/hotlowsal")
SUMMARY_CSV   = HOTLOWSAL_DIR / "summary_hotlowsal.csv"

@st.cache_data(ttl=300)
def load_hotlowsal_summary():
    if not SUMMARY_CSV.exists():
        return None
    df = pd.read_csv(SUMMARY_CSV, encoding="utf-8-sig", parse_dates=["date"])
    return df[df["error"].isna() | (df["error"] == "")].copy() if "error" in df.columns else df

@st.cache_data(ttl=300)
def load_hotlowsal_day(date_str: str):
    path = HOTLOWSAL_DIR / "csv" / f"HOTLOWSAL_{date_str.replace('-','')}.csv"
    if not path.exists():
        return None
    return pd.read_csv(path, encoding="utf-8-sig")

summary_df = load_hotlowsal_summary()

if summary_df is None or summary_df.empty:
    st.warning("결과 파일 없음 — `python src/hot_lowsal.py` 실행 후 새로고침하세요.")
else:
    col1, col2, col3 = st.columns(3)
    col1.metric("총 분석일", f"{len(summary_df)}일")
    col2.metric("평균 공통 격자 수", f"{summary_df['both_count'].mean():,.0f}")
    col3.metric("최대 공통 격자 수", f"{summary_df['both_count'].max():,.0f}")

    fig_hl = go.Figure()
    fig_hl.add_trace(go.Scatter(x=summary_df["date"], y=summary_df["hot_count"],
                                name="고수온 격자", line=dict(color="#ff6b35")))
    fig_hl.add_trace(go.Scatter(x=summary_df["date"], y=summary_df["lowsal_count"],
                                name="저염분 격자", line=dict(color="#00c2d4")))
    fig_hl.add_trace(go.Scatter(x=summary_df["date"], y=summary_df["both_count"],
                                name="공통(고수온∩저염분)", line=dict(color="#00e5ff", width=2.5),
                                fill="tozeroy", fillcolor="rgba(0,229,255,0.08)"))
    fig_hl.update_layout(
        xaxis_title="날짜", yaxis_title="격자 수",
        hovermode="x unified", height=380,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#c8e6f0", legend_title="유형", margin=dict(t=20, b=40),
    )
    st.plotly_chart(fig_hl, use_container_width=True)

    st.markdown("##### 날짜별 공통지역 지도")
    date_options = summary_df["date"].dt.strftime("%Y-%m-%d").tolist()
    sel_date = st.selectbox("날짜 선택", date_options, index=len(date_options)//2)
    day_df = load_hotlowsal_day(sel_date)
    if day_df is not None and not day_df.empty:
        try:
            import folium
            from streamlit_folium import st_folium
            from folium.plugins import HeatMap
            m = folium.Map(location=[day_df["lat"].mean(), day_df["lon"].mean()],
                           zoom_start=7, tiles="CartoDB dark_matter")
            HeatMap(day_df[["lat", "lon", "sst_celsius"]].values.tolist(),
                    radius=8, blur=6,
                    gradient={"0.4": "#00c2d4", "0.7": "#ff6b35", "1.0": "#ff0000"}).add_to(m)
            st_folium(m, width=None, height=420, use_container_width=True)
        except Exception as e:
            st.warning(f"지도 오류: {e}")
    else:
        st.info(f"{sel_date} 공통지역 CSV 파일이 없습니다.")

st.markdown("---")

# ── 원본 데이터 테이블 ───────────────────────────────────
with st.expander("📋 원본 데이터 보기"):
    tab_list = st.tabs(selected)
    for tab, region in zip(tab_list, selected):
        with tab:
            df = sst_data[region].copy()
            df["date"] = df["date"].dt.strftime("%Y-%m-%d")
            df["고수온"] = (df["sst"] >= threshold).map({True: "🔴", False: ""})
            st.dataframe(df[["date", "lat", "lon", "sst", "고수온", "source"]],
                         use_container_width=True, height=300)
