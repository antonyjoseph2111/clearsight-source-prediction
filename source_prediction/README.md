# Delhi Air Pollution Source Attribution System
## Complete Implementation Guide for Claude Code

---

# PROJECT OVERVIEW

## What This Project Does

Build a system that takes hourly air pollution data from Delhi-NCR monitoring stations and attributes the pollution to its likely sources:

1. **Stubble Burning** - Crop residue fires in Punjab/Haryana
2. **Traffic** - Vehicle emissions
3. **Industry** - Industrial emissions (power plants, factories)
4. **Dust** - Road dust, construction, soil
5. **Meteorological Trapping** - Low boundary layer trapping pollutants

## Output

For each station at each hour, produce:
```json
{
  "station": "Anand Vihar",
  "timestamp": "2025-11-08T09:00:00",
  "pm25": 186,
  "contributions": {
    "stubble_burning": {"percentage": 38, "level": "High"},
    "traffic": {"percentage": 25, "level": "Medium"},
    "industry": {"percentage": 12, "level": "Low"},
    "dust": {"percentage": 9, "level": "Low"},
    "trapping": {"percentage": 16, "level": "High"}
  },
  "explanations": ["Wind from NW with 89 fires upwind", "Rush hour, NO2=92µg/m³"],
  "top_fire_locations": [{"district": "Sangrur", "fires": 23}],
  "top_industries": [{"name": "Okhla WTE", "distance_km": 8.2}]
}
```

---

# PROJECT STRUCTURE

```
delhi_pollution_attribution/
│
├── data/
│   ├── raw/
│   │   └── station_data/           # Individual station CSV files (62 files)
│   │
│   └── cleaned/
│       ├── industries_cleaned.csv  # 2,906 industrial facilities
│       ├── fires_combined.csv      # 49,171 fires (Feb-Dec 2025)
│       ├── stations_metadata.csv   # 62 stations with coordinates
│       └── wind_filtered.csv       # Hourly meteorology
│
├── src/
│   ├── __init__.py
│   ├── geo_utils.py               # Haversine, bearing, upwind check
│   ├── modulation_engine.py       # Core attribution logic (Validated Prior + Modulation)
│   ├── data_engine.py             # Data loading and management
│   └── outfall_engine.py          # Pollution dispersion simulation
│
├── app/
│   └── app.py                     # Flask REST API & Live Data Endpoint
│
├── dashboard/
│   ├── index.html                 # Main dashboard UI
│   ├── app.js                     # Frontend logic
│   └── styles.css                 # Styling
│
├── update_fires.py                # Live fire data fetcher (NASA FIRMS)
├── fetch_cpcb_live.py             # Live CPCB data fetcher
├── backfill_wind.py               # Historical wind data backfiller
├── test_comprehensive_attribution.py # Validation test suite
├── requirements.txt
└── README.md
```

---

# DATA FILES

## 1. stations_metadata.csv

Station information with coordinates and traffic exposure.

| Column | Type | Description |
|--------|------|-------------|
| station_id | int | Unique ID |
| station_name | string | Full name |
| filename | string | Corresponding data file |
| lat | float | Latitude |
| lon | float | Longitude |
| has_pm25, has_no2, has_so2 | bool | Pollutant availability |
| traffic_exposure | string | very_high/high/medium/low/industrial |
| traffic_factor | float | 0.4-1.2 multiplier |

## 2. Station Data Files (in station_data/)

62 CSV files, one per station. Columns vary but typically include:

| Column | Type | Description |
|--------|------|-------------|
| Local Time | datetime | Timestamp (IST, +05:30) |
| PM25 | float | PM2.5 in µg/m³ |
| PM10 | float | PM10 in µg/m³ (not all stations) |
| NO2 | float | NO2 in µg/m³ |
| SO2 | float | SO2 in µg/m³ (only 27 stations) |
| CO | float | CO in mg/m³ |
| NO, NOX, O3 | float | Other pollutants |

**Note**: PM column is named "PM25" not "PM2.5" in the files.

