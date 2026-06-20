"""
Gridlock — Data Pipeline & Intelligence Engine
================================================
Person 1 (Nishchay) · Day 1

Pipeline stages:
  1. Load & clean raw CSV
  2. Parse datetimes, derive response/lag/resolution hours
  3. DBSCAN spatial clustering on (lat, lng)
  4. Congestion Risk Score (CRS) per cluster
  5. SCITA gap analysis
  6. Export cleaned parquet + cluster/gap JSON summaries
"""

import os
import json
import warnings
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import MinMaxScaler

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
RAW_CSV = os.path.join(os.path.dirname(__file__),
                       "jan to may police violation_anonymized791b166.csv")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

PARQUET_PATH       = os.path.join(OUTPUT_DIR, "cleaned_data.parquet")
CLUSTER_JSON_PATH  = os.path.join(OUTPUT_DIR, "cluster_summary.json")
GAPS_JSON_PATH     = os.path.join(OUTPUT_DIR, "scita_gaps.json")
STATION_JSON_PATH  = os.path.join(OUTPUT_DIR, "station_summary.json")
TIMELINE_JSON_PATH = os.path.join(OUTPUT_DIR, "timeline_summary.json")

# DBSCAN hyper-params  (eps ~= 300 m in degree-space)
DBSCAN_EPS = 0.003
DBSCAN_MIN_SAMPLES = 10

# CRS weights
W_DENSITY    = 0.4
W_RECURRENCE = 0.3
W_DELAY      = 0.3


# ──────────────────────────────────────────────
# 1.  Load & Clean
# ──────────────────────────────────────────────
def load_and_clean(path: str) -> pd.DataFrame:
    """Load raw CSV and perform initial cleaning."""
    print("[1/6] Loading raw CSV ...")
    df = pd.read_csv(path, low_memory=False)
    print(f"       Loaded {len(df):,} rows x {len(df.columns)} cols")

    # Replace literal 'NULL' strings with NaN
    df.replace("NULL", np.nan, inplace=True)

    # Drop rows without coordinates
    before = len(df)
    df.dropna(subset=["latitude", "longitude"], inplace=True)
    print(f"       Dropped {before - len(df)} rows with missing lat/lng")

    # Drop rows with coordinates outside Bengaluru bounding box (rough)
    mask = (
        (df["latitude"].between(12.7, 13.2)) &
        (df["longitude"].between(77.3, 77.9))
    )
    dropped = (~mask).sum()
    df = df[mask].copy()
    print(f"       Dropped {dropped} rows outside Bengaluru bounds")

    return df


# ──────────────────────────────────────────────
# 2.  Datetime Parsing & Derived Columns
# ──────────────────────────────────────────────
DATETIME_COLS = [
    "created_datetime",
    "modified_datetime",
    "data_sent_to_scita_timestamp",
    "validation_timestamp",
    "action_taken_timestamp",
]

def parse_datetimes(df: pd.DataFrame) -> pd.DataFrame:
    """Parse all datetime columns and derive hour-based lag features."""
    print("[2/6] Parsing datetimes & deriving lag features ...")
    for col in DATETIME_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="mixed", utc=True, errors="coerce")

    # Also parse closed_datetime (entirely NaN in this dataset, but handle gracefully)
    if "closed_datetime" in df.columns:
        df["closed_datetime"] = pd.to_datetime(
            df["closed_datetime"], format="mixed", utc=True, errors="coerce"
        )

    # ── Derived columns (in hours) ──
    # response_time_hrs: time from creation to first modification
    df["response_time_hrs"] = (
        (df["modified_datetime"] - df["created_datetime"])
        .dt.total_seconds() / 3600
    )

    # scita_lag_hrs: time from creation to SCITA transmission
    df["scita_lag_hrs"] = (
        (df["data_sent_to_scita_timestamp"] - df["created_datetime"])
        .dt.total_seconds() / 3600
    )

    # resolution_time_hrs: time from creation to validation
    df["resolution_time_hrs"] = (
        (df["validation_timestamp"] - df["created_datetime"])
        .dt.total_seconds() / 3600
    )

    # Clamp negative values to 0 (clock-skew edge cases)
    for col in ["response_time_hrs", "scita_lag_hrs", "resolution_time_hrs"]:
        df[col] = df[col].clip(lower=0)

    # ── Time-based features for later analysis ──
    df["hour_of_day"] = df["created_datetime"].dt.hour
    df["day_of_week"] = df["created_datetime"].dt.dayofweek   # 0=Mon
    df["month"]       = df["created_datetime"].dt.month
    df["date"]        = df["created_datetime"].dt.date

    print(f"       response_time_hrs — mean {df['response_time_hrs'].mean():.1f}h, "
          f"median {df['response_time_hrs'].median():.1f}h")
    print(f"       scita_lag_hrs     — mean {df['scita_lag_hrs'].mean():.1f}h  "
          f"(of {df['scita_lag_hrs'].notna().sum():,} non-null)")
    print(f"       resolution_time_hrs — mean {df['resolution_time_hrs'].mean():.1f}h  "
          f"(of {df['resolution_time_hrs'].notna().sum():,} non-null)")

    return df


