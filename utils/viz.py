import pandas as pd
import pydeck as pdk
import plotly.express as px
from pathlib import Path


# ── pydeck 공통 설정 ─────────────────────────────────────
_VIEW = pdk.ViewState(
    latitude=35.5,
    longitude=128.0,
    zoom=6.5,
    pitch=40,
    bearing=0,
)

_MAPSTYLE = "mapbox://styles/mapbox/dark-v10"

_TOOLTIP_STYLE = {
    "background": "#020d1a",
    "color": "#c8e6f0",
    "font-family": "Noto Sans KR, sans-serif",
    "border": "1px solid rgba(0,194,212,0.3)",
    "border-radius": "8px",
    "padding": "8px 12px",
    "font-size": "13px",
}


def _empty_deck() -> pdk.Deck:
    return pdk.Deck(layers=[], initial_view_state=_VIEW, map_style=_MAPSTYLE)


def make_frequency_map(freq_df: pd.DataFrame) -> pdk.Deck:
    """뉴스 빈도 기반 버블맵 (ScatterplotLayer)."""
    if freq_df.empty:
        return _empty_deck()

    df = freq_df.dropna(subset=["lat", "lon"]).copy()
    max_c = df["count"].max()
    df["radius"] = (df["count"] / max_c * 28000 + 6000).astype(int)
    df["alpha"]  = ((df["count"] / max_c) * 170 + 60).astype(int)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["lon", "lat"],
        get_radius="radius",
        get_fill_color="[0, 194, 212, alpha]",
        get_line_color=[0, 229, 255, 200],
        line_width_min_pixels=1,
        pickable=True,
        stroked=True,
    )

    return pdk.Deck(
        layers=[layer],
        initial_view_state=_VIEW,
        map_style=_MAPSTYLE,
        tooltip={
            "html": "<b>{location}</b><br/>뉴스 {count}건",
            "style": _TOOLTIP_STYLE,
        },
    )


def make_sst_heatmap(sst_df: pd.DataFrame, threshold: float = 28.0) -> pdk.Deck:
    """SST 히트맵 (HeatmapLayer) — 고수온 구간 강조."""
    if sst_df.empty:
        return _empty_deck()

    df = sst_df.dropna(subset=["lat", "lon", "sst"]).copy()
    df["weight"] = (df["sst"] - threshold).clip(lower=0) + 0.1

    layer = pdk.Layer(
        "HeatmapLayer",
        data=df,
        get_position=["lon", "lat"],
        get_weight="weight",
        aggregation="MEAN",
        color_range=[
            [0, 50, 80, 0],
            [0, 130, 160, 120],
            [0, 194, 212, 180],
            [255, 160, 0, 200],
            [255, 80, 0, 220],
            [255, 20, 20, 240],
        ],
        threshold=0.05,
        radius_pixels=40,
        pickable=False,
    )

    return pdk.Deck(
        layers=[layer],
        initial_view_state=_VIEW,
        map_style=_MAPSTYLE,
    )


def make_alert_bubble_map(alerts: list[dict], region_coords: dict | None = None) -> pdk.Deck:
    """경보/주의보 지역 버블맵."""
    if not alerts:
        return _empty_deck()

    rows = []
    for a in alerts:
        lat = a.get("lat") or (region_coords or {}).get(a["region"], (None, None))[0]
        lon = a.get("lon") or (region_coords or {}).get(a["region"], (None, None))[1]
        if lat is None or lon is None:
            continue
        is_alarm = a["level"] == "alarm"
        rows.append({
            "region":  a["region"],
            "lat":     lat,
            "lon":     lon,
            "streak":  a["current_streak"],
            "sst":     round(a.get("latest_sst") or 0, 1),
            "label":   "경보" if is_alarm else "주의보",
            "color":   [255, 40, 40, 200] if is_alarm else [255, 210, 0, 200],
            "radius":  max(18000, a["current_streak"] * 9000),
        })

    if not rows:
        return _empty_deck()

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=pd.DataFrame(rows),
        get_position=["lon", "lat"],
        get_radius="radius",
        get_fill_color="color",
        get_line_color=[255, 255, 255, 60],
        line_width_min_pixels=1,
        pickable=True,
        stroked=True,
    )

    return pdk.Deck(
        layers=[layer],
        initial_view_state=_VIEW,
        map_style=_MAPSTYLE,
        tooltip={
            "html": "<b>{region}</b> {label}<br/>연속 {streak}일 · 최근 {sst}°C",
            "style": {**_TOOLTIP_STYLE, "border-color": "rgba(255,80,80,0.5)"},
        },
    )


def make_hotlowsal_heatmap(day_df: pd.DataFrame) -> pdk.Deck:
    """고수온∩저염분 공통지역 히트맵."""
    if day_df is None or day_df.empty:
        return _empty_deck()

    df = day_df.dropna(subset=["lat", "lon"]).copy()
    sst_col = "sst_celsius" if "sst_celsius" in df.columns else df.columns[2]
    df["weight"] = df[sst_col].clip(lower=0)

    layer = pdk.Layer(
        "HeatmapLayer",
        data=df,
        get_position=["lon", "lat"],
        get_weight="weight",
        aggregation="MEAN",
        color_range=[
            [0, 80, 100, 0],
            [0, 194, 212, 120],
            [0, 229, 255, 200],
            [255, 160, 0, 210],
            [255, 40, 0, 240],
        ],
        radius_pixels=30,
        threshold=0.03,
    )

    return pdk.Deck(
        layers=[layer],
        initial_view_state=_VIEW,
        map_style=_MAPSTYLE,
    )


def make_bar_chart(freq_df: pd.DataFrame):
    return px.bar(
        freq_df.sort_values("count", ascending=True),
        x="count", y="location", orientation="h",
        labels={"count": "발생 횟수", "location": "지역"},
        title="관심지역 발생 빈도",
    )
