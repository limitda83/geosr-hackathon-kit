# -*- coding: utf-8 -*-
"""
sst_processing.py — 해수면온도(SST) NC 파일 전처리 & 고수온 격자 추출 (핵심 모듈)

이 파일이 하는 일 (큰 그림):
  1) 일별 SST NC 파일을 읽는다. (xarray + netCDF4)
  2) 전처리: 튐값 제거(0~40℃ 밖은 결측 처리) + 좌표계(EPSG:4326) 메타 명시.   → 요구사항3
  3) 28℃ 이상의 '고수온' 격자만 남기고 나머지는 결측(NaN)으로 만든다.        → 요구사항4
  4) 결과를 새 NC 파일로 저장한다. (격자 크기는 그대로 유지 → 다일 누적 분석에 그대로 사용)

초보자 안내:
  - 함수 process_file(in_path, out_dir) 하나만 알면 됩니다. 새 NC 경로를 돌려줍니다.
  - 폴더 통째로 처리하려면 process_dir(in_dir, out_dir) 를 쓰세요.
  - app.py(스트림릿 화면)가 이 함수들을 가져다 씁니다.
  - 이 파일만 단독 실행해도 됩니다(맨 아래 __main__): 폴더의 모든 .nc 를 처리.

입력 파일 형식(확인됨):
  - 변수 'sst' : dims (time, lat, lon), 단위 ℃, 육지/결측은 NaN
  - 좌표 lon(117~150°E), lat(20~53°N), 0.01° 간격, 3301×3301
  - 좌표계 : WGS84 / EPSG:4326 (이미 경위도 체계 → 재투영 불필요)

필요 패키지:  pip install xarray netCDF4 numpy
"""

import os
import re
import glob
from datetime import datetime, timezone

import numpy as np
import xarray as xr


# ---------------------------------------------------------------------------
# 공통 설정값 (한 곳에서 관리)
# ---------------------------------------------------------------------------

# 고수온 기준 온도(℃). 이 값 이상인 격자만 추출한다. (요구사항4)
HIGH_SST_THRESHOLD = 28.0

# 유효 온도 범위(℃). 이 범위 밖은 '튐값'으로 보고 결측 처리한다. (요구사항3)
VALID_MIN = 0.0
VALID_MAX = 40.0

# SST 변수 이름 후보 (파일마다 이름이 다를 수 있어 자동 탐색)
SST_NAME_CANDIDATES = ["sst", "SST", "sea_surface_temperature", "analysed_sst", "temp"]

# WGS84(EPSG:4326) 좌표계 정의 (QGIS 등에서 인식되도록 grid_mapping 변수로 심는다)
WGS84_WKT = (
    'GEOGCS["WGS 84",DATUM["WGS_1984",'
    'SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],'
    'AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],'
    'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],'
    'AUTHORITY["EPSG","4326"]]'
)


# ---------------------------------------------------------------------------
# 1) 파일 읽기 + SST 변수 찾기
# ---------------------------------------------------------------------------
def open_sst(path: str):
    """NC 파일을 열어 (Dataset, sst변수이름) 을 돌려준다.

    변수 이름이 'sst' 가 아닐 수도 있어 후보를 차례로 찾는다.
    못 찾으면 '온도처럼 보이는' 첫 2D 이상 변수를 쓴다.
    """
    ds = xr.open_dataset(path, decode_timedelta=False)

    # (1) 알려진 후보 이름부터 확인
    for name in SST_NAME_CANDIDATES:
        if name in ds.data_vars:
            return ds, name

    # (2) 후보가 없으면 2차원 이상인 첫 변수를 SST 로 간주
    for name, var in ds.data_vars.items():
        if var.ndim >= 2:
            return ds, name

    ds.close()
    raise ValueError(f"SST 로 쓸 만한 변수를 찾지 못했습니다: {path}")