# ──────────────────────────────────────────────
# 3.  DBSCAN Spatial Clustering
# ──────────────────────────────────────────────
def cluster_violations(df: pd.DataFrame) -> pd.DataFrame:
    """Run DBSCAN on (lat, lng) to identify violation hotspot clusters."""
    print("[3/6] Running DBSCAN clustering ...")
    coords = df[["latitude", "longitude"]].values

    db = DBSCAN(eps=DBSCAN_EPS, min_samples=DBSCAN_MIN_SAMPLES, metric="euclidean")
    df["cluster_id"] = db.fit_predict(coords)

    n_clusters = df["cluster_id"].nunique() - (1 if -1 in df["cluster_id"].values else 0)
    noise = (df["cluster_id"] == -1).sum()
    print(f"       Found {n_clusters} clusters, {noise:,} noise points")

    return df


# ──────────────────────────────────────────────
# 4.  Congestion Risk Score (CRS)
# ──────────────────────────────────────────────
def compute_crs(df: pd.DataFrame) -> pd.DataFrame:
    """
    CRS = 0.4 x violation_density + 0.3 x recurrence_rate + 0.3 x avg_response_delay
    All components min-max scaled to [0, 1].
    """
    print("[4/6] Computing Congestion Risk Score ...")
    # Only scored clusters (ignore noise = -1)
    clustered = df[df["cluster_id"] != -1].copy()

    # ── Basic per-cluster stats ──
    cluster_stats = clustered.groupby("cluster_id").agg(
        violation_count=("id", "size"),
        centroid_lat=("latitude", "mean"),
        centroid_lng=("longitude", "mean"),
        avg_response_delay=("response_time_hrs", "mean"),
    ).reset_index()

    # ── Top station / junction per cluster ──
    top_station = (
        clustered.groupby("cluster_id")["police_station"]
        .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "Unknown")
        .reset_index(name="top_station")
    )
    top_junction = (
        clustered.groupby("cluster_id")["junction_name"]
        .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "Unknown")
        .reset_index(name="top_junction")
    )
    cluster_stats = cluster_stats.merge(top_station, on="cluster_id", how="left")
    cluster_stats = cluster_stats.merge(top_junction, on="cluster_id", how="left")

    # ── Recurrence rate (vectorized) ──
    loc_counts = (
        clustered.groupby(["cluster_id", "latitude", "longitude"])
        .size()
        .reset_index(name="loc_count")
    )
    recurrence_data = {}
    for cid, grp in loc_counts.groupby("cluster_id"):
        recurrence_data[cid] = (grp["loc_count"] > 1).sum() / len(grp) if len(grp) > 0 else 0.0
    cluster_stats["recurrence_rate"] = cluster_stats["cluster_id"].map(recurrence_data)

    # ── Top vehicle types per cluster ──
    vtype_data = {}
    for cid, grp in clustered.groupby("cluster_id"):
        vtype_data[cid] = grp["vehicle_type"].value_counts().head(3).to_dict()
    cluster_stats["top_vehicle_types"] = cluster_stats["cluster_id"].map(vtype_data)

    # ── Top violation types per cluster ──
    violtype_data = {}
    for cid, grp in clustered.groupby("cluster_id"):
        violtype_data[cid] = grp["violation_type"].value_counts().head(3).to_dict()
    cluster_stats["top_violation_types"] = cluster_stats["cluster_id"].map(violtype_data)

    # ── Min-Max normalize components ──
    scaler = MinMaxScaler()
    components = cluster_stats[["violation_count", "recurrence_rate", "avg_response_delay"]].copy()
    components = components.fillna(0)
    scaled = scaler.fit_transform(components)

    cluster_stats["norm_density"]    = scaled[:, 0]
    cluster_stats["norm_recurrence"] = scaled[:, 1]
    cluster_stats["norm_delay"]      = scaled[:, 2]

    cluster_stats["crs"] = (
        W_DENSITY    * cluster_stats["norm_density"]
        + W_RECURRENCE * cluster_stats["norm_recurrence"]
        + W_DELAY      * cluster_stats["norm_delay"]
    )

    # Round for readability
    cluster_stats["crs"] = cluster_stats["crs"].round(4)

    # ── Map CRS back to main df (dict-based, guaranteed unique) ──
    crs_dict = dict(zip(cluster_stats["cluster_id"], cluster_stats["crs"]))
    df["crs"] = df["cluster_id"].map(crs_dict)

    print(f"       CRS range: {cluster_stats['crs'].min():.4f} - {cluster_stats['crs'].max():.4f}")
    print(f"       Top 5 clusters by CRS:")
    top5 = cluster_stats.nlargest(5, "crs")[["cluster_id", "crs", "violation_count", "top_station"]]
    for _, row in top5.iterrows():
        print(f"         Cluster {row['cluster_id']:>4d}  CRS={row['crs']:.4f}  "
              f"violations={row['violation_count']:>5d}  station={row['top_station']}")

    return df, cluster_stats


