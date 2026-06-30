# -*- coding: utf-8 -*-
"""
5_SST_Timeseries.py — 해수면온도 일별 시계열 (웹에서 '일자 지정')

무엇을 하나:
  - sst_timeseries.py 가 미리 만들어 둔 일별 전체격자 평균 CSV
    (data/results/sst_analysis/timeseries/SST_daily_mean_*.csv)를 불러와,
  - 사용자가 고른 기간(시작·종료일)으로 잘라 시계열 그래프를 그린다.
  - 최대온도 = 막대(파랑), 평균온도 = 선(빨강), Y축 기본 15~36℃.

설계: 무거운 .nc 를 매번 읽지 않고 CSV 만 필터링 → 즉시 그래프(빠름).
      (CSV 가 없으면:  python src/sst_timeseries.py  실행 안내)
"""

from pathlib import Path

import pandas as pd
import streamlit as st

# 공통 스타일/챗 위젯 (다른 페이지와 동일). 환경에 따라 없을 수 있어 안전하게 처리.
try:
    from utils.style import apply
    from utils.chat_widget import inject
except Exception:                      # utils 미존재 시에도 페이지는 동작
    def apply(): pass
    def inject(): pass

st.set_page_config(page_title="SST Timeseries", page_icon="📈", layout="wide")
# 공통 스타일/챗 위젯 적용 (secrets.toml 미설정 등으로 실패해도 페이지는 계속 동작)
try:
    apply()
except Exception:
    pass
try:
    inject()
except Exception:
    pass

st.title("📈 해수면온도 일별 시계열 — 일자 지정")
st.caption("KHOA SST 전체 격자 평균(빨간 선)과 일별 최고온도(파란 막대). 기간을 골라 시계열을 확인하세요.")

CSV_DIR = Path("data/results/sst_analysis/timeseries")


@st.cache_data
def load_latest_csv():
    """가장 최근 일별 평균 CSV 를 불러온다. 없으면 (None, None)."""
    csvs = sorted(CSV_DIR.glob("SST_daily_mean_*.csv"))
    if not csvs:
        return None, None
    path = csvs[-1]
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df, path


df, csv_path = load_latest_csv()

if df is None:
    st.warning(
        "일별 평균 CSV 가 아직 없습니다.\n\n"
        "터미널에서 아래를 먼저 실행해 주세요:\n"
        "```bash\npython src/sst_timeseries.py\n```\n"
        f"(예상 위치: `{CSV_DIR}/SST_daily_mean_*.csv`)"
    )
    st.stop()

st.caption(f"자료: `{csv_path.name}`  ·  전체 {len(df)}일  "
           f"({df['date'].min():%Y-%m-%d} ~ {df['date'].max():%Y-%m-%d})")

# ── 일자(기간) 지정 ────────────────────────────────────────────────
dmin, dmax = df["date"].min().date(), df["date"].max().date()
c1, c2 = st.columns([3, 1])
with c1:
    sel = st.date_input("기간 선택 (시작일 · 종료일)", value=(dmin, dmax),
                        min_value=dmin, max_value=dmax)
with c2:
    show_max = st.checkbox("최고온도 막대 표시", value=True)

# date_input 은 선택 도중 1개만 올 수 있어 안전 처리
if isinstance(sel, (list, tuple)) and len(sel) == 2:
    start, end = sel
else:
    start, end = dmin, dmax

with st.expander("표시 옵션 (Y축 온도 범위)"):
    oc1, oc2 = st.columns(2)
    ymin = oc1.number_input("Y축 최소 (℃)", value=15.0, step=1.0)
    ymax = oc2.number_input("Y축 최대 (℃)", value=36.0, step=1.0)

# 선택 기간으로 자르기
mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
d = df.loc[mask].sort_values("date")
if d.empty:
    st.error("선택한 기간에 자료가 없습니다.")
    st.stop()

# ── 요약 지표 ──────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("선택 기간 일수", f"{len(d)}일")
m2.metric("기간 평균 SST", f"{d['mean_sst'].mean():.2f} ℃")
hi = d.loc[d["mean_sst"].idxmax()]
lo = d.loc[d["mean_sst"].idxmin()]
m3.metric("평균 최고일", f"{hi['mean_sst']:.2f} ℃", help=f"{hi['date']:%Y-%m-%d}")
m4.metric("평균 최저일", f"{lo['mean_sst']:.2f} ℃", help=f"{lo['date']:%Y-%m-%d}")

# ── 시계열 그래프 (최고=막대 / 평균=선, Y축 15~36℃) ────────────────
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

fig, ax = plt.subplots(figsize=(11, 4.6))
if show_max and "max_sst" in d.columns:
    ax.bar(d["date"], d["max_sst"], width=0.85, color="#7fb3d5",
           edgecolor="#4f8fc0", linewidth=0.3, alpha=0.85,
           label="domain-max SST", zorder=1)
ax.plot(d["date"], d["mean_sst"], color="#c0392b", marker="o", ms=3.5,
        lw=1.8, label="domain-mean SST", zorder=3)
ax.set_title(f"KHOA SST domain-mean daily time series  "
             f"({d['date'].min():%Y-%m-%d} ~ {d['date'].max():%Y-%m-%d})")
ax.set_xlabel("Date")
ax.set_ylabel("Sea surface temperature (°C)")
ax.set_ylim(ymin, ymax)
ax.grid(True, alpha=0.3)
ax.legend(loc="best")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
fig.autofmt_xdate()
fig.tight_layout()
st.pyplot(fig)

# ── 데이터 표 + 다운로드 ──────────────────────────────────────────
with st.expander("선택 기간 데이터 표 보기"):
    st.dataframe(d.reset_index(drop=True), use_container_width=True)
    st.download_button(
        "선택 기간 CSV 다운로드",
        data=d.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"SST_daily_mean_{start:%Y%m%d}_{end:%Y%m%d}.csv",
        mime="text/csv",
    )
