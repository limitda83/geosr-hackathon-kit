import streamlit as st
from utils.style import apply
from utils.chat_widget import inject

st.set_page_config(
    page_title="고수온 연안재해 모니터링",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply()
inject()

st.title("🌊 고수온 연안재해 모니터링")
st.caption("재난 뉴스 기반 관심지역 도출 · 국가해양위성센터 해수면온도 분석")
st.info("사이드바에서 페이지를 선택하세요.")
