import streamlit as st
import pandas as pd
from pathlib import Path
from utils.style import apply
from utils.chat_widget import inject

st.set_page_config(page_title="Disaster Areas", page_icon="📰", layout="wide")
apply()
inject()
st.title("📰 Disaster Areas — 재난 뉴스 & 관심지역")

DISASTER_DB = Path("data/processed/disaster_db/disaster_events.csv")
REGION_FREQ = Path("data/results/frequency/region_frequency.csv")

@st.cache_data
def load_disaster_db():
    if DISASTER_DB.exists():
        return pd.read_csv(DISASTER_DB)
    # 샘플 데이터
    return pd.DataFrame([
        {"date": "2025-07-14", "location": "통영", "keyword": "고수온", "title": "경남 통영 고수온 피해 확산", "url": ""},
        {"date": "2025-07-28", "location": "여수", "keyword": "고수온", "title": "전남 여수 양식장 집단폐사", "url": ""},
        {"date": "2025-08-03", "location": "부산", "keyword": "고수온", "title": "부산 연안 수온 30도 돌파", "url": ""},
        {"date": "2025-07-20", "location": "거제", "keyword": "고수온", "title": "거제 해수욕장 고수온 경보", "url": ""},
        {"date": "2025-08-10", "location": "완도", "keyword": "고수온", "title": "완도 전복 집단폐사 우려", "url": ""},
    ])

@st.cache_data
def load_region_freq():
    if REGION_FREQ.exists():
        return pd.read_csv(REGION_FREQ)
    return pd.DataFrame([
        {"location": "통영", "count": 23, "lat": 34.85, "lon": 128.43},
        {"location": "여수", "count": 19, "lat": 34.76, "lon": 127.66},
        {"location": "부산", "count": 15, "lat": 35.10, "lon": 129.03},
        {"location": "거제", "count": 12, "lat": 34.88, "lon": 128.62},
        {"location": "완도", "count": 10, "lat": 34.31, "lon": 126.75},
    ])

df = load_disaster_db()
freq_df = load_region_freq()

# 필터
col1, col2 = st.columns(2)
with col1:
    dates = sorted(df["date"].unique()) if "date" in df.columns else []
    date_range = st.select_slider("기간 필터", options=dates or ["2025-06-01", "2025-08-31"],
                                   value=(dates[0], dates[-1]) if len(dates) >= 2 else ("2025-06-01", "2025-08-31"))
with col2:
    keywords = df["keyword"].unique().tolist() if "keyword" in df.columns else ["고수온"]
    selected_keywords = st.multiselect("재난 키워드", keywords, default=keywords)

filtered = df[
    (df["date"] >= date_range[0]) & (df["date"] <= date_range[1]) &
    (df["keyword"].isin(selected_keywords))
] if "date" in df.columns else df

st.markdown("---")

# 뉴스 테이블
st.subheader("📋 뉴스 기사 목록")
st.dataframe(filtered[["date", "location", "keyword", "title", "url"]], use_container_width=True)

st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📊 발생 위치 빈도")
    if not freq_df.empty:
        import plotly.express as px
        fig = px.bar(freq_df.sort_values("count", ascending=True),
                     x="count", y="location", orientation="h",
                     labels={"count": "발생 횟수", "location": "지역"})
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🏆 관심지역 TOP N")
    top_n = st.slider("TOP N", 3, 10, 5)
    top_regions = freq_df.sort_values("count", ascending=False).head(top_n)
    for i, row in top_regions.iterrows():
        st.markdown(f"**{top_regions.index.get_loc(i)+1}위** {row['location']} — {row['count']}건")

st.markdown("---")

# 지도
st.subheader("🗺️ 관심지역 지도")
try:
    import folium
    from streamlit_folium import st_folium
    m = folium.Map(location=[35.5, 128.0], zoom_start=7)
    for _, row in freq_df.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=row["count"] / 2,
            color="red", fill=True, fill_opacity=0.6,
            tooltip=f"{row['location']}: {row['count']}건",
        ).add_to(m)
    st_folium(m, width=900, height=450)
except Exception as e:
    st.warning(f"지도 오류: {e}")
