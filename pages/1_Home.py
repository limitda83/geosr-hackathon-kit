import streamlit as st
from utils.style import apply, card, section, hero
from utils.chat_widget import inject

st.set_page_config(page_title="Home", page_icon="🌊", layout="wide")
apply()
inject()

hero(
    "🌊 고수온 연안재해 모니터링",
    "재난 뉴스 기반 관심지역 도출 · 국가해양위성센터 해수면온도 분석 · 이상탐지 자동화"
)

# 핵심 지표
section("핵심 분석 지표", "📡")
c1, c2, c3, c4 = st.columns(4)
with c1: card("재난 뉴스 수집", "47건", "2025.06 ~ 08", "📰")
with c2: card("수온 데이터", "1,247건", "KOSC SST API", "🌡️")
with c3: card("28°C↑ 격자", "분석 중", "고수온 필터", "🔥")
with c4: card("이상 탐지", "3지역", "연속 3일↑", "⚠️")

# 전체 흐름
section("분석 파이프라인", "🔄")
st.markdown("""
<div style="display:flex;align-items:center;gap:0;flex-wrap:wrap;margin:8px 0;">
""" + "".join([
    f"""<div style="display:flex;align-items:center;gap:0;">
        <div class="ocean-card" style="padding:14px 18px;min-width:120px;text-align:center;margin:4px;">
            <div style="font-size:20px;margin-bottom:4px;">{icon}</div>
            <div style="font-size:12px;font-weight:700;color:#00e5ff;">{step}</div>
            <div style="font-size:11px;color:#4a7a8a;margin-top:2px;">{desc}</div>
        </div>
        {'<div style="color:#00c2d4;font-size:20px;margin:0 -2px;">→</div>' if i < 5 else ''}
    </div>"""
    for i, (icon, step, desc) in enumerate([
        ("📰", "뉴스 수집", "재난 크롤링"),
        ("📍", "지역 추출", "관심지역 도출"),
        ("🛰️", "수온 수집", "KOSC API"),
        ("⚙️", "전처리", "NC → 격자"),
        ("📊", "고수온 분석", "28°C / 누적"),
        ("📄", "보고서", "자동 생성"),
    ])
]) + "</div>", unsafe_allow_html=True)

# 데이터 소스
section("데이터 소스", "🛰️")
c1, c2 = st.columns(2)
with c1:
    st.markdown("""
<div class="ocean-card">
<table style="width:100%;border-collapse:collapse;color:#c8e6f0;">
<tr style="border-bottom:1px solid rgba(0,194,212,0.1);">
  <th style="text-align:left;padding:8px 4px;color:#7aacbf;font-size:12px;">구분</th>
  <th style="text-align:left;padding:8px 4px;color:#7aacbf;font-size:12px;">소스</th>
</tr>
<tr><td style="padding:8px 4px;">📰 재난 뉴스</td><td style="padding:8px 4px;color:#00c2d4;">네이버 뉴스 크롤링</td></tr>
<tr><td style="padding:8px 4px;">🛰️ 해수면온도</td><td style="padding:8px 4px;color:#00c2d4;">국가해양위성센터 (KOSC)</td></tr>
<tr><td style="padding:8px 4px;">📅 분석 기간</td><td style="padding:8px 4px;color:#00c2d4;">2025년 6월 ~ 8월</td></tr>
<tr><td style="padding:8px 4px;">🗺️ 분석 범위</td><td style="padding:8px 4px;color:#00c2d4;">한반도 연안 격자</td></tr>
</table>
</div>
""", unsafe_allow_html=True)
with c2:
    st.markdown("""
<div class="ocean-card">
<table style="width:100%;border-collapse:collapse;color:#c8e6f0;">
<tr style="border-bottom:1px solid rgba(0,194,212,0.1);">
  <th style="text-align:left;padding:8px 4px;color:#7aacbf;font-size:12px;">파일 형식</th>
  <th style="text-align:left;padding:8px 4px;color:#7aacbf;font-size:12px;">설명</th>
</tr>
<tr><td style="padding:8px 4px;">📄 CSV</td><td style="padding:8px 4px;color:#00a896;">뉴스·지역 집계 데이터</td></tr>
<tr><td style="padding:8px 4px;">🌐 NC (NetCDF)</td><td style="padding:8px 4px;color:#00a896;">해수면온도 격자 원천</td></tr>
<tr><td style="padding:8px 4px;">🖼️ PNG</td><td style="padding:8px 4px;color:#00a896;">분석 결과 지도 이미지</td></tr>
<tr><td style="padding:8px 4px;">📝 DOCX</td><td style="padding:8px 4px;color:#00a896;">자동 생성 보고서</td></tr>
</table>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='margin-top:16px;font-size:12px;color:#2a5a6a;text-align:center;'>분석 기준: SST 28°C 이상 / 누적 2일 이상 / 연속 3일 이상</div>", unsafe_allow_html=True)
