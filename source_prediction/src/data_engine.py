"""
Data Engine - Handles data loading for attribution
===================================================

This module provides the DataEngine class that loads and manages:
- Station metadata
- Wind/meteorology data
- Fire hotspot data
- Industry locations

The actual attribution calculations are done in modulation_engine.py.
"""

import pandas as pd
import os


class DataEngine:
    """
    Data loading engine for pollution attribution.
    
    Loads:
    - stations: CPCB monitoring station metadata
    - wind: ERA5 wind/BLH data (hourly)
    - fires: VIIRS fire hotspot data
    - industries: Major pollution source locations
    """
    
    def __init__(self, industries_path: str, fires_path: str,
                 stations_path: str, wind_path: str):
        """Initialize data engine with paths to data files."""
        print("Loading data for Data Engine...")
        self.industries = pd.read_csv(industries_path)
        self.fires = pd.read_csv(fires_path)
        self.fires['acq_date'] = pd.to_datetime(self.fires['acq_date'])
        self.stations = pd.read_csv(stations_path)
        
        # Load regional wind data
        self.wind = pd.read_csv(wind_path)
        self.wind['timestamp'] = pd.to_datetime(self.wind['timestamp'])
        
        # Try to load station-specific wind data
        self.station_wind = None
        station_wind_path = wind_path.replace('wind_filtered.csv', 'wind_stations.csv')
        try:
            if os.path.exists(station_wind_path):
                self.station_wind = pd.read_csv(station_wind_path)
                self.station_wind['timestamp'] = pd.to_datetime(self.station_wind['timestamp'])
                print(f"Loaded station wind data: {len(self.station_wind)} records for {self.station_wind['station_id'].nunique()} stations")
        except Exception as e:
            print(f"Note: Station wind data not loaded: {e}")
        
        print(f"Loaded: {len(self.stations)} stations, {len(self.industries)} industries, {len(self.fires)} fires")
        self.fires_path = fires_path
    
    def reload_fires(self):
        """Reload fire data from disk."""
        try:
            print("Reloading fire data...")
            new_fires = pd.read_csv(self.fires_path)
            if 'timestamp' in new_fires.columns:
                new_fires['timestamp'] = pd.to_datetime(new_fires['timestamp'])
            if 'acq_date' in new_fires.columns:
                new_fires['acq_date'] = pd.to_datetime(new_fires['acq_date'])
            
            self.fires = new_fires
            print(f"Reloaded fires: {len(self.fires)} records")
            return True
        except Exception as e:
            print(f"Error reloading fires: {e}")
            return False
    
    def get_station(self, name: str):
        """Get station by name (partial match)."""
        matches = self.stations[self.stations['station_name'].str.contains(name, case=False, na=False)]
        return matches.iloc[0] if len(matches) > 0 else None
    
    def get_wind(self, timestamp, lat, lon, station_id=None):
        """Get wind data - prioritizes station-specific data, fallback to regional."""
        hour = timestamp.replace(minute=0, second=0, microsecond=0)
        
        # Try station-specific wind data first
        if self.station_wind is not None and station_id is not None:
            station_wind = self.station_wind[
                (self.station_wind['timestamp'] == hour) & 
                (self.station_wind['station_id'] == station_id)
            ]
            if len(station_wind) > 0:
                return station_wind.iloc[0]
        
        # Fallback to regional wind data
        wind_hour = self.wind[self.wind['timestamp'] == hour]
        if len(wind_hour) == 0:
            return None
        delhi = wind_hour[wind_hour['wind_location'] == 'Delhi']
        return delhi.iloc[0] if len(delhi) > 0 else wind_hour.iloc[0]
    
    def get_fires(self, dt, lookback_hours=48):
        """
        Get fires from past N hours for time-lagged attribution.
        Default 48 hours covers max travel time from Punjab (~400km at ~15km/h = 27h)
        plus ±6 hour arrival window.
        """
        end_time = dt
        start_time = dt - pd.Timedelta(hours=lookback_hours)
        
        # Use timestamp column if available, otherwise fall back to date
        if 'timestamp' in self.fires.columns:
            fires_ts = pd.to_datetime(self.fires['timestamp'])
            return self.fires[(fires_ts >= start_time) & (fires_ts <= end_time)]
        else:
            # Fallback: get fires from that day and previous day
            dates = [dt.date(), (dt - pd.Timedelta(days=1)).date()]
            return self.fires[self.fires['acq_date'].dt.date.isin(dates)]
    
    def get_fire_region_wind(self, timestamp):
        """Get wind data from fire source region (Punjab/Amritsar) for 2-point averaging."""
        hour = timestamp.replace(minute=0, second=0, microsecond=0)
        wind_hour = self.wind[self.wind['timestamp'] == hour]
        if len(wind_hour) == 0:
            return None
        # Prefer Amritsar (major Punjab fire region), fallback to Ludhiana
        amritsar = wind_hour[wind_hour['wind_location'] == 'Amritsar']
        if len(amritsar) > 0:
            return amritsar.iloc[0]
        ludhiana = wind_hour[wind_hour['wind_location'] == 'Ludhiana']
        if len(ludhiana) > 0:
            return ludhiana.iloc[0]
        return None


# For backward compatibility - alias to old class name
ExpandedSourceAttributionEngine = DataEngine
