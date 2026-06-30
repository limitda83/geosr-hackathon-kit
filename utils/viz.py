import pandas as pd
import plotly.express as px
import folium
from folium.plugins import HeatMap
from pathlib import Path


def make_hot28_map(df: pd.DataFrame) -> folium.Map:
    center_lat = df["lat"].mean() if "lat" in df.columns else 35.5
    center_lon = df["lon"].mean() if "lon" in df.columns else 128.0
    m = folium.Map(location=[center_lat, center_lon], zoom_start=8)
    if {"lat", "lon", "value"}.issubset(df.columns):
        heat_data = df[["lat", "lon", "value"]].dropna().values.tolist()
        HeatMap(heat_data, radius=12, blur=8).add_to(m)
    return m


def make_frequency_map(freq_df: pd.DataFrame) -> folium.Map:
    m = folium.Map(location=[35.5, 128.0], zoom_start=7)
    if freq_df.empty:
        return m
    max_count = freq_df["count"].max()
    for _, row in freq_df.iterrows():
        ratio = row["count"] / max_count
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=max(5, row["count"] / 2),
            color="red", fill=True, fill_opacity=0.6 * ratio,
            tooltip=f"{row['location']}: {row['count']}건",
        ).add_to(m)
    return m


def make_bar_chart(freq_df: pd.DataFrame):
    return px.bar(
        freq_df.sort_values("count", ascending=True),
        x="count", y="location", orientation="h",
        labels={"count": "발생 횟수", "location": "지역"},
        title="관심지역 발생 빈도",
    )


def save_map_image(m: folium.Map, output_path: Path):
    import io
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from selenium import webdriver
        # selenium 없으면 HTML로 저장
        html_path = output_path.with_suffix(".html")
        m.save(str(html_path))
    except Exception:
        html_path = output_path.with_suffix(".html")
        m.save(str(html_path))
