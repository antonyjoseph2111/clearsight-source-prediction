"""
Fetch Live Data from CPCB RSS Feed
===================================
Fetches real-time hourly air quality data from CPCB RSS feed
and appends to station CSV files.

Usage: python3 fetch_cpcb_live.py
       python3 fetch_cpcb_live.py --continuous  # Run every hour
"""

import os
import sys
import time
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime
from difflib import SequenceMatcher

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIONS_PATH = os.path.join(SCRIPT_DIR, "data", "cleaned", "stations_metadata.csv")
STATION_DATA_DIR = os.path.join(SCRIPT_DIR, "data", "raw", "station_data")
CPCB_RSS_URL = "https://airquality.cpcb.gov.in/caaqms/rss_feed"

# Pollutant mapping (RSS feed ID -> CSV column name)
POLLUTANT_MAP = {
    "PM2.5": "PM25",
    "PM10": "PM10",
    "NO2": "NO2",
    "SO2": "SO2",
    "CO": "CO",
    "OZONE": "O3",
    "NH3": "NH3"
}


def fetch_rss_feed():
    """Fetch the CPCB RSS feed."""
    try:
        response = requests.get(CPCB_RSS_URL, headers={"accept": "application/xml"}, timeout=60)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"❌ Error fetching RSS feed: {e}")
        return None


def parse_rss_feed(xml_content):
    """Parse RSS feed and extract all station data."""
    stations_data = {}
    
    try:
        root = ET.fromstring(xml_content)
        
        # Find all Station elements
        for station in root.iter("Station"):
            station_id = station.get("id")
            lastupdate = station.get("lastupdate")
            lat = station.get("latitude")
            lon = station.get("longitude")
            
            if not station_id or not lastupdate:
                continue
            
            # Parse timestamp (format: 07-01-2026 22:00:00)
            try:
                timestamp = datetime.strptime(lastupdate, "%d-%m-%Y %H:%M:%S")
            except ValueError:
                continue
            
            # Extract pollutant values
            pollutants = {}
            for pollutant in station.findall("Pollutant_Index"):
                poll_id = pollutant.get("id")
                # Use Hourly_sub_index for current hourly value
                hourly_value = pollutant.get("Hourly_sub_index")
                
                if poll_id and hourly_value and hourly_value != "NA":
                    try:
                        pollutants[poll_id] = float(hourly_value)
                    except ValueError:
                        pass
            
            # Get AQI
            aqi_elem = station.find("Air_Quality_Index")
            if aqi_elem is not None:
                pollutants["AQI"] = aqi_elem.get("Value")
            
            stations_data[station_id] = {
                "timestamp": timestamp,
                "lat": lat,
                "lon": lon,
                "pollutants": pollutants
            }
    
    except ET.ParseError as e:
        print(f"❌ Error parsing XML: {e}")
        return {}
    
    return stations_data


def normalize_station_name(name):
    """Normalize station name for matching."""
    # Remove common suffixes and normalize
    name = name.lower().strip()
    for suffix in [" - dpcc", " - cpcb", " - imd", " - uppcb", " - hspcb", " - rspcb", " - iitm"]:
        name = name.replace(suffix, "")
    name = name.replace(",", "").replace("  ", " ")
    return name.strip()


def find_matching_station(rss_name, our_stations):
    """Find the best matching station from our metadata."""
    rss_normalized = normalize_station_name(rss_name)
    
    best_match = None
    best_score = 0
    
    for _, row in our_stations.iterrows():
        our_normalized = normalize_station_name(row["station_name"])
        
        # Try exact match first
        if rss_normalized == our_normalized:
            return row
        
        # Try partial match
        score = SequenceMatcher(None, rss_normalized, our_normalized).ratio()
        if score > best_score and score > 0.6:  # Threshold
            best_score = score
            best_match = row
    
    return best_match


def update_station_csv(station_row, rss_data):
    """Append new data to station CSV file."""
    csv_path = os.path.join(STATION_DATA_DIR, station_row["filename"])
    
    if not os.path.exists(csv_path):
        print(f"   ⚠️ CSV not found: {csv_path}")
        return False
    
    # Read existing data
    try:
        df = pd.read_csv(csv_path)
        df["Local Time"] = pd.to_datetime(df["Local Time"])
    except Exception as e:
        print(f"   ⚠️ Error reading CSV: {e}")
        return False
    
    # Check if this timestamp already exists
    timestamp = rss_data["timestamp"]
    # Convert to timezone-aware for comparison
    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S") + "+05:30"
    
    if len(df[df["Local Time"] == pd.to_datetime(timestamp_str)]) > 0:
        print(f"   ⏭️ Data for {timestamp} already exists")
        return False
    
    # Create new row
    new_row = {"Local Time": pd.to_datetime(timestamp_str)}
    
    # Map pollutants to column names
    for rss_key, csv_col in POLLUTANT_MAP.items():
        if rss_key in rss_data["pollutants"]:
            new_row[csv_col] = rss_data["pollutants"][rss_key]
    
    # Only add if we have at least PM25 or PM10
    if "PM25" not in new_row and "PM10" not in new_row:
        print(f"   ⚠️ No PM data available")
        return False
    
    # Append to dataframe
    new_df = pd.DataFrame([new_row])
    df = pd.concat([df, new_df], ignore_index=True)
    df["Local Time"] = pd.to_datetime(df["Local Time"])
    df = df.sort_values("Local Time")
    
    # Save
    df.to_csv(csv_path, index=False)
    
    return True


def main():
    print("=" * 60)
    print("CPCB RSS Feed Live Data Fetcher")
    print("=" * 60)
    print(f"🕐 Current time: {datetime.now()}")
    
    # Load our stations
    if not os.path.exists(STATIONS_PATH):
        print(f"❌ Stations metadata not found: {STATIONS_PATH}")
        return
    
    our_stations = pd.read_csv(STATIONS_PATH)
    print(f"📋 Loaded {len(our_stations)} stations from metadata")
    
    # Fetch RSS feed
    print("\n📡 Fetching CPCB RSS feed...")
    xml_content = fetch_rss_feed()
    if not xml_content:
        return
    
    print(f"   ✅ Received {len(xml_content)} bytes")
    
    # Parse RSS feed
    print("\n🔍 Parsing station data...")
    rss_stations = parse_rss_feed(xml_content)
    print(f"   Found {len(rss_stations)} stations in RSS feed")
    
    # Match and update
    print("\n📊 Matching and updating stations...")
    print("-" * 60)
    
    updated = 0
    matched = 0
    
    for rss_name, rss_data in rss_stations.items():
        match = find_matching_station(rss_name, our_stations)
        
        if match is not None:
            matched += 1
            print(f"✓ {rss_name[:45]:45} → {match['station_name'][:30]}")
            
            # Get pollutant summary
            polls = rss_data["pollutants"]
            pm25 = polls.get("PM2.5", "N/A")
            pm10 = polls.get("PM10", "N/A")
            no2 = polls.get("NO2", "N/A")
            
            if update_station_csv(match, rss_data):
                updated += 1
                print(f"   ✅ Added: PM2.5={pm25}, PM10={pm10}, NO2={no2}")
            
    print("-" * 60)
    print(f"\n📈 SUMMARY")
    print(f"   RSS stations: {len(rss_stations)}")
    print(f"   Matched: {matched}")
    print(f"   Updated: {updated}")
    print("=" * 60)


if __name__ == "__main__":
    if "--continuous" in sys.argv:
        print("Running in continuous mode (every hour)...")
        while True:
            main()
            print("\n⏰ Sleeping for 1 hour...\n")
            time.sleep(3600)
    else:
        main()
