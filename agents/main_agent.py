"""
메인 에이전트 — 전체 파이프라인 조율

순서: news_agent → collection_agent → alert_agent → report_agent

각 단계는 독립 서브에이전트로 분리되어 있으며,
alert_agent는 수집된 SST 데이터 기반으로 경보/주의보를 판단한다.
"""
from agents.news_agent import run as run_news
from agents.collection_agent import run as run_collection
from agents.alert_agent import get_active_alerts, check as check_alerts
from agents.report_agent import run as run_report


def run_pipeline(
    keyword: str = "고수온",
    start: str = "2025-06-01",
    end: str = "2025-08-31",
    threshold: float = 28.0,
    generate_report: bool = True,
):
    """전체 파이프라인 실행.

    Returns
    -------
    dict: {
        "regions": list,
        "alerts": list,          # 경보/주의보 지역 목록
        "report": dict | None,   # 보고서 생성 결과
    }
    """
    print("[1/4] 뉴스 수집 & 관심지역 추출...")
    regions = run_news(keyword, start, end)
    print(f"  → {len(regions)}개 지역 추출")

    print(f"[2/4] 수온 데이터 수집 ({len(regions)}개 지역)...")
    results = run_collection(regions, start, end)

    print("[3/4] 고수온 경보·주의보 판단...")
    alerts = get_active_alerts(threshold=threshold)
    for a in alerts:
        level_kr = "경보" if a["level"] == "alarm" else "주의보"
        print(f"  {level_kr}: {a['region']} (연속 {a['current_streak']}일, 최근 {a['latest_sst']:.1f}°C)")
    if not alerts:
        print("  → 현재 경보/주의보 없음")

    report = None
    if generate_report:
        print("[4/4] 보고서 생성...")
        report = run_report(threshold=threshold)
        print(f"  → 보고서 완료")

    print("\n=== 파이프라인 완료 ===")
    print(f"  분석 지역 : {len(regions)}개")
    print(f"  활성 경보 : {sum(1 for a in alerts if a['level'] == 'alarm')}개")
    print(f"  활성 주의보: {sum(1 for a in alerts if a['level'] == 'advisory')}개")

    return {"regions": regions, "alerts": alerts, "report": report}


if __name__ == "__main__":
    run_pipeline()
