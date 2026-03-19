"""
Phase 2: Location tools – nearby_places (Nominatim + Overpass), OSRM, area_safety.

Uses public Nominatim/Overpass/OSRM APIs when no env override is set.
Extended: POI categories (schools, grocery, hospitals, gym, car wash, etc.),
OSRM route with profile (car / walk / bike) and distance/duration per POI.
"""
from __future__ import annotations

import math
import os
import urllib.parse
import urllib.request
import json

NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
OVERPASS_URL = os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
OSRM_URL = os.environ.get("OSRM_URL", "https://router.project-osrm.org").rstrip("/")

# POI categories for map: Overpass selector(s) and display label
POI_CATEGORIES = {
    "schools": ('node["amenity"~"school|university|college|kindergarten"]', "School"),
    "grocery": ('node["shop"~"supermarket|convenience|grocery"]', "Grocery"),
    "hospitals": ('node["amenity"~"hospital|clinic|doctors|pharmacy"]', "Health"),
    "gym": ('node["leisure"~"sports_centre|fitness"]', "Gym"),
    "car_wash": ('node["amenity"~"car_wash"]', "Car wash"),
    "parks": ('node["leisure"~"park"]', "Park"),
    "restaurants": ('node["amenity"~"restaurant|cafe|fast_food"]', "Restaurant"),
    "place_of_worship": ('node["amenity"~"place_of_worship"]', "Place of worship"),
    "banks": ('node["amenity"~"bank|atm"]', "Bank"),
    "public_transport": ('node["railway"~"station|halt"]', "Transport"),
}

# Map OSM tag values to our category key (so we assign label from actual tags, not query order)
def _tags_to_category(tags: dict) -> tuple[str, str]:
    """Return (category_key, category_label) from OSM tags."""
    amenity = (tags.get("amenity") or "").lower()
    shop = (tags.get("shop") or "").lower()
    leisure = (tags.get("leisure") or "").lower()
    railway = (tags.get("railway") or "").lower()
    if amenity in ("school", "university", "college", "kindergarten"):
        return "schools", "School"
    if shop in ("supermarket", "convenience", "grocery"):
        return "grocery", "Grocery"
    if amenity in ("hospital", "clinic", "doctors", "pharmacy"):
        return "hospitals", "Health"
    if leisure in ("sports_centre", "fitness") or amenity == "gym":
        return "gym", "Gym"
    if amenity == "car_wash" or shop == "car_repair":
        return "car_wash", "Car wash"
    if leisure == "park":
        return "parks", "Park"
    if amenity in ("restaurant", "cafe", "fast_food"):
        return "restaurants", "Restaurant"
    if amenity == "place_of_worship":
        return "place_of_worship", "Place of worship"
    if amenity in ("bank", "atm"):
        return "banks", "Bank"
    if railway in ("station", "halt") or tags.get("public_transport"):
        return "public_transport", "Transport"
    if amenity:
        return "other", amenity.replace("_", " ").title()
    if shop:
        return "other", shop.replace("_", " ").title()
    if leisure:
        return "other", leisure.replace("_", " ").title()
    return "other", "Other"


def _nominatim_geocode(address: str) -> tuple[float, float] | None:
    """Return (lat, lon) or None."""
    try:
        url = f"{NOMINATIM_URL}/search?q={urllib.parse.quote(address)}&format=json&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "ExpatNLMortgageRAG/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        if data and len(data) > 0:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


def _overpass_pois(lat: float, lon: float, radius_m: int = 1000) -> list[dict]:
    """Query Overpass for POIs (all default categories). Returns list of {name, type, category, lat, lon}."""
    return overpass_pois_by_categories(lat, lon, list(POI_CATEGORIES.keys()), radius_m)


