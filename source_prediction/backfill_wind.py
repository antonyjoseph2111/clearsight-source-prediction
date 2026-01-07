"""
Backfill Wind/Meteorology Data
===============================
Checks the last recorded timestamp in wind_stations.csv and fetches
missing data from OpenMeteo Archive API up to the current time.

Usage: python3 backfill_wind.py
"""

import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import os

# --- CONFIGURATION ---
ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"

# For recent data (last 5 days), use forecast API which has more recent data
FORECAST_API = "https://api.open-meteo.com/v1/forecast"

HOURLY_VARS = [
    "temperature_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_speed_80m",
    "wind_direction_80m",
    "boundary_layer_height"
]

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIONS_PATH = os.path.join(SCRIPT_DIR, "data", "cleaned", "stations_metadata.csv")
WIND_STATIONS_PATH = os.path.join(SCRIPT_DIR, "data", "cleaned", "wind_stations.csv")


def get_station_timestamps():
    """Get the last timestamp for each station from wind_stations.csv."""
    if not os.path.exists(WIND_STATIONS_PATH):
        return None, None
    
    try:
        df = pd.read_csv(WIND_STATIONS_PATH)
        if 'timestamp' not in df.columns or len(df) == 0:
            return None, None
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Per-station max timestamp
        station_max = df.groupby('station_id')['timestamp'].max().to_dict()
        
        # Global max for display
        global_max = df['timestamp'].max()
        
        return station_max, global_max
    except Exception as e:
        print(f"⚠️ Error reading wind_stations.csv: {e}")
        return None, None


def fetch_station_wind(station_id, name, lat, lon, start_date, end_date, use_forecast=False):
    """Fetch wind data for a single station."""
    api_url = FORECAST_API if use_forecast else ARCHIVE_API
    
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "Asia/Kolkata"
    }
    
    # Forecast API uses different parameter names
    if use_forecast:
        params["past_days"] = 7  # Get past 7 days
        del params["start_date"]
        del params["end_date"]
    
    try:
        response = requests.get(api_url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        if "hourly" not in data:
            return None
        
        hourly = data["hourly"]
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(hourly["time"]),
            "station_id": station_id,
            "station_name": name,
            "lat": lat,
            "lon": lon,
            "wind_temp": hourly.get("temperature_2m"),
            "wind_speed_10m": hourly.get("wind_speed_10m"),
            "wind_dir_10m": hourly.get("wind_direction_10m"),
            "wind_speed_80m": hourly.get("wind_speed_80m"),
            "wind_dir_80m": hourly.get("wind_direction_80m"),
            "blh": hourly.get("boundary_layer_height")
        })
        
        return df
        
    except requests.RequestException as e:
        print(f"  ❌ Error: {e}")
        return None


def main():
    print("=" * 60)
    print("Wind Data Backfill Script")
    print("=" * 60)
    
    # Load stations
    if not os.path.exists(STATIONS_PATH):
        print(f"❌ Error: Stations file not found: {STATIONS_PATH}")
        return
    
    stations = pd.read_csv(STATIONS_PATH)
    print(f"📋 Loaded {len(stations)} stations")
    
    # Get last timestamp
    last_ts = get_last_timestamp()
    
    if last_ts is None:
        print("❌ No existing wind_stations.csv or empty file")
        print("   Run the full fetch_wind_data.py script first")
        return
    
    print(f"📅 Last recorded: {last_ts}")
    
    # Calculate date range to fetch
    start_date = (last_ts + timedelta(hours=1)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    # Check if archive API can handle this (it has a ~5 day delay)
    days_gap = (datetime.now() - last_ts.to_pydatetime().replace(tzinfo=None)).days
    
    print(f"📊 Gap: {days_gap} days")
    print(f"📅 Fetching: {start_date} to {end_date}")
    
    if days_gap <= 0:
        print("✅ Already up to date!")
        return
    
    # OpenMeteo Archive API has ~5 day delay for historical data
    # For recent data, we need to use forecast API with past_days
    use_forecast = days_gap <= 7
    
    if use_forecast:
        print("ℹ️ Using Forecast API (for recent data)")
    else:
        print("ℹ️ Using Archive API (for historical data)")
    
    print("=" * 60)
    
    all_data = []
    
    for idx, row in stations.iterrows():
        station_id = row["station_id"]
        name = row["station_name"]
        lat = row["lat"]
        lon = row["lon"]
        
        print(f"[{idx+1}/{len(stations)}] {name}...", end=" ", flush=True)
        
        df = fetch_station_wind(station_id, name, lat, lon, start_date, end_date, use_forecast)
        
        if df is not None and len(df) > 0:
            # Filter to only new data
            df = df[df['timestamp'] > last_ts]
            if len(df) > 0:
                all_data.append(df)
                print(f"✅ {len(df)} hours")
            else:
                print("⏭️ no new data")
        else:
            print("⏭️ skipped")
        
        time.sleep(0.3)  # Rate limiting
    
    if not all_data:
        print("\n❌ No new data fetched")
        return
    
    # Combine new data
    new_df = pd.concat(all_data, ignore_index=True)
    print(f"\n📊 New records: {len(new_df)}")
    
    # Load existing data
    existing_df = pd.read_csv(WIND_STATIONS_PATH)
    existing_df['timestamp'] = pd.to_datetime(existing_df['timestamp'])
    
    # Append and deduplicate
    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    combined_df = combined_df.drop_duplicates(subset=['timestamp', 'station_id'], keep='last')
    combined_df = combined_df.sort_values(['station_id', 'timestamp'])
    
    # Save
    combined_df.to_csv(WIND_STATIONS_PATH, index=False)
    
    new_rows = len(combined_df) - len(existing_df)
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✅ Added {new_rows} new rows")
    print(f"📊 Total records: {len(combined_df)}")
    print(f"📅 Date range: {combined_df['timestamp'].min()} to {combined_df['timestamp'].max()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
