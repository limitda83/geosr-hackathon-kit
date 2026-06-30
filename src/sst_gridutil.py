# -*- coding: utf-8 -*-
"""
sst_gridutil.py — 고수온 다일 분석 '공용 도우미' (요구사항5 두 기능이 함께 씀)

여기에는 두 기능(누적빈도 / 지속일수)이 공통으로 쓰는 부품만 모았습니다.
  - list_hot_files / read_hot_2d / grid_from_file : 일별 고수온 파일을 '한 장씩' 읽기(메모리 절약)
  - load_hot_stack : (작은 자료용) 한꺼번에 시간축으로 쌓기
  - wrap_2d        : 2D 결과 배열을 좌표·CRS·기간메타와 함께 NC용 Dataset 으로 포장
  - save_map_png   : 2D 변수 하나를 Natural Earth 해안선 배경 위에 지도 PNG 로 저장
  - make_crs_var / save_nc : 앞 모듈(sst_processing)에서 그대로 재사용 (여기서 재노출)

기능 모듈(sst_frequency.py, sst_persistence.py)은 이 파일만 import 하면 됩니다.

메모리 메모: 파일이 많을 때(수십 일치)는 load_hot_stack 으로 전부 올리지 말고
            list_hot_files + read_hot_2d 로 '한 장씩' 읽어 누적하세요(스트리밍).
"""

import os
import glob
import re

import numpy as np
import pandas as pd
import xarray as xr

# 앞 단계 모듈에서 좌표계 정의·저장 함수를 그대로 재사용 (중복 방지)
try:
    from sst_processing import make_crs_var, save_nc          # src 안에서 실행 시
except ImportError:                                            # 다른 위치에서 import 시
    from src.sst_processing import make_crs_var, save_nc

HOT_VAR = "hot_mask"   # 일별 파일의 변수: 1=고수온 / 0=비고수온 / NaN=육지·결측


# ---------------------------------------------------------------------------
# 파일 목록 / 한 장씩 읽기 (스트리밍용 — 수십 일치도 메모리 안전)
# ---------------------------------------------------------------------------
def list_hot_files(hot_dir: str = "data/results/sst_analysis/sst_over28") -> list:
    """폴더 안의 _HOT*.nc 파일을 '파일명 속 날짜' 순으로 정렬해 돌려준다."""
    paths = glob.glob(os.path.join(hot_dir, "*_HOT*.nc"))
    if not paths:
        raise FileNotFoundError(
            f"고수온 파일(_HOT*.nc)을 찾지 못했습니다: {hot_dir}\n"
            f"  → 먼저 sst_processing.py 로 일별 고수온 파일을 만들어 주세요."
        )

    def datekey(p):
        m = re.search(r"(\d{8})", os.path.basename(p))   # ..._U20250801_... → 20250801
        return m.group(1) if m else os.path.basename(p)

    return sorted(paths, key=datekey)


def grid_from_file(path: str):
    """파일에서 (lat, lon) 좌표(DataArray)를 읽어 돌려준다."""
    ds = xr.open_dataset(path, decode_timedelta=False)
    lat, lon = ds["lat"].load(), ds["lon"].load()
    ds.close()
    return lat, lon


def read_hot_2d(path: str, var: str = HOT_VAR):
    """파일 1장에서 (날짜time, 2D배열 lat×lon) 을 읽어 돌려준다. (한 장씩 = 메모리 절약)"""
    ds = xr.open_dataset(path, decode_timedelta=False)
    if var not in ds:
        ds.close()
        raise KeyError(f"'{var}' 변수가 없습니다: {path}")
    da = ds[var]
    if "time" in da.dims:
        da = da.isel(time=0)
    t = pd.to_datetime(ds["time"].values[0]) if "time" in ds else None
    arr = da.values.astype("float32")
    ds.close()
    return t, arr


# ---------------------------------------------------------------------------
# (작은 자료용) 한꺼번에 시간축으로 쌓기
# ---------------------------------------------------------------------------
def load_hot_stack(hot_dir: str = "data/results/sst_analysis/sst_over28", var: str = HOT_VAR) -> xr.DataArray:
    """폴더 안의 _HOT*.nc 들을 (time, lat, lon) 으로 쌓은 DataArray 로 돌려준다(날짜순)."""
    arrays = []
    for p in list_hot_files(hot_dir):
        ds = xr.open_dataset(p, decode_timedelta=False)
        arrays.append(ds[var].load())
        ds.close()
    return xr.concat(arrays, dim="time").sortby("time")


def period_tag(times):
    """시각 목록에서 (정렬된 DatetimeIndex, 'YYYYMMDD_YYYYMMDD' 태그) 를 돌려준다."""
    times = pd.to_datetime(pd.Index(times)).sort_values()
    tag = f"{times.min():%Y%m%d}_{times.max():%Y%m%d}"
    return times, tag


# ---------------------------------------------------------------------------
# 2D 결과들을 좌표·CRS·기간메타와 함께 Dataset 으로 포장
# ---------------------------------------------------------------------------
def wrap_2d(lat, lon, times, var_dict: dict, title: str,
            extra_attrs: dict = None) -> xr.Dataset:
    """{변수명: (2D배열, 속성dict)} 묶음을 lat/lon 좌표·CRS 와 함께 Dataset 으로 만든다.

    lat, lon : 좌표(DataArray 또는 배열)
    times    : 분석에 쓴 날짜 목록 (기간 메타에 기록)
    """
    times, _ = period_tag(times)

    data_vars = {}
    for name, (arr, attrs) in var_dict.items():
        da = xr.DataArray(np.asarray(arr), dims=("lat", "lon"),
                          coords={"lat": np.asarray(lat), "lon": np.asarray(lon)})
        attrs = dict(attrs)
        attrs["grid_mapping"] = "crs"
        da.attrs = attrs
        data_vars[name] = da
    data_vars["crs"] = make_crs_var()

    out = xr.Dataset(data_vars)
    out.attrs = {
        "title": title,
        "Conventions": "CF-1.8",
        "geographic_crs_name": "WGS84, EPSG:4326",
        "high_sst_threshold_celsius": 28.0,
        "n_days_analyzed": int(len(times)),
        "time_coverage_start": times.min().strftime("%Y-%m-%d"),
        "time_coverage_end": times.max().strftime("%Y-%m-%d"),
        "source_dates": ", ".join(t.strftime("%Y-%m-%d") for t in times),
        "processed_by": "team-gvidia / sst_gridutil.py",
    }
    if extra_attrs:
        out.attrs.update(extra_attrs)

    out["lon"].attrs.setdefault("standard_name", "longitude")
    out["lon"].attrs.setdefault("units", "degrees_east")
    out["lat"].attrs.setdefault("standard_name", "latitude")
    out["lat"].attrs.setdefault("units", "degrees_north")
    return out


# ---------------------------------------------------------------------------
# 지도 PNG 저장 — Natural Earth 해안선 배경 위에 그림 (basemap 위임)
# ---------------------------------------------------------------------------
def save_map_png(ds: xr.Dataset, var: str, out_png: str, title: str,
                 cmap: str = "YlOrRd", label: str = "", vmin=None, vmax=None) -> str:
    """Dataset 의 2D 변수 하나를 해안선 배경 지도 PNG 로 저장한다."""
    try:
        from basemap import plot_grid_map
    except ImportError:
        from src.basemap import plot_grid_map
    return plot_grid_map(ds[var].values, ds["lon"].values, ds["lat"].values,
                         out_png, title=title, cmap=cmap, label=label,
                         vmin=vmin, vmax=vmax)
