# alert-agent

고수온 지속 조건을 감지하고 경보/주의보 수준을 판단하는 서브에이전트.

## 역할

`data/` 폴더의 KHOA_OPeNDAP 실측 SST CSV를 스캔하여 지역별 고수온 지속 현황을 분석하고,
경보·주의보 발령 조건을 판단한다.

## 경보 기준 (28°C 이상 현재 연속 지속일수 기준)

| 조건 | 수준 | level 값 |
|------|------|----------|
| 현재 연속 1~2일 | 🟡 주의보 | `advisory` |
| 현재 연속 3일↑  | 🔴 경보   | `alarm`    |
| 해당 없음       | 정상      | `normal`   |

## 사용 방법

```python
from agents.alert_agent import get_active_alerts, check

# 경보/주의보 지역만
alerts = get_active_alerts(threshold=28.0)

# 전체 지역 상세 결과
all_results = check(threshold=28.0)
```

## 반환값 구조

```python
{
    "region": "고흥",
    "level": "alarm",          # alarm | advisory | normal
    "current_streak": 10,      # 현재 연속 고수온 일수
    "max_consec": 10,          # 분석 기간 최장 연속 일수
    "hot_freq": 14,            # 누적 고수온 일수
    "latest_sst": 26.19,       # 최근 측정 SST (°C)
    "latest_date": "2025-08-31",
    "threshold": 28.0,
}
```

## 파이프라인 위치

`main_agent.run_pipeline()` 3단계에서 호출됨:
뉴스 수집 → SST 수집 → **알림 판단** → 보고서 생성

## 시연 모드

`get_active_alerts(demo=True)` (기본값): 현재 streak이 없어도 과거 최장 streak으로
알림 수준을 산출하여 시연 환경에서도 결과 확인 가능.
