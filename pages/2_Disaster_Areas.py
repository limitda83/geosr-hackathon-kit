import streamlit as st
import pandas as pd
from pathlib import Path

from utils.alert_widget import inject_alerts
from utils.chat_widget import inject
from utils.region_extractor import extract_regions, load_disaster_events
from utils.style import apply
from utils.viz import make_frequency_map
from agents.alert_agent import get_active_alerts

st.set_page_config(page_title="Disaster Areas", page_icon="📰", layout="wide")
apply()
inject()
inject_alerts(get_active_alerts())

st.title("📰 관심지역 지도")
st.caption("실제 재난 뉴스에서 추출한 지역 빈도를 시각화합니다.")


@st.cache_data(ttl=300)
def load_data():
    df = load_disaster_events()
    freq_df = extract_regions(df)
    return df, freq_df


df, freq_df = load_data()

col1, col2 = st.columns(2)
with col1:
    dates = sorted(df["date"].dropna().unique()) if "date" in df.columns else []
    if len(dates) >= 2:
        date_range = st.select_slider("기간", options=dates, value=(dates[0], dates[-1]))
    else:
        date_range = (dates[0], dates[0]) if dates else ("", "")
with col2:
    keywords = df["keyword"].dropna().unique().tolist() if "keyword" in df.columns else []
    selected_keywords = st.multiselect("키워드", keywords, default=keywords)

if date_range[0] and date_range[1] and selected_keywords:
    filtered = df[
        (df["date"] >= date_range[0]) &
        (df["date"] <= date_range[1]) &
        (df["keyword"].isin(selected_keywords))
    ]
else:
    filtered = df

st.caption(f"표시 기사 {len(filtered):,}건 / 전체 {len(df):,}건")
st.markdown("---")

st.subheader("재난 뉴스 목록")
show_cols = [c for c in ["date", "location", "keyword", "title", "url"] if c in filtered.columns]
st.dataframe(filtered[show_cols], use_container_width=True)

st.markdown("---")

col1, col2 = st.columns([1, 1])
with col1:
    st.subheader("지역별 언급 빈도")
    if not freq_df.empty:
        import plotly.express as px

        fig = px.bar(
            freq_df.sort_values("count", ascending=True).head(20),
            x="count",
            y="location",
            orientation="h",
            labels={"count": "언급 수", "location": "지역"},
            color="count",
            color_continuous_scale=["#bfefff", "#00c2d4", "#005f6e"],
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#c8e6f0",
            showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("TOP 지역")
    top_n = st.slider("TOP N", 3, 15, 5)
    top_regions = freq_df.sort_values("count", ascending=False).head(top_n)
    for rank, (_, row) in enumerate(top_regions.iterrows(), 1):
        st.markdown(
            f"<div class='ocean-card' style='padding:12px 14px;margin-bottom:10px;'>"
            f"<div style='font-size:12px;color:#7aacbf;'>TOP {rank}</div>"
            f"<div style='font-size:18px;font-weight:800;color:#e8f4f8;'>{row['location']}</div>"
            f"<div style='font-size:13px;color:#7aacbf;'>언급 수 {int(row['count'])}건</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

st.markdown("---")

st.markdown(
    """
    <div class="ocean-card">
        <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:14px;">
            <div>
                <div style="font-size:12px;color:#7aacbf;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;">Map View</div>
                <h3 style="margin:0;color:#e8f4f8;">관심 지역 지도</h3>
                <div style="margin-top:6px;color:#7aacbf;font-size:13px;">실제 기사에서 추출한 지역 빈도를 기본 지도 위에 표시합니다.</div>
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
                <span style="padding:7px 12px;border-radius:999px;background:rgba(0,194,212,0.10);color:#c8e6f0;font-size:12px;border:1px solid rgba(0,194,212,0.18);">OpenStreetMap</span>
                <span style="padding:7px 12px;border-radius:999px;background:rgba(0,168,150,0.10);color:#c8e6f0;font-size:12px;border:1px solid rgba(0,168,150,0.18);">실데이터 기준</span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

map_df = freq_df.dropna(subset=["lat", "lon"])
map_left, map_right = st.columns([1.35, 0.65])
with map_left:
    if map_df.empty:
        st.warning("지리 정보가 없어 지도를 표시할 수 없습니다.")
    else:
        try:
            from streamlit_folium import st_folium
            m = make_frequency_map(map_df)
            st_folium(m, width=None, height=520, use_container_width=True)
        except Exception as e:
            st.warning(f"지도 표시 오류: {e}")
with map_right:
    top_region = freq_df.sort_values("count", ascending=False).iloc[0] if not freq_df.empty else None
    st.markdown(
        f"""
        <div class="ocean-card" style="height:100%;">
            <div style="font-size:12px;color:#7aacbf;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:8px;">Map Summary</div>
            <div style="display:grid;grid-template-columns:1fr;gap:12px;">
                <div style="padding:14px;border-radius:14px;background:rgba(0,194,212,0.06);border:1px solid rgba(0,194,212,0.12);">
                    <div style="font-size:12px;color:#7aacbf;">표시 지역 수</div>
                    <div style="font-size:26px;font-weight:800;color:#00e5ff;">{len(map_df):,}</div>
                </div>
                <div style="padding:14px;border-radius:14px;background:rgba(0,168,150,0.06);border:1px solid rgba(0,168,150,0.12);">
                    <div style="font-size:12px;color:#7aacbf;">가장 많이 언급된 지역</div>
                    <div style="font-size:22px;font-weight:800;color:#e8f4f8;">{top_region['location'] if top_region is not None else '-'}</div>
                </div>
                <div style="padding:14px;border-radius:14px;background:rgba(255,107,53,0.06);border:1px solid rgba(255,107,53,0.12);">
                    <div style="font-size:12px;color:#7aacbf;">최다 언급 건수</div>
                    <div style="font-size:22px;font-weight:800;color:#ffb199;">{int(top_region['count']) if top_region is not None else 0:,}건</div>
                </div>
                <div style="padding:14px;border-radius:14px;background:rgba(0,194,212,0.05);border:1px solid rgba(0,194,212,0.10);">
                    <div style="font-size:12px;color:#7aacbf;">표시 방식</div>
                    <div style="font-size:14px;color:#c8e6f0;line-height:1.7;">기본 지도로 공간감을 살리고, 지역별 점의 크기로 빈도를 강조합니다.</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
