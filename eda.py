import pandas as pd

# Load dataset
df = pd.read_csv("jan to may police violation_anonymized791b166 (1).csv")

# Convert datetime
df['created_datetime'] = pd.to_datetime(
    df['created_datetime'],
    format='mixed',
    utc=True,
    errors='coerce'
)

df['created_datetime_ist'] = df['created_datetime'].dt.tz_convert('Asia/Kolkata')

df['hour'] = df['created_datetime_ist'].dt.hour
df['day'] = df['created_datetime_ist'].dt.day_name()

# Vehicle Breakdown
vehicle = (
    df['vehicle_type']
    .value_counts()
    .reset_index()
)

vehicle.columns = ['vehicle_type', 'violations']
vehicle.to_csv('vehicle_breakdown.csv', index=False)

# Violation Distribution
violations = (
    df['violation_type']
    .value_counts()
    .reset_index()
)

violations.columns = ['violation_type', 'count']
violations.to_csv('violation_distribution.csv', index=False)

# Hourly Pattern
hourly = (
    df.groupby('hour')
    .size()
    .reset_index(name='violations')
)

hourly.to_csv('hourly_pattern.csv', index=False)

# Daily Pattern
daily = (
    df['day']
    .value_counts()
    .reset_index()
)

daily.columns = ['day', 'violations']
daily.to_csv('daily_pattern.csv', index=False)

# Top Junctions
top_junctions = (
    df[df['junction_name'] != 'No Junction']
    ['junction_name']
    .value_counts()
    .head(10)
    .reset_index()
)

top_junctions.columns = ['junction_name', 'violations']
top_junctions.to_csv('top_junctions.csv', index=False)

print("All exports complete!")