## 3. industries_cleaned.csv

2,906 industrial facilities after deduplication.

| Column | Type | Description |
|--------|------|-------------|
| latitude | float | Location |
| longitude | float | Location |
| facility_type | string | power_plant / wte_plant / industry |
| category | string | Thermal_Power, Waste_to_Energy, Captive_Power, etc. |
| stack_height | float | Stack height in meters |
| emission_weight | int | 3-100, importance for attribution |
| source | string | Region (Delhi, Gurugram_Ind, etc.) |
| name | string | Facility name (may be empty) |

**Emission Weights**:
- 100: Thermal power plants (14 facilities)
- 30: WTE plants (5 facilities)
- 20: Captive power (688 facilities)
- 5-15: Smaller industries

## 4. fires_combined.csv

49,171 VIIRS fire detections from Feb 18 - Dec 2, 2025.

| Column | Type | Description |
|--------|------|-------------|
| latitude | float | Fire location |
| longitude | float | Fire location |
| acq_date | date | Detection date |
| acq_time | int | Detection time (HHMM format) |
| frp | float | Fire Radiative Power in MW |
| confidence | string | Detection confidence |
| daynight | string | D or N |
| timestamp | datetime | Parsed datetime |

**Key periods**:
- Oct-Nov: Stubble burning peak (11,554 fires)
- May: Pre-monsoon agricultural burning (24,813 fires)

## 5. wind_filtered.csv

69,120 hourly meteorology records from 10 locations.

| Column | Type | Description |
|--------|------|-------------|
| timestamp | datetime | Hour (UTC or local, verify) |
| wind_location | string | Amritsar, Delhi, Patiala, etc. |
| wind_lat, wind_lon | float | Met station location |
| wind_speed_10m | float | Wind speed at 10m (m/s) |
| wind_dir_10m | float | Wind direction at 10m (degrees) |
| wind_speed_180m | float | Wind speed at 180m |
| wind_dir_180m | float | Wind direction at 180m |
| blh | float | Boundary Layer Height (meters) |

**Use Delhi location for Delhi stations, or nearest location for NCR stations.**

---

# EQUATIONS AND ALGORITHMS

## Geographic Utilities

### Haversine Distance (km)

```python
import math

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c
```

### Bearing (degrees, 0=North, clockwise)

```python
def bearing(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(dlambda)
    
    theta = math.atan2(x, y)
    return (math.degrees(theta) + 360) % 360
```

### Angular Difference (handles wrap-around)

```python
def angular_diff(a1, a2):
    diff = abs(a1 - a2)
    return min(diff, 360 - diff)
```

### Upwind Check

```python
def is_upwind(source_bearing, wind_direction, tolerance=45):
    """
    Wind direction = where wind comes FROM.
    Source is upwind if its bearing ≈ wind direction.
    """
    return angular_diff(source_bearing, wind_direction) <= tolerance
```

---

## Stubble Burning Score

### When to Apply
- **Months**: October, November, December, January only
- **Wind direction**: 250° - 340° (NW sector, towards Punjab/Haryana)

### Algorithm

```python
def calculate_stubble_score(station_lat, station_lon, wind_dir, blh, fires_df, month):
    # 1. Seasonal check
    if month not in [10, 11, 12, 1]:
        return {'score': 5, 'level': 'None', 'fires': []}
    
    # 2. Wind direction check
    if not (250 <= wind_dir <= 340):
        return {'score': 10, 'level': 'Low', 'fires': []}
    
    # 3. Calculate fire contributions
    total = 0
    contributing_fires = []
    
    for fire in fires_df.itertuples():
        dist = haversine(station_lat, station_lon, fire.latitude, fire.longitude)
        if dist > 400:  # km max
            continue
        
        fire_bearing = bearing(station_lat, station_lon, fire.latitude, fire.longitude)
        angle_diff = angular_diff(fire_bearing, wind_dir)
        
        if angle_diff > 60:  # tolerance
            continue
        
        # Contribution factors
        alignment = 1 - (angle_diff / 60)           # 1.0 if perfect, 0 at 60°
        distance_decay = 1 / (1 + dist / 100)       # half at 100km
        blh_factor = max(0, 1 - blh / 1000)         # 0 above 1000m
        frp_factor = min(fire.frp / 50, 1.0)        # capped at 1
        
        contribution = alignment * distance_decay * blh_factor * frp_factor * 100
        
        if contribution > 2:
            total += contribution
            contributing_fires.append({...})
    
    # 4. Final score
    score = min(85, 15 + total / 3)
    level = 'High' if total >= 150 else 'Medium' if total >= 50 else 'Low'
    
    return {'score': score, 'level': level, 'fires': contributing_fires[:5]}
```

