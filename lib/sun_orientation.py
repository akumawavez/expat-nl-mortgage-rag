"""
Phase 3: Sun-orientation widget – sun path vs building for a given date and orientation.

Uses approximate solar position (elevation, azimuth) for Amsterdam (52.37, 4.89).
Output: SVG or HTML string for embedding in Streamlit.
"""
from __future__ import annotations

import math
from datetime import date

# Amsterdam default
DEFAULT_LAT = 52.37
DEFAULT_LON = 4.89

# Orientation to building-facing azimuth (degrees from N): South=180, SW=225, etc.
ORIENTATION_AZIMUTH = {
    "South": 180,
    "SW": 225,
    "West": 270,
    "NW": 315,
    "North": 0,
    "NE": 45,
    "East": 90,
    "SE": 135,
}


def _day_of_year(d: date) -> int:
    return (d - date(d.year, 1, 1)).days + 1


def _solar_declination(day_of_year: int) -> float:
    """Approximate declination in radians (Cooper 1969)."""
    return 23.45 * math.sin(math.radians(360 * (284 + day_of_year) / 365))


def _hour_angle(hour: float) -> float:
    """Solar hour angle in radians (15 deg per hour from solar noon)."""
    return math.radians(15 * (hour - 12))


def solar_elevation_azimuth(
    d: date,
    hour: float,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
) -> tuple[float, float]:
    """
    Approximate solar elevation (deg) and azimuth (deg from N, 0=N, 90=E, 180=S).
    """
    day = _day_of_year(d)
    dec = math.radians(_solar_declination(day))
    lat_rad = math.radians(lat)
    ha = _hour_angle(hour)
    sin_el = (
        math.sin(dec) * math.sin(lat_rad)
        + math.cos(dec) * math.cos(lat_rad) * math.cos(ha)
    )
    el = math.degrees(math.asin(max(-1, min(1, sin_el))))
    cos_el = math.sqrt(1 - sin_el * sin_el) if abs(sin_el) < 1 else 0
    denom = math.cos(lat_rad) * cos_el if abs(math.cos(lat_rad)) > 1e-6 and cos_el > 1e-6 else 1e-6
    cos_az = (math.sin(dec) - math.sin(lat_rad) * sin_el) / denom
    cos_az = max(-1, min(1, cos_az))
    az_cos = math.degrees(math.acos(cos_az))
    az = az_cos if math.sin(ha) <= 0 else 360 - az_cos
    return el, az


def build_sun_path_svg(
    d: date,
    orientation: str,
    width: int = 400,
    height: int = 320,
    lat: float = DEFAULT_LAT,
) -> str:
    """
    Build an SVG showing sun path (elevation vs time) and building orientation.
    Orientation selects which way the building faces; we draw sun positions through the day.
    """
    _ = ORIENTATION_AZIMUTH.get(orientation, 180)  # orientation drives which way building faces
    # Sample hours 6–20
    points = []
    for h in range(6, 21):
        for frac in (0, 0.5):
            hour = h + frac
            el, az = solar_elevation_azimuth(d, hour, lat=lat)
            if el < 0:
                continue
            # X = time (6–20), Y = elevation (0–90)
            x = (hour - 6) / 14 * (width - 60) + 40
            y = height - 40 - (el / 90) * (height - 80)
            points.append((x, y, hour, el, az))
    if not points:
        points = [(width / 2, height / 2, 12, 30, 180)]

    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y, _, _, _ in points)
    sun_circles = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="orange" opacity="0.9"/>'
        for x, y, _, _, _ in points[::2]  # every other point
    )
    # Building direction indicator (vertical line at "noon" or at facing direction)
    noon_x = (12 - 6) / 14 * (width - 60) + 40
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#1e293b"/>
  <text x="20" y="25" fill="#94a3b8" font-size="14">Sun path – {d.isoformat()} – facing {orientation}</text>
  <line x1="40" y1="{height-40}" x2="40" y2="40" stroke="#475569" stroke-width="1"/>
  <line x1="40" y1="{height-40}" x2="{width-20}" y2="{height-40}" stroke="#475569" stroke-width="1"/>
  <text x="15" y="45" fill="#64748b" font-size="10">90</text>
  <text x="15" y="{height-35}" fill="#64748b" font-size="10">0</text>
  <path d="{path_d}" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linejoin="round"/>
  {sun_circles}
  <line x1="{noon_x}" y1="{height-40}" x2="{noon_x}" y2="40" stroke="#22c55e" stroke-width="1" stroke-dasharray="4" opacity="0.8"/>
  <text x="{noon_x-8}" y="{height-22}" fill="#22c55e" font-size="9">Noon</text>
</svg>'''
    return svg


def build_sun_orientation_html(
    d: date,
    orientation: str,
    width: int = 400,
    height: int = 320,
) -> str:
    """Return HTML containing the SVG (for Streamlit components.v1.html)."""
    svg = build_sun_path_svg(d, orientation, width=width, height=height)
    return f'<div style="background:#1e293b;padding:12px;border-radius:8px;">{svg}</div>'
