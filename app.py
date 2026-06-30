import streamlit as st

st.set_page_config(page_title="고수온 연안재해 모니터링", layout="wide")

st.title("고수온 연안재해 모니터링 시스템")

menu = st.sidebar.selectbox("메뉴", [
    "뉴스 크롤링 / 관심지역 추출",
    "수온 분석",
    "이상 지역 알림",
    "빈도 지도 / 그래프",
    "보고서 생성",
])

if menu == "뉴스 크롤링 / 관심지역 추출":
    st.header("뉴스 크롤링 / 관심지역 추출")
    st.info("크롤링 기능 개발 중")

elif menu == "수온 분석":
    st.header("수온 분석")
    st.info("수온 데이터 분석 개발 중")

elif menu == "이상 지역 알림":
    st.header("이상 지역 알림")
    st.info("알림 서비스 개발 중")

elif menu == "빈도 지도 / 그래프":
    st.header("빈도 지도 / 그래프")
    st.info("시각화 개발 중")

elif menu == "보고서 생성":
    st.header("보고서 생성")
    st.info("보고서 생성 개발 중")
