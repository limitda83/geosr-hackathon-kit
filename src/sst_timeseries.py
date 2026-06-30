# -*- coding: utf-8 -*-
"""
sst_timeseries.py — KHOA SST 원자료의 '전체 격자 평균' 일별 시계열 산출·그래프

무엇을 하나:
  1) data/khoa_sst 의 일별 SST 원자료(.nc)를 한 장씩 읽어
     '전체 (바다)격자 평균 SST'를 하루당 1개 값으로 계산한다.   → 전체 격자 평균자료
  2) 일별 평균을 표(CSV)로 저장한다. (날짜·평균·최저·최고·유효격자수)
  3) 그 표를 바탕으로 '일별 시계열 그래프'를 그린다.

설계 의도(웹 연계):
  - 평균값은 한 번만 계산해 CSV 로 저장 → 웹(app.py)에서는 무거운 .nc 를 다시 읽지 않고
    CSV 만 불러 '사용자가 고른 기간'으로 잘라 그래프를 그린다(빠름).
  - 그래서 plot_timeseries(df, start, end) 처럼 '기간 지정' 인자를 미리 갖춰 둠.
    (지금은 전체 기간 그래프를 그리지만, 최종 웹 기능에서 start/end 만 넘기면 됨.)

초보자 안내:
  - 함수 run(src_dir, out_dir) 하나면 CSV + 전체기간 그래프 PNG 를 만들어 줍니다.
  - 단독 실행:  python sst_timeseries.py [원자료폴더] [출력폴더]
  - 파일을 한 장씩 읽어 평균만 남기므로 수십~수백 일치도 메모리에 안전합니다(스트리밍).

전제: 원자료폴더 안에 KHOA SST .nc (변수 sst, 단위 ℃)가 있어야 함.
"""

import os
import re
import glob

import numpy as np
import pandas as pd

# 앞 모듈의 SST 읽기/튐값제거 로직을 그대로 재사용 (일관성)
try:
    from sst_processing import open_sst, clean_sst, VALID_MIN, VALID_MAX
except ImportError:
    from src.sst_processing import open_sst, clean_sst, VALID_MIN, VALID_MAX

CSV_COLUMNS = ["date", "mean_sst", "min_sst", "max_sst", "valid_cells"]


# ---------------------------------------------------------------------------
# 1) 파일 1장 → 전체 격자 평균 (하루치)
# ---------------------------------------------------------------------------
def daily_mean_one(path: str, valid_min: float = VALID_MIN,
                   valid_max: float = VALID_MAX) -> dict:
    """SST .nc 1장에서 '전체 (바다)격자 평균 SST'와 요약통계를 계산한다.

    반환 dict: date(Timestamp), mean_sst, min_sst, max_sst, valid_cells
    - 육지/결측(NaN)과 0~40℃ 밖 튐값은 평균에서 자동 제외된다.
    """
    ds, name = open_sst(path)
    try:
        sst = clean_sst(ds[name], valid_min, valid_max)   # 튐값(0~40℃ 밖) 제거
        if "time" in sst.dims:
            sst = sst.isel(time=0)
        vals = np.asarray(sst.values, dtype="float64")
        finite = np.isfinite(vals)
        n = int(finite.sum())

        # 날짜: time 좌표 우선, 없으면 파일명에서 YYYYMMDD 파싱
        if "time" in ds and ds["time"].size:
            t = pd.to_datetime(ds["time"].values[0])
        else:
            m = re.search(r"(\d{8})", os.path.basename(path))
            t = pd.to_datetime(m.group(1), format="%Y%m%d") if m else pd.NaT

        return {
            "date": t,
            "mean_sst": float(np.nanmean(vals)) if n else np.nan,   # ← 전체 격자 평균
            "min_sst": float(np.nanmin(vals)) if n else np.nan,
            "max_sst": float(np.nanmax(vals)) if n else np.nan,
            "valid_cells": n,
        }
    finally:
        ds.close()


