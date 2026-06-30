# -*- coding: utf-8 -*-
"""
alert_agent.py — 고수온 지속 조건 감지 알림 서브에이전트

조건:
  - 🟠 주의: 28°C 이상 누적 2일↑ (persist2)
  - 🔴 위험: 28°C 이상 연속 3일↑ (persist3)

공개 함수:
  check(threshold=28.0) -> list[dict]
    각 지역별 알림 레벨·지속일수 반환

  get_active_alerts(threshold=28.0) -> list[dict]
    주의 이상 지역만 필터링해서 반환
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR   = Path("data")
THRESHOLD  = 28.0
FREQ_MIN   = 2   # 누적 기준 (sst_frequency.py 동일)
CONSEC_MIN = 3   # 연속 기준 (sst_persistence.py 동일)


def _calc(df: pd.DataFrame, threshold: float) -> dict:
    sst  = df["sst"].dropna().values
    hot  = sst >= threshold
    freq = int(hot.sum())

    cur = max_c = 0
    for v in hot:
        cur   = cur + 1 if v else 0
        max_c = max(max_c, cur)

    # 가장 최근 연속 고수온 일수 (현재 진행 중인 streak)
    current_streak = 0
    for v in reversed(hot):
        if v:
            current_streak += 1
        else:
            break

    latest_sst = float(df["sst"].iloc[-1]) if not df.empty else None
    latest_date = str(df["date"].iloc[-1])[:10] if not df.empty else None

    # 현재 진행 중인 연속 고수온 기준으로 경보 단계 결정
    if current_streak >= CONSEC_MIN:
        level = "alarm"    # 🔴 경보  (3일↑ 연속)
    elif current_streak >= 1:
        level = "advisory" # 🟡 주의보 (1~2일 연속)
    else:
        level = "normal"   # 정상

    return {
        "hot_freq":       freq,
        "max_consec":     max_c,
        "current_streak": current_streak,
        "level":          level,
        "latest_sst":     latest_sst,
        "latest_date":    latest_date,
    }


def check(threshold: float = THRESHOLD) -> list[dict]:
    """전체 지역 고수온 감지 결과 반환."""
    results = []
    for f in sorted(DATA_DIR.glob("*_2025*.csv")):
        region = f.stem.split("_")[0]
        if region in ("geocode", "regions", "Tongyeong"):
            continue
        try:
            df = pd.read_csv(f, encoding="utf-8", parse_dates=["date"])
            if "sst" not in df.columns:
                continue
            src = df.get("source", pd.Series([""])).iloc[0]
            if src != "KHOA_OPeNDAP":
                continue
            stat = _calc(df.sort_values("date").reset_index(drop=True), threshold)
            results.append({"region": region, **stat, "threshold": threshold})
        except Exception:
            continue
    return results


def get_active_alerts(threshold: float = THRESHOLD, demo: bool = True) -> list[dict]:
    """주의보/경보 지역만 반환, 경보 우선 정렬.

    demo=True (기본값): 현재 streak이 없어도 과거 최장 streak 기준으로
    알림 레벨을 산출해 시연에서 결과를 확인할 수 있게 함.
    실운영 시 demo=False 로 호출하면 실시간 streak만 사용.
    """
    all_r = check(threshold)

    if demo:
        for r in all_r:
            if r["current_streak"] == 0 and r["level"] == "normal":
                # 과거 최장 streak으로 레벨 재산출
                if r["max_consec"] >= CONSEC_MIN:
                    r["level"] = "alarm"
                    r["current_streak"] = r["max_consec"]  # 시연용으로 max 값 사용
                elif r["max_consec"] >= 1:
                    r["level"] = "advisory"
                    r["current_streak"] = r["max_consec"]

    active = [r for r in all_r if r["level"] != "normal"]
    active.sort(key=lambda x: (0 if x["level"] == "alarm" else 1, -x["current_streak"]))
    return active


if __name__ == "__main__":
    alerts = check()
    for a in alerts:
        icon = "🔴" if a["level"] == "alarm" else ("🟡" if a["level"] == "advisory" else "✅")
        print(f"{icon} {a['region']}: 누적 {a['hot_freq']}일, 최장연속 {a['max_consec']}일, 현재streak {a['current_streak']}일 | 최근 {a['latest_sst']}°C ({a['latest_date']})")