### Key Formulas

For each fire i:
$$C_i = A_i \times D_i \times B_i \times F_i \times 100$$

Where:
- $A_i = 1 - \frac{|\theta_{fire} - \theta_{wind}|}{60}$ (alignment, 0-1)
- $D_i = \frac{1}{1 + d_i / 100}$ (distance decay)
- $B_i = \max(0, 1 - \frac{BLH}{1000})$ (trapping factor)
- $F_i = \min(\frac{FRP_i}{50}, 1)$ (fire intensity)

Final score:
$$S_{stubble} = \min(85, 15 + \frac{\sum_i C_i}{3})$$

---

## Traffic Score

### Algorithm

```python
def calculate_traffic_score(hour, day_of_week, no2, station_traffic_factor):
    # 1. Time factor
    if hour in [7, 8, 9, 10]:        # morning rush
        time_factor = 1.0
    elif hour in [17, 18, 19, 20, 21]:  # evening rush
        time_factor = 1.0
    elif hour in [0, 1, 2, 3, 4, 5]:    # night
        time_factor = 0.2
    else:                               # midday
        time_factor = 0.5
    
    # 2. Day factor
    day_factor = 1.0 if day_of_week < 5 else 0.6  # weekday vs weekend
    
    # 3. NO2 factor (CPCB standard = 80 µg/m³)
    if no2 is None:
        no2_factor = 0.5
    elif no2 > 80:
        no2_factor = 1.0
    elif no2 > 50:
        no2_factor = 0.7
    elif no2 > 30:
        no2_factor = 0.4
    else:
        no2_factor = 0.2
    
    # 4. Station factor (from metadata)
    # very_high=1.2, high=1.0, medium=0.7, low=0.4, industrial=0.5
    
    score = time_factor * day_factor * no2_factor * station_traffic_factor * 100
    return {'score': min(90, max(5, score)), 'level': ...}
```

### Formula

$$S_{traffic} = T \times D \times N \times F \times 100$$

| Factor | Values |
|--------|--------|
| T (time) | 0.2 (night), 0.5 (midday), 1.0 (rush) |
| D (day) | 0.6 (weekend), 1.0 (weekday) |
| N (NO2) | 0.2-1.0 based on concentration |
| F (station) | 0.4-1.2 based on traffic exposure |

---

## Industry Score

### Algorithm

```python
def calculate_industry_score(station_lat, station_lon, wind_dir, so2, industries_df):
    # 1. SO2 signal (PRIMARY - 70% weight)
    if so2 is None:
        so2_score = 20  # unknown
    elif so2 > 40:
        so2_score = 80
    elif so2 > 25:
        so2_score = 50
    elif so2 > 15:
        so2_score = 25
    else:
        so2_score = 10
    
    # 2. Proximity signal (SECONDARY - 30% weight)
    # Only major emitters (emission_weight >= 20) that are upwind
    proximity_score = 0
    contributing = []
    
    major = industries_df[industries_df['emission_weight'] >= 20]
    
    for ind in major.itertuples():
        dist = haversine(station_lat, station_lon, ind.latitude, ind.longitude)
        if dist > 30:  # km
            continue
        
        ind_bearing = bearing(station_lat, station_lon, ind.latitude, ind.longitude)
        if not is_upwind(ind_bearing, wind_dir, tolerance=60):
            continue
        
        alignment = 1 - angular_diff(ind_bearing, wind_dir) / 60
        distance_decay = 1 / (1 + dist / 10)
        emission_factor = ind.emission_weight / 100
        
        contribution = alignment * distance_decay * emission_factor * 100
        proximity_score += contribution
        contributing.append({...})
    
    # 3. Combine
    proximity_score = min(50, proximity_score)
    
    # If SO2 data missing, rely more on proximity
    if so2 is None:
        final_score = 0.5 * so2_score + 0.5 * proximity_score
    else:
        final_score = 0.7 * so2_score + 0.3 * proximity_score
    
    return {'score': final_score, 'level': ..., 'facilities': contributing[:5]}
```

