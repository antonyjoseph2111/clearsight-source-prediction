"""
Delhi Air Pollution Source Attribution
======================================

Modules:
- data_engine: Data loading (stations, wind, fires, industries)
- modulation_engine: Validated prior + modulation attribution
- geo_utils: Geographic utilities
"""
from .data_engine import DataEngine
from .modulation_engine import calculate_modulated_attribution
from .geo_utils import haversine, bearing, angular_diff, is_upwind

__all__ = [
    'DataEngine',
    'calculate_modulated_attribution',
    'haversine', 'bearing', 'angular_diff', 'is_upwind',
]
