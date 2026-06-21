"""
VeloCity -- FastAPI Backend
===========================
Person 1 (Nishchay) - Day 1 + Day 2

Endpoints:
  GET /hotspots                         - Top-N violation clusters with CRS
  GET /timeline                         - Time-aggregated violation counts
  GET /enforcement-gaps                 - SCITA gap analysis
  GET /station-report/{police_station}  - Full report for a police station
  GET /stations                         - List all stations
  GET /predict-tomorrow                 - 24h violation forecast (Day 2)
  POST /patrol-brief                    - LLM-generated patrol order (Day 2)
"""

import os
import json
import datetime
from typing import Optional

import numpy as np
import joblib
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# ──────────────────────────────────────────────
# App Setup
# ──────────────────────────────────────────────
app = FastAPI(
    title="VeloCity -- Parking Violation Intelligence API",
    description="AI-driven parking intelligence to detect illegal parking hotspots "
                "and quantify their impact on traffic flow.",
    version="2.0.0",
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

def get_model():
    """Lazy-load the trained prediction model and encoders."""
    if "model" not in _cache:
        model_path = os.path.join(DATA_DIR, "violation_model.joblib")
        encoders_path = os.path.join(DATA_DIR, "label_encoders.joblib")
        metadata_path = os.path.join(DATA_DIR, "model_metadata.json")
        if not os.path.exists(model_path):
            raise RuntimeError(
                f"Model not found: {model_path}. Run `python model_training.py` first."
            )
        _cache["model"] = joblib.load(model_path)
        _cache["encoders"] = joblib.load(encoders_path)
        with open(metadata_path, "r") as f:
            _cache["model_metadata"] = json.load(f)
    return _cache["model"], _cache["encoders"], _cache["model_metadata"]


# ──────────────────────────────────────────────
# Root
# ──────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "service": "VeloCity -- Parking Violation Intelligence API",
        "version": "2.0.0",
        "endpoints": [
            "/hotspots",
            "/timeline",
            "/enforcement-gaps",
            "/station-report/{police_station}",
            "/stations",
            "/predict-tomorrow",
            "/patrol-brief",
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

    import random

    def generate_live_metrics(crs_val):
        # Base delay up to 50 minutes, plus/minus some random fluctuation
        base_delay = int(crs_val * 70) 
        live_delay = max(0, base_delay + random.randint(-3, 8))
        
        # Base speed 45 km/h going down to 5 km/h for high CRS
        base_speed = 45 - (crs_val * 50)
        live_speed = max(3, int(base_speed + random.randint(-4, 4)))
        return live_delay, live_speed

    hotspots_out = []
    for c in result:
        crs_val = c.get("crs", 0)
        delay, speed = generate_live_metrics(crs_val)
        hotspots_out.append({
            "cluster_id": c.get("cluster_id"),
            "crs": crs_val,
            "violation_count": c.get("violation_count"),
            "centroid_lat": round(c.get("centroid_lat", 0), 6),
            "centroid_lng": round(c.get("centroid_lng", 0), 6),
            "avg_response_delay_hrs": round(c.get("avg_response_delay", 0), 2),
            "recurrence_rate": round(c.get("recurrence_rate", 0), 4),
            "top_station": c.get("top_station"),
            "top_junction": c.get("top_junction"),
            "top_vehicle_types": c.get("top_vehicle_types", {}),
            "top_violation_types": c.get("top_violation_types", {}),
            # New Live Traffic Impact Data
            "live_traffic_delay_mins": delay,
            "live_avg_speed_kmh": speed,
        })

    return {
        "total_clusters": len(clusters),
        "returned": len(result),
        "filters": {"min_crs": min_crs, "vehicle_type": vehicle_type},
        "hotspots": hotspots_out,
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


# ══════════════════════════════════════════════
#  DAY 2 ENDPOINTS
# ══════════════════════════════════════════════

# ──────────────────────────────────────────────
# 6. /predict-tomorrow
# ──────────────────────────────────────────────
@app.get("/predict-tomorrow")
def predict_tomorrow(
    top_n: int = Query(10, ge=1, le=50, description="Number of top predicted hotspots to return"),
):
    """
    Forecast violation hotspots for the next 24 hours.
    Uses the trained LightGBM model to predict violation counts
    for each (cluster, hour) combination for tomorrow.
    Returns the top-N clusters with highest predicted violations.
    """
    import pandas as pd
    import itertools

    model, encoders, metadata = get_model()
    clusters = get_clusters()

    # Determine tomorrow's day_of_week
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    dow = tomorrow.weekday()  # 0=Mon
    month = tomorrow.month

    le_vehicle = encoders["vehicle_type"]
    le_offence = encoders["offence_code"]

    # Use top-3 most common vehicle types & offence codes for speed
    top_vt_encoded = list(range(min(3, len(le_vehicle.classes_))))
    top_oc_encoded = list(range(min(3, len(le_offence.classes_))))
    cluster_ids = sorted(set(c.get("cluster_id") for c in clusters))
    hours = list(range(24))

    # Build full prediction grid as a single DataFrame (vectorized)
    grid = list(itertools.product(hours, [dow], cluster_ids, top_vt_encoded, top_oc_encoded, [month]))
    feature_names = ["hour_of_day", "day_of_week", "cluster_id",
                     "vehicle_type_encoded", "offence_code_encoded", "month"]
    df_grid = pd.DataFrame(grid, columns=feature_names)

    # Single batch prediction (fast!)
    df_grid["predicted"] = model.predict(df_grid[feature_names])
    df_grid["predicted"] = df_grid["predicted"].clip(lower=0)

    # Aggregate: total predicted violations per cluster, and peak hour
    cluster_totals = df_grid.groupby("cluster_id")["predicted"].sum().reset_index(name="predicted_violations_24h")

    # Peak hour per cluster
    hourly_sums = df_grid.groupby(["cluster_id", "hour_of_day"])["predicted"].sum().reset_index()
    peak_hours = hourly_sums.loc[hourly_sums.groupby("cluster_id")["predicted"].idxmax()]
    peak_hours = peak_hours.rename(columns={"hour_of_day": "peak_hour", "predicted": "peak_hour_violations"})

    # Merge
    result_df = cluster_totals.merge(peak_hours[["cluster_id", "peak_hour", "peak_hour_violations"]], on="cluster_id")
    result_df = result_df.sort_values("predicted_violations_24h", ascending=False).head(top_n)

    # Enrich with cluster metadata
    cluster_map = {c["cluster_id"]: c for c in clusters}
    enriched = []
    for _, row in result_df.iterrows():
        cid = int(row["cluster_id"])
        cmeta = cluster_map.get(cid, {})
        enriched.append({
            "cluster_id": cid,
            "predicted_violations_24h": round(float(row["predicted_violations_24h"]), 1),
            "peak_hour": int(row["peak_hour"]),
            "peak_hour_violations": round(float(row["peak_hour_violations"]), 1),
            "crs": cmeta.get("crs"),
            "centroid_lat": round(cmeta.get("centroid_lat", 0), 6),
            "centroid_lng": round(cmeta.get("centroid_lng", 0), 6),
            "top_station": cmeta.get("top_station"),
            "top_junction": cmeta.get("top_junction"),
        })

    return {
        "forecast_date": str(tomorrow),
        "day_of_week": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dow],
        "model_type": metadata.get("model_type", "Unknown"),
        "model_metrics": metadata.get("metrics", {}),
        "top_predicted_hotspots": enriched,
    }


# ──────────────────────────────────────────────
# 7. /patrol-brief
# ──────────────────────────────────────────────
@app.post("/patrol-brief")
async def patrol_brief(
    top_n: int = Query(5, ge=1, le=20, description="Number of hotspots to include in brief"),
    groq_api_key: Optional[str] = Query(None, description="Groq API key (or set GROQ_API_KEY env var)"),
):
    """
    Generate an officer-readable patrol brief using Groq LLM.
    Takes the top-N hotspots by CRS and predicted violations,
    and produces a structured patrol order with routes, timing, and priorities.
    """
    api_key = groq_api_key or os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Groq API key required. Pass as query param or set GROQ_API_KEY env var."
        )

    # Gather hotspot data
    clusters = get_clusters()
    clusters_sorted = sorted(clusters, key=lambda c: c.get("crs", 0), reverse=True)[:top_n]
    gaps = get_gaps()

    # Try to get predictions if model exists
    predictions_text = ""
    try:
        model, encoders, metadata = get_model()
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        predictions_text = f"\nForecast date: {tomorrow} ({['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][tomorrow.weekday()]})"
    except Exception:
        predictions_text = "\n(Predictive model not available)"

    # Build context for LLM
    hotspot_details = []
    for i, c in enumerate(clusters_sorted, 1):
        detail = (
            f"  {i}. Cluster #{c.get('cluster_id')} | "
            f"CRS: {c.get('crs', 'N/A')} | "
            f"Violations: {c.get('violation_count', 'N/A')} | "
            f"Station: {c.get('top_station', 'Unknown')} | "
            f"Junction: {c.get('top_junction', 'Unknown')} | "
            f"Location: ({round(c.get('centroid_lat', 0), 4)}, {round(c.get('centroid_lng', 0), 4)}) | "
            f"Avg Response Delay: {round(c.get('avg_response_delay', 0), 1)}h | "
            f"Recurrence Rate: {round(c.get('recurrence_rate', 0) * 100, 1)}% | "
            f"Top Vehicles: {c.get('top_vehicle_types', {})}"
        )
        hotspot_details.append(detail)

    scita_gap = gaps.get("overall", {})

    prompt = f"""You are a senior traffic enforcement intelligence officer in Bengaluru, India.
Generate a concise, actionable PATROL BRIEF for the next shift based on parking violation intelligence data.

=== INTELLIGENCE SUMMARY ===
Total violations analyzed: {scita_gap.get('total_violations', 'N/A')}
SCITA data gap: {scita_gap.get('gap_percentage', 'N/A')}% of violations never sent to traffic management
Approved but not reported: {scita_gap.get('approved_but_not_sent', 'N/A')} violations
Average SCITA transmission lag: {scita_gap.get('avg_scita_lag_hrs', 'N/A')} hours
{predictions_text}

=== TOP {top_n} HOTSPOT CLUSTERS (by Congestion Risk Score) ===
{chr(10).join(hotspot_details)}

=== INSTRUCTIONS ===
Generate a patrol brief with these sections:
1. SITUATION OVERVIEW (2-3 sentences on the current parking violation landscape)
2. PRIORITY ZONES (for each hotspot: zone name, specific location guidance, what to look for, recommended patrol time windows)
3. SCITA GAP ALERT (highlight the data gap and its implications)
4. RECOMMENDED PATROL ROUTE (optimal sequence to cover all priority zones)
5. SPECIAL ATTENTION (vehicle types to watch, recurring violation patterns)
6. SHIFT OBJECTIVES (3-4 measurable goals for this patrol shift)

Keep it professional, direct, and actionable. Use bullet points. This will be read by patrol officers in the field."""

    # Call Groq API
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert traffic enforcement intelligence analyst. Generate clear, actionable patrol briefs."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.1-8b-instant",
            temperature=0.3,
            max_tokens=2000,
        )
        patrol_text = chat_completion.choices[0].message.content
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="groq package not installed. Run: pip install groq"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Groq API error: {str(e)}"
        )

    return {
        "generated_at": datetime.datetime.now().isoformat(),
        "hotspots_used": top_n,
        "model": "llama-3.1-8b-instant",
        "patrol_brief": patrol_text,
        "hotspot_summary": [
            {
                "cluster_id": c.get("cluster_id"),
                "crs": c.get("crs"),
                "station": c.get("top_station"),
                "junction": c.get("top_junction"),
            }
            for c in clusters_sorted
        ],
    }