### Formula

$$S_{industry} = 0.7 \times S_{SO2} + 0.3 \times \min(50, P)$$

Where SO2 score:
| SO2 (µg/m³) | Score |
|-------------|-------|
| > 40 | 80 |
| > 25 | 50 |
| > 15 | 25 |
| ≤ 15 | 10 |
| missing | 20 |

And proximity:
$$P = \sum_{j \in upwind} \left(1 - \frac{\Delta\theta_j}{60}\right) \times \frac{1}{1 + d_j/10} \times \frac{w_j}{100} \times 100$$

---

## Dust Score

### Algorithm

```python
def calculate_dust_score(pm25, pm10, wind_speed):
    if pm25 is None or pm10 is None or pm10 <= 0:
        return {'score': 15, 'level': 'Unknown', 'ratio': None}
    
    ratio = pm25 / pm10
    
    if ratio > 1:  # sensor error
        return {'score': 15, 'level': 'Unknown', 'ratio': ratio}
    
    # Based on AQMD: dust=0.21, combustion=0.99
    if ratio < 0.3:
        score = 70  # dust dominant
    elif ratio < 0.4:
        score = 50
    elif ratio < 0.5:
        score = 30
    elif ratio < 0.6:
        score = 20
    else:
        score = 10  # combustion dominant
    
    # Wind amplification
    if wind_speed and wind_speed > 5:
        score = min(90, score * 1.3)
    
    return {'score': score, 'level': ..., 'ratio': ratio}
```

### Formula

$$R = \frac{PM2.5}{PM10}$$

| Ratio | Interpretation | Score |
|-------|----------------|-------|
| < 0.3 | Dust dominant | 70 |
| 0.3-0.4 | Significant dust | 50 |
| 0.4-0.5 | Some dust | 30 |
| 0.5-0.6 | Mixed | 20 |
| > 0.6 | Combustion | 10 |

If wind > 5 m/s: multiply by 1.3

---

## Trapping Score

### Algorithm

```python
def calculate_trapping_score(blh):
    if blh is None:
        return {'score': 30, 'level': 'Unknown'}
    
    blh = max(50, blh)  # cap minimum
    
    if blh < 200:
        score, level = 90, 'Severe'
    elif blh < 400:
        score, level = 65, 'High'
    elif blh < 700:
        score, level = 40, 'Medium'
    elif blh < 1000:
        score, level = 20, 'Low'
    else:
        score, level = 10, 'None'
    
    return {'score': score, 'level': level, 'blh': blh}
```

### Formula

| BLH (m) | Score | Level |
|---------|-------|-------|
| < 200 | 90 | Severe |
| 200-400 | 65 | High |
| 400-700 | 40 | Medium |
| 700-1000 | 20 | Low |
| > 1000 | 10 | None |

---

## Normalization

Convert raw scores to percentages:

```python
def normalize(stubble, traffic, industry, dust, trapping):
    total = stubble + traffic + industry + dust + trapping
    if total == 0:
        return {s: 20 for s in ['stubble', 'traffic', 'industry', 'dust', 'trapping']}
    
    return {
        'stubble': stubble / total * 100,
        'traffic': traffic / total * 100,
        'industry': industry / total * 100,
        'dust': dust / total * 100,
        'trapping': trapping / total * 100,
    }
```

