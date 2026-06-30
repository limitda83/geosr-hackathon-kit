# -*- coding: utf-8 -*-
"""
sst_persistence.py — [요구사항5-②] 동일공간 고수온 '지속일수(연속)' 확인 기능

무엇을 하나:
  여러 날의 일별 고수온 파일(_HOT28.nc 의 hot_mask=1/0)을 날짜 순서대로 보며,
  같은 위치(격자)에서 28℃ 이상이 '연속으로 며칠' 이어졌는지(= 최장 연속 지속일수)를 구한다.
  → 3일 이상 '연속' 고수온이 이어진 격자의 공간분포 지도.

누적 빈도(sst_frequency.py)와의 차이:
  - 누적 빈도 : 띄엄띄엄이라도 '총 며칠' 고수온이었나 (순서 무관)
  - 지속일수 : '연속으로 몇 일' 이어졌나 (순서 중요, 중간에 끊기면 0으로 리셋)  ← 이 파일

핵심 계산:
  날짜를 순서대로 보며 '현재 연속 카운트'를 +1 하고, 비고수온인 날엔 0 으로 리셋.
  각 격자의 '최장 연속 일수'를 기록한다.

만들어지는 NC 변수 (lat×lon 2D):
  - max_consec    : 최장 연속 고수온 일수 (0~N), 육지·결측은 NaN
  - persist3_mask : consec_min(기본 3)일 이상 '연속'이면 1 (공간분포 지도용)
  - crs           : EPSG:4326 좌표계

초보자 안내:
  - 함수 run(hot_dir, out_dir) 하나면 NC + 해안선 배경 지도 PNG 를 만들어 줍니다.
  - 단독 실행:  python sst_persistence.py [고수온폴더] [출력폴더] [연속기준일]
  - 파일이 많아도 한 장씩 순서대로 읽어 계산하므로 메모리에 안전합니다(스트리밍).

전제: 고수온폴더 안에 sst_processing.py 가 만든 *_HOT28.nc 들이 있어야 함.
"""

import os

import numpy as np

try:
    from sst_gridutil import (list_hot_files, grid_from_file, read_hot_2d,
                              period_tag, wrap_2d, save_map_png, save_nc)
except ImportError:
    from src.sst_gridutil import (list_hot_files, grid_from_file, read_hot_2d,
                                  period_tag, wrap_2d, save_map_png, save_nc)

# 연속 지속으로 볼 최소 '연속' 일수 (요구사항5: 3일 이상 연속)
CONSEC_MIN_DAYS = 3


# ---------------------------------------------------------------------------
# 결과 2D 배열 → NC Dataset 으로 포장 (스트리밍/일괄 경로 공용)
# ---------------------------------------------------------------------------
def _assemble(lat, lon, times, max_run, persist3, consec_min):
    return wrap_2d(
        lat, lon, times,
        {
            "max_consec": (max_run, {
                "long_name": "longest consecutive run of days with SST >= 28 C",
                "units": "days",
                "comment": "시간축 연속 길이(run-length) 중 최댓값 = 최장 연속 지속일수",
            }),
            "persist3_mask": (persist3, {
                "long_name": f"consecutive high-SST mask (>= {consec_min} days in a row)",
                "units": "1",
                "flag_values": "0, 1",
                "flag_meanings": "not_consecutive consecutive",
                "comment": f"{consec_min}일 이상 '연속' 고수온이면 1 (공간분포 지도)",
            }),
        },
        title=f"고수온(≥28℃) {consec_min}일 이상 연속 지속 공간분포 지도",
        extra_attrs={"consec_min_days": consec_min, "analysis": "consecutive_persistence"},
    )


# ---------------------------------------------------------------------------
# 핵심: 최장 연속 지속일수 (작은 자료용 — 이미 쌓은 stack 을 받는 버전)
# ---------------------------------------------------------------------------
def build_consecutive(stack, consec_min: int = CONSEC_MIN_DAYS):
    """이미 (time,lat,lon) 으로 쌓인 stack 에서 최장 연속 지속일수 Dataset 을 만든다."""
    vals = stack.values
    sea = np.isfinite(vals).any(axis=0)
    hot_bool = (vals == 1.0)
    cur = np.zeros(vals.shape[1:], dtype=np.int16)
    max_run = np.zeros(vals.shape[1:], dtype=np.int16)
    for t in range(vals.shape[0]):
        cur = np.where(hot_bool[t], cur + 1, 0)
        max_run = np.maximum(max_run, cur)
    max_run_f = max_run.astype("float32")
    max_run_f[~sea] = np.nan
    persist3 = np.where(sea, (max_run >= consec_min), np.nan).astype("float32")
    return _assemble(stack["lat"], stack["lon"], stack["time"].values,
                     max_run_f, persist3, consec_min)


