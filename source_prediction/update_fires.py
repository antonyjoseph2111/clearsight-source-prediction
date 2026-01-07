"""
Update Fire Data from NASA FIRMS
================================
Fetches real-time VIIRS fire data for North India and updates the local CSV.

Usage: python3 update_fires.py
"""

import os
import sys
import pandas as pd
import requests
import io
from datetime import datetime, timedelta

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FIRES_PATH = os.path.join(SCRIPT_DIR, "data", "cleaned", "fires_combined.csv")
MAP_KEY = "9ee37fbc1af5b50e41ed0821c8394649"  # Provided by user

# North India Bounding Box (South, West, North, East)
# Covers Punjab, Haryana, Delhi, Western UP
AREA_COORDS = "70,25,85,35"  # Note: FIRMS uses West,South,East,North format for area/csv? 
# Actually FIRMS API documentation says: "min_lon,min_lat,max_lon,max_lat" (West, South, East, North)
# So 70,25,85,35 is correct.

SOURCES = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT"]
DAYS = 7  # Fetch last 7 days to ensure coverage even if script isn't run daily

def fetch_fires():
    print("=" * 60)
    print("NASA FIRMS Fire Data Updater")
    print("=" * 60)
    print(f"🕐 Current time: {datetime.now()}")
    
    new_fires = []
    
    for source in SOURCES:
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{source}/{AREA_COORDS}/{DAYS}"
        print(f"\n📡 Fetching {source}...")
        
        try:
            response = requests.get(url, timeout=60)
            
            if response.status_code != 200:
                print(f"   ❌ Error {response.status_code}: {response.text}")
                continue
                
            # Parse CSV
            csv_content = response.text
            if not csv_content.strip():
                print("   ⚠️ Empty response")
                continue
                
            df = pd.read_csv(io.StringIO(csv_content))
            print(f"   ✅ Received {len(df)} fire records")
            
            if len(df) > 0:
                # Standardize columns
                # VIIRS columns: latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_t31,frp,daynight
                
                # We need to match fires_combined.csv structure:
                # latitude,longitude,acq_date,acq_time,satellite,instrument,confidence,version,bright_t31,frp,daynight,timestamp
                
                # Ensure timestamp column exists
                # acq_time is typically HHMM (int) or string. Need to convert.
                
                def parse_time(row):
                    date_str = str(row['acq_date'])
                    time_str = str(row['acq_time']).zfill(4)
                    return pd.to_datetime(f"{date_str} {time_str}", format="%Y-%m-%d %H%M")
                
                df['timestamp'] = df.apply(parse_time, axis=1)
                new_fires.append(df)
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
    
    if not new_fires:
        print("\n⚠️ No new fire data fetched.")
        return
    
    # Combine new fires
    new_df = pd.concat(new_fires, ignore_index=True)
    print(f"\n📊 Total new fires fetched: {len(new_df)}")
    
    # Load existing fires
    if os.path.exists(FIRES_PATH):
        print(f"📂 Loading existing fires from {FIRES_PATH}...")
        existing_df = pd.read_csv(FIRES_PATH)
        existing_df['timestamp'] = pd.to_datetime(existing_df['timestamp'])
        
        # Combine and remove duplicates
        # Duplicate definition: same lat, lon, timestamp (within small tolerance?)
        # For now, exact match on lat/lon/timestamp
        
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        
        # Drop duplicates
        before_dedup = len(combined_df)
        combined_df = combined_df.drop_duplicates(subset=['latitude', 'longitude', 'timestamp'])
        after_dedup = len(combined_df)
        
        added_count = after_dedup - len(existing_df)
        print(f"   Existing: {len(existing_df)}")
        print(f"   After update: {after_dedup}")
        print(f"   ✅ Added {added_count} new unique fires")
        
    else:
        combined_df = new_df
        print(f"   Created new fire database with {len(combined_df)} records")
    
    # Sort by timestamp
    combined_df = combined_df.sort_values('timestamp')
    
    # Save
    combined_df.to_csv(FIRES_PATH, index=False)
    print(f"💾 Saved to {FIRES_PATH}")

if __name__ == "__main__":
    fetch_fires()
