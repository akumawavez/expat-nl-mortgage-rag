"""
Phase 2: Location tools – nearby_places (Nominatim + Overpass), OSRM, area_safety.

Uses public Nominatim/Overpass/OSRM APIs when no env override is set.
"""
from __future__ import annotations

import os
import urllib.parse
import urllib.request
import json
from typing import Any


NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
OVERPASS_URL = os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
OSRM_URL = os.environ.get("OSRM_URL", "https://router.project-osrm.org").rstrip("/")


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
    """Query Overpass for POIs near (lat, lon). Returns list of {name, type, lat, lon}."""
    try:
        bbox = f"{lat - 0.01},{lon - 0.01},{lat + 0.01},{lon + 0.01}"
        query = f"""
        [out:json][timeout:15];
        (
          node["amenity"~"school|university|college"]({bbox});
          node["amenity"~"hospital|clinic"]({bbox});
          node["shop"~"supermarket|convenience"]({bbox});
          node["amenity"~"place_of_worship"]({bbox});
          node["leisure"~"gym"]({bbox});
        );
        out center;
        """
        req = urllib.request.Request(
            OVERPASS_URL,
            data=urllib.parse.urlencode({"data": query}).encode(),
            method="POST",
            headers={"User-Agent": "ExpatNLMortgageRAG/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        elements = data.get("elements", [])
        out = []
        for el in elements[:30]:
            tags = el.get("tags", {})
            name = tags.get("name", tags.get("amenity", tags.get("shop", "POI")))
            lat = el.get("lat") or (el.get("center", {}).get("lat"))
            lon = el.get("lon") or (el.get("center", {}).get("lon"))
            if lat is not None and lon is not None:
                out.append({"name": name, "type": tags.get("amenity", tags.get("shop", "poi")), "lat": lat, "lon": lon})
        return out
    except Exception:
        return []


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
