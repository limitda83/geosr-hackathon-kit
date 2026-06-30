import streamlit as st


def apply():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Pretendard', 'Noto Sans KR', sans-serif;
}

:root {
    --ocean-dark:   #020d1a;
    --ocean-deep:   #041529;
    --ocean-mid:    #062240;
    --ocean-light:  #0a3660;
    --cyan:         #00c2d4;
    --cyan-2:       #00e5ff;
    --teal:         #00a896;
    --warn:         #ff6b35;
    --text:         #e8f4f8;
    --text-muted:   #7aacbf;
    --panel:        rgba(4, 21, 41, 0.85);
    --panel-border: rgba(0, 194, 212, 0.15);
    --glow:         0 0 24px rgba(0, 194, 212, 0.12);
}

/* 배경 — 바다 느낌 */
.stApp {
    background:
        radial-gradient(ellipse at 20% 0%, rgba(0,194,212,0.08) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 100%, rgba(0,168,150,0.07) 0%, transparent 50%),
        linear-gradient(180deg, #020d1a 0%, #041529 50%, #020d1a 100%);
    min-height: 100vh;
}

/* 사이드바 */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #020d1a 0%, #041529 100%) !important;
    border-right: 1px solid rgba(0,194,212,0.12) !important;
}
[data-testid="stSidebar"] * { color: #c8e6f0 !important; }
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {
    border-radius: 10px;
    transition: background 0.2s;
}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {
    background: rgba(0,194,212,0.08) !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] {
    background: rgba(0,194,212,0.13) !important;
    border-left: 3px solid var(--cyan);
}

/* 메인 컨텐츠 배경 투명 */
[data-testid="stAppViewContainer"] { background: transparent; }
section.main .block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}

/* 메트릭 카드 */
[data-testid="stMetric"] {
    background: var(--panel);
    border: 1px solid var(--panel-border);
    border-radius: 16px;
    padding: 18px;
    box-shadow: var(--glow);
    backdrop-filter: blur(12px);
}
[data-testid="stMetricLabel"] { color: var(--text-muted) !important; font-size: 12px !important; }
[data-testid="stMetricValue"] { color: var(--cyan) !important; font-weight: 800 !important; }

/* 버튼 */
.stButton > button {
    border-radius: 12px;
    font-weight: 700;
    background: linear-gradient(135deg, #08324f, #0e5f7a);
    color: white !important;
    border: 1px solid rgba(0,194,212,0.25) !important;
    box-shadow: 0 4px 16px rgba(0,96,144,0.25);
    transition: all 0.2s;
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,168,212,0.28);
    border-color: var(--cyan) !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #0b5f8a, #00c2d4) !important;
    border-color: rgba(0,229,255,0.35) !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #0f719f, #21d8e8) !important;
}

/* 폼 submit 버튼 */
div[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #0b5f8a, #00c2d4) !important;
    border-color: rgba(0,229,255,0.35) !important;
}
div[data-testid="stFormSubmitButton"] > button:hover {
    background: linear-gradient(135deg, #0f719f, #21d8e8) !important;
}

/* 데이터프레임 */
[data-testid="stDataFrame"] {
    background: var(--panel);
    border: 1px solid var(--panel-border);
    border-radius: 14px;
    overflow: hidden;
    box-shadow: var(--glow);
}

/* 텍스트 */
h1 { color: var(--cyan-2) !important; font-weight: 800 !important; letter-spacing: -0.03em; }
h2, h3 { color: var(--text) !important; letter-spacing: -0.02em; }
p, li, span { color: var(--text-muted); }

/* 인풋 */
.stTextInput input, .stSelectbox select, .stNumberInput input {
    background: rgba(4,21,41,0.8) !important;
    border: 1px solid rgba(0,194,212,0.2) !important;
    border-radius: 10px !important;
    color: var(--text) !important;
}
.stTextInput input:focus {
    border-color: var(--cyan) !important;
    box-shadow: 0 0 0 2px rgba(0,194,212,0.15) !important;
}

/* 탭 */
.stTabs [data-baseweb="tab"] {
    color: var(--text-muted) !important;
    border-radius: 8px 8px 0 0;
}
.stTabs [aria-selected="true"] {
    color: var(--cyan) !important;
    border-bottom: 2px solid var(--cyan) !important;
}

/* 알림 박스 */
.stInfo { background: rgba(0,194,212,0.07) !important; border-color: rgba(0,194,212,0.25) !important; color: var(--text) !important; }
.stSuccess { background: rgba(0,168,150,0.07) !important; border-color: rgba(0,168,150,0.3) !important; }
.stWarning { background: rgba(255,107,53,0.07) !important; border-color: rgba(255,107,53,0.3) !important; }
.stError { background: rgba(220,53,69,0.07) !important; border-color: rgba(220,53,69,0.3) !important; }

/* 스크롤바 */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(0,194,212,0.2); border-radius: 4px; }

/* 구분선 */
hr { border-color: rgba(0,194,212,0.1) !important; }

/* Streamlit 기본 숨김 */
#MainMenu, footer, header { visibility: hidden; }

/* 소프트 카드 */
.ocean-card {
    background: var(--panel);
    border: 1px solid var(--panel-border);
    border-radius: 18px;
    padding: 20px 24px;
    box-shadow: var(--glow);
    backdrop-filter: blur(12px);
    margin-bottom: 12px;
}
</style>
""", unsafe_allow_html=True)


def card(title: str, value: str, sub: str = "", icon: str = ""):
    st.markdown(f"""
<div class="ocean-card" style="text-align:left;">
    <div style="font-size:11px;color:#7aacbf;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;">{icon} {title}</div>
    <div style="font-size:32px;font-weight:800;color:#00e5ff;line-height:1.1;letter-spacing:-0.02em;">{value}</div>
    <div style="font-size:12px;color:#4a7a8a;margin-top:8px;">{sub}</div>
</div>
""", unsafe_allow_html=True)


def section(title: str, icon: str = ""):
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;margin:28px 0 14px 0;">
    <div style="width:3px;height:22px;border-radius:2px;background:linear-gradient(180deg,#00c2d4,#00a896);"></div>
    <span style="font-size:17px;font-weight:700;color:#e8f4f8;">{icon} {title}</span>
</div>
""", unsafe_allow_html=True)


def hero(title: str, subtitle: str):
    st.markdown(f"""
<div style="
    background: linear-gradient(135deg, rgba(0,194,212,0.08) 0%, rgba(0,168,150,0.05) 100%);
    border: 1px solid rgba(0,194,212,0.15);
    border-radius: 20px;
    padding: 36px 40px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
">
    <div style="position:absolute;top:-40px;right:-40px;width:200px;height:200px;
        border-radius:50%;background:radial-gradient(circle,rgba(0,194,212,0.08),transparent);"></div>
    <div style="position:absolute;bottom:-60px;left:30%;width:300px;height:150px;
        border-radius:50%;background:radial-gradient(ellipse,rgba(0,168,150,0.06),transparent);"></div>
    <h1 style="color:#00e5ff;margin:0 0 10px 0;font-size:2rem;">{title}</h1>
    <p style="color:#7aacbf;margin:0;font-size:15px;">{subtitle}</p>
</div>
""", unsafe_allow_html=True)
