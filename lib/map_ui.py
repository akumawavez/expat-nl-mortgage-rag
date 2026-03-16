"""
Map interface: given an address, show nearby facilities by category on a map,
with route/distance and option to toggle walk / bike / car.
Uses Pydeck (Streamlit-native) so the map is always visible; no iframe/folium dependency.
"""
from __future__ import annotations

from typing import Any

# RGB list for Pydeck by category
CATEGORY_COLORS = {
    "schools": [65, 105, 225],      # blue
    "grocery": [34, 139, 34],       # green
    "hospitals": [220, 20, 60],     # red
    "gym": [255, 165, 0],           # orange
    "car_wash": [139, 0, 0],        # darkred
    "parks": [0, 100, 0],           # darkgreen
    "restaurants": [128, 0, 128],   # purple
    "place_of_worship": [128, 128, 128],
    "banks": [95, 158, 160],        # cadetblue
    "public_transport": [0, 0, 0],
    "other": [211, 211, 211],       # lightgray
}


def build_pydeck_map(
    center: dict[str, Any],
    pois: list[dict],
    profile: str = "driving",
    height: int = 500,
):
    """
    Build a Pydeck Deck for st.pydeck_chart. Works natively in Streamlit (no iframe).
    Returns the Deck or None if pydeck unavailable.
    """
    try:
        import pydeck as pdk
    except ImportError:
        return None
    lat, lon = center.get("lat"), center.get("lon")
    if lat is None or lon is None:
        return None
    # Home marker
    home_data = [{
        "lon": lon,
        "lat": lat,
        "name": center.get("address", "Your location"),
        "category_label": "Your location",
        "distance_km": None,
        "duration_min": None,
    }]
    # POIs with [lon, lat] for Pydeck
    poi_data = []
    for p in pois:
        plon, plat = p.get("lon"), p.get("lat")
        if plat is None or plon is None:
            continue
        cat = p.get("category") or "other"
        rgb = CATEGORY_COLORS.get(cat, CATEGORY_COLORS["other"])
        poi_data.append({
            "lon": plon,
            "lat": plat,
            "name": p.get("name", "POI"),
            "category_label": p.get("category_label", ""),
            "distance_km": p.get("distance_km"),
            "duration_min": p.get("duration_min"),
            "color": rgb,
        })
    home_layer = pdk.Layer(
        "ScatterplotLayer",
        home_data,
        get_position="[lon, lat]",
        get_color="[255, 0, 0]",
        get_radius=80,
        pickable=True,
    )
    poi_layer = pdk.Layer(
        "ScatterplotLayer",
        poi_data,
        get_position="[lon, lat]",
        get_color="color",
        get_radius=50,
        pickable=True,
    )
    view = pdk.ViewState(latitude=lat, longitude=lon, zoom=14, pitch=0)
    return pdk.Deck(
        layers=[home_layer, poi_layer],
        initial_view_state=view,
        tooltip={"html": "<b>{name}</b><br/>{category_label}<br/>Distance: {distance_km} km<br/>~{duration_min} min", "style": {"backgroundColor": "steelblue", "color": "white"}},
        map_style="light",
        height=height,
    )


def build_map_html(
    center: dict[str, Any],
    pois: list[dict],
    profile: str = "driving",
) -> str:
    """
    Fallback: build Folium map HTML. Use build_pydeck_map + st.pydeck_chart for reliable display.
    """
    try:
        import folium
    except ImportError:
        return "<p>Install folium: <code>pip install folium</code></p>"
    lat, lon = center.get("lat"), center.get("lon")
    if lat is None or lon is None:
        return "<p>Invalid center.</p>"
    m = folium.Map(location=[lat, lon], zoom_start=15, tiles="OpenStreetMap")
    folium.Marker(
        [lat, lon],
        popup=center.get("address", "Address"),
        tooltip="Your location",
        icon=folium.Icon(color="red", icon="home"),
    ).add_to(m)
    for p in pois:
        plat, plon = p.get("lat"), p.get("lon")
        if plat is None or plon is None:
            continue
        dist = p.get("distance_km")
        dur = p.get("duration_min")
        popup = f"<b>{p.get('name', 'POI')}</b><br>{p.get('category_label', '')}"
        if dist is not None:
            popup += f"<br>Distance: {dist} km"
        if dur is not None:
            popup += f"<br>~{dur} min ({profile})"
        folium.Marker(
            [plat, plon],
            popup=folium.Popup(popup, max_width=200),
            tooltip=p.get("name", "POI"),
            icon=folium.Icon(color="blue", icon="info-sign"),
        ).add_to(m)
    return m._repr_html_()


def build_pois_table_data(pois: list[dict], profile: str) -> list[dict]:
    """Return list of dicts for Streamlit table/display: name, category, distance_km, duration_min."""
    rows = []
    for p in pois:
        rows.append({
            "Name": p.get("name", "—"),
            "Category": p.get("category_label", "—"),
            "Distance (km)": p.get("distance_km"),
            f"Duration min ({profile})": p.get("duration_min"),
        })
    return rows
