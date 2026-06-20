"""
Gridlock — FastAPI Backend
===========================
Person 1 (Nishchay) · Day 1

Endpoints:
  GET /hotspots                         → Top-N violation clusters with CRS
  GET /timeline                         → Time-aggregated violation counts
  GET /enforcement-gaps                 → SCITA gap analysis
  GET /station-report/{police_station}  → Full report for a police station
"""

import os
import json
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ──────────────────────────────────────────────
# App Setup
# ──────────────────────────────────────────────
app = FastAPI(
    title="Gridlock — Parking Violation Intelligence API",
    description="AI-driven parking intelligence to detect illegal parking hotspots "
                "and quantify their impact on traffic flow.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Data Loading
# ──────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def _load_json(filename: str):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        raise RuntimeError(
            f"Data file not found: {path}. Run `python data_pipeline.py` first."
        )
    with open(path, "r") as f:
        return json.load(f)

# Lazy-loaded caches
_cache = {}

def get_clusters():
    if "clusters" not in _cache:
        _cache["clusters"] = _load_json("cluster_summary.json")
    return _cache["clusters"]

def get_gaps():
    if "gaps" not in _cache:
        _cache["gaps"] = _load_json("scita_gaps.json")
    return _cache["gaps"]

def get_stations():
    if "stations" not in _cache:
        _cache["stations"] = _load_json("station_summary.json")
    return _cache["stations"]

def get_timeline():
    if "timeline" not in _cache:
        _cache["timeline"] = _load_json("timeline_summary.json")
    return _cache["timeline"]


# ──────────────────────────────────────────────
# Root
# ──────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "service": "Gridlock — Parking Violation Intelligence API",
        "version": "1.0.0",
        "endpoints": [
            "/hotspots",
            "/timeline",
            "/enforcement-gaps",
            "/station-report/{police_station}",
        ],
    }


# ──────────────────────────────────────────────
# 1. /hotspots
# ──────────────────────────────────────────────
@app.get("/hotspots")
def hotspots(
    top_n: int = Query(20, ge=1, le=500, description="Number of top clusters to return"),
    min_crs: float = Query(0.0, ge=0.0, le=1.0, description="Minimum CRS threshold"),
    vehicle_type: Optional[str] = Query(None, description="Filter by vehicle type"),
):
    """
    Return top-N violation clusters ranked by Congestion Risk Score (CRS).
    Each cluster includes centroid, violation count, CRS, and top violation types.
    """
    clusters = get_clusters()

    # Filter by min CRS
    filtered = [c for c in clusters if c.get("crs", 0) >= min_crs]

    # Sort by CRS descending
    filtered.sort(key=lambda c: c.get("crs", 0), reverse=True)

    # Return top N
    result = filtered[:top_n]

    return {
        "total_clusters": len(clusters),
        "returned": len(result),
        "filters": {"min_crs": min_crs, "vehicle_type": vehicle_type},
        "hotspots": [
            {
                "cluster_id": c.get("cluster_id"),
                "crs": c.get("crs"),
                "violation_count": c.get("violation_count"),
                "centroid_lat": round(c.get("centroid_lat", 0), 6),
                "centroid_lng": round(c.get("centroid_lng", 0), 6),
                "avg_response_delay_hrs": round(c.get("avg_response_delay", 0), 2),
                "recurrence_rate": round(c.get("recurrence_rate", 0), 4),
                "top_station": c.get("top_station"),
                "top_junction": c.get("top_junction"),
                "top_vehicle_types": c.get("top_vehicle_types", {}),
                "top_violation_types": c.get("top_violation_types", {}),
            }
            for c in result
        ],
    }


# ──────────────────────────────────────────────
# 2. /timeline
# ──────────────────────────────────────────────
@app.get("/timeline")
def timeline(
    vehicle_type: Optional[str] = Query(None, description="Filter hourly data by vehicle type"),
):
    """
    Return time-aggregated violation data for charts:
    hourly distribution, day-of-week, monthly trend, daily time series.
    """
    tl = get_timeline()

    result = {
        "hourly_distribution": tl.get("hourly_distribution", {}),
        "day_of_week": tl.get("day_of_week", {}),
        "monthly_trend": tl.get("monthly_trend", {}),
        "daily_timeseries": tl.get("daily_timeseries", []),
    }

    # If vehicle_type filter, return that vehicle's hourly breakdown
    if vehicle_type:
        vtype_hourly = tl.get("vehicle_type_hourly", {})
        vt_key = vehicle_type.upper()
        if vt_key in vtype_hourly:
            result["filtered_hourly"] = vtype_hourly[vt_key]
            result["filter_applied"] = vt_key
        else:
            result["filtered_hourly"] = {}
            result["filter_applied"] = vt_key
            result["available_vehicle_types"] = list(vtype_hourly.keys())

    return result


# ──────────────────────────────────────────────
# 3. /enforcement-gaps
# ──────────────────────────────────────────────
@app.get("/enforcement-gaps")
def enforcement_gaps(
    top_n: int = Query(20, ge=1, le=100, description="Top N stations/junctions by gap %"),
    view: str = Query("overall", description="'overall', 'by_station', or 'by_junction'"),
):
    """
    Return SCITA gap analysis: percentage of violations never transmitted
    to the traffic management system, broken down by station/junction.
    """
    gaps = get_gaps()

    if view == "overall":
        return gaps["overall"]
    elif view == "by_station":
        return {
            "total_stations": len(gaps["by_station"]),
            "showing": min(top_n, len(gaps["by_station"])),
            "stations": gaps["by_station"][:top_n],
        }
    elif view == "by_junction":
        return {
            "total_junctions": len(gaps["by_junction"]),
            "showing": min(top_n, len(gaps["by_junction"])),
            "junctions": gaps["by_junction"][:top_n],
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid view '{view}'. Use 'overall', 'by_station', or 'by_junction'."
        )


# ──────────────────────────────────────────────
# 4. /station-report/{police_station}
# ──────────────────────────────────────────────
@app.get("/station-report/{police_station}")
def station_report(police_station: str):
    """
    Full intelligence report for a specific police station:
    violation count, CRS hotspots, gap %, vehicle types, peak hours.
    """
    stations = get_stations()

    # Case-insensitive lookup
    match = None
    for s in stations:
        if s["police_station"].lower() == police_station.lower():
            match = s
            break

    if not match:
        available = [s["police_station"] for s in stations]
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Station '{police_station}' not found.",
                "available_stations": available,
            }
        )

    return match


# ──────────────────────────────────────────────
# 5. /stations  (list all)
# ──────────────────────────────────────────────
@app.get("/stations")
def list_stations():
    """List all police stations with summary stats."""
    stations = get_stations()
    return {
        "total": len(stations),
        "stations": [
            {
                "police_station": s["police_station"],
                "total_violations": s["total_violations"],
                "gap_percentage": s["gap_percentage"],
                "avg_response_time_hrs": s["avg_response_time_hrs"],
            }
            for s in stations
        ],
    }
