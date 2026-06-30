# -*- coding: utf-8 -*-
"""
hot_lowsal.py — 고수온(SST≥28℃) ∩ 저염분(LSS 속성=1) 공통지역 추출

무엇을 하나 (큰 그림):
  1) SST 일자별 NC(1km, data/input/khoa_sst) 에서 28℃ 이상 '고수온' 격자를 본다.
  2) LSS 일자별 NC(250m, data/input/lss) 의 '저염분 플래그'를 1km(SST) 격자로 재가공한다.
       - LSS 변수 SSS 는 연속 염분이 아니라 '범주 플래그' 다(실측 확인):
             1 = 저염분(28 psu 미만)   2 = 정상   NaN = 육지/결측
       - 따라서 저염분 = (SSS == 1).
       - 250m → 1km 재가공: 값을 '평균'하지 않고, 각 1km 칸 안 250m 칸들의
         속성을 세어 다수인 쪽의 '속성값(1 또는 2)'을 그 칸 값으로 정한다(다수결/최빈값).
         저염분 = 재가공된 속성값(lss_class) == 1 인 칸.
  3) 같은 1km 격자에서  고수온(SST≥28)  AND  저염분(재가공 플래그=1)  인
     공통지역(hotlowsal)을 추출해 NC·CSV·지도PNG 로 저장한다.

좌표 주의(실측):
  - SST : lat 20~53N '오름차순', lon 117~150E, 0.01°(~1km), 3301×3301, 변수 sst(℃)
  - LSS : lat 36~28N '내림차순', lon 119~129E, ~250m, 2667×3333, 변수 SSS(플래그 1/2)
  → LSS 가 덮는 영역(대략 28~36N/119~129E)으로 SST 를 잘라 같은 격자에서 비교한다.

기존 모듈 재사용:
  - sst_processing : open_sst, clean_sst, make_crs_var, save_nc
  - sst_gridutil   : wrap_2d, save_map_png

사용 예 (NC·지도PNG·CSV 가 함께 만들어짐):
  python src/hot_lowsal.py                                  # 7/1~8/31 전체
  python src/hot_lowsal.py --start 2025-07-01 --end 2025-07-05
  python src/hot_lowsal.py --no-image                        # 지도 PNG 없이 NC/CSV 만
"""

import os
import re
import glob
import argparse
from datetime import date, datetime

import numpy as np
import xarray as xr

try:                                  # src 안에서 실행할 때
    from sst_processing import open_sst, clean_sst, save_nc
    from sst_gridutil import wrap_2d, save_map_png
except ImportError:                   # 저장소 루트에서 실행할 때
    from src.sst_processing import open_sst, clean_sst, save_nc
    from src.sst_gridutil import wrap_2d, save_map_png

# ---------------------------------------------------------------------------
# 설정값
# ---------------------------------------------------------------------------
SST_THRESHOLD = 28.0       # 고수온 기준(℃ 이상)
LOWSAL_FLAG = 1            # LSS 속성: 1=저염분 / 2=정상
SST_NAME = "sst"


def _date_from_name(path: str) -> str:
    """파일명에서 8자리 날짜(YYYYMMDD)를 뽑는다. 없으면 ''"""
    m = re.search(r"(\d{8})", os.path.basename(path))
    return m.group(1) if m else ""


def pair_files(sst_dir: str, lss_dir: str, start: date, end: date) -> list:
    """SST·LSS 폴더에서 '같은 날짜'끼리 (날짜, sst경로, lss경로) 로 묶는다."""
    def index(d):
        out = {}
        for p in glob.glob(os.path.join(d, "*.nc")):
            ymd = _date_from_name(p)
            if ymd:
                out[ymd] = p
        return out

    sst_idx, lss_idx = index(sst_dir), index(lss_dir)
    pairs = []
    for ymd in sorted(set(sst_idx) & set(lss_idx)):
        dt = datetime.strptime(ymd, "%Y%m%d").date()
        if start <= dt <= end:
            pairs.append((dt, sst_idx[ymd], lss_idx[ymd]))
    return pairs