# ──────────────────────────────────────────────
# 5.  SCITA Gap Analysis
# ──────────────────────────────────────────────
def analyse_scita_gaps(df: pd.DataFrame) -> dict:
    """Quantify the SCITA data-transmission gap."""
    print("[5/6] Analysing SCITA gaps ...")

    total = len(df)
    not_sent = (~df["data_sent_to_scita"]).sum()
    gap_pct = round(not_sent / total * 100, 2)

    print(f"       {not_sent:,} / {total:,} violations NOT sent to SCITA ({gap_pct}%)")

    # ── Per police station ──
    station_gaps = (
        df.groupby("police_station")
        .agg(
            total=("id", "size"),
            not_sent=("data_sent_to_scita", lambda x: (~x).sum()),
        )
        .assign(gap_pct=lambda x: (x["not_sent"] / x["total"] * 100).round(2))
        .sort_values("gap_pct", ascending=False)
        .reset_index()
    )

    # ── Per junction ──
    junction_gaps = (
        df[df["junction_name"] != "No Junction"]
        .groupby("junction_name")
        .agg(
            total=("id", "size"),
            not_sent=("data_sent_to_scita", lambda x: (~x).sum()),
        )
        .assign(gap_pct=lambda x: (x["not_sent"] / x["total"] * 100).round(2))
        .sort_values("gap_pct", ascending=False)
        .reset_index()
    )

    # ── Approved but NOT sent  (the damning stat) ──
    approved_not_sent = df[
        (df["validation_status"] == "approved") & (~df["data_sent_to_scita"])
    ]
    approved_total = (df["validation_status"] == "approved").sum()
    approved_gap_pct = round(len(approved_not_sent) / approved_total * 100, 2) if approved_total > 0 else 0

    print(f"       Approved but NOT sent: {len(approved_not_sent):,} / {approved_total:,} ({approved_gap_pct}%)")

    # ── Average SCITA lag for those that WERE sent ──
    sent_mask = df["data_sent_to_scita"] & df["scita_lag_hrs"].notna()
    avg_scita_lag = round(df.loc[sent_mask, "scita_lag_hrs"].mean(), 2) if sent_mask.sum() > 0 else None

    # ── Validation status breakdown for not-sent ──
    not_sent_validation = (
        df[~df["data_sent_to_scita"]]["validation_status"]
        .fillna("no_status")
        .value_counts()
        .to_dict()
    )

    gaps_summary = {
        "overall": {
            "total_violations": int(total),
            "not_sent_to_scita": int(not_sent),
            "gap_percentage": gap_pct,
            "approved_but_not_sent": int(len(approved_not_sent)),
            "approved_total": int(approved_total),
            "approved_gap_percentage": approved_gap_pct,
            "avg_scita_lag_hrs": avg_scita_lag,
            "not_sent_validation_breakdown": not_sent_validation,
        },
        "by_station": station_gaps.to_dict(orient="records"),
        "by_junction": junction_gaps.to_dict(orient="records"),
    }

    return gaps_summary