# ---------------------------------------------------------------------------
# 2) 좌표계(EPSG:4326) 메타를 심는 grid_mapping 변수 만들기
# ---------------------------------------------------------------------------
def make_crs_var():
    """EPSG:4326(WGS84) 좌표계 정의를 담은 스칼라 DataArray 를 만든다.

    이 변수를 데이터셋에 넣고, SST 변수의 grid_mapping 속성으로 가리키게 하면
    QGIS·GDAL·rioxarray 등이 좌표계를 정확히 인식한다.
    """
    return xr.DataArray(
        np.int32(0),
        attrs={
            "grid_mapping_name": "latitude_longitude",
            "long_name": "CRS definition",
            "longitude_of_prime_meridian": 0.0,
            "semi_major_axis": 6378137.0,
            "inverse_flattening": 298.257223563,
            "horizontal_datum_name": "WGS84",
            "reference_ellipsoid_name": "WGS 84",
            "geographic_crs_name": "WGS 84",
            "epsg_code": "EPSG:4326",
            "spatial_ref": WGS84_WKT,
            "crs_wkt": WGS84_WKT,
        },
    )


# ---------------------------------------------------------------------------
# 3) 전처리: 튐값 제거 (요구사항3)
# ---------------------------------------------------------------------------
def clean_sst(sst, valid_min: float = VALID_MIN, valid_max: float = VALID_MAX):
    """유효 범위(0~40℃) 밖의 값을 결측(NaN)으로 만든다. (튐값 제거)

    반환: 정리된 SST DataArray (원본 격자 크기 그대로).
    """
    # where 조건을 만족하지 않는 곳은 NaN 으로 바뀐다.
    return sst.where((sst >= valid_min) & (sst <= valid_max))


# ---------------------------------------------------------------------------
# 4) 고수온(≥28℃) 격자만 추출 (요구사항4)
# ---------------------------------------------------------------------------
def extract_high_sst(ds: xr.Dataset, sst_name: str,
                     threshold: float = HIGH_SST_THRESHOLD,
                     valid_min: float = VALID_MIN,
                     valid_max: float = VALID_MAX) -> xr.Dataset:
    """전처리 후 28℃ 이상 격자만 남긴 새 Dataset 을 만든다.

    만들어지는 변수:
      - sst_hot  : 28℃ 이상인 곳의 '실제 온도', 그 외는 NaN  (float32)
      - hot_mask : 고수온=1.0 / 유효하지만 28℃ 미만=0.0 / 육지·결측=NaN (float32)
                   → 요구사항5에서 '며칠이나 28℃ 이상이었나' 누적 계산에 바로 사용
      - crs      : EPSG:4326 좌표계 정의 (grid_mapping)

    격자 크기(lat×lon)는 입력과 똑같이 유지한다(같은 위치끼리 누적하기 위함).
    """
    sst = ds[sst_name]

    # (1) 튐값 제거 → 유효한 바다 격자만 남음
    sst_clean = clean_sst(sst, valid_min, valid_max)

    # (2) 유효 격자 여부 (바다=값 있음, 육지/결측=NaN)
    valid = np.isfinite(sst_clean)

    # (3) 고수온 여부 (유효하면서 28℃ 이상)
    is_hot = valid & (sst_clean >= threshold)

    # (4) 28℃ 이상의 실제 온도만 남기기 (그 외 NaN)
    sst_hot = sst_clean.where(is_hot).astype("float32")
    sst_hot.attrs = {
        "long_name": f"sea surface temperature (>= {threshold} C only)",
        "units": "celsius",
        "high_sst_threshold": threshold,
        "grid_mapping": "crs",
        "comment": f"{threshold}℃ 미만 및 0~40℃ 밖 값은 결측(NaN) 처리됨",
    }

    # (5) 고수온 마스크: 1.0(고수온) / 0.0(유효·비고수온) / NaN(육지·결측)
    hot_mask = xr.where(valid, is_hot.astype("float32"), np.nan).astype("float32")
    hot_mask.attrs = {
        "long_name": f"high SST mask (1 if SST >= {threshold} C, else 0; NaN over land/missing)",
        "units": "1",
        "high_sst_threshold": threshold,
        "flag_values": "0, 1",
        "flag_meanings": "below_threshold high_sst",
        "grid_mapping": "crs",
    }

    # (6) 새 Dataset 조립 (좌표는 그대로 물려받음)
    out = xr.Dataset(
        {"sst_hot": sst_hot, "hot_mask": hot_mask, "crs": make_crs_var()},
        coords={c: ds.coords[c] for c in ds.coords},
    )

    # (7) 좌표 메타 보강 (혹시 비어 있으면 표준값 채움)
    if "lon" in out.coords:
        out["lon"].attrs.setdefault("standard_name", "longitude")
        out["lon"].attrs.setdefault("units", "degrees_east")
        out["lon"].attrs.setdefault("axis", "X")
    if "lat" in out.coords:
        out["lat"].attrs.setdefault("standard_name", "latitude")
        out["lat"].attrs.setdefault("units", "degrees_north")
        out["lat"].attrs.setdefault("axis", "Y")

    # (8) 전역 속성: 원본 메타 유지 + 처리 이력 추가 (증빙·재현성용)
    out.attrs = dict(ds.attrs)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out.attrs.update({
        "title": "고수온 격자 추출 결과 (SST >= %g C)" % threshold,
        "processing_level": "L4-derived",
        "high_sst_threshold_celsius": threshold,
        "valid_range_celsius": f"{valid_min} ~ {valid_max}",
        "Conventions": "CF-1.8",
        "geographic_crs_name": "WGS84, EPSG:4326",
        "processing_history": (
            f"{stamp} sst_processing.extract_high_sst: "
            f"튐값 제거({valid_min}~{valid_max}℃) 후 {threshold}℃ 이상 격자 추출"
        ),
        "processed_by": "team-gvidia / sst_processing.py",
    })

    return out