def overpass_pois_by_categories(
    lat: float,
    lon: float,
    categories: list[str],
    radius_m: int = 1500,
) -> list[dict]:
    """Query Overpass for POIs in the given categories. Returns list of {name, type, category, lat, lon}."""
    if not categories:
        return []
    try:
        # bbox approx from radius (rough: 1 deg ~ 111km at equator)
        delta = max(0.005, radius_m / 111000.0 * 1.5)
        bbox = f"{lat - delta},{lon - delta},{lat + delta},{lon + delta}"
        parts = []
        for cat in categories:
            if cat not in POI_CATEGORIES:
                continue
            selector, _ = POI_CATEGORIES[cat]
            for part in selector.split(";"):
                part = part.strip()
                if part:
                    parts.append(f"  {part}({bbox});")
        if not parts:
            return []
        query = "[out:json][timeout:20];\n(\n" + "\n".join(parts) + "\n);\nout center 50;"
        req = urllib.request.Request(
            OVERPASS_URL,
            data=urllib.parse.urlencode({"data": query}).encode(),
            method="POST",
            headers={"User-Agent": "ExpatNLMortgageRAG/1.0"},
        )
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode())
        elements = data.get("elements", [])
        out = []
        seen = set()
        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("amenity") or tags.get("shop") or "POI"
            lat_poi = el.get("lat") or (el.get("center", {}).get("lat"))
            lon_poi = el.get("lon") or (el.get("center", {}).get("lon"))
            if lat_poi is None or lon_poi is None:
                continue
            key = (round(lat_poi, 5), round(lon_poi, 5))
            if key in seen:
                continue
            seen.add(key)
            # Assign category from the POI's actual OSM tags (not query order)
            cat_key, cat_label = _tags_to_category(tags)
            out.append({
                "name": name,
                "type": tags.get("amenity") or tags.get("shop") or tags.get("leisure") or "poi",
                "category": cat_key,
                "category_label": cat_label,
                "lat": lat_poi,
                "lon": lon_poi,
            })
        return out[:80]
    except Exception:
        return []


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance in km."""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(min(1, a)))


def osrm_route(
    orig_lat: float,
    orig_lon: float,
    dest_lat: float,
    dest_lon: float,
    profile: str = "driving",
) -> dict | None:
    """
    Get route from (orig_lat, orig_lon) to (dest_lat, dest_lon).
    profile: driving, walking, cycling (public OSRM may only support driving).
    Returns {duration_sec, distance_m, distance_km} or None.
    """
    profile = (profile or "driving").lower()
    if profile not in ("driving", "walking", "cycling"):
        profile = "driving"
    try:
        coords = f"{orig_lon},{orig_lat};{dest_lon},{dest_lat}"
        url = f"{OSRM_URL}/route/v1/{profile}/{coords}?overview=false"
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ExpatNLMortgageRAG/1.0"}), timeout=15) as r:
            data = json.loads(r.read().decode())
        routes = data.get("routes", [])
        if not routes:
            return None
        r = routes[0]
        return {
            "duration_sec": r.get("duration", 0),
            "duration_min": round(r.get("duration", 0) / 60, 1),
            "distance_m": r.get("distance", 0),
            "distance_km": round(r.get("distance", 0) / 1000, 2),
        }
    except Exception:
        return None


def nearby_pois_with_routes(
    address: str,
    categories: list[str],
    profile: str = "driving",
    radius_m: int = 1500,
    max_pois: int = 25,
) -> tuple[dict | None, list[dict]]:
    """
    Geocode address, get POIs in categories, compute route (or straight-line) from address to each POI.
    Returns (center_dict with lat, lon, address, pois list with distance_km, duration_min), or (None, []).
    """
    coords = _nominatim_geocode(address)
    if not coords:
        return None, []
    lat, lon = coords
    pois = overpass_pois_by_categories(lat, lon, categories or list(POI_CATEGORIES.keys()), radius_m)
    pois = pois[:max_pois]
    for p in pois:
        route = osrm_route(lat, lon, p["lat"], p["lon"], profile)
        if route:
            p["distance_km"] = route["distance_km"]
            p["duration_min"] = route["duration_min"]
        else:
            p["distance_km"] = round(_haversine_km(lat, lon, p["lat"], p["lon"]), 2)
            p["duration_min"] = None  # straight-line, no duration
    center = {"lat": lat, "lon": lon, "address": address}
    return center, pois


def nearby_places(address: str, radius_m: int = 1000) -> tuple[list[dict], list[dict]]:
    """
    Geocode address via Nominatim, then query Overpass for POIs.
    Returns (pois, tool_calls_for_ui).
    """
    tool_calls = [{"tool": "nearby_places", "args": {"address": address[:80], "radius_m": radius_m}}]
    coords = _nominatim_geocode(address)
    if not coords:
        return [], tool_calls
    lat, lon = coords
    pois = _overpass_pois(lat, lon, radius_m)
    return [{"address": address, "lat": lat, "lon": lon, "pois": pois}], tool_calls


def osrm_commute(origin: str, destination: str) -> tuple[dict | None, list[dict]]:
    """
    Get car commute time (minutes) and distance between two addresses via OSRM.
    Returns (result_with_duration_km, tool_calls).
    """
    tool_calls = [{"tool": "osrm_commute", "args": {"origin": origin[:50], "destination": destination[:50]}}]
    o = _nominatim_geocode(origin)
    d = _nominatim_geocode(destination)
    if not o or not d:
        return None, tool_calls
    try:
        url = f"{OSRM_URL}/route/v1/driving/{o[1]},{o[0]};{d[1]},{d[0]}?overview=false"
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ExpatNLMortgageRAG/1.0"}), timeout=10) as r:
            data = json.loads(r.read().decode())
        routes = data.get("routes", [])
        if not routes:
            return None, tool_calls
        route = routes[0]
        duration_sec = route.get("duration", 0)
        distance_m = route.get("distance", 0)
        return {
            "duration_min": round(duration_sec / 60, 1),
            "distance_km": round(distance_m / 1000, 2),
            "origin": origin,
            "destination": destination,
        }, tool_calls
    except Exception:
        return None, tool_calls


def area_safety(area_name: str) -> tuple[dict | None, list[dict]]:
    """
    Placeholder for CBS / data.overheid.nl safety (wijk/buurt).
    Returns (placeholder_result, tool_calls). Replace with real API when available.
    """
    tool_calls = [{"tool": "area_safety", "args": {"area": area_name[:80]}}]
    return {
        "area": area_name,
        "note": "Safety data from CBS/data.overheid.nl not wired; consult local sources.",
        "placeholder": True,
    }, tool_calls