# ──────────────────────────────────────────────
# 6.  Build Station Summary
# ──────────────────────────────────────────────
def build_station_summary(df: pd.DataFrame, cluster_stats: pd.DataFrame) -> list:
    """Build per-station report data."""
    print("[6/6] Building station summaries ...")

    stations = []
    for station, grp in df.groupby("police_station"):
        # Top clusters in this station
        station_clusters = (
            grp[grp["cluster_id"] != -1]
            .groupby("cluster_id")
            .agg(count=("id", "size"))
            .sort_values("count", ascending=False)
            .head(5)
        )
        top_cluster_ids = station_clusters.index.tolist()
        top_cluster_info = []
        for cid in top_cluster_ids:
            cdata = cluster_stats[cluster_stats["cluster_id"] == cid]
            if len(cdata):
                row = cdata.iloc[0]
                top_cluster_info.append({
                    "cluster_id": int(cid),
                    "crs": float(row["crs"]),
                    "violation_count": int(row["violation_count"]),
                    "centroid_lat": round(float(row["centroid_lat"]), 6),
                    "centroid_lng": round(float(row["centroid_lng"]), 6),
                })

        # Gap stats for this station
        total_s = len(grp)
        not_sent_s = int((~grp["data_sent_to_scita"]).sum())

        # Vehicle type breakdown
        vtype = grp["vehicle_type"].value_counts().head(5).to_dict()

        # Average response time
        avg_resp = round(grp["response_time_hrs"].mean(), 2) if grp["response_time_hrs"].notna().any() else None

        # Peak hours
        peak_hours = grp["hour_of_day"].value_counts().head(3).to_dict()

        stations.append({
            "police_station": station,
            "total_violations": total_s,
            "not_sent_to_scita": not_sent_s,
            "gap_percentage": round(not_sent_s / total_s * 100, 2) if total_s > 0 else 0,
            "avg_response_time_hrs": avg_resp,
            "top_vehicle_types": vtype,
            "peak_hours": {str(k): int(v) for k, v in peak_hours.items()},
            "top_clusters": top_cluster_info,
        })

    return sorted(stations, key=lambda x: x["total_violations"], reverse=True)