# ---------------------------------------------------------------------------
# 1) SST 읽기 (해당 영역으로 자르기는 호출부에서)
# ---------------------------------------------------------------------------
def load_sst_2d(sst_path: str):
    """SST 파일에서 (정리된 sst 2D DataArray[lat,lon], lat, lon) 를 돌려준다."""
    ds, name = open_sst(sst_path)
    sst = clean_sst(ds[name])               # 0~40℃ 밖 튐값은 NaN
    if "time" in sst.dims:
        sst = sst.isel(time=0)
    sst = sst.load()
    lat = ds["lat"].load()
    lon = ds["lon"].load()
    ds.close()
    return sst, lat, lon


# ---------------------------------------------------------------------------
# 2) LSS 저염분 플래그를 목표(SST) 격자로 면적집계(250m → 1km 재가공)
# ---------------------------------------------------------------------------
def _bin_edges(centers: np.ndarray) -> np.ndarray:
    """격자 '중심좌표'(오름차순)에서 칸 '경계'를 만든다. (길이 n+1)"""
    c = np.asarray(centers, dtype="float64")
    mid = (c[:-1] + c[1:]) / 2.0
    first = c[0] - (mid[0] - c[0])
    last = c[-1] + (c[-1] - mid[-1])
    return np.concatenate([[first], mid, [last]])


def regrid_lss_class(lss_lat, lss_lon, sss, target_lat, target_lon,
                     lowsal_flag: int = LOWSAL_FLAG):
    """LSS 속성(1=저염분/2=정상)을 목표 1km 격자로 '다수결'로 재가공한다.

    ※ 값을 '평균'하지 않는다. 각 1km 칸 안에 들어온 250m 칸들의 속성을 세어,
      더 많은 쪽의 '속성값(1 또는 2)'을 그 칸의 값으로 정한다(최빈값/다수결).
        - n1 = 저염분(1) 칸 수,  n2 = 정상(2) 칸 수
        - 칸 값 = 1 (n1 >= n2; 동수는 저염분 우선) / 2 (n2 > n1) / NaN(자료없음)
    반환: (lss_class 2D[값 1 또는 2 또는 NaN], count 2D[유효 250m칸 수])
    """
    tlat = np.asarray(target_lat, dtype="float64")
    tlon = np.asarray(target_lon, dtype="float64")
    nlat, nlon = tlat.size, tlon.size

    late = _bin_edges(tlat)
    lone = _bin_edges(tlon)

    # LSS 각 행/열 중심이 어느 목표 칸에 속하는지 (0..n-1, 벗어나면 -1 또는 n)
    ri = np.digitize(np.asarray(lss_lat, "float64"), late) - 1   # 길이 = LSS lat 수
    ci = np.digitize(np.asarray(lss_lon, "float64"), lone) - 1   # 길이 = LSS lon 수

    sss = np.asarray(sss)
    valid = np.isfinite(sss) & ((sss == 1) | (sss == 2))   # 유효 = 1 또는 2
    is1 = (sss == lowsal_flag)                              # 저염분(1)

    # 2D 브로드캐스트로 목표 칸 선형인덱스 만들기
    Ri = ri[:, None]
    Ci = ci[None, :]
    inside = (Ri >= 0) & (Ri < nlat) & (Ci >= 0) & (Ci < nlon)
    good = valid & inside

    lin = (Ri * nlon + Ci)             # (nlat_lss, nlon_lss)
    lin_good = lin[good]
    nbins = nlat * nlon
    cnt = np.bincount(lin_good, minlength=nbins).astype("float64")          # 유효 칸 수
    n1 = np.bincount(lin_good, weights=is1[good].astype("float64"),
                     minlength=nbins)                                       # 저염분(1) 칸 수
    n2 = cnt - n1                                                           # 정상(2) 칸 수

    # 다수결: 평균이 아니라 '속성값 1 또는 2'를 그대로 부여
    lss_class = np.full(nbins, np.nan)
    has = cnt > 0
    lss_class[has] = np.where(n1[has] >= n2[has], 1.0, 2.0)
    return lss_class.reshape(nlat, nlon), cnt.reshape(nlat, nlon)


