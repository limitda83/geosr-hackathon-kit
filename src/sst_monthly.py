# -*- coding: utf-8 -*-
"""
sst_monthly.py — 월별 평균 해수면온도(SST) + 전월 대비 차이지도 생산

무엇을 하나:
  1) data/input/khoa_sst 의 일별 SST 원자료(.nc)를 '월'별로 묶어
     전처리(튐값 0~40℃ 제거) 후 격자별 월평균을 계산한다.
       → mean_month/  : 월평균 NC + 지도 PNG
  2) 각 월에 대해 '직전 달(전월)'의 월평균이 있으면 (해당월 − 전월) 차이지도를 만든다.
       → diff_month/  : 차이 NC + 지도 PNG
     전월 자료가 없으면 그 달의 차이자료는 생산하지 않는다.

좌표계 EPSG:4326, 배경지도는 Natural Earth 해안선(basemap) 재사용.

초보자 안내:
  - 함수 run(src_dir, mean_dir, diff_dir) 하나면 다 만들어 줍니다.
  - 단독 실행:  python sst_monthly.py [원자료폴더] [mean_month폴더] [diff_month폴더]
  - 파일을 한 장씩 읽어 누적하므로 메모리에 안전합니다(스트리밍).
"""

import os
import re
import glob
from datetime import date, timedelta

import numpy as np
import xarray as xr

# 앞 모듈들 재사용 (SST 읽기·튐값제거·CRS·저장·해안선 지도)
try:
    from sst_processing import open_sst, clean_sst, make_crs_var, save_nc, VALID_MIN, VALID_MAX
    from basemap import plot_grid_map
except ImportError:
    from src.sst_processing import open_sst, clean_sst, make_crs_var, save_nc, VALID_MIN, VALID_MAX
    from src.basemap import plot_grid_map

# 월평균 지도 표시 범위(℃) — 달 간 비교가 쉽도록 고정
MEAN_VMIN, MEAN_VMAX = 10.0, 31.0


# ---------------------------------------------------------------------------
# 파일을 '월(YYYYMM)' 별로 묶기
# ---------------------------------------------------------------------------
def group_by_month(src_dir: str, pattern: str = "*.nc") -> dict:
    """폴더의 일별 .nc 를 {'YYYYMM': [경로…]} 로 묶는다(가공본 _HOT 제외, 날짜순)."""
    paths = sorted(glob.glob(os.path.join(src_dir, pattern)))
    groups = {}
    for p in paths:
        if "_HOT" in os.path.basename(p):
            continue
        m = re.search(r"(\d{8})", os.path.basename(p))
        if not m:
            continue
        groups.setdefault(m.group(1)[:6], []).append(p)   # YYYYMM
    return {ym: sorted(v) for ym, v in groups.items()}


def prev_month(ym: str) -> str:
    """'YYYYMM' 의 직전 달 'YYYYMM' 을 돌려준다. (예: 202508 → 202507)"""
    y, m = int(ym[:4]), int(ym[4:6])
    d = date(y, m, 1) - timedelta(days=1)     # 전월의 마지막 날
    return f"{d.year}{d.month:02d}"


# ---------------------------------------------------------------------------
# 한 달치 → 격자별 월평균 (스트리밍 누적)
# ---------------------------------------------------------------------------
def monthly_mean(paths: list, valid_min: float = VALID_MIN, valid_max: float = VALID_MAX):
    """일별 파일들을 한 장씩 읽어 격자별 월평균(유효일 평균)을 계산한다.

    반환: (mean 2D float32, lat, lon, n_days)  — 육지·전일 결측은 NaN
    """
    sum_arr = cnt_arr = lat = lon = None
    for p in paths:
        ds, name = open_sst(p)
        sst = clean_sst(ds[name], valid_min, valid_max)    # 튐값(0~40℃ 밖) 제거
        if "time" in sst.dims:
            sst = sst.isel(time=0)
        arr = np.asarray(sst.values, dtype="float64")
        if lat is None:
            lat = ds["lat"].values.copy()
            lon = ds["lon"].values.copy()
        ds.close()

        finite = np.isfinite(arr)
        if sum_arr is None:
            sum_arr = np.where(finite, arr, 0.0)
            cnt_arr = finite.astype("int32")
        else:
            sum_arr += np.where(finite, arr, 0.0)
            cnt_arr += finite
        del arr

    mean = np.where(cnt_arr > 0, sum_arr / np.maximum(cnt_arr, 1), np.nan).astype("float32")
    return mean, lat, lon, len(paths)


# ---------------------------------------------------------------------------
# 2D 배열 → NC Dataset (좌표·CRS·메타 포함)
# ---------------------------------------------------------------------------
def _build_ds(varname: str, arr, lat, lon, var_attrs: dict, title: str, extra_attrs: dict):
    da = xr.DataArray(np.asarray(arr), dims=("lat", "lon"),
                      coords={"lat": np.asarray(lat), "lon": np.asarray(lon)})
    va = dict(var_attrs); va["grid_mapping"] = "crs"
    da.attrs = va
    out = xr.Dataset({varname: da, "crs": make_crs_var()})
    out["lon"].attrs.update({"standard_name": "longitude", "units": "degrees_east"})
    out["lat"].attrs.update({"standard_name": "latitude", "units": "degrees_north"})
    out.attrs = {
        "title": title,
        "Conventions": "CF-1.8",
        "geographic_crs_name": "WGS84, EPSG:4326",
        "processed_by": "team-gvidia / sst_monthly.py",
    }
    out.attrs.update(extra_attrs)
    return out


