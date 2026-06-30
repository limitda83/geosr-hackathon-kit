from pathlib import Path

import pandas as pd
import streamlit as st

from agents.alert_agent import get_active_alerts
from utils.alert_widget import inject_alerts
from utils.chat_widget import inject
from utils.style import apply, card, hero, section

st.set_page_config(page_title="Home", page_icon="🌊", layout="wide")
apply()
inject()
inject_alerts(get_active_alerts())


@st.cache_data(ttl=300)
def load_stats():
    stats = {}
    news_path = Path("data/processed/disaster_db/disaster_events.csv")
    if news_path.exists():
        news_df = pd.read_csv(news_path, encoding="utf-8")
        stats["news_count"] = len(news_df)
        dates = pd.to_datetime(news_df["date"], errors="coerce").dropna()
        stats["news_period"] = (
            f"{dates.min().strftime('%Y.%m')} ~ {dates.max().strftime('%Y.%m')}"
            if not dates.empty
            else "2025.06 ~ 08"
        )
        stats["last_updated"] = dates.max().strftime("%Y-%m-%d") if not dates.empty else None
    else:
        stats["news_count"] = None
        stats["news_period"] = "2025.06 ~ 08"
        stats["last_updated"] = None

    sst_total, sst_regions, hot_regions = 0, 0, []
    for f in sorted(Path("data").glob("*_2025*.csv")):
        region = f.stem.split("_")[0]
        if region in ("geocode", "regions", "Tongyeong"):
            continue
        try:
            df = pd.read_csv(f, encoding="utf-8")
            if "sst" in df.columns and df.get("source", pd.Series([""])).iloc[0] == "KHOA_OPeNDAP":
                sst_total += df["sst"].notna().sum()
                sst_regions += 1
                hot = df["sst"] >= 28.0
                cur = max_c = 0
                for v in hot:
                    cur = cur + 1 if v else 0
                    max_c = max(max_c, cur)
                if max_c >= 3:
                    hot_regions.append(region)
        except Exception:
            pass

    stats["sst_count"] = sst_total if sst_total > 0 else None
    stats["sst_regions"] = sst_regions
    stats["hot_regions"] = hot_regions
    return stats


s = load_stats()

hero(
    "예보사업부 AI·AX 플랫폼",
    "관심지역 수집, 고수온 분석, 보고서 생성을 한 화면에서 연결하는 운영 대시보드입니다.",
)

section("현재 분석 현황", "📡")
c1, c2, c3, c4 = st.columns(4)
with c1:
    card("수집된 뉴스", f"{s['news_count']:,}건" if s["news_count"] else "없음", s["news_period"], "📰")
with c2:
    card("수집된 수온", f"{s['sst_count']:,}건" if s["sst_count"] else "없음", f"KHOA OPeNDAP · {s['sst_regions']}개 지역", "🌡️")
with c3:
    card("고수온 위험 지역", f"{len(s['hot_regions'])}개" if s["hot_regions"] else "없음", ", ".join(s["hot_regions"]) if s["hot_regions"] else "연속 3일 이상 지역", "⚠️")
with c4:
    card("최신 갱신", s["last_updated"] or "미확인", "분석 데이터 기준", "🔄")

section("분석 데이터 업데이트", "✨")
st.markdown(
    """
<div class="ocean-card" style="padding:24px 28px;">
  <div style="font-size:14px;color:#e8f4f8;margin-bottom:6px;font-weight:700;">최신 뉴스를 수집하고 분석 결과를 갱신합니다</div>
  <div style="font-size:12px;color:#7aacbf;">수집된 데이터는 재난 지역 분석과 수온 현황 페이지에 즉시 반영됩니다.</div>
</div>
""",
    unsafe_allow_html=True,
)

with st.form("quick_pipeline"):
    fc1, fc2 = st.columns([3, 2])
    with fc1:
        q_keywords = st.multiselect("관심 재난 유형", ["고수온", "폭염", "태풍"], default=["고수온"])
        q_start = st.date_input("분석 시작일", value=pd.Timestamp("2025-06-01")).strftime("%Y-%m-%d")
        q_end = st.date_input("분석 종료일", value=pd.Timestamp("2025-08-31")).strftime("%Y-%m-%d")
    with fc2:
        q_max = st.slider("뉴스 수집 범위", 10, 200, 50, step=10)
        q_thr = st.slider("고수온 경보 기준(℃)", 24.0, 32.0, 28.0, 0.5)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    submitted = st.form_submit_button("업데이트 실행", type="primary", use_container_width=True)

if submitted:
    prog = st.progress(0, text="뉴스를 수집하는 중...")
    result_ph = st.empty()
    try:
        from utils.region_extractor import load_disaster_events, extract_regions

        events_df = load_disaster_events()
        freq_df = extract_regions(events_df)
        n_news = len(events_df)
        prog.progress(40, text=f"뉴스 {n_news}건 로드 · 지역 추출 완료")

        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "collect_sst_by_region",
            Path("scripts/collect_sst_by_region.py").resolve(),
        )
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        collect_region = _mod.collect_region
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
        prog.progress(85, text=f"수온 수집 완료: {ok_n}/{len(regions_df)}개 지역")

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
    <div><span style="color:#7aacbf;font-size:11px;">수온 수집</span><br><span style="color:#00e5ff;font-weight:700;font-size:18px;">{ok_n}개 지역</span></div>
    <div><span style="color:#7aacbf;font-size:11px;">경보 현황</span><br><span style="color:#ffb86b;font-weight:700;font-size:18px;">경보 {alarm_n} · 주의보 {advisory_n}</span></div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    except Exception as e:
        prog.empty()
        result_ph.error(f"업데이트 중 오류가 발생했습니다: {e}")

section("서비스 안내", "🧭")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        """
<div class="ocean-card" style="height:160px;">
  <div style="font-size:28px;margin-bottom:10px;">📰</div>
  <div style="font-size:14px;font-weight:700;color:#e8f4f8;margin-bottom:6px;">뉴스 수집</div>
  <div style="font-size:12px;color:#7aacbf;line-height:1.6;">재난 관련 뉴스를 자동으로 수집하고 지역 정보를 추출합니다.</div>
</div>
""",
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        """
<div class="ocean-card" style="height:160px;">
  <div style="font-size:28px;margin-bottom:10px;">🌡️</div>
  <div style="font-size:14px;font-weight:700;color:#e8f4f8;margin-bottom:6px;">수온 분석</div>
  <div style="font-size:12px;color:#7aacbf;line-height:1.6;">관심지역 SST를 모아 일별 추세와 고수온 상태를 확인합니다.</div>
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
  <div style="font-size:12px;color:#7aacbf;line-height:1.6;">28℃ 이상 연속 조건을 바탕으로 경보와 주의보를 자동 판정합니다.</div>
</div>
""",
        unsafe_allow_html=True,
    )