# ──────────────────────────────────────────────
# 7.  Build Timeline Summary
# ──────────────────────────────────────────────
def build_timeline_summary(df: pd.DataFrame) -> dict:
    """Pre-aggregate violation counts for timeline charts."""
    # Hourly distribution
    hourly = df["hour_of_day"].value_counts().sort_index().to_dict()
    hourly = {str(k): int(v) for k, v in hourly.items()}

    # Day of week distribution
    dow_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
    daily = df["day_of_week"].value_counts().sort_index()
    daily = {dow_map.get(k, str(k)): int(v) for k, v in daily.items()}

    # Monthly trend
    monthly = df.groupby("month").size().to_dict()
    monthly = {str(k): int(v) for k, v in monthly.items()}

    # Daily time series (for line chart)
    daily_ts = df.groupby("date").size().reset_index(name="count")
    daily_ts["date"] = daily_ts["date"].astype(str)
    daily_timeseries = daily_ts.to_dict(orient="records")

    # By vehicle type x hour (for the polished filter)
    vtype_hourly = (
        df.groupby(["vehicle_type", "hour_of_day"])
        .size()
        .reset_index(name="count")
    )
    vtype_hourly_dict = {}
    for vtype, grp in vtype_hourly.groupby("vehicle_type"):
        vtype_hourly_dict[vtype] = {
            str(int(row["hour_of_day"])): int(row["count"])
            for _, row in grp.iterrows()
        }

    return {
        "hourly_distribution": hourly,
        "day_of_week": daily,
        "monthly_trend": monthly,
        "daily_timeseries": daily_timeseries,
        "vehicle_type_hourly": vtype_hourly_dict,
    }


# ──────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  GRIDLOCK — Data Pipeline & Intelligence Engine")
    print("=" * 60)

    # 1. Load & clean
    df = load_and_clean(RAW_CSV)

    # 2. Datetimes & derived features
    df = parse_datetimes(df)

    # 3. DBSCAN clustering
    df = cluster_violations(df)

    # 4. CRS
    df, cluster_stats = compute_crs(df)

    # 5. SCITA gap analysis
    gaps = analyse_scita_gaps(df)

    # 6. Station summaries
    station_summary = build_station_summary(df, cluster_stats)

    # 7. Timeline summary
    timeline = build_timeline_summary(df)

    # ── Save outputs ──
    print("\n[SAVE] Writing outputs ...")

    # Convert datetime cols to string for parquet compatibility
    dt_cols_to_convert = ["created_datetime", "modified_datetime",
                          "data_sent_to_scita_timestamp", "validation_timestamp",
                          "action_taken_timestamp", "closed_datetime"]
    for col in dt_cols_to_convert:
        if col in df.columns and pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str).replace("NaT", None)

    # Convert date column
    if "date" in df.columns:
        df["date"] = df["date"].astype(str)

    df.to_parquet(PARQUET_PATH, index=False)
    print(f"       -> {PARQUET_PATH}  ({os.path.getsize(PARQUET_PATH) / 1e6:.1f} MB)")

    # Cluster summary JSON
    # Convert non-serializable types
    cs_out = cluster_stats.copy()
    for col in cs_out.columns:
        if cs_out[col].dtype == "object":
            cs_out[col] = cs_out[col].apply(
                lambda x: x if isinstance(x, (str, dict, list)) else str(x)
            )
    cs_records = cs_out.to_dict(orient="records")
    # Ensure all values are JSON-serializable
    for rec in cs_records:
        for k, v in rec.items():
            if isinstance(v, (np.integer,)):
                rec[k] = int(v)
            elif isinstance(v, (np.floating,)):
                rec[k] = float(v)
    with open(CLUSTER_JSON_PATH, "w") as f:
        json.dump(cs_records, f, indent=2, default=str)
    print(f"       -> {CLUSTER_JSON_PATH}")

    with open(GAPS_JSON_PATH, "w") as f:
        json.dump(gaps, f, indent=2, default=str)
    print(f"       -> {GAPS_JSON_PATH}")

    with open(STATION_JSON_PATH, "w") as f:
        json.dump(station_summary, f, indent=2, default=str)
    print(f"       -> {STATION_JSON_PATH}")

    with open(TIMELINE_JSON_PATH, "w") as f:
        json.dump(timeline, f, indent=2, default=str)
    print(f"       -> {TIMELINE_JSON_PATH}")

    print("\n[OK] Pipeline complete!")
    print(f"   {len(df):,} rows processed")
    print(f"   {df['cluster_id'].nunique() - (1 if -1 in df['cluster_id'].values else 0)} clusters found")
    print(f"   CRS range: {cluster_stats['crs'].min():.4f} - {cluster_stats['crs'].max():.4f}")
    print(f"   SCITA gap: {gaps['overall']['gap_percentage']}%")


if __name__ == "__main__":
    main()
