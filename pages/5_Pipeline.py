from pathlib import Path

import pandas as pd
import streamlit as st

import config
from agents.alert_agent import get_active_alerts
from agents.report_agent import run as run_report
from utils.alert_widget import inject_alerts
from utils.chat_widget import inject
from utils.style import apply, card, hero, section

st.set_page_config(page_title="Pipeline", page_icon="🌐", layout="wide")
apply()
inject()
inject_alerts(get_active_alerts())

hero(
    "운영 파이프라인",
    "수집, 분석, 알림, 보고서를 한 번에 실행하는 내부 운영 화면입니다.",
)

section("실행 제어", "⚙️")
with st.container():
    left, right = st.columns([1.2, 0.8])
    with left:
        st.markdown('<div class="ocean-card">', unsafe_allow_html=True)
        st.markdown("#### 실행 범위")
        keywords = st.multiselect("관심 키워드", config.DEFAULT_KEYWORDS, default=["고수온"])
        max_items = st.slider("기사 수", 10, 200, 50, 10)
        threshold = st.slider("고수온 기준(℃)", 24.0, 32.0, 28.0, 0.5)
        generate_report = st.checkbox("보고서 자동 생성", value=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="ocean-card">', unsafe_allow_html=True)
        st.markdown("#### 운영 요약")
        card("수집", "대기", "뉴스 수집 및 위치 매칭", "📥")
        card("분석", "대기", "SST 수집 및 경보 판정", "📊")
        card("보고서", "대기", "Word / PDF 생성", "📝")
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

if st.button("파이프라인 실행", type="primary", use_container_width=True):
    with st.spinner("플랫폼 파이프라인을 실행 중입니다."):
        try:
            # ── Step 1: 기존 disaster_events.csv에서 지역 추출 ──
            # (Google RSS는 현재 뉴스만 반환하므로 기수집된 데이터를 사용)
            from utils.region_extractor import load_disaster_events, extract_regions

            events_df = load_disaster_events()
            freq_df = extract_regions(events_df)
            n_news = len(events_df)
            n_located = freq_df.dropna(subset=["lat", "lon"]).shape[0]

            # ── Step 2: 지역별 SST 수집 (KHOA OPeNDAP, API 키 불필요) ──
            import sys, importlib.util
            from datetime import date

            _spec = importlib.util.spec_from_file_location(
                "collect_sst_by_region",
                Path(__file__).parent.parent / "scripts" / "collect_sst_by_region.py",
            )
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            collect_region = _mod.collect_region

            regions_df = freq_df.dropna(subset=["lat", "lon"])
            saved, failed = [], []
            for _, row in regions_df.iterrows():
                try:
                    collect_region(
                        region=row["location"],
                        lat=float(row["lat"]),
                        lon=float(row["lon"]),
                        start=date(2025, 6, 1),
                        end=date(2025, 8, 31),
                        out_dir=config.DATA_DIR,
                    )
                    saved.append(row["location"])
                except Exception as e:
                    failed.append(f"{row['location']}({e})")

            # ── Step 3: 경보 판단 ──
            alerts = get_active_alerts(threshold=threshold)

            # ── Step 4: 보고서 ──
            report = run_report(threshold=threshold) if generate_report else None

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("수집 기사", f"{n_news}건")
            c2.metric("위치 추출", f"{n_located}개 지역")
            c3.metric("수온 수집", f"{len(saved)}개 지역")
            c4.metric("경보", f"{sum(1 for a in alerts if a['level'] == 'alarm')}건")

            if failed:
                st.warning(f"수온 수집 실패: {', '.join(failed)}")
            st.success("파이프라인 실행이 완료되었습니다.")
            if report:
                st.session_state["pipeline_report"] = report
            st.cache_data.clear()
        except Exception as e:
            st.error(f"실행 중 오류가 발생했습니다: {e}")
