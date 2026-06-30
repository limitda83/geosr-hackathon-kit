"""파이프라인 실행 페이지 — 크롤링→수온수집→경보→보고서 전 흐름 상세 실행·결과 확인."""
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.style import apply
from utils.chat_widget import inject
from utils.alert_widget import inject_alerts
from agents.alert_agent import get_active_alerts
import config

st.set_page_config(page_title="Pipeline", page_icon="🔄", layout="wide")
apply()
inject()
inject_alerts(get_active_alerts())

st.title("🔄 파이프라인 실행")
st.caption(
    "뉴스 크롤링 → 수온 수집 → 경보 판단 → 보고서 생성. "
    "실행 후 **2_Disaster_Areas**, **3_Heat_Analysis** 페이지에 결과가 반영됩니다."
)

# ── API 키 상태 ───────────────────────────────────────────
with st.expander("🔑 API 키 상태", expanded=False):
    c1, c2, c3 = st.columns(3)
    c1.metric("네이버 API", "✅" if config.has_naver() else "❌ 미설정")
    c2.metric("공공데이터 API", "✅" if config.has_public_data() else "❌ 미설정")
    c3.metric("KOSC API", "✅" if config._get("KOSC_API_KEY") else "❌ 미설정")
    if not config.has_naver() and not config.has_public_data():
        st.info("뉴스 API 키 없음 → 시드(seed) 파일로 폴백됩니다.")

# ── 파라미터 ──────────────────────────────────────────────
st.subheader("⚙️ 파라미터")
col1, col2, col3 = st.columns(3)
with col1:
    keywords = st.multiselect("크롤링 키워드", config.DEFAULT_KEYWORDS + ["적조", "냉수"], default=["고수온"])
    max_items = st.number_input("기사 최대 수집 건수", 10, 200, 50, step=10)
    damage_only = st.checkbox("실제 피해 기사만 수집", value=False)
with col2:
    start = st.date_input("시작일", value=pd.Timestamp("2025-06-01")).strftime("%Y-%m-%d")
    end   = st.date_input("종료일", value=pd.Timestamp("2025-08-31")).strftime("%Y-%m-%d")
    top_n = st.number_input("관심지역 상위 N", 1, 10, 3, step=1)
with col3:
    threshold       = st.slider("고수온 기준(℃)", 24.0, 32.0, 28.0, 0.5)
    generate_report = st.checkbox("보고서 자동 생성", value=True)

st.markdown("---")

# ── 단계 표시 ─────────────────────────────────────────────
# Step1: crawler.run_pipeline() = 크롤링 + 위치추출 + SQLite 저장 + CSV export 통합
# Step2: collection_agent.run() = KOSC API 수온 수집
# Step3: alert_agent             = 경보 판단
# Step4: report_agent            = 보고서 생성
STEPS = [
    ("📰", "뉴스 크롤링·지역 추출", "crawl"),
    ("🛰️", "수온 수집",             "sst"),
    ("⚠️", "경보 판단",             "alert"),
    ("📄", "보고서 생성",           "report"),
]

def _badge(state: str) -> str:
    return {"waiting": "⬜", "running": "🔵", "done": "✅", "skip": "⏭️", "error": "❌"}.get(state, "⬜")

step_ph = st.empty()