# ---------------------------------------------------------------------------
# 2) 폴더 전체 → 일별 평균 시계열 표(DataFrame)
# ---------------------------------------------------------------------------
def compute_daily_means(src_dir: str = "data/khoa_sst", pattern: str = "*.nc",
                        progress: bool = False) -> pd.DataFrame:
    """폴더 안 모든 원자료의 일별 전체격자 평균을 계산해 날짜순 DataFrame 으로 돌려준다."""
    paths = sorted(glob.glob(os.path.join(src_dir, pattern)))
    paths = [p for p in paths if "_HOT" not in os.path.basename(p)]   # 가공본 제외
    if not paths:
        raise FileNotFoundError(f"원자료(.nc)를 찾지 못했습니다: {src_dir}")

    rows = []
    for i, p in enumerate(paths, start=1):
        if progress:
            print(f"  ({i}/{len(paths)}) {os.path.basename(p)}", flush=True)
        rows.append(daily_mean_one(p))

    df = pd.DataFrame(rows, columns=CSV_COLUMNS)
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# 3) CSV 저장 / 읽기 (웹에서 빠르게 재사용)
# ---------------------------------------------------------------------------
def save_csv(df: pd.DataFrame, path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")   # 엑셀 호환
    return path


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    return df


# ---------------------------------------------------------------------------
# 4) 시계열 그래프 (기간 지정 가능 — 웹 연계용)
# ---------------------------------------------------------------------------
def plot_timeseries(df: pd.DataFrame, out_png: str,
                    start=None, end=None, title: str = None,
                    show_max: bool = True) -> str:
    """일별 SST 시계열 그래프를 그린다. (최대온도 + 평균온도, 최소온도는 제외)

    start, end : 'YYYY-MM-DD' (또는 Timestamp). 주면 그 기간만 그린다.
                 → 최종 웹에서 사용자가 고른 일자를 그대로 넘기면 됨.
    show_max   : 일별 최대온도 선을 함께 표시(True). 평균온도 선은 항상 표시.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    if start is not None:
        d = d[d["date"] >= pd.to_datetime(start)]
    if end is not None:
        d = d[d["date"] <= pd.to_datetime(end)]
    d = d.sort_values("date")
    if d.empty:
        raise ValueError("선택한 기간에 자료가 없습니다.")

    fig, ax = plt.subplots(figsize=(11, 5))
    # 최대온도 = 막대그래프 (파란 계열) — 평균선(빨강)과 색이 겹치지 않게 구분
    if show_max and "max_sst" in d.columns:
        ax.bar(d["date"], d["max_sst"], width=0.85, color="#7fb3d5",
               edgecolor="#4f8fc0", linewidth=0.3, alpha=0.85,
               label="domain-max SST", zorder=1)
    # 평균온도 = 선그래프 (빨강) — 막대 위에 그림
    ax.plot(d["date"], d["mean_sst"], color="#c0392b", marker="o", ms=3.5,
            lw=1.8, label="domain-mean SST", zorder=3)

    p0, p1 = d["date"].min(), d["date"].max()
    ax.set_title(title or f"KHOA SST domain-mean daily time series  "
                          f"({p0:%Y-%m-%d} ~ {p1:%Y-%m-%d})")
    ax.set_xlabel("Date")
    ax.set_ylabel("Sea surface temperature (°C)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate()

    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    fig.savefig(out_png, dpi=120)
    plt.close(fig)
    return out_png


# ---------------------------------------------------------------------------
# 5) 전체 실행: 평균 계산 → CSV → 전체기간 그래프
# ---------------------------------------------------------------------------
def run(src_dir: str = "data/khoa_sst", out_dir: str = "data/sst/timeseries",
        make_png: bool = True, progress: bool = True) -> dict:
    """일별 전체격자 평균 CSV + 전체기간 시계열 그래프를 만든다. 요약 dict 반환."""
    df = compute_daily_means(src_dir, progress=progress)
    tag = f"{df['date'].min():%Y%m%d}_{df['date'].max():%Y%m%d}"

    csv_path = os.path.join(out_dir, f"SST_daily_mean_{tag}.csv")
    save_csv(df, csv_path)

    summary = {
        "n_days": int(len(df)),
        "period": f"{df['date'].min():%Y-%m-%d} ~ {df['date'].max():%Y-%m-%d}",
        "csv": csv_path,
        "overall_mean": float(df["mean_sst"].mean()),
        "min_day": f"{df.loc[df['mean_sst'].idxmin(),'date']:%Y-%m-%d} ({df['mean_sst'].min():.2f}℃)",
        "max_day": f"{df.loc[df['mean_sst'].idxmax(),'date']:%Y-%m-%d} ({df['mean_sst'].max():.2f}℃)",
    }
    if make_png:
        png = os.path.join(out_dir, f"SST_daily_mean_{tag}.png")
        plot_timeseries(df, png)
        summary["png"] = png
    return summary


if __name__ == "__main__":
    import sys

    src_dir = sys.argv[1] if len(sys.argv) > 1 else "data/khoa_sst"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "data/sst/timeseries"

    print("=== KHOA SST 전체 격자 평균 일별 시계열 ===")
    print(f"입력: {src_dir}  →  출력: {out_dir}\n")

    s = run(src_dir, out_dir)

    print(f"\n분석 기간: {s['period']}  (총 {s['n_days']}일)")
    print(f"기간 평균 SST: {s['overall_mean']:.2f}℃")
    print(f"  · 최저일: {s['min_day']}")
    print(f"  · 최고일: {s['max_day']}")
    print(f"\n[CSV]  → {s['csv']}")
    if "png" in s:
        print(f"[그래프] → {s['png']}")
    print("\n완료.")
