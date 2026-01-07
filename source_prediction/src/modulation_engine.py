"""
Validated Prior + Anomaly Modulation Attribution Engine

VERIFIED SOURCE CITATIONS:
=========================
1. ARAI & TERI (2018). "Source Apportionment of PM2.5 & PM10 of Delhi NCR 
   for Identification of Major Sources." Report No. ARAI/16-17/DHI-SA-NCR.
   Department of Heavy Industry, Ministry of Heavy Industries, New Delhi.
   - Source priors: Chapter 4, Section 4.4.1, Page 396

2. Sharma, M. & Dikshit, O. (2016). "Comprehensive Study on Air Pollution 
   and Green House Gases (GHGs) in Delhi." IIT Kanpur. 
   Prepared for Delhi Pollution Control Committee.
   - Winter source summary: Executive Summary, Page ix

3. BLH & Fire baselines computed from project data files:
   - wind_filtered.csv (BLH seasonal averages)
   - fires_combined.csv (fire count statistics)

Methodology:
1. Use validated priors from ARAI/TERI receptor modeling (PM2.5 Winter)
2. Compute modulation factors from real-time signals vs baselines
3. Normalize modulated contributions to 100%
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional, Union

# =============================================================================
# VALIDATED BASELINES
# =============================================================================
# Sources verified from project data files

BASELINES = {
    # BLH baselines - VERIFIED from wind_filtered.csv (computed seasonal averages)
    'blh_winter_avg': 381,     # Nov-Feb average (meters) - from data
    'blh_summer_avg': 1106,    # Mar-May average - from data
    'blh_monsoon_avg': 669,    # Jun-Oct average - from data
    
    # Fire baselines - VERIFIED from fires_combined.csv (computed statistics)
    'fires_daily_avg': 183,           # Overall daily average - from data
    'fires_stubble_season_avg': 193,  # Oct-Nov daily average - from data
    'fires_stubble_peak': 529,        # Peak day in stubble season - from data
    
    # NO2 baselines - VERIFIED from IIT Kanpur 2016 study
    # Source: 1576211826iitk.pdf, Chapter 2, Section 2.4.7.2
    # Quote: "The overall average NO2 concentration estimated was 83µg/m3 for winter 
    #         and 59 µg/m3 for summer season (Table 2.14 (a) and (c))"
    'no2_overall_avg': 71,      # μg/m³ annual average ((83+59)/2 from IIT Kanpur 2016)
    'no2_winter_avg': 83,       # μg/m³ winter average (IIT Kanpur 2016, Section 2.4.7.2)
    'no2_summer_avg': 59,       # μg/m³ summer average (IIT Kanpur 2016, Section 2.4.7.2)
    'no2_rush_hour_avg': 100,   # μg/m³ estimated rush hour (based on OKH winter 101 µg/m³)
    'no2_night_avg': 40,        # μg/m³ estimated night (approx 50% of daytime)
    
    # SO2 baseline - from IIT Kanpur 2016 study
    # Source: Chapter 2 states "SO2 concentrations were low and meets the air quality standard"
    # NAAQS standard is 80 µg/m³, typical values described as "low" ~10-20 µg/m³
    # Note: No specific average given in study, using conservative estimate
    'so2_avg': 15,  # μg/m³ estimated (study notes SO2 was consistently low)
    
    # PM2.5 baselines - VERIFIED from Anand Vihar 2025 station data
    # Computed seasonal averages from 235_Anand Vihar New Delhi - DPCC.csv
    'pm25_winter_avg': 228,        # Nov-Feb average (µg/m³) - from data
    'pm25_summer_avg': 80,         # Mar-May average - from data
    'pm25_monsoon_avg': 49,        # Jun-Sep average - from data
    'pm25_postmonsoon_avg': 139,   # Oct average - from data (includes Diwali!)
    
    # PM10 baselines - Derived from PM2.5 using PM2.5/PM10 ratio of 0.625
    # Source: IIT Kanpur 2016 states PM10 winter avg ~600 µg/m³ (375/600 = 0.625 ratio)
    'pm10_winter_avg': 365,        # 228 / 0.625 = 365 µg/m³
    'pm10_summer_avg': 128,        # 80 / 0.625 = 128 µg/m³
    'pm10_monsoon_avg': 78,        # 49 / 0.625 = 78 µg/m³
    'pm10_postmonsoon_avg': 222,   # 139 / 0.625 = 222 µg/m³
    
    # PM ratio baseline - VERIFIED from IIT Kanpur 2016 study
    # Source: 1576211826iitk.pdf, Executive Summary
    # Quote: "overall average concentration of PM2.5 in winter is 375 µg/m3"
    # Quote: "overall average concentration of PM10 in winter season is around 600 µg/m3"
    # Computed: 375/600 = 0.625
    'pm_ratio_avg': 0.625,  # PM2.5/PM10 winter ratio (computed from IIT Kanpur 2016)
}

# =============================================================================
# SOURCE PRIORS - VERIFIED FROM ARAI/TERI 2018 STUDY
# =============================================================================
# Source: Report_SA_AQM-Delhi-NCR_0.pdf, Chapter 4, Section 4.4.1, Page 396
# Values are for PM2.5 Winter Season (Delhi NCR average)
# 
# Original text from Page 396:
# "Average of estimated contribution from vehicles towards PM2.5 in winter season was
# found to be 22% ± 4% (35±15 µg/m3). Similarly, contribution of dust and construction
# was 15% ± 7% (24 ± 14 µg/m3), biomass burning 22% ± 4% (34 ± 12 µg/m3), industry 12%
# ± 7% (20 ± 18 µg/m3), secondary particulates 26% ± 7% (40 ± 15 µg/m3), and others 4%
# ± 4% (7 ± 7 µg/m3)."

PRIORS = {
    # Vehicles: 22% ± 4% (Page 396, ARAI/TERI 2018)
    'traffic': 0.22,
    
    # Industry: 12% ± 7% (Page 396, ARAI/TERI 2018)
    'industry': 0.12,
    
    # Dust and construction: 15% ± 7% (Page 396, ARAI/TERI 2018)
    'dust': 0.15,
    
    # Biomass burning: 22% ± 4% (Page 396, ARAI/TERI 2018)
    # Note: This includes stubble burning + other biomass
    'stubble_burning': 0.22,
    
    # Secondary particulates: 26% ± 7% (Page 396, ARAI/TERI 2018)
    'secondary_aerosols': 0.26,
    
    # Others (DG sets, cooking, etc.): 4% ± 4% (Page 396, ARAI/TERI 2018)
    # Note: Renamed from 'local_combustion' for accuracy
    'local_combustion': 0.04,
}

# Verification: Priors sum to 101% due to rounding in original study
# 22 + 12 + 15 + 22 + 26 + 4 = 101%
# This is acceptable as original values have ± error ranges

# =============================================================================
# MODULATION FACTOR CALCULATORS
# =============================================================================

def calculate_traffic_modulation(no2: Optional[float], hour: int) -> tuple:
    """
    Traffic modulation based on NO2 anomaly.
    M = Current_NO2 / Baseline_NO2
    """
    # Get hour-appropriate baseline
    if hour in [7, 8, 9, 10, 17, 18, 19, 20]:
        baseline = BASELINES['no2_rush_hour_avg']
        time_context = 'rush hour'
    elif hour in [0, 1, 2, 3, 4, 5]:
        baseline = BASELINES['no2_night_avg']
        time_context = 'night'
    else:
        baseline = BASELINES['no2_overall_avg']
        time_context = 'daytime'
    
    if no2 is None or np.isnan(no2):
        return 1.0, "NO2 unavailable (using baseline)"
    
    modulation = no2 / baseline
    modulation = max(0.3, min(3.0, modulation))  # Cap between 0.3x and 3x
    
    return modulation, f"NO2={no2:.0f} vs avg {baseline:.0f} ({time_context})"


def calculate_stubble_modulation(
    fire_count: int, wind_dir: Optional[float], month: int
) -> tuple:
    """
    Stubble burning modulation based on fire count anomaly.
    Gated by: (1) month and (2) wind direction from NW.
    """
    # Seasonal gate - stubble is Oct-Nov primarily
    if month not in [10, 11]:
        if month in [12, 1]:
            season_factor = 0.5  # Late season residual
        else:
            return 0.0, "Not stubble season"
    else:
        season_factor = 1.0
    
    # Wind gate - must be from NW (Punjab direction)
    if wind_dir is None:
        wind_gate = 0.5  # Uncertain wind
        wind_desc = "wind unknown"
    elif 250 <= wind_dir <= 340:
        wind_gate = 1.0
        wind_desc = f"wind from NW ({wind_dir:.0f}°)"
    elif 200 <= wind_dir < 250 or 340 < wind_dir <= 360:
        wind_gate = 0.5  # Partially from NW
        wind_desc = f"wind partially from NW ({wind_dir:.0f}°)"
    else:
        wind_gate = 0.0
        return 0.0, f"Wind from wrong direction ({wind_dir:.0f}°)"
    
    # Fire count modulation
    baseline = BASELINES['fires_stubble_season_avg']
    if fire_count == 0:
        return 0.0, "No fires detected"
    
    modulation = (fire_count / baseline) * season_factor * wind_gate
    modulation = max(0.0, min(5.0, modulation))  # Cap at 5x (severe event)
    
    return modulation, f"{fire_count} fires vs avg {baseline:.0f}, {wind_desc}"


def calculate_secondary_modulation(blh: Optional[float], month: int) -> tuple:
    """
    Secondary aerosol modulation based on BLH anomaly.
    Low BLH = high trapping = more secondary formation.
    M = Baseline_BLH / Current_BLH (inverted because low BLH = high effect)
    """
    # Get seasonal baseline
    if month in [11, 12, 1, 2]:
        baseline = BASELINES['blh_winter_avg']
        season = 'winter'
    elif month in [3, 4, 5]:
        baseline = BASELINES['blh_summer_avg']
        season = 'summer'
    else:
        baseline = BASELINES['blh_monsoon_avg']
        season = 'monsoon'
    
    if blh is None or np.isnan(blh) or blh <= 0:
        return 1.0, "BLH unavailable (using baseline)"
    
    # Apply BLH floor to prevent extreme modulation from very low values
    blh_effective = max(150, blh)
    
    # Inverted modulation - low BLH = high factor
    # Reduced cap since secondary aerosols already has highest prior (26%)
    modulation = baseline / blh_effective
    modulation = max(0.5, min(2.0, modulation))  # Cap between 0.5x and 2x
    
    if blh < 300:
        trap_desc = "severe trapping"
    elif blh < 500:
        trap_desc = "moderate trapping"
    else:
        trap_desc = "good mixing"
    
    return modulation, (
        f"Model-based estimate of regional/background PM2.5 and secondary formation. "
        f"Inferred from BLH trapping, not directly measured. "
        f"BLH={blh:.0f}m vs {season} avg {baseline:.0f}m ({trap_desc})"
    )


def calculate_industry_modulation(so2: Optional[float]) -> tuple:
    """
    Industry modulation based on SO2 anomaly.
    SO2 is unique industrial marker (vehicles emit negligible SO2).
    """
    baseline = BASELINES['so2_avg']
    
    if so2 is None or np.isnan(so2):
        return 1.0, "SO2 unavailable (using baseline)"
    
    modulation = so2 / baseline
    modulation = max(0.3, min(3.0, modulation))
    
    return modulation, f"SO2={so2:.0f} vs avg {baseline:.0f}"


def calculate_dust_modulation(
    pm25: Optional[float], pm10: Optional[float], 
    wind_speed: Optional[float]
) -> tuple:
    """
    Dust modulation based on PM2.5/PM10 ratio anomaly.
    Low ratio (more PM10) = more dust. High wind = more resuspension.
    """
    baseline_ratio = BASELINES['pm_ratio_avg']
    
    if pm25 is None or pm10 is None or pm10 == 0:
        return 1.0, "PM data unavailable"
    
    ratio = pm25 / pm10
    
    # Lower ratio = more coarse particles = more dust
    # Inverted modulation
    ratio_mod = baseline_ratio / max(ratio, 0.2)
    
    # Wind speed adds dust resuspension
    wind_mod = 1.0
    if wind_speed and wind_speed > 5:
        wind_mod = 1.0 + (wind_speed - 5) * 0.1  # +10% per m/s above 5
    
    modulation = ratio_mod * wind_mod
    modulation = max(0.3, min(3.0, modulation))
    
    return modulation, f"PM ratio={ratio:.2f} vs avg {baseline_ratio:.2f}"


def calculate_local_combustion_modulation(
    hour: int, month: int, co: Optional[float], pm25: Optional[float], 
    pm10: Optional[float], wind_speed: Optional[float]
) -> tuple:
    """
    Local combustion modulation based on particulate matter.
    
    Uses modulation index (current/baseline) for both PM2.5 and PM10 independently,
    each with their own seasonal baselines. This ensures sensors with only one 
    reading work, and sensors with both get a combined modulation signal.
    
    Fireworks signature detection for extreme events (Diwali, etc.)
    """
    factors = []
    
    # Get seasonal baselines for PM2.5 and PM10
    if month in [11, 12, 1, 2]:
        pm25_baseline = BASELINES['pm25_winter_avg']  # 228 µg/m³
        pm10_baseline = BASELINES['pm10_winter_avg']  # 365 µg/m³
        season = 'winter'
    elif month in [10]:
        pm25_baseline = BASELINES['pm25_postmonsoon_avg']  # 139 µg/m³
        pm10_baseline = BASELINES['pm10_postmonsoon_avg']  # 222 µg/m³
        season = 'post-monsoon'
    elif month in [3, 4, 5]:
        pm25_baseline = BASELINES['pm25_summer_avg']  # 80 µg/m³
        pm10_baseline = BASELINES['pm10_summer_avg']  # 128 µg/m³
        season = 'summer'
    else:
        pm25_baseline = BASELINES['pm25_monsoon_avg']  # 49 µg/m³
        pm10_baseline = BASELINES['pm10_monsoon_avg']  # 78 µg/m³
        season = 'monsoon'
    
    # For fireworks detection, prefer PM2.5 (fine particles = combustion)
    fine_pm = pm25 if pm25 is not None else None
    fine_pm_label = "PM2.5"
    
    # FIREWORKS SIGNATURE DETECTION (inferred from pollution, not calendar)
    has_extreme_pm = fine_pm is not None and fine_pm > 500
    has_high_pm_ratio = (fine_pm is not None and pm10 is not None and pm10 > 0 
                         and (fine_pm / pm10) > 0.75)
    has_combustion_sig = co is not None and co > 2.0
    is_stagnant = wind_speed is None or wind_speed < 3.0
    
    if has_extreme_pm and has_high_pm_ratio and has_combustion_sig and is_stagnant:
        modulation = fine_pm / pm25_baseline
        modulation = min(25.0, modulation)
        factors.append(f"🎆 fireworks ({fine_pm_label}={fine_pm:.0f} vs {season} avg {pm25_baseline})")
        return modulation, ", ".join(factors)
    
    # MODULATION INDEX - evaluate PM2.5 and PM10 independently with their own baselines
    # M = Current_PM / Baseline_PM (same pattern as traffic uses NO2)
    pm_modulations = []
    
    # PM2.5 modulation index
    if pm25 is not None:
        pm25_mod = pm25 / pm25_baseline
        pm_modulations.append(pm25_mod)
        factors.append(f"PM2.5={pm25:.0f} vs {season} avg {pm25_baseline}")
    
    # PM10 modulation index (with its own baseline)
    if pm10 is not None:
        pm10_mod = pm10 / pm10_baseline
        pm_modulations.append(pm10_mod)
        factors.append(f"PM10={pm10:.0f} vs {season} avg {pm10_baseline}")
    
    # Use average of available PM modulations, or 1.0 if none available
    if pm_modulations:
        base_mod = sum(pm_modulations) / len(pm_modulations)
    else:
        base_mod = 1.0
        factors.append("PM unavailable (using baseline)")
    
    # Time factor - heating/cooking peaks
    if hour in [6, 7, 8, 19, 20, 21, 22]:
        base_mod *= 1.3
        factors.append("cooking/heating hours")
    elif hour in [0, 1, 2, 3, 4, 5]:
        base_mod *= 1.1
        factors.append("night heating")
    
    # Winter factor
    if month in [11, 12, 1, 2]:
        base_mod *= 1.2
        factors.append("winter")
    
    # CO modulation (biomass signature)
    if co is not None:
        co_baseline = 1.5  # typical ambient CO
        co_mod = co / co_baseline
        base_mod *= min(co_mod, 2.0)
        if co > co_baseline:
            factors.append(f"CO={co:.1f} vs avg {co_baseline}")
    
    modulation = max(0.3, min(10.0, base_mod))
    
    return modulation, ", ".join(factors) if factors else "baseline"


# =============================================================================
# MAIN MODULATION ATTRIBUTION
# =============================================================================

def calculate_modulated_attribution(
    timestamp: datetime,
    readings: Dict,
    wind_dir: Optional[float],
    wind_speed: Optional[float],
    blh: Optional[float],
    fire_count: int
) -> Dict:
    """
    Calculate source attribution using validated priors + modulation.
    
    Returns normalized percentages that sum to 100%.
    """
    hour = timestamp.hour
    month = timestamp.month
    
    # Extract readings
    pm25 = readings.get('PM25')
    pm10 = readings.get('PM10')
    no2 = readings.get('NO2')
    so2 = readings.get('SO2')
    co = readings.get('CO')
    
    # Calculate modulation factors for each source
    modulations = {}
    explanations = {}
    
    # Traffic
    m_traffic, exp_traffic = calculate_traffic_modulation(no2, hour)
    modulations['traffic'] = m_traffic
    explanations['traffic'] = exp_traffic
    
    # Stubble burning
    m_stubble, exp_stubble = calculate_stubble_modulation(fire_count, wind_dir, month)
    modulations['stubble_burning'] = m_stubble
    explanations['stubble_burning'] = exp_stubble
    
    # Secondary aerosols
    m_secondary, exp_secondary = calculate_secondary_modulation(blh, month)
    modulations['secondary_aerosols'] = m_secondary
    explanations['secondary_aerosols'] = exp_secondary
    
    # Industry
    m_industry, exp_industry = calculate_industry_modulation(so2)
    modulations['industry'] = m_industry
    explanations['industry'] = exp_industry
    
    # Dust
    m_dust, exp_dust = calculate_dust_modulation(pm25, pm10, wind_speed)
    modulations['dust'] = m_dust
    explanations['dust'] = exp_dust
    
    # Local combustion (with signature-based fireworks detection)
    # Uses both PM2.5 and PM10 with their respective baselines
    m_local, exp_local = calculate_local_combustion_modulation(hour, month, co, pm25, pm10, wind_speed)
    modulations['local_combustion'] = m_local
    explanations['local_combustion'] = exp_local
    
    # Apply modulation to priors
    weighted = {}
    for source, prior in PRIORS.items():
        weighted[source] = prior * modulations[source]
    
    # Normalize to 100%
    total = sum(weighted.values())
    if total == 0:
        total = 1  # Prevent division by zero
    
    contributions = {}
    for source in PRIORS.keys():
        percentage = (weighted[source] / total) * 100
        contributions[source] = {
            'percentage': round(percentage, 1),
            'modulation_factor': round(modulations[source], 2),
            'prior': PRIORS[source] * 100,
            'explanation': explanations[source],
            'level': 'High' if percentage > 25 else ('Medium' if percentage > 15 else 'Low')
        }
    
    return {
        'method': 'validated_prior_modulation',
        'timestamp': timestamp.isoformat(),
        'contributions': contributions,
        'baselines_used': {
            'blh_baseline': BASELINES[f'blh_{"winter" if month in [11,12,1,2] else "summer" if month in [3,4,5] else "monsoon"}_avg'],
            'fires_baseline': BASELINES['fires_stubble_season_avg'],
            'no2_baseline': BASELINES['no2_rush_hour_avg'] if hour in [7,8,9,10,17,18,19,20] else BASELINES['no2_overall_avg'],
        }
    }


# =============================================================================
# TEST FUNCTION
# =============================================================================

def test_modulation_system():
    """Run test cases to validate the modulation system."""
    
    test_cases = [
        {
            'name': 'Rush Hour High Traffic',
            'timestamp': datetime(2025, 11, 8, 9, 0),  # 9 AM Nov
            'readings': {'PM25': 200, 'PM10': 350, 'NO2': 120, 'SO2': 15, 'CO': 1.2},
            'wind_dir': 308,
            'wind_speed': 4.0,
            'blh': 300,
            'fire_count': 150
        },
        {
            'name': 'Peak Stubble Event',
            'timestamp': datetime(2025, 11, 8, 18, 0),  # 6 PM Nov
            'readings': {'PM25': 400, 'PM10': 550, 'NO2': 80, 'SO2': 20, 'CO': 2.5},
            'wind_dir': 290,  # NW wind
            'wind_speed': 5.0,
            'blh': 200,  # Low BLH = trapping
            'fire_count': 500  # High fire count
        },
        {
            'name': 'Summer Dust Storm',
            'timestamp': datetime(2025, 5, 15, 14, 0),  # 2 PM May
            'readings': {'PM25': 150, 'PM10': 500, 'NO2': 50, 'SO2': 10, 'CO': 0.8},
            'wind_dir': 250,
            'wind_speed': 12.0,  # High wind
            'blh': 2000,  # High BLH (good mixing)
            'fire_count': 10
        },
        {
            'name': 'Night Winter Inversion',
            'timestamp': datetime(2025, 12, 15, 3, 0),  # 3 AM Dec
            'readings': {'PM25': 350, 'PM10': 450, 'NO2': 40, 'SO2': 25, 'CO': 2.0},
            'wind_dir': 90,  # East wind
            'wind_speed': 1.5,
            'blh': 100,  # Severe inversion
            'fire_count': 20
        },
    ]
    
    print("="*70)
    print("MODULATION SYSTEM TEST RESULTS")
    print("="*70)
    
    for tc in test_cases:
        print(f"\n>>> TEST CASE: {tc['name']}")
        print(f"    Timestamp: {tc['timestamp']}")
        print(f"    Fires: {tc['fire_count']}, Wind: {tc['wind_dir']}°, BLH: {tc['blh']}m")
        
        result = calculate_modulated_attribution(
            tc['timestamp'],
            tc['readings'],
            tc['wind_dir'],
            tc['wind_speed'],
            tc['blh'],
            tc['fire_count']
        )
        
        print(f"\n    CONTRIBUTIONS (Prior → Modulated):")
        for source, data in result['contributions'].items():
            arrow = "↑" if data['modulation_factor'] > 1.1 else ("↓" if data['modulation_factor'] < 0.9 else "→")
            print(f"    {source:20s}: {data['prior']:5.1f}% {arrow} {data['percentage']:5.1f}% (M={data['modulation_factor']:.2f}) - {data['explanation']}")
        
        # Check if total ≈ 100%
        total = sum(d['percentage'] for d in result['contributions'].values())
        print(f"\n    Total: {total:.1f}%")


if __name__ == '__main__':
    test_modulation_system()
