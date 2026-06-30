"""
메인 에이전트 — news_agent → collection_agent → report_agent 순서로 조율
LangGraph 없이 순차 호출로 동작 (초안)
"""
from agents.news_agent import run as run_news
from agents.collection_agent import run as run_collection
from agents.report_agent import run as run_report


def run_pipeline(keyword: str = "고수온", start: str = "2025-06-01", end: str = "2025-08-31"):
    print("[1/3] 뉴스 수집 & 관심지역 추출...")
    regions = run_news(keyword, start, end)

    print(f"[2/3] 수온 데이터 수집 ({len(regions)}개 지역)...")
    results = run_collection(regions, start, end)

    print("[3/3] 보고서 생성...")
    report_path = run_report(regions, results)

    print(f"완료: {report_path}")
    return report_path


if __name__ == "__main__":
    run_pipeline()
