from pathlib import Path

import pandas as pd
import streamlit as st

from agents.alert_agent import get_active_alerts
from utils.alert_widget import inject_alerts
from utils.chat_widget import inject
from utils.style import apply, card, hero, section

st.set_page_config(page_title="Home", page_icon="🏠", layout="wide")
apply()
inject()
inject_alerts(get_active_alerts())

NEWS_PATH = Path("data/processed/disaster_db/disaster_events.csv")
SST_DIR = Path("data")
SST_EXCLUDE = {"geocode", "regions", "Tongyeong"}
TARGET_START = pd.Timestamp("2025-07-01")
TARGET_END = pd.Timestamp("2025-08-31")
TARGET_PERIOD_LABEL = "2025.7 ~ 2025.8"


@st.cache_data(ttl=300)
def load_stats():
    stats: dict[str, object] = {}

    if NEWS_PATH.exists():
        news_df = pd.read_csv(NEWS_PATH, encoding="utf-8")
        dates = pd.to_datetime(news_df.get("date"), errors="coerce")
        period_mask = (dates >= TARGET_START) & (dates <= TARGET_END)
        filtered = news_df.loc[period_mask.fillna(False)].copy()
        filtered_dates = pd.to_datetime(filtered.get("date"), errors="coerce").dropna()
        stats["news_count"] = int(len(filtered))
        stats["news_period"] = TARGET_PERIOD_LABEL
        stats["last_updated"] = filtered_dates.max().strftime("%Y-%m-%d") if not filtered_dates.empty else None
    else:
        stats["news_count"] = 0
        stats["news_period"] = TARGET_PERIOD_LABEL
        stats["last_updated"] = None

    sst_total = 0
    sst_regions = []
    hot_regions = []

    for path in sorted(SST_DIR.glob("*_2025*.csv")):
        region = path.stem.split("_")[0]
        if region in SST_EXCLUDE:
            continue
        try:
            df = pd.read_csv(path, encoding="utf-8")
        except Exception:
            continue

        if "sst" not in df.columns or "source" not in df.columns:
            continue
        if df["source"].astype(str).str.contains("KHOA_OPeNDAP", na=False).sum() == 0:
            continue

        sst_total += int(df["sst"].notna().sum())
        sst_regions.append(region)

        hot = df["sst"] >= 28.0
        streak = 0
        max_streak = 0
        for flag in hot.fillna(False):
            streak = streak + 1 if bool(flag) else 0
            max_streak = max(max_streak, streak)
        if max_streak >= 3:
            hot_regions.append(region)

    stats["sst_count"] = sst_total
    stats["sst_regions"] = len(sst_regions)
    stats["hot_regions"] = hot_regions
    return stats


s = load_stats()

hero(
    "예보사업부 AI·AX 해커톤",
    "관측 수집, 고수온 분석, 보고서 생성을 한 화면에서 연결하는 해양 데이터 대시보드입니다.",
)

section("현재 분석 현황", "📊")
c1, c2, c3, c4 = st.columns(4)
with c1:
    card("수집된 뉴스", f"{s['news_count']:,}건", s["news_period"], "📰")
with c2:
    card("수집된 SST", f"{s['sst_count']:,}건", f"KHOA OPeNDAP · {s['sst_regions']}개 지역", "🌊")
with c3:
    card("고수온 위험 지역", f"{len(s['hot_regions'])}개", ", ".join(s["hot_regions"]) if s["hot_regions"] else "연속 3일 이상 기준 충족 지역 없음", "⚠️")
with c4:
    card("최신 갱신", s["last_updated"] or "확인 불가", "분석 데이터 기준", "🔄")

section("분석 데이터 안내", "🧭")
st.markdown(
    """
<div class="ocean-card" style="padding:24px 28px;">
  <div style="font-size:14px;color:#e8f4f8;margin-bottom:6px;font-weight:700;">실제 제출 데이터 기준으로만 집계하도록 정리했습니다.</div>
  <div style="font-size:12px;color:#7aacbf;">뉴스는 `disaster_events.csv` 전체 건수와 실제 기간을 표시하고, SST는 지역별 수집 CSV만 집계합니다.</div>
</div>
""",
    unsafe_allow_html=True,
)

