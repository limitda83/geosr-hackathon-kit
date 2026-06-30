import streamlit as st
import pandas as pd
from pathlib import Path
from utils.style import apply
from utils.chat_widget import inject
from utils.alert_widget import inject_alerts
from utils.region_extractor import load_disaster_events, extract_regions
from utils.viz import make_frequency_map
from agents.alert_agent import get_active_alerts

st.set_page_config(page_title="Disaster Areas", page_icon="📰", layout="wide")
apply()
inject()
inject_alerts(get_active_alerts())
st.title("📰 Disaster Areas — 재난 뉴스 & 관심지역")

# 실제 크롤링 데이터 로드 (없으면 샘플 fallback은 region_extractor 내부에서 처리)
@st.cache_data(ttl=300)
def load_data():
    df = load_disaster_events()
    freq_df = extract_regions(df)
    return df, freq_df

df, freq_df = load_data()

# 필터
col1, col2 = st.columns(2)
with col1:
    if "date" in df.columns:
        dates = sorted(df["date"].dropna().unique())
        if len(dates) >= 2:
            date_range = st.select_slider("기간 필터", options=dates, value=(dates[0], dates[-1]))
        else:
            date_range = (dates[0], dates[0]) if dates else ("", "")
    else:
        date_range = ("", "")
with col2:
    keywords = df["keyword"].dropna().unique().tolist() if "keyword" in df.columns else ["고수온"]
    selected_keywords = st.multiselect("재난 키워드", keywords, default=keywords)

if date_range[0] and date_range[1]:
    filtered = df[
        (df["date"] >= date_range[0]) & (df["date"] <= date_range[1]) &
        (df["keyword"].isin(selected_keywords))
    ]
else:
    filtered = df

st.caption(f"총 {len(filtered):,}건 / 전체 {len(df):,}건")
st.markdown("---")

# 뉴스 테이블
st.subheader("📋 뉴스 기사 목록")
show_cols = [c for c in ["date", "location", "keyword", "title", "url"] if c in filtered.columns]
st.dataframe(filtered[show_cols], use_container_width=True)

st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📊 발생 위치 빈도")
    if not freq_df.empty:
        import plotly.express as px
        fig = px.bar(
            freq_df.sort_values("count", ascending=True).head(20),
            x="count", y="location", orientation="h",
            labels={"count": "발생 횟수", "location": "지역"},
            color="count", color_continuous_scale="teal",
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#c8e6f0", showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🏆 관심지역 TOP N")
    top_n = st.slider("TOP N", 3, 15, 5)
    top_regions = freq_df.sort_values("count", ascending=False).head(top_n)
    for rank, (_, row) in enumerate(top_regions.iterrows(), 1):
        st.markdown(f"**{rank}위** {row['location']} — {int(row['count'])}건")

st.markdown("---")

# 지도
st.subheader("🗺️ 관심지역 지도")
map_df = freq_df.dropna(subset=["lat", "lon"])
if map_df.empty:
    st.warning("?????????? ??? ????? ?????????????.")
else:
    try:
        from streamlit_folium import st_folium
        m = make_frequency_map(map_df)
        st_folium(m, width=None, height=450, use_container_width=True)
    except Exception as e:
        st.warning(f"???????: {e}")