# ---------------------------------------------------------------------------
# 5) NC 파일로 저장 (압축 적용)
# ---------------------------------------------------------------------------
def save_nc(ds: xr.Dataset, out_path: str) -> str:
    """Dataset 을 NetCDF4 파일로 저장한다. (zlib 압축으로 용량 절감)

    반환값: 저장한 파일 경로.
    """
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    # 데이터 변수에 압축/결측값 인코딩 지정
    encoding = {}
    for name, var in ds.data_vars.items():
        if np.issubdtype(var.dtype, np.floating):
            encoding[name] = {"zlib": True, "complevel": 4,
                              "_FillValue": np.float32(np.nan)}
        elif var.ndim >= 1:
            encoding[name] = {"zlib": True, "complevel": 4}

    ds.to_netcdf(out_path, format="NETCDF4", encoding=encoding)
    return out_path


# ---------------------------------------------------------------------------
# 6) 파일 1개 처리: 읽기 → 추출 → 저장 (한 번에)
# ---------------------------------------------------------------------------
def process_file(in_path: str, out_dir: str = "data/results/sst_analysis/sst_over28",
                 threshold: float = HIGH_SST_THRESHOLD,
                 make_image: bool = False, img_dir: str = None,
                 img_vmin: float = 28.0, img_vmax: float = 33.0) -> dict:
    """SST NC 파일 1개를 고수온 추출하여 새 NC 로 저장한다.

    make_image=True 이면 추출한 고수온영역(sst_hot)을 Natural Earth 해안선 배경 위에
    지도 PNG 로도 저장한다(img_dir, 기본 out_dir/img).

    반환값(dict): 처리 요약
        in_path, out_path, img_path, hot_count(고수온 격자 수),
        valid_count(유효 바다 격자 수), hot_ratio(고수온 비율), max_sst
    """
    ds, sst_name = open_sst(in_path)
    try:
        out = extract_high_sst(ds, sst_name, threshold=threshold)

        # 요약 통계 계산 (로그·검증용)
        mask = out["hot_mask"]
        valid_count = int(np.isfinite(mask).sum())
        hot_count = int((mask == 1.0).sum())
        hot_vals = out["sst_hot"].values
        finite_hot = hot_vals[np.isfinite(hot_vals)]
        max_sst = float(np.nanmax(ds[sst_name].values)) if ds[sst_name].size else float("nan")

        # 출력 파일명: 입력명 뒤에 _HOT{threshold} 를 붙인다
        base = os.path.splitext(os.path.basename(in_path))[0]
        out_name = f"{base}_HOT{int(threshold)}.nc"
        out_path = os.path.join(out_dir, out_name)
        save_nc(out, out_path)

        # (선택) 고수온영역 이미지: Natural Earth 해안선 배경 위에 sst_hot 을 그림
        img_path = ""
        if make_image:
            try:
                from basemap import plot_grid_map
            except ImportError:
                from src.basemap import plot_grid_map
            img_dir = img_dir or os.path.join(out_dir, "img")
            img_path = os.path.join(img_dir, f"{base}_HOT{int(threshold)}.png")
            # 파일명 끝 8자리 날짜(YYYYMMDD)를 제목에 표기
            m = re.search(r"(\d{8})", base)
            date_txt = (f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
                        if m else base)
            field = out["sst_hot"]
            if "time" in field.dims:
                field = field.isel(time=0)
            plot_grid_map(field.values, out["lon"].values, out["lat"].values,
                          img_path,
                          title=f"High-SST area (>= {int(threshold)}C)  {date_txt}",
                          cmap="turbo", label=f"SST (>= {int(threshold)} C)",
                          vmin=img_vmin, vmax=img_vmax)

        return {
            "in_path": in_path,
            "out_path": out_path,
            "img_path": img_path,
            "valid_count": valid_count,
            "hot_count": hot_count,
            "hot_ratio": (hot_count / valid_count) if valid_count else 0.0,
            "max_sst": max_sst,
            "hot_min": float(finite_hot.min()) if finite_hot.size else float("nan"),
            "hot_max": float(finite_hot.max()) if finite_hot.size else float("nan"),
        }
    finally:
        ds.close()


