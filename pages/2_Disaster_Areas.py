import streamlit as st
import pandas as pd
from pathlib import Path
from utils.style import apply
from utils.chat_widget import inject
from utils.alert_widget import inject_alerts
from utils.region_extractor import load_disaster_events, extract_regions
from utils.viz import make_frequency_map, make_alert_bubble_map
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

st.markdown(
    """
    <div class="ocean-card">
        <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:14px;">
            <div>
                <div style="font-size:12px;color:#7aacbf;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;">Map View</div>
                <h3 style="margin:0;color:#e8f4f8;">?? ?? ??</h3>
                <div style="margin-top:6px;color:#7aacbf;font-size:13px;">?? ???? ??? ?? ??? ?? ?? ?? ?????.</div>
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
                <span style="padding:7px 12px;border-radius:999px;background:rgba(0,194,212,0.10);color:#c8e6f0;font-size:12px;border:1px solid rgba(0,194,212,0.18);">OpenStreetMap</span>
                <span style="padding:7px 12px;border-radius:999px;background:rgba(0,168,150,0.10);color:#c8e6f0;font-size:12px;border:1px solid rgba(0,168,150,0.18);">???? ??</span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

map_left, map_right = st.columns([1.3, 0.7])
with map_left:
    if map_df.empty:
        st.warning("지도 데이터가 없습니다.")
    else:
        try:
            deck = make_frequency_map(map_df)
            st.pydeck_chart(deck, use_container_width=True, height=520)
        except Exception as e:
            st.warning(f"지도 오류: {e}")
with map_right:
    top_region = freq_df.sort_values("count", ascending=False).iloc[0] if not freq_df.empty else None
    st.markdown(
        f"""
        <div class="ocean-card" style="height:100%;">
            <div style="font-size:12px;color:#7aacbf;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:8px;">Map Summary</div>
            <div style="display:grid;grid-template-columns:1fr;gap:12px;">
                <div style="padding:14px;border-radius:14px;background:rgba(0,194,212,0.06);border:1px solid rgba(0,194,212,0.12);">
                    <div style="font-size:12px;color:#7aacbf;">?? ?? ?</div>
                    <div style="font-size:26px;font-weight:800;color:#00e5ff;">{len(map_df):,}</div>
                </div>
                <div style="padding:14px;border-radius:14px;background:rgba(0,168,150,0.06);border:1px solid rgba(0,168,150,0.12);">
                    <div style="font-size:12px;color:#7aacbf;">?? ?? ??? ??</div>
                    <div style="font-size:22px;font-weight:800;color:#e8f4f8;">{top_region['location'] if top_region is not None else "-"}</div>
                </div>
                <div style="padding:14px;border-radius:14px;background:rgba(255,107,53,0.06);border:1px solid rgba(255,107,53,0.12);">
                    <div style="font-size:12px;color:#7aacbf;">?? ?? ??</div>
                    <div style="font-size:22px;font-weight:800;color:#ffb199;">{int(top_region['count']) if top_region is not None else 0:,}?</div>
                </div>
                <div style="padding:14px;border-radius:14px;background:rgba(0,194,212,0.05);border:1px solid rgba(0,194,212,0.10);">
                    <div style="font-size:12px;color:#7aacbf;">?? ??</div>
                    <div style="font-size:14px;color:#c8e6f0;line-height:1.7;">?? ??? ???? ???, ??? ?? ??? ??? ?????.</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
