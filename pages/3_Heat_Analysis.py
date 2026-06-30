import streamlit as st
import pandas as pd
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
HIGH_SST = 28.0


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
                result[region] = df
    return result


sst_data = load_all_sst()

if not sst_data:
    st.warning("수집된 SST 데이터가 없습니다. `scripts/collect_sst_by_region.py` 를 먼저 실행하세요.")
    st.stop()

regions = list(sst_data.keys())

# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.subheader("필터")
    selected = st.multiselect("분석 지역", regions, default=regions[:3])
    threshold = st.slider("고수온 기준 (°C)", 24.0, 32.0, HIGH_SST, 0.5)

if not selected:
    st.info("왼쪽에서 지역을 하나 이상 선택하세요.")
    st.stop()

# ── 요약 메트릭 ───────────────────────────────────────────
st.subheader("📊 지역별 요약")
cols = st.columns(len(selected))
for col, region in zip(cols, selected):
    df = sst_data[region]
    avg   = df["sst"].mean()
    mx    = df["sst"].max()
    hot_days = (df["sst"] >= threshold).sum()
    col.metric(f"🌊 {region}", f"평균 {avg:.1f}°C", f"최고 {mx:.1f}°C")
    col.caption(f"고수온({threshold}°C↑) {hot_days}일")

st.markdown("---")

# ── 시계열 차트 ──────────────────────────────────────────
st.subheader("📈 일별 해수면온도 추이")

fig = go.Figure()

for region in selected:
    df = sst_data[region].sort_values("date")
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["sst"],
        mode="lines", name=region,
        hovertemplate=f"{region}<br>%{{x|%Y-%m-%d}}<br>%{{y:.2f}}°C<extra></extra>",
    ))

# 고수온 기준선
fig.add_hline(
    y=threshold, line_dash="dash", line_color="red", line_width=1.5,
    annotation_text=f"고수온 기준 {threshold}°C",
    annotation_position="top left",
)

fig.update_layout(
    xaxis_title="날짜",
    yaxis_title="SST (°C)",
    legend_title="지역",
    hovermode="x unified",
    height=420,
    margin=dict(t=20, b=40),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── 고수온 일수 비교 ─────────────────────────────────────
st.subheader(f"🔥 고수온({threshold}°C↑) 일수 비교")

hot_rows = []
for region in selected:
    df = sst_data[region]
    hot_days = int((df["sst"] >= threshold).sum())
    hot_rows.append({"지역": region, "고수온 일수": hot_days})

hot_df = pd.DataFrame(hot_rows).sort_values("고수온 일수", ascending=True)
fig2 = px.bar(
    hot_df, x="고수온 일수", y="지역", orientation="h",
    color="고수온 일수", color_continuous_scale="YlOrRd",
    text="고수온 일수",
)
fig2.update_traces(textposition="outside")
fig2.update_layout(
    height=60 + 50 * len(selected),
    margin=dict(t=10, b=30),
    coloraxis_showscale=False,
)
st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ── 월별 평균 히트맵 ─────────────────────────────────────
st.subheader("🗓️ 월별 평균 SST 히트맵")

monthly_rows = []
for region in selected:
    df = sst_data[region].copy()
    df["month"] = df["date"].dt.to_period("M").astype(str)
    for month, grp in df.groupby("month"):
        monthly_rows.append({"지역": region, "월": month, "평균SST": round(grp["sst"].mean(), 2)})

monthly_df = pd.DataFrame(monthly_rows)
if not monthly_df.empty:
    pivot = monthly_df.pivot(index="지역", columns="월", values="평균SST")
    fig3 = px.imshow(
        pivot,
        color_continuous_scale="YlOrRd",
        zmin=15, zmax=32,
        text_auto=".1f",
        labels={"color": "SST (°C)"},
    )
    fig3.update_layout(height=60 + 50 * len(selected), margin=dict(t=10, b=30))
    st.plotly_chart(fig3, use_container_width=True)

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
    st.info("`src/hot_lowsal.py`를 실행하면 이 섹션에 결과가 표시됩니다.\n\n"
            "```bash\npython src/hot_lowsal.py --start 2025-07-01 --end 2025-08-31\n```")
else:
    # 날짜별 격자 수 추이
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
        font_color="#c8e6f0", legend_title="유형",
        margin=dict(t=20, b=40),
    )
    st.plotly_chart(fig_hl, use_container_width=True)

    # 특정 날짜 지도
    st.markdown("##### 날짜별 공통지역 지도")
    date_options = summary_df["date"].dt.strftime("%Y-%m-%d").tolist()
    sel_date = st.selectbox("날짜 선택", date_options, index=len(date_options)//2)
    day_df = load_hotlowsal_day(sel_date)

    if day_df is not None and not day_df.empty:
        try:
            import folium
            from streamlit_folium import st_folium
            m = folium.Map(location=[day_df["lat"].mean(), day_df["lon"].mean()],
                           zoom_start=7, tiles="CartoDB dark_matter")
            heat_data = day_df[["lat", "lon", "sst_celsius"]].values.tolist()
            from folium.plugins import HeatMap
            HeatMap(heat_data, radius=8, blur=6,
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
            df = sst_data[region].sort_values("date")
            df_show = df[["date", "lat", "lon", "sst", "source"]].copy()
            df_show["date"] = df_show["date"].dt.strftime("%Y-%m-%d")
            st.dataframe(df_show, use_container_width=True, height=300)