# ---------------------------------------------------------------------------
# 전체 실행: 파일을 날짜순 한 장씩 읽어 연속 계산 → NC + 지도 PNG (메모리 안전)
# ---------------------------------------------------------------------------
def run(hot_dir: str = "data/results/sst_analysis/sst_over28", out_dir: str = "data/results/sst_analysis/persistence",
        consec_min: int = CONSEC_MIN_DAYS, make_png: bool = True) -> dict:
    """연속 지속일수 NC 와 해안선 배경 지도 PNG 를 만든다. 결과 요약 dict 를 돌려준다."""
    paths = list_hot_files(hot_dir)   # 날짜순 정렬됨
    lat, lon = grid_from_file(paths[0])

    cur = None        # 현재 연속 카운트
    max_run = None    # 격자별 최장 연속
    sea = None        # 한 번이라도 값이 있었던 '바다' 격자
    times = []
    for p in paths:
        t, arr = read_hot_2d(p)
        times.append(t)
        finite = np.isfinite(arr)
        hot = (arr == 1.0)
        if cur is None:
            cur = hot.astype("int16")
            max_run = cur.copy()
            sea = finite.copy()
        else:
            cur = np.where(hot, cur + 1, 0).astype("int16")
            max_run = np.maximum(max_run, cur)
            sea |= finite
        del arr

    n_days = len(times)
    if n_days < consec_min:
        print(f"  [주의] 분석 일수({n_days})가 연속 기준({consec_min}일)보다 적습니다.")

    max_run_f = max_run.astype("float32")
    max_run_f[~sea] = np.nan
    persist3 = np.where(sea, (max_run >= consec_min), np.nan).astype("float32")

    ds = _assemble(lat, lon, times, max_run_f, persist3, consec_min)

    _, tag = period_tag(times)
    nc_path = os.path.join(out_dir, f"SST_HOTCONSEC{consec_min}_28C_{tag}.nc")
    save_nc(ds, nc_path)

    summary = {
        "feature": "지속일수(consecutive persistence)",
        "n_days": n_days,
        "period": f"{ds.attrs['time_coverage_start']} ~ {ds.attrs['time_coverage_end']}",
        "nc": nc_path,
        "sea_cells": int(np.isfinite(max_run_f).sum()),
        "consec_min": consec_min,
        "consec_cells": int(np.nansum(persist3)),
        "max_consec_observed": int(np.nanmax(max_run_f)),
    }

    if make_png:
        png = os.path.join(out_dir, f"SST_HOTCONSEC{consec_min}_28C_{tag}.png")
        save_map_png(ds, "max_consec", png,
                     title=f"Longest consecutive high-SST days (>=28C)  {summary['period']}",
                     cmap="hot_r", label="consecutive days", vmin=0, vmax=n_days)
        summary["png"] = png

    return summary


if __name__ == "__main__":
    import sys

    hot_dir = sys.argv[1] if len(sys.argv) > 1 else "data/results/sst_analysis/sst_over28"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "data/results/sst_analysis/persistence"
    c_min = int(sys.argv[3]) if len(sys.argv) > 3 else CONSEC_MIN_DAYS

    print("=== [요구사항5-②] 동일공간 고수온 지속일수(연속) 확인 ===")
    print(f"입력: {hot_dir}  →  출력: {out_dir}  (연속 기준 {c_min}일 이상)\n")

    s = run(hot_dir, out_dir, consec_min=c_min)

    print(f"분석 기간: {s['period']}  (총 {s['n_days']}일)")
    print(f"바다 격자 수: {s['sea_cells']:,}")
    print(f"  · {s['consec_min']}일 이상 '연속' 고수온 격자: {s['consec_cells']:,}")
    print(f"  · 관측된 최장 연속 일수: {s['max_consec_observed']}일")
    print(f"\n[NC]   → {s['nc']}")
    if "png" in s:
        print(f"[지도] → {s['png']}")
    print("\n완료.")
