# -*- coding: utf-8 -*-
"""
basemap.py — Natural Earth 해안선(육지 폴리곤) 배경지도 + 격자 지도 그리기 공용 모듈

이 파일이 하는 일:
  - Natural Earth 10m 육지 폴리곤(ne_10m_land)을 읽어 지도 배경(해안선)으로 깔아준다.
  - 격자 자료(2D lat×lon)를 위경도 지도 PNG 로 그려준다. (해안선 폴리곤 위/아래로 합성)

왜 pyshp 인가:
  - GDAL/GEOS 없이도 셰이프파일(.shp)을 순수 파이썬으로 읽을 수 있어 설치가 가볍다.
  - 우리 자료는 이미 EPSG:4326(경위도)라서 별도 투영 변환 없이 그대로 겹쳐 그리면 정확히 맞는다.

자료 출처:
  Natural Earth (public domain) — github 미러(nvkelso/natural-earth-vector)에서 자동 내려받음.
"""

import os

import numpy as np

try:
    import shapefile  # pyshp
except ImportError as e:  # 안내 메시지
    raise ImportError("pyshp 가 필요합니다.  pip install pyshp") from e


DEFAULT_NE_DIR = "data/naturalearth"
LAND_NAME = "ne_10m_land"
NE_BASE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/10m_physical"

# 읽어둔 폴리곤을 재사용하기 위한 캐시 (파일 여러 장 그릴 때 셰이프파일을 반복해서 안 읽도록)
_CACHE = {}


# ---------------------------------------------------------------------------
# Natural Earth 육지 폴리곤 내려받기 (없으면 자동)
# ---------------------------------------------------------------------------
def ensure_naturalearth(ne_dir: str = DEFAULT_NE_DIR, name: str = LAND_NAME) -> str:
    """ne_10m_land.{shp,shx,dbf} 가 없으면 github 미러에서 내려받는다. .shp 경로 반환."""
    os.makedirs(ne_dir, exist_ok=True)
    shp = os.path.join(ne_dir, f"{name}.shp")
    need = [ext for ext in ("shp", "shx", "dbf")
            if not os.path.exists(os.path.join(ne_dir, f"{name}.{ext}"))]
    if need:
        import requests
        for ext in need:
            url = f"{NE_BASE_URL}/{name}.{ext}"
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            with open(os.path.join(ne_dir, f"{name}.{ext}"), "wb") as f:
                f.write(r.content)
    return shp