# ---------------------------------------------------------------------------
# 7) 폴더 통째로 처리: 안의 모든 .nc 를 고수온 추출
# ---------------------------------------------------------------------------
def process_dir(in_dir: str, out_dir: str = "data/results/sst_analysis/sst_over28",
                threshold: float = HIGH_SST_THRESHOLD,
                pattern: str = "*.nc", make_image: bool = False,
                img_dir: str = None, progress: bool = False) -> list:
    """in_dir 안의 모든 NC 파일을 처리한다. 결과 요약 dict 리스트를 돌려준다.

    이미 처리된 출력(_HOT*.nc)은 건너뛴다.
    make_image=True 이면 각 파일의 고수온영역 지도 PNG 도 함께 만든다.
    """
    paths = sorted(glob.glob(os.path.join(in_dir, pattern)))
    paths = [p for p in paths if "_HOT" not in os.path.basename(p)]

    results = []
    for i, p in enumerate(paths, start=1):
        if progress:
            print(f"  ({i}/{len(paths)}) {os.path.basename(p)}", flush=True)
        try:
            results.append(process_file(p, out_dir=out_dir, threshold=threshold,
                                        make_image=make_image, img_dir=img_dir))
        except Exception as exc:
            results.append({"in_path": p, "out_path": "", "error": str(exc)})
    return results


# ---------------------------------------------------------------------------
# 단독 실행(CLI): 폴더(또는 파일)를 받아 고수온 NC 를 만든다
#   사용법:
#     python sst_processing.py                       # 현재 폴더의 *.nc 처리
#     python sst_processing.py 입력폴더 출력폴더       # 폴더 지정
#     python sst_processing.py 파일.nc 출력폴더        # 파일 1개 지정
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    in_arg = sys.argv[1] if len(sys.argv) > 1 else "."
    out_arg = sys.argv[2] if len(sys.argv) > 2 else "data/results/sst_analysis/sst_over28"
    thr = float(sys.argv[3]) if len(sys.argv) > 3 else HIGH_SST_THRESHOLD

    print(f"=== 고수온(≥{thr}℃) 격자 추출 ===")
    print(f"입력: {in_arg}  →  출력 폴더: {out_arg}\n")

    if os.path.isdir(in_arg):
        summary = process_dir(in_arg, out_dir=out_arg, threshold=thr)
    else:
        summary = [process_file(in_arg, out_dir=out_arg, threshold=thr)]

    ok = 0
    for r in summary:
        if r.get("error"):
            print(f"  [실패] {os.path.basename(r['in_path'])}: {r['error']}")
            continue
        ok += 1
        print(f"  [완료] {os.path.basename(r['in_path'])}")
        print(f"         → {r['out_path']}")
        print(f"         고수온 격자 {r['hot_count']:,}개 / 유효 {r['valid_count']:,}개 "
              f"({r['hot_ratio']*100:.1f}%), 추출온도 {r['hot_min']:.2f}~{r['hot_max']:.2f}℃")

    print(f"\n총 {ok}/{len(summary)}개 파일 처리 완료. 출력 폴더: {out_arg}")
