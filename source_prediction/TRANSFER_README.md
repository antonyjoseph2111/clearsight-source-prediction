# Delhi Air Pollution Source Attribution - Transfer Package

## For New Claude Session

This package contains everything needed to continue development of the Delhi-NCR
air pollution source attribution system.

## CRITICAL CONTEXT

### What This Project Does
A physics-based source attribution system that identifies contributions from 
6 pollution sources for any station/time in Delhi-NCR:
1. **Stubble Burning** - Crop fires transported from Punjab/Haryana
2. **Traffic** - Vehicle emissions (NO2 is primary indicator)
3. **Industry** - Power plants, factories (SO2 is primary indicator)
4. **Dust** - Road/soil/construction (PM2.5/PM10 ratio)
5. **Local Combustion** - Fireworks, waste burning, domestic heating
6. **Secondary Aerosols** - Formed in atmosphere from precursor gases

### Why Previous Models Failed

**Original Model (BROKEN):** 99.9% Industry attribution
- Used 4,700 dense industry points with IDW
- Summed ALL contributions regardless of wind direction
- Feature importance ≠ source attribution

**First Fix (STILL WRONG):** 34% "Trapping" 
- Treated low BLH as a source category
- "Trapping" is a MECHANISM, not a SOURCE
- You cannot regulate Boundary Layer Height

**Current Model (CORRECT):** 6 real sources only
- BLH is explanatory context, not a source
- Chemistry-based attribution (NO2→traffic, SO2→industry, etc.)
- Special event handling (Diwali, dust storms)

## Quick Start

```python
from src.attribution_engine_expanded import ExpandedSourceAttributionEngine

engine = ExpandedSourceAttributionEngine(
    industries_path='data/cleaned/industries_cleaned.csv',
    fires_path='data/cleaned/fires_combined.csv',
    stations_path='data/cleaned/stations_metadata.csv',
    wind_path='data/cleaned/wind_filtered.csv'
)

# Normal November morning
result = engine.calculate_attribution(
    'Anand Vihar',
    '2025-11-08 09:00:00',
    {'PM25': 186, 'PM10': 298, 'NO2': 92, 'SO2': 15, 'CO': 1.5}
)

# Diwali night (local combustion should be high)
diwali = engine.calculate_attribution(
    'Anand Vihar',
    '2025-10-20 22:00:00',
    {'PM25': 450, 'PM10': 520, 'NO2': 65, 'SO2': 20, 'CO': 3.5}
)
```

## Files in This Package

```
├── src/
│   ├── attribution_engine_expanded.py  # MAIN - Use this!
│   ├── attribution_engine.py           # Copy of expanded
│   ├── geo_utils.py                    # Haversine, bearing
│   ├── stubble_score.py
│   ├── traffic_score.py
│   ├── industry_score.py
│   ├── dust_score.py
│   └── trapping_score.py               # (Legacy, for reference)
├── data/
│   ├── cleaned/
│   │   ├── industries_cleaned.csv      # 2,906 facilities
│   │   ├── fires_combined.csv          # 49,171 fires
│   │   ├── stations_metadata.csv       # 62 stations
│   │   └── wind_filtered.csv           # Hourly met data
│   └── raw/station_data/               # 62 station CSVs
├── docs_COMPLETE_METHODOLOGY.md        # All formulas
├── docs_METHODOLOGY_WITH_SOURCES.md    # Scientific citations
├── test_attribution.py                 # Run this to verify
└── README.md                           # This file
```

## Key Chemical Signatures

| Pollutant | Indicates | Threshold |
|-----------|-----------|-----------|
| NO2 | Traffic | >80 µg/m³ = high |
| SO2 | Industry | >35 µg/m³ = high |
| CO/NOx ratio | Traffic vs Biomass | <15 = traffic, >40 = biomass |
| PM2.5/PM10 | Dust vs Combustion | <0.3 = dust, >0.6 = combustion |

## Special Events

- **Diwali 2025:** Oct 20-22 (peak), Oct 17-25 (extended)
- **Wedding Season:** Nov-Feb (more nighttime fireworks)
- **Dust storms:** May-June (check PM ratio)

## What Still Needs To Be Done

1. **Build API** - REST endpoints for querying attribution
2. **Build Dashboard** - Map visualization with station popups
3. **Batch Processing** - Process all stations for a date range
4. **Validation** - Test against known events
5. **Connect to CPCB API** - Real-time data fetching

## Contact

This is a student project for Delhi-NCR air pollution forecasting.
