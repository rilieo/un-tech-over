import pandas as pd
import geopandas as gpd
import zipfile
import os
import tempfile
from pathlib import Path
import rasterio as rio
from geopy.distance import geodesic
import numpy as np
import plotly.graph_objects as go
import base64
import io
from PIL import Image

# Calculate the estimated impact of natural disaster
def calculate_effect(borders, weather, impact):
    if borders is None or weather is None or impact is None:
        return pd.DataFrame()  # Return empty

    left, bottom, right, top = borders.total_bounds
    country_weather = []

    # Filter out points
    for row in weather.itertuples():
        point = row.geometry
        x, y = point.x, point.y
        if (left <= x <= right) and (bottom <= y <= top):
            country_weather.append((point, row.radius_oci))

    results = []
    impact_priority = {"None": 0, "Low": 1, "Medium": 2, "High": 3}

    # Determine impact level 
    for idx, point in enumerate(impact.geometry):
        impact_level = "None"
        # Compare hurricane points with the place
        for center, radius_km in country_weather:
            distance = geodesic((point.y, point.x), (center.y, center.x)).km

            if distance <= radius_km * 0.5:
                    level = "High"
            elif distance <= radius_km:
                level = "Medium"
            elif distance <= radius_km * 1.5:
                level = "Low"
            else:
                level = "None"

            # Keep strongest
            if impact_priority[level] > impact_priority[impact_level]:
                impact_level = level

        results.append({
            "id": idx,
            "lat": point.y,
            "lon": point.x,
            "impact": impact_level
        })

    return pd.DataFrame(results)

# csv, xls, xlsx
def handle_text(file_path) -> pd.DataFrame:
    return pd.read_csv(file_path)

# tiff, tif, geotiff, geojson
def handle_geo(file_path) -> gpd.GeoDataFrame:
    ext = Path(file_path).suffix.lower()
    
    if ext in ['.geojson', '.json']:
        return gpd.read_file(file_path)
    
    elif ext == '.kmz':
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            temp_dir = tempfile.mkdtemp()
            zip_ref.extractall(temp_dir)
            kml_files = [f for f in os.listdir(temp_dir) if f.endswith('.kml')]
            if kml_files:
                return gpd.read_file(os.path.join(temp_dir, kml_files[0]))
            else:
                raise ValueError("No .kml file found inside KMZ.")

    elif ext == '.kml':
        return gpd.read_file(file_path)

# Add borders given coordinates
def add_polygon_borders(fig, gdf, name):
    if name == "Borders":
                geojson = gdf.__geo_interface__
                fig.add_trace(go.Choroplethmap(
                    geojson=geojson,
                    locations=gdf.index,
                    z=[1] * len(gdf),
                    name=name,
                    showscale=False,
                    marker_line_width=1,
                    marker_line_color="black"
                ))

    elif name == "Hurricanes":
        fig.add_trace(go.Scattermap(
            lat=gdf.geometry.y,
            lon=gdf.geometry.x,
            mode="markers+lines",
            marker=dict(size=10, color="red"),
            name=name,
            text=gdf['time'] if 'time' in gdf.columns else name,
            hoverinfo="text"
        ))

    return fig

def add_geotiff_heatmap_mapbox(tiff_path, opacity=0.6):
    fig = go.Figure()
    with rio.open(tiff_path) as src:
        if src.crs.to_string() != "EPSG:4326":
            raise ValueError("GeoTIFF must be in EPSG:4326 CRS")

        data = src.read(1)
        bounds = src.bounds  # left, bottom, right, top

        # Normalize to 0-255 uint8
        norm = (255 * (data - np.nanmin(data)) / (np.nanmax(data) - np.nanmin(data))).astype(np.uint8)
        img = Image.fromarray(norm).convert("L").convert("RGBA")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        fig.update_layout(
            mapbox_layers=[
                {
                    "sourcetype": "raster",
                    "source": [f"data:image/png;base64,{b64}"],
                    "coordinates": [
                        [bounds.left, bounds.top],     # NW
                        [bounds.right, bounds.top],    # NE
                        [bounds.right, bounds.bottom], # SE
                        [bounds.left, bounds.bottom],  # SW
                    ],
                    "opacity": opacity,
                    "below": "traces"
                }
            ]
        )
    return fig
