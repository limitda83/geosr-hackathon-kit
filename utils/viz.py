from pathlib import Path

import folium
import pandas as pd
import plotly.express as px


def make_frequency_map(freq_df: pd.DataFrame) -> folium.Map:
    if freq_df.empty:
        return folium.Map(location=[35.5, 128.0], zoom_start=7, tiles="OpenStreetMap")

    df = freq_df.dropna(subset=["lat", "lon"]).copy()
    if df.empty:
        return folium.Map(location=[35.5, 128.0], zoom_start=7, tiles="OpenStreetMap")

    m = folium.Map(
        location=[df["lat"].mean(), df["lon"].mean()],
        zoom_start=7,
        tiles="OpenStreetMap",
    )
    max_count = float(df["count"].max()) if not df.empty else 1.0
    for _, row in df.iterrows():
        ratio = float(row["count"]) / max_count if max_count else 0.0
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=max(5, float(row["count"]) / 4),
            color="#0f172a",
            weight=1,
            fill=True,
            fill_color="#00a3a3",
            fill_opacity=0.35 + 0.45 * ratio,
            tooltip=f"{row['location']}: {int(row['count'])}건",
        ).add_to(m)
    return m


def make_hot28_map(df: pd.DataFrame) -> folium.Map:
    if df.empty:
        return folium.Map(location=[35.5, 128.0], zoom_start=7, tiles="OpenStreetMap")

    data = df.dropna(subset=["lat", "lon", "value"]).copy()
    if data.empty:
        return folium.Map(location=[35.5, 128.0], zoom_start=7, tiles="OpenStreetMap")

    m = folium.Map(
        location=[data["lat"].mean(), data["lon"].mean()],
        zoom_start=7,
        tiles="OpenStreetMap",
    )
    for _, row in data.iterrows():
        folium.Circle(
            location=[row["lat"], row["lon"]],
            radius=max(5000, float(row["value"]) * 1200),
            color="#ef4444",
            fill=True,
            fill_color="#fb7185",
            fill_opacity=0.35,
        ).add_to(m)
    return m


def make_bar_chart(freq_df: pd.DataFrame):
    return px.bar(
        freq_df.sort_values("count", ascending=True),
        x="count",
        y="location",
        orientation="h",
        labels={"count": "언급 수", "location": "지역"},
        title="지역별 언급 빈도",
    )


def save_map_image(m: folium.Map, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path.with_suffix(".html")))
