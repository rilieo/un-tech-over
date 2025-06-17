import streamlit as st
import geopandas as gpd
import plotly.graph_objects as go
import plotly.express as px
from utils import calculate_effect, add_polygon_borders, add_geotiff_heatmap_mapbox, handle_tiff
import rasterio as rio

def reset():
    layers["Factors"] = None
    st.session_state["uploader_key"] += 1

st.set_page_config(layout="wide")

# Session state initialization
layers = {
    "Borders": None,
    "Hurricanes": None,
    "Factors": None,
    "Images": []
}
# Colors for factors trace
colors = ["green", "blue", "black"]
titles = ["Population Density", "Wind", "Wind"]
color_idx = 0
num_images = 0

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 1

# Form for uploads and action
with st.form("weather_map_form"):
    border_file = st.file_uploader("Borders of Country", type=["geojson", "json"], key="borders")
    if border_file:
        layers["Borders"] = gpd.read_file(border_file)

    hurricane_file = st.file_uploader("Hurricane Paths", type=["geojson", "json"], key="hurricanes")
    if hurricane_file:
        layers["Hurricanes"] = gpd.read_file(hurricane_file)

    left, right = st.columns(2)
    factors_file = left.file_uploader("Factors of Impact", type=["geojson", "json"], key=st.session_state["uploader_key"])
    images_files = right.file_uploader("Image Tiff", type=["tif", "geotiff", "tiff"], key="images", accept_multiple_files=True)
    clear = st.form_submit_button(label="Clear Factors of Impact", on_click=reset)

    if factors_file:
        layers["Factors"] = gpd.read_file(factors_file)
    if images_files:
        for image in images_files:
            layers["Images"].append(handle_tiff("data/" + image.name))
            num_images += 1
    
    submitted = st.form_submit_button("Generate Map")

# Only plot if form is submitted and files are uploaded
if border_file and hurricane_file and factors_file:
    fig_map = go.Figure()

    for name, gdf in layers.items():
        if gdf is not None:
            fig_map = add_polygon_borders(fig_map, gdf, name)
    
    # Map center calculation
    minxs, minys, maxxs, maxys = layers["Borders"].total_bounds
    center_lon = (minxs + maxxs) / 2
    center_lat = (minys + maxys) / 2

    fig_map.update_layout(
        map=dict(
            center=dict(lat=center_lat, lon=center_lon),
            zoom=5
        ),
        margin={"r": 0, "t": 0, "l": 0, "b": 0}
    )

    # Result calculation
    affected_df = calculate_effect(
        layers["Borders"],
        layers["Hurricanes"],
        layers["Factors"]
    )

    st.subheader("Summary")
    st.dataframe(affected_df)

    if not affected_df.empty:
        color_map = {"High": "red", "Medium": "orange", "Low": "yellow", "None": "gray"}
        fig_map.add_trace(go.Scattermap(
            lat=affected_df["lat"],
            lon=affected_df["lon"],
            mode="markers",
            marker=dict(
                size=10,
                color=affected_df["impact"].map(color_map),
                opacity=0.7
            ),
            text=affected_df["impact"],
            name="School Impact"
        ))

    st.plotly_chart(fig_map, use_container_width=True)

    #Read the GeoTIFF
    for i, col in enumerate(st.columns(num_images)):
        # Plot as heatmap
        heatmap = px.imshow(layers["Images"][i], color_continuous_scale="gray")
        heatmap.update_xaxes(showticklabels=False)
        heatmap.update_yaxes(showticklabels=False)
        heatmap.update_layout(
            coloraxis_showscale=False, # hide colorbar
            map=dict(
                center=dict(lat=center_lat, lon=center_lon),
                zoom=5
            ),
            margin={"r": 0, "t": 0, "l": 0, "b": 0, "pad": 0
        })
        col.plotly_chart(heatmap)

    st.markdown("#")