# ---------------------------------------------------------------------------
# 3) 하루치 교집합(고수온 ∩ 저염분) 추출
# ---------------------------------------------------------------------------
def intersect_day(dt: date, sst_path: str, lss_path: str, out_dir: str,
                  sst_threshold: float = SST_THRESHOLD,
                  make_image: bool = True) -> dict:
    """하루치 SST·LSS 를 받아 공통지역(hotlowsal)을 추출·저장하고 요약을 돌려준다."""
    sst, lat, lon = load_sst_2d(sst_path)

    # LSS 좌표/값 읽기
    dl = xr.open_dataset(lss_path, decode_timedelta=False)
    lss_lat = dl["latitude"].values
    lss_lon = dl["longitude"].values
    sss = dl["SSS"].values
    dl.close()

    # LSS 가 덮는 영역으로 SST 를 자른다 (이 영역 밖은 염분자료가 없음)
    s, n = float(np.min(lss_lat)), float(np.max(lss_lat))
    w, e = float(np.min(lss_lon)), float(np.max(lss_lon))
    sst_sub = sst.sel(lat=slice(s, n), lon=slice(w, e))      # SST lat/lon 오름차순
    tlat = sst_sub["lat"].values
    tlon = sst_sub["lon"].values

    # 250m → 1km 재가공 (다수결로 속성값 1/2 결정 — 평균하지 않음)
    lss_class, cnt = regrid_lss_class(lss_lat, lss_lon, sss, tlat, tlon)

    sst_arr = sst_sub.values.astype("float32")              # (lat, lon)
    sst_valid = np.isfinite(sst_arr)                        # 바다(유효 SST)
    lss_valid = cnt > 0                                     # 염분자료 있는 칸

    is_hot = sst_valid & (sst_arr >= sst_threshold)
    is_lowsal = lss_valid & (lss_class == LOWSAL_FLAG)      # 재가공 속성값이 1이면 저염분
    both = is_hot & is_lowsal

    # 마스크 만들기: 1=해당 / 0=유효하나 비해당 / NaN=자료없음
    def mask01(cond, valid):
        return np.where(valid, cond.astype("float32"), np.nan).astype("float32")

    hot_mask = mask01(is_hot, sst_valid)
    lowsal_mask = mask01(is_lowsal, lss_valid)
    common_valid = sst_valid & lss_valid                   # 둘 다 자료 있는 칸만 판정
    hotlowsal_mask = mask01(both, common_valid)

    # 공통지역의 '실제 수온'(보기/검증용): both 인 곳만 온도, 그 외 NaN
    sst_common = np.where(both, sst_arr, np.nan).astype("float32")

    # 요약 통계
    hot_count = int(np.nansum(hot_mask == 1))
    lowsal_count = int(np.nansum(lowsal_mask == 1))
    both_count = int(np.nansum(hotlowsal_mask == 1))
    summary = {
        "date": dt.isoformat(),
        "grid": f"{tlat.size}x{tlon.size}",
        "hot_count": hot_count,
        "lowsal_count": lowsal_count,
        "both_count": both_count,
        "out_nc": "", "out_png": "",
    }

    # --- NC 저장 (wrap_2d 로 좌표·CRS·기간메타 포함) ---
    os.makedirs(out_dir, exist_ok=True)
    var_dict = {
        "sst": (sst_arr, {"long_name": "sea surface temperature", "units": "celsius"}),
        "lss_class": (lss_class.astype("float32"),
                      {"long_name": "regridded LSS attribute at 1km grid by majority vote (1=low-salinity, 2=normal)",
                       "units": "1", "flag_values": "1, 2",
                       "flag_meanings": "low_salinity normal"}),
        "hot_mask": (hot_mask,
                     {"long_name": f"high SST mask (1 if SST>={sst_threshold}C)",
                      "units": "1", "flag_values": "0, 1",
                      "flag_meanings": "not_high high_sst"}),
        "lowsal_mask": (lowsal_mask,
                        {"long_name": "low salinity mask (1 if regridded LSS class == 1)",
                         "units": "1", "flag_values": "0, 1",
                         "flag_meanings": "not_lowsal lowsal"}),
        "hotlowsal_mask": (hotlowsal_mask,
                           {"long_name": "high-SST AND low-salinity common area (1=common)",
                            "units": "1", "flag_values": "0, 1",
                            "flag_meanings": "not_common common"}),
        "sst_common": (sst_common,
                       {"long_name": "SST over high-SST & low-salinity common area only",
                        "units": "celsius"}),
    }
    title = f"고수온(≥{sst_threshold}℃) ∩ 저염분(LSS=1) 공통지역  {dt:%Y-%m-%d}"
    out = wrap_2d(tlat, tlon, [datetime(dt.year, dt.month, dt.day)], var_dict, title,
                  extra_attrs={
                      "low_salinity_definition": "regridded LSS class == 1 (=< 28 psu)",
                      "regrid_method": "LSS 250m -> SST 1km majority vote (class 1 or 2; NOT averaged)",
                      "processed_by": "team-gvidia / hot_lowsal.py",
                  })
    base = f"HOTLOWSAL_{dt:%Y%m%d}"
    out_nc = os.path.join(out_dir, base + ".nc")
    save_nc(out, out_nc)
    summary["out_nc"] = out_nc

    # --- 지도 PNG (공통지역 수온) ---
    if make_image:
        img_dir = os.path.join(out_dir, "area_all")
        os.makedirs(img_dir, exist_ok=True)
        out_png = os.path.join(img_dir, base + ".png")
        try:
            save_map_png(out, "sst_common", out_png,
                         title=f"High-SST & Low-salinity  {dt:%Y-%m-%d}",
                         cmap="turbo", label="SST (℃) in common area",
                         vmin=28.0, vmax=31.0)
            summary["out_png"] = out_png
        except Exception as exc:           # 지도 실패해도 본 결과는 유지
            summary["out_png"] = f"(지도 실패: {exc})"

    return summary


