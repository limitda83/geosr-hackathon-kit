"""파이프라인 실행 페이지 — 뉴스→수집→경보→보고서 전체 흐름을 웹에서 실행."""
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.style import apply
from utils.chat_widget import inject
from utils.alert_widget import inject_alerts
from agents.alert_agent import get_active_alerts

st.set_page_config(page_title="Pipeline", page_icon="🔄", layout="wide")
apply()
inject()
inject_alerts(get_active_alerts())

st.title("🔄 파이프라인 실행")
st.caption("뉴스 수집 → 관심지역 도출 → 수온 수집 → 경보 판단 → 보고서 생성 전 단계를 한 번에 실행합니다.")

# ── 파라미터 설정 ─────────────────────────────────────────
st.subheader("⚙️ 실행 파라미터")
col1, col2, col3 = st.columns(3)
with col1:
    keyword = st.text_input("뉴스 키워드", value="고수온")
with col2:
    start = st.date_input("시작일", value=pd.Timestamp("2025-06-01")).strftime("%Y-%m-%d")
    end   = st.date_input("종료일", value=pd.Timestamp("2025-08-31")).strftime("%Y-%m-%d")
with col3:
    threshold     = st.slider("고수온 기준(℃)", 24.0, 32.0, 28.0, 0.5)
    generate_report = st.checkbox("보고서 자동 생성", value=True)

st.markdown("---")

# ── 파이프라인 상태 표시 ──────────────────────────────────
STEPS = [
    ("📰", "뉴스 수집·지역 추출", "news"),
    ("🛰️", "수온 데이터 수집",   "collection"),
    ("⚠️", "고수온 경보 판단",   "alert"),
    ("📄", "보고서 생성",         "report"),
]

def _step_badge(state: str) -> str:
    return {"waiting": "⬜", "running": "🔵", "done": "✅", "skip": "⏭️", "error": "❌"}.get(state, "⬜")

def render_steps(states: dict):
    cols = st.columns(len(STEPS))
    for col, (icon, label, key) in zip(cols, STEPS):
        badge = _step_badge(states.get(key, "waiting"))
        col.markdown(
            f"<div style='text-align:center;padding:12px;background:rgba(0,194,212,0.07);"
            f"border-radius:8px;border:1px solid rgba(0,194,212,0.15);'>"
            f"<div style='font-size:22px;'>{badge} {icon}</div>"
            f"<div style='font-size:12px;color:#7aacbf;margin-top:4px;'>{label}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

placeholder = st.empty()
with placeholder.container():
    render_steps({})

# ── 실행 버튼 ────────────────────────────────────────────
if st.button("▶ 파이프라인 전체 실행", type="primary", use_container_width=True):
    states: dict = {k: "waiting" for _, _, k in STEPS}
    result_log: list[str] = []

    def update(key: str, state: str, msg: str = ""):
        states[key] = state
        with placeholder.container():
            render_steps(states)
        if msg:
            result_log.append(msg)

    try:
        # 1단계: 뉴스
        update("news", "running")
        from agents.news_agent import run as run_news
        regions = run_news(keyword, start, end)
        update("news", "done", f"✅ 관심지역 {len(regions)}개 추출")

        # 2단계: 수온 수집
        update("collection", "running")
        from agents.collection_agent import run as run_collection
        col_results = run_collection(regions, start, end)
        success_n = sum(1 for r in col_results if r.get("success"))
        update("collection", "done", f"✅ 수온 수집 완료 ({success_n}/{len(col_results)}개 지역 성공)")

        # 3단계: 경보 판단
        update("alert", "running")
        from agents.alert_agent import get_active_alerts
        alerts = get_active_alerts(threshold=threshold)
        alarm_n    = sum(1 for a in alerts if a["level"] == "alarm")
        advisory_n = sum(1 for a in alerts if a["level"] == "advisory")
        update("alert", "done", f"✅ 경보 {alarm_n}건 / 주의보 {advisory_n}건")

        # 4단계: 보고서
        if generate_report:
            update("report", "running")
            from agents.report_agent import run as run_report
            report = run_report(threshold=threshold)
            update("report", "done", "✅ 보고서 생성 완료")
            st.session_state["pipeline_report"] = report
        else:
            update("report", "skip")

        st.session_state["pipeline_result"] = {
            "regions": regions,
            "col_results": col_results,
            "alerts": alerts,
        }
        st.success("파이프라인 실행 완료!")

    except Exception as e:
        for key, state in states.items():
            if state == "running":
                states[key] = "error"
        with placeholder.container():
            render_steps(states)
        st.error(f"파이프라인 오류: {e}")
        result_log.append(f"❌ 오류: {e}")

    if result_log:
        st.markdown("---")
        for msg in result_log:
            st.write(msg)

# ── 결과 표시 ────────────────────────────────────────────
if "pipeline_result" in st.session_state:
    res = st.session_state["pipeline_result"]
    st.markdown("---")
    st.subheader("📊 실행 결과")

    tab1, tab2, tab3 = st.tabs(["관심지역", "수온 수집", "경보·주의보"])

    with tab1:
        regions_df = pd.DataFrame(res["regions"])
        st.dataframe(regions_df, use_container_width=True)

    with tab2:
        col_df = pd.DataFrame(res["col_results"])
        show_cols = [c for c in ["region", "success", "count", "error"] if c in col_df.columns]
        st.dataframe(col_df[show_cols], use_container_width=True)

    with tab3:
        alerts = res["alerts"]
        if alerts:
            alert_df = pd.DataFrame(alerts)
            level_map = {"alarm": "🔴 경보", "advisory": "🟡 주의보"}
            alert_df["단계"] = alert_df["level"].map(level_map)
            show = [c for c in ["region", "단계", "current_streak", "latest_sst", "latest_date"] if c in alert_df.columns]
            st.dataframe(alert_df[show], use_container_width=True)
        else:
            st.info("현재 경보·주의보 지역 없음")

# ── 보고서 다운로드 ──────────────────────────────────────
if "pipeline_report" in st.session_state:
    report = st.session_state["pipeline_report"]
    st.markdown("---")
    st.subheader("📄 보고서 다운로드")
    stem = report.get("filename_stem", "report")
    d1, d2 = st.columns(2)
    if report.get("docx") and report["docx"].get("bytes"):
        d1.download_button(
            "Word 다운로드",
            report["docx"]["bytes"],
            file_name=f"{stem}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    if report.get("pdf") and report["pdf"].get("bytes"):
        d2.download_button(
            "PDF 다운로드",
            report["pdf"]["bytes"],
            file_name=f"{stem}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
