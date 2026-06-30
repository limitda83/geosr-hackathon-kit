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

# ── 원본 데이터 테이블 ───────────────────────────────────
with st.expander("📋 원본 데이터 보기"):
    tab_list = st.tabs(selected)
    for tab, region in zip(tab_list, selected):
        with tab:
            df = sst_data[region].sort_values("date")
            df_show = df[["date", "lat", "lon", "sst", "source"]].copy()
            df_show["date"] = df_show["date"].dt.strftime("%Y-%m-%d")
            st.dataframe(df_show, use_container_width=True, height=300)