# ---------------------------------------------------------------------------
# 폴리곤(육지) 읽어 캐시에 올리기
# ---------------------------------------------------------------------------
def _load_shapes(ne_dir: str = DEFAULT_NE_DIR, name: str = LAND_NAME):
    """[(bbox, [ring(Nx2)…]), …] 형태로 육지 폴리곤들을 읽어 캐시한다."""
    shp = ensure_naturalearth(ne_dir, name)
    if shp in _CACHE:
        return _CACHE[shp]

    reader = shapefile.Reader(shp)
    shapes = []
    for sr in reader.iterShapes():
        bbox = tuple(sr.bbox)  # (xmin, ymin, xmax, ymax)
        pts = np.asarray(sr.points, dtype="float64")
        parts = list(sr.parts) + [len(pts)]
        rings = [pts[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]
        rings = [r for r in rings if len(r) >= 2]
        if rings:
            shapes.append((bbox, rings))
    reader.close()
    _CACHE[shp] = shapes
    return shapes


def _bbox_intersects(b, extent) -> bool:
    """폴리곤 bbox(xmin,ymin,xmax,ymax)가 지도 범위 extent(xmin,xmax,ymin,ymax)와 겹치나?"""
    xmin, ymin, xmax, ymax = b
    ex0, ex1, ey0, ey1 = extent
    return not (xmax < ex0 or xmin > ex1 or ymax < ey0 or ymin > ey1)


# ---------------------------------------------------------------------------
# 축(ax)에 해안선(육지 폴리곤) 배경 깔기
# ---------------------------------------------------------------------------
def add_coastline(ax, extent, ne_dir: str = DEFAULT_NE_DIR,
                  land_face: str = "#efeae1", coast_color: str = "#3a3a3a",
                  coast_lw: float = 0.6, fill_land: bool = True,
                  land_zorder: float = 0.0, coast_zorder: float = 2.5):
    """ax 에 Natural Earth 해안선 폴리곤을 그린다. (육지 채움 + 해안선 외곽선)

    extent = [lon_min, lon_max, lat_min, lat_max]
    """
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch
    from matplotlib.collections import LineCollection

    shapes = _load_shapes(ne_dir)
    segments = []     # 해안선(라인) 모음
    for bbox, rings in shapes:
        if not _bbox_intersects(bbox, extent):
            continue   # 화면 밖 폴리곤은 건너뜀(속도)

        # (1) 육지 채움: 한 폴리곤의 모든 링을 하나의 compound path 로 (구멍=호수 처리)
        if fill_land:
            verts, codes = [], []
            for ring in rings:
                verts.extend(ring.tolist())
                codes.append(Path.MOVETO)
                codes.extend([Path.LINETO] * (len(ring) - 1))
            patch = PathPatch(Path(verts, codes), facecolor=land_face,
                              edgecolor="none", zorder=land_zorder, antialiased=True)
            ax.add_patch(patch)

        # (2) 해안선(외곽선): 각 링을 선으로
        for ring in rings:
            segments.append(ring)

    if segments:
        lc = LineCollection(segments, colors=coast_color, linewidths=coast_lw,
                            zorder=coast_zorder)
        ax.add_collection(lc)

    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])


# ---------------------------------------------------------------------------
# 격자 자료 1장을 위경도 지도 PNG 로 (해안선 배경 합성)
# ---------------------------------------------------------------------------
def plot_grid_map(field, lon, lat, out_png: str, title: str,
                  cmap="YlOrRd", label: str = "",
                  vmin=None, vmax=None, ne_dir: str = DEFAULT_NE_DIR,
                  figsize=(9, 9), dpi: int = 110, add_colorbar: bool = True) -> str:
    """2D 격자(field, dims lat×lon)를 해안선 배경 위에 그려 PNG 로 저장한다.

    - 바다(값 있음)는 컬러맵, 육지/결측(NaN)은 투명 → 뒤의 Natural Earth 육지색이 보임
    - lat 오름차순이므로 origin='lower' (북쪽이 위)
    - cmap : 이름(str) 또는 Colormap 객체(예: 단색 ListedColormap) 모두 허용
    - add_colorbar=False 면 범례(컬러바)를 그리지 않음(단색 마스크 표시용)
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import Colormap

    lon = np.asarray(lon); lat = np.asarray(lat)
    extent = [float(lon.min()), float(lon.max()), float(lat.min()), float(lat.max())]
    arr = np.ma.masked_invalid(np.asarray(field))

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_facecolor("#eef5fb")             # 옅은 바다색 (값 없는 바다와 육지 구분용)

    cmap_obj = (cmap if isinstance(cmap, Colormap) else plt.get_cmap(cmap)).copy()
    cmap_obj.set_bad((0, 0, 0, 0))         # NaN(육지)은 '투명' → 배경 육지색이 비침

    im = ax.imshow(arr, origin="lower", extent=extent, cmap=cmap_obj,
                   vmin=vmin, vmax=vmax, zorder=1.0, interpolation="nearest")

    # 해안선 폴리곤 배경 (육지 채움은 raster 아래, 해안선 라인은 위)
    add_coastline(ax, extent, ne_dir=ne_dir)

    ax.set_aspect("equal")                  # 경위도 1:1 (PlateCarree)
    ax.set_title(title)
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    if add_colorbar:
        cb = fig.colorbar(im, ax=ax, shrink=0.82)
        cb.set_label(label or "")

    fig.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    fig.savefig(out_png, dpi=dpi)
    plt.close(fig)
    return out_png