$$P_i = \frac{S_i}{\sum_j S_j} \times 100$$

---

# VALIDATION

## Known Events to Test

| Date | Event | Expected Dominant |
|------|-------|-------------------|
| Oct 20-21, 2025 | Diwali | Trapping + local combustion, NOT stubble |
| May 14-15, 2025 | Dust storm | Dust (ratio < 0.4) |
| Nov 1-15, 2025 | Peak stubble | Stubble 30-40% when NW wind |
| Any Monday 9 AM | Rush hour | Traffic peaks |
| Any Sunday 3 AM | Night | Trapping high, traffic low |

## Sanity Checks

1. No source > 60% on average (unlike broken 99.9% industry model)
2. Traffic low at 3 AM (< 10%)
3. Stubble low in summer (< 10%)
4. Percentages sum to 100%

## Correlations to Verify

| Score | Should Correlate With | Expected r |
|-------|----------------------|------------|
| Stubble | Fire count upwind | > 0.5 |
| Traffic | NO2 | > 0.5 |
| Industry | SO2 | > 0.5 |
| Dust | PM ratio (negative) | < -0.4 |
| Trapping | BLH (negative) | < -0.6 |

---

# IMPLEMENTATION NOTES

## Data Loading Strategy

```python
def load_all_data():
    # 1. Load station metadata
    stations = pd.read_csv('data/cleaned/stations_metadata.csv')
    
    # 2. Load industry data
    industries = pd.read_csv('data/cleaned/industries_cleaned.csv')
    
    # 3. Load fire data (filter to current day ± 1 for speed)
    fires = pd.read_csv('data/cleaned/fires_combined.csv')
    fires['acq_date'] = pd.to_datetime(fires['acq_date'])
    
    # 4. Load wind data
    wind = pd.read_csv('data/cleaned/wind_filtered.csv')
    wind['timestamp'] = pd.to_datetime(wind['timestamp'])
    
    # 5. Load station readings (on demand, per station)
    return stations, industries, fires, wind
```

## Processing One Station-Hour

```python
def process_station_hour(station_row, timestamp, readings, wind_row, fires_today, industries):
    # Get coordinates
    lat, lon = station_row['lat'], station_row['lon']
    
    # Get meteorology
    wind_dir = wind_row['wind_dir_10m']  # or wind_dir_180m for transport
    wind_speed = wind_row['wind_speed_10m']
    blh = wind_row['blh']
    
    # Get readings
    pm25 = readings.get('PM25')
    pm10 = readings.get('PM10')
    no2 = readings.get('NO2')
    so2 = readings.get('SO2')
    
    # Calculate scores
    stubble = calculate_stubble_score(lat, lon, wind_dir, blh, fires_today, timestamp.month)
    traffic = calculate_traffic_score(timestamp.hour, timestamp.weekday(), no2, station_row['traffic_factor'])
    industry = calculate_industry_score(lat, lon, wind_dir, so2, industries)
    dust = calculate_dust_score(pm25, pm10, wind_speed)
    trapping = calculate_trapping_score(blh)
    
    # Normalize
    pct = normalize(stubble['score'], traffic['score'], industry['score'], dust['score'], trapping['score'])
    
    return {
        'station': station_row['station_name'],
        'timestamp': timestamp.isoformat(),
        'pm25': pm25,
        'contributions': {
            'stubble': {'percentage': pct['stubble'], 'level': stubble['level']},
            'traffic': {'percentage': pct['traffic'], 'level': traffic['level']},
            'industry': {'percentage': pct['industry'], 'level': industry['level']},
            'dust': {'percentage': pct['dust'], 'level': dust['level']},
            'trapping': {'percentage': pct['trapping'], 'level': trapping['level']},
        },
        'top_fires': stubble.get('fires', []),
        'top_industries': industry.get('facilities', []),
    }
```

## Wind Data Matching

