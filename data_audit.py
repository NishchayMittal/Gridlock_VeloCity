import pandas as pd
import os

RAW_CSV = "jan to may police violation_anonymized791b166.csv"
OUTPUT_DOC = "data_audit_report.md"

def main():
    print("Loading data...")
    df = pd.read_csv(RAW_CSV, low_memory=False)
    
    # 1. Check for null lat/lng rows
    null_lat = df['latitude'].isnull().sum()
    null_lng = df['longitude'].isnull().sum()
    
    # Check for literal 'NULL' strings if any
    null_str_lat = (df['latitude'] == 'NULL').sum() if df['latitude'].dtype == object else 0
    null_str_lng = (df['longitude'] == 'NULL').sum() if df['longitude'].dtype == object else 0
    
    total_null_lat = null_lat + null_str_lat
    total_null_lng = null_lng + null_str_lng
    
    # 2. Validate date ranges
    print("Parsing dates...")
    dates = pd.to_datetime(df['created_datetime'], format="mixed", utc=True, errors="coerce")
    min_date = dates.min()
    max_date = dates.max()
    null_dates = dates.isnull().sum()
    
    # 3. List unique police_stations and junction_names
    # Handle literal 'NULL' strings first
    # Drop rows where police_station or junction_name is missing to properly sort
    stations = df['police_station'].replace('NULL', pd.NA).dropna().unique()
    stations = [str(s) for s in stations]
    stations.sort()
    
    junctions = df['junction_name'].replace('NULL', pd.NA).dropna().unique()
    junctions = [str(j) for j in junctions]
    junctions.sort()
    
    # 4. Write to Markdown document
    print("Writing report...")
    with open(OUTPUT_DOC, 'w', encoding='utf-8') as f:
        f.write("# Data Audit Report (Person 3 - Day 1)\n\n")
        
        f.write("## 1. Null Lat/Lng Rows\n")
        f.write(f"- Null Latitude rows: {total_null_lat}\n")
        f.write(f"- Null Longitude rows: {total_null_lng}\n\n")
        
        f.write("## 2. Date Ranges (`created_datetime`)\n")
        f.write(f"- Minimum Date: {min_date}\n")
        f.write(f"- Maximum Date: {max_date}\n")
        f.write(f"- Unparseable/Null Dates: {null_dates}\n\n")
        
        f.write(f"## 3. Unique Police Stations ({len(stations)})\n")
        for s in stations:
            f.write(f"- {s}\n")
        f.write("\n")
        
        f.write(f"## 4. Unique Junction Names ({len(junctions)})\n")
        for j in junctions:
            f.write(f"- {j}\n")
            
    print(f"Audit complete. Report saved to {OUTPUT_DOC}")

if __name__ == "__main__":
    main()