# ---------------------------------------------------------------------------
# 전체 실행
# ---------------------------------------------------------------------------
def run(src_dir: str = "data/input/khoa_sst",
        mean_dir: str = "data/results/sst_analysis/mean_month",
        diff_dir: str = "data/results/sst_analysis/diff_month",
        make_png: bool = True) -> dict:
    """월평균(mean_month) + 전월 대비 차이(diff_month)를 생산한다. 요약 dict 반환."""
    groups = group_by_month(src_dir)
    if not groups:
        raise FileNotFoundError(f"원자료(.nc)를 찾지 못했습니다: {src_dir}")

    print(f"=== 월별 평균 SST + 전월 대비 차이 ===")
    print(f"입력: {src_dir}  |  월: {', '.join(sorted(groups))}\n")

    # 1) 월평균
    means = {}     # ym -> (mean, lat, lon, n_days)
    mean_out = []
    for ym in sorted(groups):
        mean, lat, lon, n = monthly_mean(groups[ym])
        means[ym] = (mean, lat, lon, n)
        ymlabel = f"{ym[:4]}-{ym[4:6]}"

        ds = _build_ds("sst_mean", mean, lat, lon,
                       {"long_name": f"monthly mean sea surface temperature ({ymlabel})",
                        "units": "celsius",
                        "comment": f"{n}일 일평균의 격자별 평균 (튐값 0~40℃ 밖 제외)"},
                       title=f"월평균 해수면온도 {ymlabel}",
                       extra_attrs={"year_month": ymlabel, "n_days": n,
                                    "analysis": "monthly_mean"})
        nc = os.path.join(mean_dir, f"SST_MONMEAN_{ym}.nc")
        save_nc(ds, nc)
        rec = {"ym": ym, "n_days": n, "nc": nc}
        if make_png:
            png = os.path.join(mean_dir, f"SST_MONMEAN_{ym}.png")
            plot_grid_map(mean, lon, lat, png,
                          title=f"Monthly mean SST  {ymlabel}  ({n} days)",
                          cmap="turbo", label="monthly mean SST (°C)",
                          vmin=MEAN_VMIN, vmax=MEAN_VMAX)
            rec["png"] = png
        mean_out.append(rec)
        print(f"  [월평균] {ymlabel}  ({n}일)  → {os.path.basename(nc)}")

    # 2) 전월 대비 차이 (전월 자료 있을 때만)
    diff_out = []
    skipped = []
    for ym in sorted(means):
        pm = prev_month(ym)
        if pm not in means:
            skipped.append(ym)
            print(f"  [차이 생략] {ym[:4]}-{ym[4:6]}: 전월({pm[:4]}-{pm[4:6]}) 자료 없음")
            continue

        cur_mean, lat, lon, _ = means[ym]
        prev_mean = means[pm][0]
        diff = (cur_mean - prev_mean).astype("float32")     # 해당월 − 전월
        ymlabel, pmlabel = f"{ym[:4]}-{ym[4:6]}", f"{pm[:4]}-{pm[4:6]}"

        ds = _build_ds("sst_diff", diff, lat, lon,
                       {"long_name": f"monthly mean SST difference ({ymlabel} minus {pmlabel})",
                        "units": "celsius",
                        "comment": "양수=전월보다 따뜻 / 음수=전월보다 차가움"},
                       title=f"월평균 해수면온도 차이 {ymlabel} − {pmlabel}",
                       extra_attrs={"year_month": ymlabel, "prev_year_month": pmlabel,
                                    "analysis": "monthly_diff_vs_prev"})
        nc = os.path.join(diff_dir, f"SST_MONDIFF_{ym}_vs_{pm}.nc")
        save_nc(ds, nc)
        rec = {"ym": ym, "prev": pm, "nc": nc}
        if make_png:
            # 차이는 0 중심 발산형 컬러맵(빨강=상승/파랑=하강), 대칭 범위
            finite = diff[np.isfinite(diff)]
            vabs = float(np.nanpercentile(np.abs(finite), 99)) if finite.size else 1.0
            vabs = max(1.0, round(vabs + 0.5))
            png = os.path.join(diff_dir, f"SST_MONDIFF_{ym}_vs_{pm}.png")
            plot_grid_map(diff, lon, lat, png,
                          title=f"Monthly mean SST diff: {ymlabel} − {pmlabel}",
                          cmap="RdBu_r", label="ΔSST (°C, this month − prev)",
                          vmin=-vabs, vmax=vabs)
            rec["png"] = png
            rec["vabs"] = vabs
        diff_out.append(rec)
        print(f"  [차이]    {ymlabel} − {pmlabel}  → {os.path.basename(nc)}")

    return {"months": sorted(groups), "mean": mean_out, "diff": diff_out, "skipped": skipped,
            "mean_dir": mean_dir, "diff_dir": diff_dir}


if __name__ == "__main__":
    import sys

    src_dir = sys.argv[1] if len(sys.argv) > 1 else "data/input/khoa_sst"
    mean_dir = sys.argv[2] if len(sys.argv) > 2 else "data/results/sst_analysis/mean_month"
    diff_dir = sys.argv[3] if len(sys.argv) > 3 else "data/results/sst_analysis/diff_month"

    s = run(src_dir, mean_dir, diff_dir)
    print(f"\n월평균 {len(s['mean'])}개 / 차이 {len(s['diff'])}개 "
          f"(전월없어 생략 {len(s['skipped'])}개)")
    print(f"mean_month: {mean_dir}")
    print(f"diff_month: {diff_dir}")
    print("완료.")