def render_steps(states: dict):
    with step_ph.container():
        cols = st.columns(len(STEPS))
        for col, (icon, label, key) in zip(cols, STEPS):
            col.markdown(
                f"<div style='text-align:center;padding:12px;"
                f"background:rgba(0,194,212,0.07);border-radius:8px;"
                f"border:1px solid rgba(0,194,212,0.15);'>"
                f"<div style='font-size:22px;'>{_badge(states.get(key,'waiting'))} {icon}</div>"
                f"<div style='font-size:12px;color:#7aacbf;margin-top:4px;'>{label}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

render_steps({})

if st.button("▶ 파이프라인 전체 실행", type="primary", use_container_width=True):
    states = {k: "waiting" for _, _, k in STEPS}
    logs: list[str] = []

    def upd(key: str, state: str, msg: str = ""):
        states[key] = state
        render_steps(states)
        if msg:
            logs.append(msg)

    try:
        # ── Step 1: 크롤링 + 위치추출 + CSV export ────────
        # run_pipeline() 내부: crawl() → _to_records() → EventStore → export_team_csv()
        # 결과: disaster_events.csv + region_frequency.csv 자동 갱신
        upd("crawl", "running")
        from src.news.crawler import run_pipeline as crawl_pipeline
        rep = crawl_pipeline(
            disaster_type="고수온",
            keywords=keywords,
            max_items=int(max_items),
            since=start,
            until=end,
            top_n=int(top_n),
            damage_only=damage_only,
        )
        upd("crawl", "done",
            f"✅ {rep.n_fetched}건 수집 / 신규 {rep.n_new}건 / 위치추출 {rep.n_located}건 "
            f"(소스: {rep.source_used}) → disaster_events.csv + region_frequency.csv 갱신")

        # ── Step 2: 수온 수집 ─────────────────────────────
        # region_frequency.csv에서 지역 읽어 KOSC API로 수집
        upd("sst", "running")
        from agents.collection_agent import run as run_collection
        freq_csv = config.DATA_DIR / "results" / "frequency" / "region_frequency.csv"
        freq_df = pd.read_csv(freq_csv, encoding="utf-8")
        regions = freq_df.dropna(subset=["lat", "lon"]).to_dict("records")
        col_results = run_collection(regions, start, end)
        ok_n = sum(1 for r in col_results if r.get("success"))
        upd("sst", "done", f"✅ 수온 수집 {ok_n}/{len(col_results)}개 지역 성공 → data/*.csv 저장")

        # ── Step 3: 경보 판단 ─────────────────────────────
        upd("alert", "running")
        alerts = get_active_alerts(threshold=threshold)
        alarm_n    = sum(1 for a in alerts if a["level"] == "alarm")
        advisory_n = sum(1 for a in alerts if a["level"] == "advisory")
        upd("alert", "done", f"✅ 경보 {alarm_n}건 / 주의보 {advisory_n}건")

        # ── Step 4: 보고서 ────────────────────────────────
        if generate_report:
            upd("report", "running")
            from agents.report_agent import run as run_report
            report = run_report(threshold=threshold)
            upd("report", "done", "✅ 보고서 생성 완료")
            st.session_state["pipeline_report"] = report
        else:
            upd("report", "skip")

        st.session_state["pipeline_result"] = {
            "rep": rep,
            "col_results": col_results,
            "alerts": alerts,
        }
        st.success("파이프라인 완료! 2_Disaster_Areas · 3_Heat_Analysis 페이지에서 결과를 확인하세요.")

    except Exception as e:
        for key, state in states.items():
            if state == "running":
                states[key] = "error"
        render_steps(states)
        st.error(f"오류: {e}")
        logs.append(f"❌ {e}")

    if logs:
        st.markdown("---")
        for msg in logs:
            st.write(msg)

# ── 결과 탭 ───────────────────────────────────────────────
if "pipeline_result" in st.session_state:
    res = st.session_state["pipeline_result"]
    rep = res["rep"]
    st.markdown("---")
    st.subheader("📊 실행 결과")

    tab1, tab2, tab3 = st.tabs(["관심지역(AOI)", "수온 수집", "경보·주의보"])

    with tab1:
        if rep.aois:
            aoi_rows = [{
                "순위": a.rank,
                "지역": a.region_name,
                "기사 수": a.event_count,
                "위도": round(a.center_lat, 4),
                "경도": round(a.center_lon, 4),
            } for a in rep.aois]
            st.dataframe(pd.DataFrame(aoi_rows), use_container_width=True)
        else:
            st.info("추출된 AOI가 없습니다.")

    with tab2:
        col_df = pd.DataFrame(res["col_results"])
        show = [c for c in ["region", "success", "count", "error"] if c in col_df.columns]
        st.dataframe(col_df[show] if show else col_df, use_container_width=True)

    with tab3:
        alerts = res["alerts"]
        if alerts:
            adf = pd.DataFrame(alerts)
            adf["단계"] = adf["level"].map({"alarm": "🔴 경보", "advisory": "🟡 주의보"})
            show = [c for c in ["region", "단계", "current_streak", "latest_sst", "latest_date"] if c in adf.columns]
            st.dataframe(adf[show], use_container_width=True)
        else:
            st.info("현재 경보·주의보 지역 없음")

# ── 보고서 다운로드 ───────────────────────────────────────
if "pipeline_report" in st.session_state:
    report = st.session_state["pipeline_report"]
    st.markdown("---")
    st.subheader("📄 보고서 다운로드")
    stem = report.get("filename_stem", "report")
    d1, d2 = st.columns(2)
    if report.get("docx") and report["docx"].get("bytes"):
        d1.download_button("Word 다운로드", report["docx"]["bytes"],
                           file_name=f"{stem}.docx",
                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           use_container_width=True)
    if report.get("pdf") and report["pdf"].get("bytes"):
        d2.download_button("PDF 다운로드", report["pdf"]["bytes"],
                           file_name=f"{stem}.pdf",
                           mime="application/pdf",
                           use_container_width=True)