with st.form("quick_pipeline"):
    fc1, fc2 = st.columns([3, 2])
    with fc1:
        q_keywords = st.multiselect("관심 해양 유형", ["고수온", "적조", "어업"], default=["고수온"])
        q_start = st.date_input("분석 시작일", value=TARGET_START).strftime("%Y-%m-%d")
        q_end = st.date_input("분석 종료일", value=pd.Timestamp("2025-08-31")).strftime("%Y-%m-%d")
    with fc2:
        q_max = st.slider("뉴스 수집 범위", 10, 200, 50, step=10)
        q_thr = st.slider("고수온 경보 기준", 24.0, 32.0, 28.0, 0.5)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    submitted = st.form_submit_button("업데이트 실행", type="primary", use_container_width=True)

if submitted:
    prog = st.progress(0, text="뉴스와 지역 정보를 정리하는 중...")
    result_ph = st.empty()
    try:
        from utils.region_extractor import load_disaster_events, extract_regions

        events_df = load_disaster_events()
        freq_df = extract_regions(events_df)
        n_news = len(events_df)
        prog.progress(40, text=f"뉴스 {n_news}건 로드 · 지역 추출 완료")

        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "collect_sst_by_region",
            Path("scripts/collect_sst_by_region.py").resolve(),
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        collect_region = mod.collect_region

        from datetime import date as _date

        regions_df = freq_df.dropna(subset=["lat", "lon"])
        ok_n = 0
        for _, row in regions_df.iterrows():
            try:
                collect_region(
                    region=row["location"],
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                    start=_date.fromisoformat(q_start),
                    end=_date.fromisoformat(q_end),
                    out_dir=Path("data"),
                )
                ok_n += 1
            except Exception:
                pass
        prog.progress(85, text=f"SST 수집 완료: {ok_n}/{len(regions_df)}개 지역")

        from agents.alert_agent import get_active_alerts as _alerts

        alerts = _alerts(threshold=q_thr)
        alarm_n = sum(1 for a in alerts if a["level"] == "alarm")
        advisory_n = sum(1 for a in alerts if a["level"] == "advisory")
        prog.progress(100, text="완료")

        result_ph.markdown(
            f"""
<div class="ocean-card" style="border-color:rgba(0,168,150,0.4);padding:18px 24px;">
  <div style="font-size:13px;font-weight:700;color:#00a896;margin-bottom:10px;">업데이트 완료</div>
  <div style="display:flex;gap:32px;flex-wrap:wrap;">
    <div><span style="color:#7aacbf;font-size:11px;">뉴스</span><br><span style="color:#00e5ff;font-weight:700;font-size:18px;">{n_news}건</span></div>
    <div><span style="color:#7aacbf;font-size:11px;">관심 지역</span><br><span style="color:#00e5ff;font-weight:700;font-size:18px;">{len(regions_df)}개</span></div>
    <div><span style="color:#7aacbf;font-size:11px;">수집 성공</span><br><span style="color:#00e5ff;font-weight:700;font-size:18px;">{ok_n}개 지역</span></div>
    <div><span style="color:#7aacbf;font-size:11px;">경보 현황</span><br><span style="color:#ffb86b;font-weight:700;font-size:18px;">경보 {alarm_n} · 주의보 {advisory_n}</span></div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    except Exception as e:
        prog.empty()
        result_ph.error(f"업데이트 중 오류가 발생했습니다: {e}")

section("서비스 안내", "🧩")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        """
<div class="ocean-card" style="height:160px;">
  <div style="font-size:28px;margin-bottom:10px;">📰</div>
  <div style="font-size:14px;font-weight:700;color:#e8f4f8;margin-bottom:6px;">뉴스 수집</div>
  <div style="font-size:12px;color:#7aacbf;line-height:1.6;">관심 해양 이슈 뉴스를 자동으로 모으고 지역 정보를 추출합니다.</div>
</div>
""",
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        """
<div class="ocean-card" style="height:160px;">
  <div style="font-size:28px;margin-bottom:10px;">🌊</div>
  <div style="font-size:14px;font-weight:700;color:#e8f4f8;margin-bottom:6px;">SST 분석</div>
  <div style="font-size:12px;color:#7aacbf;line-height:1.6;">관측 해역 SST를 모아 일별 추세와 고수온 상태를 확인합니다.</div>
</div>
""",
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        """
<div class="ocean-card" style="height:160px;">
  <div style="font-size:28px;margin-bottom:10px;">⚠️</div>
  <div style="font-size:14px;font-weight:700;color:#e8f4f8;margin-bottom:6px;">경보 판단</div>
  <div style="font-size:12px;color:#7aacbf;line-height:1.6;">28℃ 이상 연속 조건을 기준으로 경보와 주의보를 자동 계산합니다.</div>
</div>
""",
        unsafe_allow_html=True,
    )
