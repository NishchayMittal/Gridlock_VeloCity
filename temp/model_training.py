"""
Gridlock -- Predictive Model Training
=======================================
Person 1 (Nishchay) - Day 2 AM

Trains a LightGBM model to forecast violation hotspots for the next 24 hours.
Features: hour_of_day, day_of_week, cluster_id, vehicle_type_encoded, offence_code_encoded
Target:   violation_count per (cluster, hour, day_of_week) time-bin

Outputs:
  - data/violation_model.joblib          (trained model)
  - data/label_encoders.joblib           (fitted encoders for vehicle_type & offence_code)
  - data/model_metadata.json             (feature names, metrics, training info)
"""

import os
import json
import warnings
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")

# Try LightGBM first, fall back to sklearn GradientBoosting
try:
    import lightgbm as lgb
    USE_LGBM = True
    print("[INFO] Using LightGBM")
except ImportError:
    from sklearn.ensemble import GradientBoostingRegressor
    USE_LGBM = False
    print("[INFO] LightGBM not found, using sklearn GradientBoostingRegressor")

# ---------------------------------------------------
# Config
# ---------------------------------------------------
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PARQUET_PATH = os.path.join(DATA_DIR, "cleaned_data.parquet")
MODEL_PATH = os.path.join(DATA_DIR, "violation_model.joblib")
ENCODERS_PATH = os.path.join(DATA_DIR, "label_encoders.joblib")
METADATA_PATH = os.path.join(DATA_DIR, "model_metadata.json")

FEATURES = [
    "hour_of_day",
    "day_of_week",
    "cluster_id",
    "vehicle_type_encoded",
    "offence_code_encoded",
    "month",
]

TARGET = "violation_count"


def load_and_prepare():
    """Load cleaned parquet, encode categoricals, build aggregated training set."""
    print("[1/4] Loading cleaned data ...")
    df = pd.read_parquet(PARQUET_PATH)
    print(f"       {len(df):,} rows loaded")

    # Filter to clustered points only (cluster_id != -1)
    df = df[df["cluster_id"] != -1].copy()
    print(f"       {len(df):,} clustered rows")

    # --- Encode vehicle_type ---
    le_vehicle = LabelEncoder()
    df["vehicle_type_encoded"] = le_vehicle.fit_transform(df["vehicle_type"].fillna("UNKNOWN"))

    # --- Encode offence_code ---
    # offence_code is a string like "[112,104]" -- use as-is categorical
    le_offence = LabelEncoder()
    df["offence_code_encoded"] = le_offence.fit_transform(df["offence_code"].fillna("UNKNOWN"))

    print(f"       vehicle_type classes: {len(le_vehicle.classes_)}")
    print(f"       offence_code classes: {len(le_offence.classes_)}")

    # --- Build aggregated training data ---
    # Group by (cluster_id, hour_of_day, day_of_week, vehicle_type_encoded, offence_code_encoded, month)
    # Target = count of violations in that bin
    print("[2/4] Aggregating training features ...")
    agg = (
        df.groupby(["cluster_id", "hour_of_day", "day_of_week",
                     "vehicle_type_encoded", "offence_code_encoded", "month"])
        .agg(violation_count=("id", "size"))
        .reset_index()
    )
    print(f"       {len(agg):,} training samples (aggregated bins)")

    return agg, le_vehicle, le_offence


def train_model(agg):
    """Train LightGBM (or fallback) regressor on aggregated data."""
    print("[3/4] Training model ...")

    X = agg[FEATURES]
    y = agg[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"       Train: {len(X_train):,}  |  Test: {len(X_test):,}")

    if USE_LGBM:
        model = lgb.LGBMRegressor(
            n_estimators=300,
            max_depth=8,
            learning_rate=0.05,
            num_leaves=63,
            min_child_samples=10,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbose=-1,
        )
    else:
        model = GradientBoostingRegressor(
            n_estimators=300,
            max_depth=8,
            learning_rate=0.05,
            min_samples_leaf=10,
            subsample=0.8,
            random_state=42,
        )

    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    # Metrics
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    print(f"       MAE:  {mae:.4f}")
    print(f"       RMSE: {rmse:.4f}")
    print(f"       R2:   {r2:.4f}")

    # Feature importance
    if USE_LGBM:
        importances = dict(zip(FEATURES, model.feature_importances_.tolist()))
    else:
        importances = dict(zip(FEATURES, model.feature_importances_.tolist()))

    return model, {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "feature_importances": importances,
    }


def save_outputs(model, le_vehicle, le_offence, metrics):
    """Save model, encoders, and metadata."""
    print("[4/4] Saving outputs ...")

    joblib.dump(model, MODEL_PATH)
    print(f"       -> {MODEL_PATH}")

    joblib.dump({
        "vehicle_type": le_vehicle,
        "offence_code": le_offence,
    }, ENCODERS_PATH)
    print(f"       -> {ENCODERS_PATH}")

    metadata = {
        "model_type": "LightGBM" if USE_LGBM else "GradientBoostingRegressor",
        "features": FEATURES,
        "target": TARGET,
        "metrics": metrics,
        "vehicle_type_classes": le_vehicle.classes_.tolist(),
        "offence_code_classes": le_offence.classes_.tolist(),
    }
    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"       -> {METADATA_PATH}")


def main():
    print("=" * 60)
    print("  GRIDLOCK -- Predictive Model Training (Day 2)")
    print("=" * 60)

    agg, le_vehicle, le_offence = load_and_prepare()
    model, metrics = train_model(agg)
    save_outputs(model, le_vehicle, le_offence, metrics)

    print("\n[OK] Model training complete!")
    print(f"   Model: {metrics.get('mae', 'N/A')} MAE | {metrics.get('r2', 'N/A')} R2")
    print(f"   Top features: {sorted(metrics['feature_importances'].items(), key=lambda x: -x[1])[:3]}")


if __name__ == "__main__":
    main()
