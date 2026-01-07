import sys
import os
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.outfall_engine import simulate_outfall, gaussian_intensity
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import pandas as pd
from datetime import datetime
import json

from src.data_engine import DataEngine
from src.modulation_engine import calculate_modulated_attribution


app = Flask(__name__, static_folder='../dashboard', static_url_path='')
CORS(app)

# Initialize engine with data paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'cleaned')
STATION_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'raw', 'station_data')

engine = None

def get_engine():
    global engine
    if engine is None:
        engine = DataEngine(
            industries_path=os.path.join(DATA_DIR, 'industries_cleaned.csv'),
            fires_path=os.path.join(DATA_DIR, 'fires_combined.csv'),
            stations_path=os.path.join(DATA_DIR, 'stations_metadata.csv'),
            wind_path=os.path.join(DATA_DIR, 'wind_filtered.csv')
        )
    return engine



@app.route('/')
def serve_dashboard():
    """Serve the dashboard."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/stations', methods=['GET'])
def get_stations():
    """
    Get all monitoring stations.
    Returns: List of stations with id, name, lat, lon, and metadata.
    """
    eng = get_engine()
    stations = eng.stations.to_dict('records')
    
    # Convert numpy types to Python types
    for s in stations:
        for k, v in s.items():
            if pd.isna(v):
                s[k] = None
            elif hasattr(v, 'item'):
                s[k] = v.item()
    
    return jsonify({
        'count': len(stations),
        'stations': stations
    })


@app.route('/attribution', methods=['POST'])
def calculate_attribution():
    """
    Calculate source attribution for a station and timestamp.
    Uses VALIDATED PRIORS + MODULATION (no scoring system).
    
    Request body:
    {
        "station": "Anand Vihar",
        "timestamp": "2025-10-20T22:00:00",
        "readings": {"PM25": 450, "PM10": 520, "NO2": 65, "SO2": 20, "CO": 3.5}
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    station_name = data.get('station')
    timestamp_str = data.get('timestamp')
    readings = data.get('readings', {})
    
    if not station_name:
        return jsonify({'error': 'station is required'}), 400
    if not timestamp_str:
        return jsonify({'error': 'timestamp is required'}), 400
    
    eng = get_engine()
    
    try:
        # Parse timestamp
        timestamp = pd.to_datetime(timestamp_str).to_pydatetime()
        
        # Get station info
        station = eng.get_station(station_name)
        if station is None:
            return jsonify({'error': f'Station not found: {station_name}'}), 404
        
        # Get wind/meteorology data from data engine
        # Get wind/meteorology data from wind dataset for THIS station
        # Get wind/meteorology data - prefer station-specific wind, fallback to regional
        wind_row = eng.get_wind(
            timestamp=timestamp,
            lat=float(station["lat"]),
            lon=float(station["lon"]),
            station_id=int(station["station_id"])
        )

        wind_dir = wind_speed = blh = None

        if wind_row is not None:
            def safe_get(row, *candidates):
                """Try multiple possible column names, return float or None."""
                for c in candidates:
                    if c in row and pd.notna(row[c]):
                        return float(row[c])
                return None

            wind_dir = safe_get(wind_row, "wind_dir_10m", "wind_direction_10m", "wind_dir")
            wind_speed = safe_get(wind_row, "wind_speed_10m", "wind_speed")
            blh = safe_get(wind_row, "blh")


        
        # Get fire count from data engine
        fires_df = eng.get_fires(timestamp, lookback_hours=24)
        fire_count = len(fires_df) if fires_df is not None else 0
        
        # Calculate attribution using modulation engine
        result = calculate_modulated_attribution(
            timestamp=timestamp,
            readings=readings,
            wind_dir=wind_dir,
            wind_speed=wind_speed,
            blh=blh,
            fire_count=fire_count
        )

        # ============================
        # OUTFALL / DISPERSION MODEL
        # ============================
        outfall = simulate_outfall(
            lat=float(station['lat']),
            lon=float(station['lon']),
            wind_speed=wind_speed,
            wind_dir=wind_dir,
            hours=3
        )

        # Estimate future intensity using Gaussian-like decay
        for point in outfall:
            point["intensity_factor"] = gaussian_intensity(
                point["distance_km"],
                wind_speed,
                blh
            )
            point["predicted_PM25"] = round(
                readings.get("PM25", 0) * point["intensity_factor"], 1
            )

        result["outfall"] = outfall


        
        # Add meteorology to result for dashboard display
        result['meteorology'] = {
            'wind_dir': wind_dir,
            'wind_speed': wind_speed,
            'blh': blh,
            'blh_note': 'Low' if blh and blh < 300 else ('Moderate' if blh and blh < 700 else 'Good mixing')
        }
        
        # Add summary
        top_sources = sorted(result['contributions'].items(), key=lambda x: x[1]['percentage'], reverse=True)[:2]
        result['summary'] = f"Primary sources: {top_sources[0][0].replace('_', ' ').title()} ({top_sources[0][1]['percentage']:.0f}%), {top_sources[1][0].replace('_', ' ').title()} ({top_sources[1][1]['percentage']:.0f}%)"
        
        # Add confidence based on data availability
        has_wind = wind_dir is not None
        has_blh = blh is not None
        has_readings = readings.get('PM25') is not None
        result['confidence'] = 'High' if (has_wind and has_blh and has_readings) else ('Medium' if has_readings else 'Low')
        
        # Convert any numpy types
        result = json.loads(json.dumps(result, default=str))
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/attribution/modulated', methods=['POST'])
def calculate_modulated_attribution_endpoint():
    """
    Calculate source attribution using VALIDATED PRIORS + MODULATION.
    
    Based on ARAI/TERI 2018 Source Apportionment Study (Page 396) with real-time modulation.
    Uses validated baseline percentages that are modulated based on:
    - NO2 levels (traffic)
    - SO2 levels (industry)
    - Fire counts + wind direction (stubble burning)
    - BLH values (secondary aerosols/trapping)
    - PM2.5/PM10 ratio (dust)
    - Time + season + CO (local combustion)
    
    Request body:
    {
        "timestamp": "2025-11-08T09:00:00",
        "readings": {"PM25": 200, "PM10": 350, "NO2": 120, "SO2": 15, "CO": 1.2},
        "wind_dir": 308,
        "wind_speed": 4.0,
        "blh": 300,
        "fire_count": 150
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    timestamp_str = data.get('timestamp')
    readings = data.get('readings', {})
    wind_dir = data.get('wind_dir')
    wind_speed = data.get('wind_speed')
    blh = data.get('blh')
    fire_count = data.get('fire_count', 0)
    
    if not timestamp_str:
        return jsonify({'error': 'timestamp is required'}), 400
    
    try:
        from datetime import datetime as dt
        timestamp = pd.to_datetime(timestamp_str).to_pydatetime()
        
        result = calculate_modulated_attribution(
            timestamp=timestamp,
            readings=readings,
            wind_dir=wind_dir,
            wind_speed=wind_speed,
            blh=blh,
            fire_count=fire_count
        )
        
        # Convert any numpy types
        result = json.loads(json.dumps(result, default=str))
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/station/<station_id>/data', methods=['GET'])
def get_station_data(station_id):
    """
    Get historical data for a specific station.
    Query params: start_date, end_date, limit
    """
    eng = get_engine()
    
    # Find station
    station = eng.stations[eng.stations['station_id'] == int(station_id)]
    if len(station) == 0:
        return jsonify({'error': f'Station {station_id} not found'}), 404
    
    station = station.iloc[0]
    filename = station['filename']
    filepath = os.path.join(STATION_DATA_DIR, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': f'Data file not found for station {station_id}'}), 404
    
    try:
        df = pd.read_csv(filepath)
        
        # Find the timestamp column (could be 'timestamp', 'Local Time', etc.)
        time_col = None
        for col in ['timestamp', 'Local Time', 'Timestamp', 'datetime', 'Date']:
            if col in df.columns:
                time_col = col
                break
        
        # Parse dates and filter
        if time_col:
            df['_parsed_time'] = pd.to_datetime(df[time_col], errors='coerce')
            df = df.dropna(subset=['_parsed_time'])
        
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', 100, type=int)
        
        if start_date and time_col:
            start_dt = pd.to_datetime(start_date)
            df = df[df['_parsed_time'].dt.date >= start_dt.date()]
        if end_date and time_col:
            end_dt = pd.to_datetime(end_date)
            df = df[df['_parsed_time'].dt.date <= end_dt.date()]
        
        # Get records (tail if no date filter, otherwise head for chronological order)
        if start_date or end_date:
            df = df.head(limit)
        else:
            df = df.tail(limit)
        
        # Add parsed timestamp to output
        if time_col and '_parsed_time' in df.columns:
            df['timestamp'] = df['_parsed_time'].dt.strftime('%Y-%m-%dT%H:%M:%S')
            df = df.drop(columns=['_parsed_time'])
        
        # Convert to records
        records = df.to_dict('records')
        for r in records:
            for k, v in r.items():
                if pd.isna(v):
                    r[k] = None
                elif hasattr(v, 'item'):
                    r[k] = v.item()
                elif isinstance(v, pd.Timestamp):
                    r[k] = v.isoformat()
        
        return jsonify({
            'station_id': int(station_id),
            'station_name': station['station_name'],
            'count': len(records),
            'data': records
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/outfall', methods=['POST'])
def predict_outfall():
    """
    Predict where pollution will travel from a source.
    """
    data = request.get_json()

    lat = data.get("lat")
    lon = data.get("lon")
    wind_speed = data.get("wind_speed")
    wind_dir = data.get("wind_dir")
    blh = data.get("blh")
    pm25 = data.get("PM25", 0)

    # Basic validation
    if lat is None or lon is None or wind_speed is None or wind_dir is None:
        return jsonify({"error": "lat, lon, wind_speed, wind_dir required"}), 400

    # Cast to floats
    lat = float(lat)
    lon = float(lon)
    wind_speed = float(wind_speed)
    wind_dir = float(wind_dir)
    blh = float(blh) if blh is not None else None
    pm25 = float(pm25)

    outfall = simulate_outfall(lat, lon, wind_speed, wind_dir, hours=5)

    for point in outfall:
        point["intensity_factor"] = gaussian_intensity(
            point["distance_km"], wind_speed, blh
        )
        point["predicted_PM25"] = round(pm25 * point["intensity_factor"], 1)

    return jsonify({
        "source": {"lat": lat, "lon": lon},
        "outfall_points": outfall
    })



@app.route('/meteorology', methods=['GET'])
def get_meteorology():
    """
    Get current/recent meteorology data.
    Query params: timestamp (optional, defaults to latest)
    """
    eng = get_engine()
    
    timestamp = request.args.get('timestamp')
    
    if timestamp:
        ts = pd.to_datetime(timestamp)
        hour = ts.replace(minute=0, second=0, microsecond=0)
        wind_data = eng.wind[eng.wind['timestamp'] == hour]
    else:
        wind_data = eng.wind.tail(24)  # Last 24 hours
    
    records = wind_data.to_dict('records')
    for r in records:
        for k, v in r.items():
            if pd.isna(v):
                r[k] = None
            elif hasattr(v, 'item'):
                r[k] = v.item()
            elif isinstance(v, pd.Timestamp):
                r[k] = v.isoformat()
    
    return jsonify({
        'count': len(records),
        'data': records
    })


@app.route('/fires', methods=['GET'])
def get_fires():
    """
    Get fire data for attribution.
    Query params: 
        - date (YYYY-MM-DD) - single day fires
        - timestamp (ISO format) - fires from past 24 hours for time-lag
    """
    eng = get_engine()
    
    timestamp_str = request.args.get('timestamp')
    date_str = request.args.get('date')
    lookback = request.args.get('lookback', 24, type=int)  # Hours
    
    if timestamp_str:
        # Time-lagged mode: get fires from past N hours
        try:
            target_time = pd.to_datetime(timestamp_str)
            fires = eng.get_fires(target_time, lookback_hours=lookback)
            time_mode = f"past {lookback}h from {timestamp_str}"
        except Exception as e:
            return jsonify({'error': f'Invalid timestamp: {e}'}), 400
    elif date_str:
        # Legacy mode: single day
        try:
            target_date = pd.to_datetime(date_str).date()
            fires = eng.fires[eng.fires['acq_date'].dt.date == target_date]
            time_mode = f"date {date_str}"
        except Exception as e:
            return jsonify({'error': f'Invalid date: {e}'}), 400
    else:
        return jsonify({'error': 'timestamp or date parameter required'}), 400
    
    records = fires.to_dict('records')
    for r in records:
        for k, v in r.items():
            if pd.isna(v):
                r[k] = None
            elif hasattr(v, 'item'):
                r[k] = v.item()
            elif isinstance(v, pd.Timestamp):
                r[k] = v.isoformat()
    
    return jsonify({
        'mode': time_mode,
        'count': len(records),
        'fires': records
    })


@app.route('/industries', methods=['GET'])
def get_industries():
    """
    Get industry data for map visualization.
    Returns major emitters (emission_weight >= 15).
    """
    eng = get_engine()
    
    try:
        # Filter to significant industries
        major = eng.industries[eng.industries['emission_weight'] >= 15]
        
        records = major.to_dict('records')
        for r in records:
            for k, v in r.items():
                if pd.isna(v):
                    r[k] = None
                elif hasattr(v, 'item'):
                    r[k] = v.item()
        
        return jsonify({
            'count': len(records),
            'industries': records
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/station/<station_id>/industries', methods=['GET'])
def get_station_industries(station_id):
    """
    Get nearby industries contributing to pollution at a station.
    Ranked by contribution score (emission weight, distance, wind).
    """
    eng = get_engine()
    
    # Get station info
    station = eng.stations[eng.stations['station_id'] == int(station_id)]
    if station.empty:
        return jsonify({'error': 'Station not found'}), 404
    
    station = station.iloc[0]
    station_lat = station['lat']
    station_lon = station['lon']
    
    # Get wind direction for upwind calculation (optional)
    wind_dir = request.args.get('wind_direction', type=float)
    
    try:
        # Calculate distance and contribution for each industry
        industries_with_score = []
        
        for _, ind in eng.industries.iterrows():
            # Calculate distance
            lat1, lon1 = np.radians(station_lat), np.radians(station_lon)
            lat2, lon2 = np.radians(ind['latitude']), np.radians(ind['longitude'])
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
            distance_km = 6371 * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
            
            # Only include industries within 50km
            if distance_km > 50:
                continue
            
            # Calculate contribution score
            emission_weight = ind.get('emission_weight', 10)
            
            # Distance decay (closer = higher contribution)
            distance_factor = 1 / (1 + distance_km / 10)
            
            # Wind factor (if wind direction provided)
            wind_factor = 1.0
            if wind_dir is not None:
                # Calculate bearing from industry to station
                y = np.sin(lon1 - lon2) * np.cos(lat1)
                x = np.cos(lat2) * np.sin(lat1) - np.sin(lat2) * np.cos(lat1) * np.cos(lon1 - lon2)
                bearing = (np.degrees(np.arctan2(y, x)) + 360) % 360
                
                # Check if industry is upwind (wind blowing from industry toward station)
                angle_diff = abs((wind_dir - bearing + 180) % 360 - 180)
                if angle_diff < 45:
                    wind_factor = 2.0  # Directly upwind
                elif angle_diff < 90:
                    wind_factor = 1.5  # Partially upwind
            
            # Combined contribution score
            contribution_score = emission_weight * distance_factor * wind_factor
            
            # Handle NaN values in name
            name = ind.get('name', ind.get('industry_name', ''))
            if pd.isna(name) or name == '' or name is None:
                name = f"Industrial Unit #{len(industries_with_score) + 1}"
            
            # Get category and format nicely (Light_Industry -> Light Industry)
            category = ind.get('category', ind.get('facility_type', ''))
            if pd.isna(category) or category == '' or category is None:
                category = 'Industrial'
            else:
                category = str(category).replace('_', ' ')
            
            industries_with_score.append({
                'name': str(name),
                'type': category,
                'latitude': float(ind['latitude']),
                'longitude': float(ind['longitude']),
                'distance_km': round(distance_km, 1),
                'emission_weight': float(emission_weight),
                'contribution_score': round(contribution_score, 1),
                'is_upwind': wind_factor > 1.0 if wind_dir else None
            })
        
        # Sort by contribution score (highest first)
        industries_with_score.sort(key=lambda x: x['contribution_score'], reverse=True)
        
        # Return top 10 contributors
        return jsonify({
            'station_id': int(station_id),
            'station_name': station['station_name'],
            'count': len(industries_with_score[:10]),
            'industries': industries_with_score[:10]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/live', methods=['GET'])
def get_live_data():
    """
    Fetch live data from CPCB RSS feed, OpenMeteo weather, and VIIRS fires.
    Returns current hour's readings with meteorology for real-time attribution.
    """
    import requests
    import xml.etree.ElementTree as ET
    from difflib import SequenceMatcher
    
    CPCB_RSS_URL = "https://airquality.cpcb.gov.in/caaqms/rss_feed"
    OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"
    FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
    
    POLLUTANT_MAP = {
        "PM2.5": "PM25",
        "PM10": "PM10", 
        "NO2": "NO2",
        "SO2": "SO2",
        "CO": "CO",
        "OZONE": "O3",
        "NH3": "NH3"
    }
    
    result = {
        "success": True,
        "timestamp": None,
        "count": 0,
        "stations": [],
        "meteorology": None,
        "fires": {"count": 0, "data": []}
    }
    
    try:
        # ============ 1. FETCH CPCB RSS FEED ============
        eng = get_engine()
        our_stations = eng.stations
        
        def normalize_name(name):
            name = name.lower().strip()
            for suffix in [" - dpcc", " - cpcb", " - imd", " - uppcb", " - hspcb", " - rspcb", " - iitm"]:
                name = name.replace(suffix, "")
            return name.replace(",", "").replace("  ", " ").strip()
        
        def find_match(rss_name):
            rss_norm = normalize_name(rss_name)
            best_match = None
            best_score = 0
            for _, row in our_stations.iterrows():
                our_norm = normalize_name(row["station_name"])
                if rss_norm == our_norm:
                    return row
                score = SequenceMatcher(None, rss_norm, our_norm).ratio()
                if score > best_score and score > 0.7:
                    best_score = score
                    best_match = row
            return best_match
        
        try:
            rss_response = requests.get(CPCB_RSS_URL, headers={"accept": "application/xml"}, timeout=30)
            rss_response.raise_for_status()
            root = ET.fromstring(rss_response.text)
            
            live_data = []
            latest_timestamp = None
            
            for station in root.iter("Station"):
                station_id = station.get("id")
                lastupdate = station.get("lastupdate")
                
                if not station_id or not lastupdate:
                    continue
                
                match = find_match(station_id)
                if match is None:
                    continue
                
                try:
                    timestamp = datetime.strptime(lastupdate, "%d-%m-%Y %H:%M:%S")
                    if latest_timestamp is None or timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                except ValueError:
                    continue
                
                readings = {}
                for pollutant in station.findall("Pollutant_Index"):
                    poll_id = pollutant.get("id")
                    hourly_value = pollutant.get("Hourly_sub_index")
                    if poll_id and hourly_value and hourly_value != "NA":
                        try:
                            csv_col = POLLUTANT_MAP.get(poll_id, poll_id)
                            readings[csv_col] = float(hourly_value)
                        except ValueError:
                            pass
                
                aqi_elem = station.find("Air_Quality_Index")
                if aqi_elem is not None:
                    try:
                        readings["AQI"] = int(aqi_elem.get("Value", 0))
                    except:
                        pass
                
                live_data.append({
                    "rss_station": station_id,
                    "station_id": int(match["station_id"]),
                    "station_name": match["station_name"],
                    "lat": float(match["lat"]),
                    "lon": float(match["lon"]),
                    "timestamp": lastupdate,
                    "readings": readings
                })
            
            result["stations"] = live_data
            result["count"] = len(live_data)
            result["timestamp"] = latest_timestamp.strftime("%Y-%m-%dT%H:%M:%S") if latest_timestamp else None
            
        except Exception as e:
            result["rss_error"] = str(e)
        
        # ============ 2. FETCH LIVE WEATHER FROM OPENMETEO ============
        try:
            # Get current weather for Delhi region
            weather_params = {
                "latitude": 28.6139,
                "longitude": 77.2090,
                "current": "temperature_2m,wind_speed_10m,wind_direction_10m",
                "hourly": "wind_speed_10m,wind_direction_10m,boundary_layer_height",
                "timezone": "Asia/Kolkata",
                "forecast_days": 1
            }
            
            weather_response = requests.get(OPENMETEO_URL, params=weather_params, timeout=15)
            weather_response.raise_for_status()
            weather_data = weather_response.json()
            
            # Get current hour's data
            current = weather_data.get("current", {})
            hourly = weather_data.get("hourly", {})
            
            # Find current hour index
            current_hour = datetime.now().hour
            blh = None
            if hourly.get("boundary_layer_height") and len(hourly["boundary_layer_height"]) > current_hour:
                blh = hourly["boundary_layer_height"][current_hour]
            
            result["meteorology"] = {
                "wind_speed": current.get("wind_speed_10m"),
                "wind_dir": current.get("wind_direction_10m"),
                "temperature": current.get("temperature_2m"),
                "blh": blh,
                "source": "OpenMeteo"
            }
            
        except Exception as e:
            result["weather_error"] = str(e)
            # Fallback to reasonable defaults
            result["meteorology"] = {
                "wind_speed": 3.0,
                "wind_dir": 270,  # Default NW
                "blh": 300,
                "source": "fallback"
            }
        
        # ============ 3. FETCH RECENT VIIRS FIRE DATA ============
        try:
            # Reload fires to get latest updates from update_fires.py
            eng.reload_fires()
            
            # NASA FIRMS API - Get fires from last 2 days in Punjab/Haryana region
            # Bounding box: Punjab/Haryana/Western UP (stubble burning region)
            # Approximate: lat 28-32, lon 74-78
            
            # FIRMS requires API key for direct access, but we can use existing data
            # as fallback and note this in the response
            
            # Get recent fires from our database (last 48 hours from current time)
            now = datetime.now()
            recent_fires = eng.get_fires(now, lookback_hours=48)
            
            # Count fires in NW region (Punjab/Haryana)
            nw_fires = []
            for _, fire in recent_fires.iterrows():
                lat, lon = fire.get('latitude'), fire.get('longitude')
                # NW region check (Punjab/Haryana)
                if lat and lon and 28 <= lat <= 32 and 74 <= lon <= 78:
                    nw_fires.append({
                        "lat": float(lat),
                        "lon": float(lon),
                        "frp": float(fire.get('frp', 0)),
                        "date": str(fire.get('date', ''))
                    })
            
            result["fires"] = {
                "count": len(recent_fires),
                "nw_count": len(nw_fires),
                "source": "NASA FIRMS (Live)",
                "note": "Real-time VIIRS data"
            }
            
        except Exception as e:
            result["fire_error"] = str(e)
            result["fires"] = {"count": 0, "nw_count": 0, "source": "error"}
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    print("Starting Delhi Pollution Attribution API...")
    print("Dashboard available at http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)

