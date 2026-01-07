# Delhi NCR Pollution Source Attribution System
## Complete Documentation

**Version:** 2.1  
**Last Updated:** January 7, 2026  
**Project:** SIH 2025 - Delhi NCR Pollution Source Predictor

---

# Table of Contents

1. [Project Overview](#1-project-overview)
2. [Project Structure & File Reference](#2-project-structure--file-reference)
3. [Data Sources](#3-data-sources)
4. [Core Algorithms](#4-core-algorithms)
5. [Modulation Engine](#5-modulation-engine)
6. [API Reference](#6-api-reference)
7. [Dashboard Guide](#7-dashboard-guide)
8. [Validation & Testing](#8-validation--testing)
9. [Scientific References](#9-scientific-references)

---

# 1. Project Overview

## 1.1 What This System Does

This system identifies **which pollution sources are contributing to air quality readings** at any CPCB monitoring station in Delhi-NCR at any given time. It outputs **percentage contributions** from 6 sources:

| Source | Description |
|--------|-------------|
| **Stubble Burning** | Crop residue fires from Punjab/Haryana (transported via NW winds) |
| **Traffic** | Vehicle emissions (local, indicated by NO2 levels) |
| **Industry** | Power plants, factories (indicated by SO2 levels) |
| **Dust** | Road dust, soil, construction (indicated by PM2.5/PM10 ratio) |
| **Local Combustion** | Fireworks, waste burning, domestic heating |
| **Secondary Aerosols** | Formed in atmosphere; trapping indicated by low BLH |

## 1.2 Methodology

The system uses a **Validated Prior + Anomaly Modulation** approach:

1. **Baseline Priors**: Use scientifically validated source percentages from ARAI/TERI 2018 receptor modeling study
2. **Real-time Modulation**: Adjust priors based on current sensor readings vs. historical baselines
3. **Normalization**: Convert modulated values to percentages that sum to 100%

## 1.3 Example Output

```json
{
  "contributions": {
    "stubble_burning": {"percentage": 27.2, "level": "High"},
    "traffic": {"percentage": 17.4, "level": "Medium"},
    "secondary_aerosols": {"percentage": 34.3, "level": "High"},
    "dust": {"percentage": 10.8, "level": "Low"},
    "industry": {"percentage": 7.9, "level": "Low"},
    "local_combustion": {"percentage": 2.3, "level": "Low"}
  },
  "summary": "Primary sources: Secondary Aerosols (34%), Stubble Burning (27%)"
}
```

---

# 2. Project Structure & File Reference

```
source_prediction/
├── app/                          # Flask API
│   └── app.py                    # REST API server
├── dashboard/                    # Web frontend
│   ├── index.html                # Main HTML structure
│   ├── app.js                    # Frontend JavaScript
│   └── styles.css                # CSS styling
├── data/                         # Data storage
│   ├── cleaned/                  # Processed data
│   │   ├── stations_metadata.csv
│   │   ├── fires_combined.csv
│   │   ├── industries_cleaned.csv
│   │   ├── wind_filtered.csv
│   │   └── wind_stations.csv
│   └── raw/
│       └── station_data/         # 62 station CSV files
├── docs/                         # Documentation
│   └── DOCUMENTATION.md          # This file
├── src/                          # Core engine code
│   ├── __init__.py               # Package exports
│   ├── data_engine.py            # Data loading
│   ├── geo_utils.py              # Geographic utilities
│   ├── modulation_engine.py      # Attribution engine
│   └── outfall_engine.py         # Dispersion prediction
├── README.md                     # Quick start guide
├── requirements.txt              # Dependencies
├── test_comprehensive_attribution.py  # Test suite
├── backfill_wind.py              # Historical wind data backfiller
├── update_fires.py               # Live fire data fetcher (NASA FIRMS)
└── fetch_cpcb_live.py            # Live CPCB data fetcher (Standalone)
```

## 2.1 Source Code (`src/`)

### `src/__init__.py`
**Purpose**: Package initializer that exports the main classes and functions.

**Exports**:
- `DataEngine` - Data loading class
- `calculate_modulated_attribution` - Main attribution function
- `haversine`, `bearing`, `angular_diff`, `is_upwind` - Geographic utilities

---

### `src/geo_utils.py`
**Purpose**: Geographic calculation utilities for distance, direction, and upwind checks.

**Functions**:

| Function | Description |
|----------|-------------|
| `haversine(lat1, lon1, lat2, lon2)` | Calculate great-circle distance in km between two points |
| `bearing(lat1, lon1, lat2, lon2)` | Calculate initial bearing (0-360°, 0=North) from point 1 to point 2 |
| `angular_diff(angle1, angle2)` | Calculate smallest angle between two bearings (handles 360° wrap) |
| `is_upwind(source_bearing, wind_direction, tolerance=45)` | Check if source is within the upwind cone |

**Key Formulas**:

```
Haversine:
  a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlon/2)
  c = 2 × atan2(√a, √(1-a))
  distance = 6371 × c  (km)

Bearing:
  θ = atan2(sin(Δlon) × cos(lat2), cos(lat1) × sin(lat2) - sin(lat1) × cos(lat2) × cos(Δlon))
  bearing = (θ × 180/π + 360) mod 360
```

---

### `src/data_engine.py`
**Purpose**: Loads and manages all data sources for attribution calculations.

**Class: `DataEngine`**

| Method | Description |
|--------|-------------|
| `__init__(industries_path, fires_path, stations_path, wind_path)` | Load all data files |
| `get_station(name)` | Find station by name (partial match) |
| `get_wind(timestamp, lat, lon, station_id)` | Get wind data for a station at a time |
| `get_fires(dt, lookback_hours=48)` | Get fires from past N hours |
| `get_fire_region_wind(timestamp)` | Get wind from Punjab region |

**Data Loaded**:
- 62 monitoring stations
- 2,906 industrial facilities
- 49,171 fire hotspots
- ~400,000 hourly wind records

---

### `src/modulation_engine.py`
**Purpose**: **Core attribution engine** using validated priors + real-time modulation.

**Main Function**: `calculate_modulated_attribution(timestamp, readings, wind_dir, wind_speed, blh, fire_count)`

**Modulation Functions**:

| Function | Tracer | Baseline |
|----------|--------|----------|
| `calculate_traffic_modulation(no2, hour)` | NO2 | 100 µg/m³ (rush), 71 (day), 40 (night) |
| `calculate_stubble_modulation(fire_count, wind_dir, month)` | Fire count | 193 fires/day |
| `calculate_secondary_modulation(blh, month)` | BLH | 381m (winter), 1106m (summer) |
| `calculate_industry_modulation(so2)` | SO2 | 15 µg/m³ |
| `calculate_dust_modulation(pm25, pm10, wind_speed)` | PM ratio | 0.625 |
| `calculate_local_combustion_modulation(hour, month, co, pm25, pm10, wind_speed)` | PM + CO | Seasonal averages |

**Validated Priors** (ARAI/TERI 2018, Page 396):

| Source | Prior % |
|--------|---------|
| Traffic | 22% |
| Stubble Burning | 22% |
| Secondary Aerosols | 26% |
| Dust | 15% |
| Industry | 12% |
| Local Combustion | 4% |

---

### `src/outfall_engine.py`
**Purpose**: Predicts where pollution will travel using a Gaussian-advection hybrid model.

**Functions**:

| Function | Description |
|----------|-------------|
| `simulate_outfall(lat, lon, wind_speed, wind_dir, hours=3)` | Predict downwind locations |
| `gaussian_intensity(distance_km, wind_speed, blh)` | Calculate concentration decay |
| `wind_to_vector(speed, direction_deg)` | Convert wind to dx, dy components |

---

## 2.2 API Server (`app/`)

### `app/app.py`
**Purpose**: Flask REST API serving the dashboard and providing data endpoints.

**Server Configuration**:
- Host: `0.0.0.0:5000`
- Static folder: `../dashboard`
- CORS enabled

See [API Reference](#6-api-reference) for endpoint details.

---

## 2.3 Dashboard (`dashboard/`)

### `dashboard/index.html`
**Purpose**: Main HTML structure for the web dashboard.

**Components**:
- Header with date/hour selectors
- Leaflet map container
- Side panel with:
  - Station name and confidence badge
  - Outfall forecast
  - Current readings (PM2.5, PM10, NO2, SO2, CO)
  - Attribution pie chart
  - Source details with explanations
  - Contributing industries list
  - Fire hotspots list
  - Meteorology display (wind, BLH)
  - Top source & recommended actions

---

### `dashboard/app.js`
**Purpose**: Frontend JavaScript (~1170 lines) handling all interactivity.

**Key Features**:
- Map initialization (Leaflet with dark theme)
- Station markers with AQI-based coloring
- Fire and industry overlays
- India AQI calculation (CPCB breakpoints)
- Attribution pie chart (Chart.js)
- Outfall visualization on map
- Policy recommendations based on top source

**AQI Breakpoints** (India CPCB):

| PM2.5 (µg/m³) | AQI | Category |
|---------------|-----|----------|
| 0-30 | 0-50 | Good |
| 31-60 | 51-100 | Satisfactory |
| 61-90 | 101-200 | Moderate |
| 91-120 | 201-300 | Poor |
| 121-250 | 301-400 | Very Poor |
| 251+ | 401-500 | Severe |

---

### `dashboard/styles.css`
**Purpose**: Modern dark theme CSS with glassmorphism effects.

**Features**:
- Dark color scheme (`#0a0a0f` background)
- Glassmorphism cards with blur effects
- Custom Leaflet popup styling
- Responsive design for mobile
- Animations for panel content

---

## 2.4 Data Files (`data/`)

### `data/cleaned/stations_metadata.csv`
**Purpose**: CPCB monitoring station metadata.

| Column | Description |
|--------|-------------|
| `station_id` | Unique identifier |
| `station_name` | Full station name |
| `filename` | Corresponding data file |
| `lat`, `lon` | Coordinates |
| `has_pm25`, `has_no2`, `has_so2` | Sensor availability |
| `traffic_factor` | Traffic exposure (0.4-1.2) |

---

### `data/cleaned/fires_combined.csv`
**Purpose**: VIIRS satellite fire detections (Feb-Dec 2025).

| Column | Description |
|--------|-------------|
| `latitude`, `longitude` | Fire location |
| `acq_date`, `timestamp` | Detection time |
| `frp` | Fire Radiative Power (MW) |
| `confidence` | Detection confidence |

**Statistics**: 49,171 fires, peak in Oct-Nov (stubble season)

---

### `data/cleaned/industries_cleaned.csv`
**Purpose**: Industrial facilities with emission estimates.

| Column | Description |
|--------|-------------|
| `latitude`, `longitude` | Facility location |
| `facility_type` | power_plant / wte_plant / industry |
| `emission_weight` | Relative importance (3-100) |

**Emission Weights**:
- 100: Thermal power plants (14)
- 30: Waste-to-Energy plants (5)
- 20: Captive power (688)
- 5-15: Other industries

---

### `data/cleaned/wind_filtered.csv`
**Purpose**: Regional hourly meteorology from ERA5.

| Column | Description |
|--------|-------------|
| `timestamp` | Hour |
| `wind_location` | Amritsar, Delhi, etc. |
| `wind_dir_10m`, `wind_speed_10m` | Surface wind |
| `blh` | Boundary Layer Height (m) |

---

### `data/cleaned/wind_stations.csv`
**Purpose**: Station-specific wind data (OpenMeteo Archive).

~400,000 records for 57 stations with hourly wind and BLH.

---

### `data/raw/station_data/`
**Purpose**: Raw hourly readings from 62 CPCB stations.

Columns vary but typically include: PM25, PM10, NO2, SO2, CO, O3, etc.

---

## 2.5 Other Files

### `README.md`
Quick-start guide with algorithms, data structures, and example outputs.

### `requirements.txt`
Python dependencies: pandas, numpy, flask, flask-cors

### `test_comprehensive_attribution.py`
12 real-data test cases validating the attribution system against known events (Diwali, stubble peak, inversions).

### `fetch_wind_data.py`
Utility to fetch historical wind data from OpenMeteo Archive API.

---

# 3. Data Sources

## 3.1 Air Quality Data
- **Source**: Central Pollution Control Board (CPCB)
- **Stations**: 62 monitoring stations in Delhi-NCR
- **Parameters**: PM2.5, PM10, NO2, SO2, CO, O3
- **Historical Coverage**: Feb 2025 - Dec 2025 (CSV files)
- **Live Coverage**: Real-time via CPCB RSS Feed (`/live` endpoint)

## 3.2 Fire Data
- **Source**: NASA VIIRS (Visible Infrared Imaging Radiometer Suite)
- **Access**: NASA FIRMS (Fire Information for Resource Management)
- **Parameters**: Location, FRP, acquisition time
- **Historical Coverage**: Feb 2025 - Dec 2025 (Cached in `fires_combined.csv`)
- **Live Coverage**: Real-time via `update_fires.py` (NASA FIRMS API)

## 3.3 Meteorology
- **Source**: ERA5 Reanalysis (Copernicus), OpenMeteo Archive
- **Parameters**: Wind direction, wind speed, BLH
- **Historical Coverage**: Feb 2025 - Dec 2025
- **Live Coverage**: Real-time via OpenMeteo Forecast API (`/live` endpoint)

## 3.4 Industries
- **Source**: Manual compilation + official sources
- **Facilities**: Power plants, WTE, industrial clusters
- **Parameters**: Location, type, estimated emissions

---

# 4. Core Algorithms

## 4.1 Geographic Calculations

### Haversine Distance
```python
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
    φ1, φ2 = radians(lat1), radians(lat2)
    Δφ = radians(lat2 - lat1)
    Δλ = radians(lon2 - lon1)
    
    a = sin(Δφ/2)² + cos(φ1) × cos(φ2) × sin(Δλ/2)²
    c = 2 × atan2(√a, √(1-a))
    return R × c
```

### Upwind Check
```python
def is_upwind(source_bearing, wind_direction, tolerance=45):
    diff = angular_diff(source_bearing, wind_direction)
    return diff <= tolerance
```

Wind direction = direction wind is coming FROM (meteorological convention).

---

## 4.2 Source Tracers

| Source | Primary Tracer | Scientific Basis |
|--------|---------------|------------------|
| Traffic | NO2 | WHO REVIHAAP: "NO2 is predominantly produced by vehicle emissions in urban areas" |
| Industry | SO2 | US EIA: "Coal-fired power plants are largest SO2 source"; vehicles emit negligible SO2 |
| Dust | PM2.5/PM10 ratio | SCAQMD: Dust ratio ~0.21, combustion ratio ~0.99 |
| Stubble | Fire count + wind | Direct satellite observation from NW direction |
| Trapping | BLH | Basic atmospheric physics: lower BLH = less mixing volume |

---

## 4.3 Normalization

```python
# Apply modulation to priors
weighted = {source: prior × modulation for source in sources}

# Normalize to 100%
total = sum(weighted.values())
percentages = {source: (w / total) × 100 for source, w in weighted.items()}
```

---

# 5. Modulation Engine

## 5.1 Concept

Instead of calculating raw scores, we modulate validated baseline percentages:

```
Modulation_Factor = Current_Value / Baseline_Value
Weighted_Prior = Base_Prior × Modulation_Factor
Final_Percentage = Normalize(Weighted_Prior)
```

## 5.2 Baselines (Computed from Data)

| Baseline | Value | Source |
|----------|-------|--------|
| BLH (winter) | 381 m | wind_filtered.csv |
| BLH (summer) | 1106 m | wind_filtered.csv |
| Fires (stubble season) | 193/day | fires_combined.csv |
| NO2 (rush hour) | 100 µg/m³ | IIT Kanpur 2016 |
| NO2 (overall) | 71 µg/m³ | IIT Kanpur 2016 |
| SO2 (average) | 15 µg/m³ | IIT Kanpur 2016 |
| PM ratio | 0.625 | IIT Kanpur 2016 |

## 5.3 Modulation Caps

All modulation factors are capped to prevent extreme values:
- Traffic: 0.3x - 3.0x
- Stubble: 0.0x - 5.0x
- Secondary: 0.5x - 2.0x
- Industry: 0.3x - 3.0x
- Dust: 0.3x - 3.0x
- Local Combustion: 0.3x - 10.0x (higher for Diwali)

---

# 6. API Reference

## 6.1 Endpoints

### `GET /`
Serve the dashboard.

### `GET /stations`
Get all monitoring stations.

**Response**:
```json
{
  "count": 62,
  "stations": [
    {"station_id": 10484, "station_name": "...", "lat": 28.535, "lon": 77.19, ...}
  ]
}
```

---

### `POST /attribution`
Calculate source attribution for a station and timestamp.

**Request**:
```json
{
  "station": "Anand Vihar",
  "timestamp": "2025-11-08T09:00:00",
  "readings": {"PM25": 200, "PM10": 350, "NO2": 120, "SO2": 15, "CO": 1.2}
}
```

**Response**:
```json
{
  "contributions": {...},
  "meteorology": {"wind_dir": 273, "wind_speed": 3.8, "blh": 175},
  "outfall": [...],
  "summary": "Primary sources: ...",
  "confidence": "High"
}
```

---

### `POST /attribution/modulated`
Direct access to modulation engine (bypasses station lookup).

**Request**: Same as `/attribution` but with explicit wind_dir, wind_speed, blh, fire_count.

---

### `GET /station/<id>/data`
Get historical readings for a station.

**Query params**: `start_date`, `end_date`, `limit`

---

### `GET /fires`
Get fire hotspots.

**Query params**: 
- `timestamp` - Get fires from past 24h for time-lagged attribution
- `date` - Get fires for a specific date
- `lookback` - Hours to look back (default 24)

---

### `GET /industries`
Get major industrial emitters (emission_weight >= 15).

---

### `GET /station/<id>/industries`
Get nearby industries ranked by contribution potential.

**Query params**: `wind_direction` (optional, for upwind filtering)

---

### `GET /meteorology`
Get wind/BLH data.

**Query params**: `timestamp` (optional)

---

### `POST /outfall`
Predict pollution dispersion.

**Request**:
```json
{"lat": 28.65, "lon": 77.31, "wind_speed": 5, "wind_dir": 270, "blh": 300, "PM25": 200}
```

---

# 7. Dashboard Guide

## 7.1 Map View
- **Station Markers**: Color-coded by AQI (green → maroon)
- **Fire Hotspots**: Orange circles (size = FRP)
- **Industries**: Gray circles (size = emission weight)
- **Outfall Path**: Animated points showing predicted pollution trajectory

## 7.2 Side Panel (after clicking a station)
1. **Station Name & Confidence Badge**
2. **Outfall Forecast**: Where pollution will travel
3. **Current Readings**: PM2.5, PM10, NO2, SO2, CO with units
4. **Attribution Chart**: Doughnut chart of source percentages
5. **Source Details**: Each source with percentage, level, and explanation
6. **Industries**: Nearby facilities ranked by contribution
7. **Fires**: Top fire hotspots (if stubble season)
8. **Meteorology**: Wind direction, speed, BLH
9. **Top Source & Actions**: Policy recommendations

## 7.3 Controls
- **Date Picker**: Select analysis date
- **Hour Dropdown**: Select hour (0-23)
- **Analyze Button**: Refresh analysis

---

# 8. Validation & Testing

## 8.1 Test Suite

`test_comprehensive_attribution.py` contains 12 test cases using real data:

| Test | Date | Scenario | Expected Result |
|------|------|----------|-----------------|
| 1 | Feb 27 | Cold winter morning | High secondary (severe BLH=105m) |
| 2 | Mar 9 | Pre-monsoon afternoon | Balanced (good BLH=2100m) |
| 3 | May 16 | Summer afternoon | Low stubble (wrong season) |
| 4 | Aug 22 | Monsoon morning | Low stubble (washout) |
| 5 | Sep 14 | Post-monsoon night | High secondary |
| 6 | Oct 19 | Early stubble season | High secondary (BLH=100m) |
| 7 | Oct 21 | **Diwali peak** | High secondary, fireworks detected |
| 8 | Nov 8 | **Peak stubble** | High stubble + traffic |
| 9 | Nov 1 | Wedding season night | High secondary |
| 10 | Dec 2 | Severe winter inversion | Extreme secondary (BLH=70m) |
| 11 | Dec 2 | Industrial morning | High traffic |
| 12 | Nov 5 | High fires, EAST wind | Low stubble (wrong wind!) |

## 8.2 Run Tests

```bash
# Start API server
python3 app/app.py

# In another terminal
python3 test_comprehensive_attribution.py
```

## 8.3 Sanity Checks
- ✅ Percentages sum to 100%
- ✅ No source > 60% on average
- ✅ Traffic low at 3 AM
- ✅ Stubble low in summer
- ✅ Stubble low with east wind

---

# 9. Scientific References

## 9.1 Primary Sources

1. **ARAI & TERI (2018)**. "Source Apportionment of PM2.5 & PM10 of Delhi NCR for Identification of Major Sources." Chapter 4, Section 4.4.1, Page 396.
   - Source priors: Traffic 22%, Stubble 22%, Secondary 26%, Dust 15%, Industry 12%, Others 4%

2. **IIT Kanpur (2016)**. "Comprehensive Study on Air Pollution and Green House Gases (GHGs) in Delhi." Department of Environment, Government of NCT of Delhi.
   - NO2 baselines: Winter 83 µg/m³, Summer 59 µg/m³
   - PM2.5/PM10 ratio: 0.625

## 9.2 Supporting Literature

3. **WHO REVIHAAP (2013)**. Review of Evidence on Health Aspects of Air Pollution.
   - NO2 as traffic tracer

4. **U.S. EIA (2018)**. Sulfur dioxide emissions from power plants.
   - SO2 as industrial tracer

5. **South Coast AQMD (2006)**. PM2.5 Calculation Methodology.
   - PM2.5/PM10 ratio: Dust 0.21, Combustion 0.99

6. **CPCB (2009)**. National Ambient Air Quality Standards.
   - Regulatory thresholds

## 9.3 Data Sources

7. **NASA VIIRS/FIRMS** - Fire hotspot detection
8. **ERA5 Reanalysis** - Wind and BLH data
9. **CPCB OpenAQ** - Air quality monitoring data

---

# Appendix: Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start server
python3 app/app.py

# 3. Open browser
http://localhost:5000

# 4. Click any station marker on the map
```

---

# 10. Live Data System

**Added in Version 2.1 (Jan 2026)**

The system now supports real-time source attribution using a hybrid data approach.

## 10.1 Architecture

The **Live Mode** is activated via the "🔴 Live" button on the dashboard. It bypasses the historical CSV lookups and fetches fresh data from three live sources:

| Component | Source | Method | Update Freq |
|-----------|--------|--------|-------------|
| **Air Quality** | CPCB RSS Feed | `requests.get` in `/live` | Real-time |
| **Meteorology** | OpenMeteo API | `requests.get` in `/live` | Real-time |
| **Fires** | NASA FIRMS API | `update_fires.py` script | Periodic (Background) |

## 10.2 Components

### 1. `/live` Endpoint (`app.py`)
- **Function**: Aggregates data from all sources.
- **Logic**:
  1. Fetches CPCB RSS feed (XML).
  2. Matches RSS station names to local metadata using fuzzy string matching.
  3. Fetches live wind/BLH from OpenMeteo for Delhi coordinates.
  4. Reloads fire data from disk to get latest NASA FIRMS updates.
  5. Returns a unified JSON object with readings, meteorology, and fire counts.

### 2. Fire Updater (`update_fires.py`)
- **Function**: Background script to keep fire data fresh.
- **Logic**:
  1. Queries NASA FIRMS API (VIIRS) for North India bounding box (`70,25,85,35`).
  2. Fetches last 24 hours of fire hotspots.
  3. Appends new unique fires to `data/cleaned/fires_combined.csv`.
  4. Deduplicates based on location and time.

> [!IMPORTANT]
> **Fire Data Freshness**: 
> The `/live` endpoint reads from the local fire database. To ensure accurate real-time attribution (especially during stubble burning season), you must run the update script periodically.
> 
> **Run Periodically (e.g., Weekly):**
> ```bash
> python3 update_fires.py
> ```
> *This fetches the last 7 days of fire data to fill any gaps.*

### 3. Frontend Integration (`app.js`)
- **Event**: Clicking "Live" button triggers `handleLiveData()`.
- **Action**:
  1. Calls `/live` API.
  2. Updates all map markers with current AQI colors.
  3. Updates date/time inputs to "Now".
  4. If a station is selected, calls `/attribution/modulated` with the **live meteorology** and **live fire count** explicitly passed in the payload.
  5. Updates all charts and panels with the real-time attribution results.

---

**End of Documentation**