# ---------------------------------------------------------------------------
# 4) 기간 전체 실행
# ---------------------------------------------------------------------------
def run(sst_dir: str, lss_dir: str, out_dir: str, start: date, end: date,
        sst_threshold: float = SST_THRESHOLD,
        make_image: bool = True) -> list:
    pairs = pair_files(sst_dir, lss_dir, start, end)
    print("=== 고수온 ∩ 저염분 공통지역 추출 ===")
    print(f"기간: {start} ~ {end}  |  쌍(둘 다 있는 날): {len(pairs)}일")
    print(f"기준: SST≥{sst_threshold}℃, 저염분=재가공 LSS속성값 1 (250m→1km 다수결)")
    print(f"저장: {os.path.abspath(out_dir)}  (NC + 지도PNG)\n")

    rows = []
    for i, (dt, sp, lp) in enumerate(pairs, 1):
        try:
            s = intersect_day(dt, sp, lp, out_dir, sst_threshold, make_image)
            print(f"  ({i}/{len(pairs)}) {dt}  고수온 {s['hot_count']:,} / "
                  f"저염분 {s['lowsal_count']:,} / 공통 {s['both_count']:,}")
            rows.append(s)
        except Exception as exc:
            print(f"  ({i}/{len(pairs)}) {dt}  [실패] {exc}")
            rows.append({"date": dt.isoformat(), "error": str(exc)})

    # CSV(일별·요약)는 생성하지 않는다 — NC·지도 PNG 만 산출
    print(f"\n완료: {len(rows)}일 처리 (NC + 지도 PNG).")
    return rows


# ---------------------------------------------------------------------------
# (추가) 지정 영역만 잘라 공통지역 지도 PNG 생성  (예: south_sea)
# ---------------------------------------------------------------------------
def region_image_day(dt: date, sst_path: str, lss_path: str, out_dir: str, bbox,
                     img_subdir: str = "south_sea", sst_threshold: float = SST_THRESHOLD) -> dict:
    """하루치 공통지역(고수온∩저염분)을 지정 영역(bbox)만 잘라 지도 PNG 로 저장.

    bbox = (south, north, west, east). SST 격자를 그 영역으로 잘라 같은 칸에서
    저염분(다수결 1)·고수온(≥기준)을 다시 판정하므로, 지도 범위가 정확히 bbox 가 된다.
    저염분 자료가 없는 칸(예: 129°E 동쪽)은 공통 불가 → 빈칸으로 표시된다.
    """
    s, n, w, e = bbox
    sst, lat, lon = load_sst_2d(sst_path)
    sst_sub = sst.sel(lat=slice(s, n), lon=slice(w, e))     # 영역이 곧 지도 범위
    tlat = sst_sub["lat"].values
    tlon = sst_sub["lon"].values

    dl = xr.open_dataset(lss_path, decode_timedelta=False)
    lss_lat = dl["latitude"].values
    lss_lon = dl["longitude"].values
    sss = dl["SSS"].values
    dl.close()

    lss_class, cnt = regrid_lss_class(lss_lat, lss_lon, sss, tlat, tlon)
    sst_arr = sst_sub.values.astype("float32")
    sst_valid = np.isfinite(sst_arr)
    is_hot = sst_valid & (sst_arr >= sst_threshold)
    is_lowsal = (cnt > 0) & (lss_class == LOWSAL_FLAG)     # 다수결 속성값 1 = 저염분
    both = is_hot & is_lowsal
    # 공통지역을 '단일 빨간색'으로 표시(수온 색상 범례 사용 안 함): 1=공통 / NaN=그 외
    common = np.where(both, 1.0, np.nan).astype("float32")

    img_dir = os.path.join(out_dir, img_subdir)
    os.makedirs(img_dir, exist_ok=True)
    out_png = os.path.join(img_dir, f"HOTLOWSAL_{dt:%Y%m%d}_region.png")
    try:
        from basemap import plot_grid_map
    except ImportError:
        from src.basemap import plot_grid_map
    from matplotlib.colors import ListedColormap
    plot_grid_map(common, tlon, tlat, out_png,
                  title=f"High-SST & Low-salinity  {dt:%Y-%m-%d}  ({s}~{n}N, {w}~{e}E)",
                  cmap=ListedColormap(["red"]), vmin=0, vmax=1, add_colorbar=False)
    return {"date": dt.isoformat(), "both_count": int(both.sum()), "out_png": out_png}