```python
def get_wind_for_station(wind_df, timestamp, station_lat, station_lon):
    """
    Get wind data for a specific hour.
    Use Delhi location for Delhi stations, or nearest location for NCR.
    """
    # Round timestamp to hour
    hour = timestamp.replace(minute=0, second=0, microsecond=0)
    
    # Filter to this hour
    wind_hour = wind_df[wind_df['timestamp'] == hour]
    
    # For Delhi stations (lat 28.4-28.9), use Delhi
    if 28.4 <= station_lat <= 28.9:
        row = wind_hour[wind_hour['wind_location'] == 'Delhi']
        if len(row) > 0:
            return row.iloc[0]
    
    # Otherwise find nearest location
    # ... implement nearest neighbor
    
    return wind_hour.iloc[0]  # fallback to first available
```

---

# EXPECTED OUTPUTS

## Example: Nov 8, 2025, 9:00 AM, Anand Vihar

```json
{
  "station": "Anand Vihar New Delhi - DPCC",
  "timestamp": "2025-11-08T09:00:00+05:30",
  "coordinates": {"lat": 28.6469, "lon": 77.3164},
  "readings": {
    "pm25": 186,
    "pm10": 298,
    "no2": 92,
    "so2": null
  },
  "meteorology": {
    "wind_dir": 287,
    "wind_speed": 2.3,
    "blh": 340
  },
  "contributions": {
    "stubble_burning": {
      "percentage": 38.2,
      "level": "High",
      "fire_count": 89,
      "top_locations": [
        {"region": "Sangrur, Punjab", "fires": 23, "distance_km": 245},
        {"region": "Bathinda, Punjab", "fires": 18, "distance_km": 280}
      ]
    },
    "traffic": {
      "percentage": 25.1,
      "level": "Medium",
      "explanation": "Rush hour (9 AM, Monday), NO2=92 µg/m³"
    },
    "industry": {
      "percentage": 11.8,
      "level": "Low",
      "explanation": "SO2 data unavailable, using proximity only"
    },
    "dust": {
      "percentage": 8.9,
      "level": "Low",
      "pm_ratio": 0.62,
      "explanation": "Ratio indicates combustion, not dust"
    },
    "meteorological_trapping": {
      "percentage": 16.0,
      "level": "High",
      "blh": 340,
      "explanation": "BLH at 340m trapping pollutants"
    }
  },
  "summary": "Dominant: stubble burning (38%). Wind from NW carrying smoke from 89 active fires in Punjab."
}
```

---

# DEPENDENCIES

```
pandas>=2.0
numpy>=1.24
scipy>=1.10  # for correlations in validation
# Optional for API:
flask>=2.3
# or fastapi>=0.100
```

---

# QUICK START

```python
# 1. Load data
import pandas as pd

stations = pd.read_csv('data/cleaned/stations_metadata.csv')
industries = pd.read_csv('data/cleaned/industries_cleaned.csv')
fires = pd.read_csv('data/cleaned/fires_combined.csv')
wind = pd.read_csv('data/cleaned/wind_filtered.csv')

# 2. Pick a station and time
station = stations[stations['station_name'].str.contains('Anand Vihar')].iloc[0]
timestamp = pd.Timestamp('2025-11-08 09:00:00')

# 3. Load station readings
readings_df = pd.read_csv(f"data/raw/station_data/{station['filename']}")
readings_df['Local Time'] = pd.to_datetime(readings_df['Local Time'])
readings = readings_df[readings_df['Local Time'].dt.floor('h') == timestamp].iloc[0].to_dict()

# 4. Get wind data
wind['timestamp'] = pd.to_datetime(wind['timestamp'])
wind_row = wind[(wind['timestamp'] == timestamp) & (wind['wind_location'] == 'Delhi')].iloc[0]

# 5. Filter fires to that day
fires['acq_date'] = pd.to_datetime(fires['acq_date'])
fires_today = fires[fires['acq_date'].dt.date == timestamp.date()]

# 6. Calculate attribution
result = process_station_hour(station, timestamp, readings, wind_row, fires_today, industries)
print(result)
```