def run_region_images(sst_dir: str, lss_dir: str, out_dir: str, start: date, end: date,
                      bbox, img_subdir: str = "south_sea",
                      sst_threshold: float = SST_THRESHOLD) -> list:
    """기간 전체에 대해 지정 영역(bbox)만 잘라 공통지역 지도 PNG 를 생성한다."""
    pairs = pair_files(sst_dir, lss_dir, start, end)
    s, n, w, e = bbox
    img_dir = os.path.join(out_dir, img_subdir)
    print("=== (영역 한정) 고수온 ∩ 저염분 지도 생성 ===")
    print(f"영역: 위도 {s}~{n}, 경도 {w}~{e}  (저염분=재가공 LSS속성값 1)")
    print(f"기간: {start} ~ {end}  |  {len(pairs)}일  →  저장: {os.path.abspath(img_dir)}\n")
    rows = []
    for i, (dt, sp, lp) in enumerate(pairs, 1):
        try:
            r = region_image_day(dt, sp, lp, out_dir, bbox, img_subdir, sst_threshold)
            print(f"  ({i}/{len(pairs)}) {dt}  공통 {r['both_count']:,}칸  → {os.path.basename(r['out_png'])}")
            rows.append(r)
        except Exception as exc:
            print(f"  ({i}/{len(pairs)}) {dt}  [실패] {exc}")
            rows.append({"date": dt.isoformat(), "error": str(exc)})
    return rows


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="고수온(SST≥28℃) ∩ 저염분(LSS=1) 공통지역 추출")
    p.add_argument("--sst-dir", default="data/input/khoa_sst")
    p.add_argument("--lss-dir", default="data/input/lss")
    p.add_argument("--out", default="data/results/HS28NLS26")
    p.add_argument("--start", default="2025-07-01")
    p.add_argument("--end", default="2025-08-31")
    p.add_argument("--sst-threshold", type=float, default=SST_THRESHOLD)
    p.add_argument("--no-image", action="store_true", help="지도 PNG 생성 끄기(기본은 생성)")
    p.add_argument("--region-images", action="store_true",
                   help="지정 영역만 잘라 공통지역 지도(PNG)를 생성 (전체 NC 재처리 없이)")
    p.add_argument("--region", type=float, nargs=4, metavar=("S", "N", "W", "E"),
                   default=[33.7, 35.1, 125.2, 130.2],
                   help="영역 위경도: 남 북 서 동 (기본 33.7 35.1 125.2 130.2)")
    p.add_argument("--region-dir", default="south_sea", help="영역 이미지 저장 하위폴더명(기본 south_sea)")
    return p.parse_args(argv)


def main(argv=None):
    a = parse_args(argv)
    start, end = date.fromisoformat(a.start), date.fromisoformat(a.end)
    if a.region_images:
        run_region_images(a.sst_dir, a.lss_dir, a.out, start, end,
                          tuple(a.region), a.region_dir, a.sst_threshold)
    else:
        run(a.sst_dir, a.lss_dir, a.out, start, end,
            a.sst_threshold, make_image=not a.no_image)


if __name__ == "__main__":
    main()
