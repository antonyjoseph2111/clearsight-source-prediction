"""
Geographic Utility Functions
============================
Haversine distance, bearing calculation, upwind checks.
"""

import math


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance between two points.
    
    Parameters:
        lat1, lon1: First point (degrees)
        lat2, lon2: Second point (degrees)
    
    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth's radius in km
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = (math.sin(dphi / 2) ** 2 + 
         math.cos(phi1) * math.cos(phi2) * 
         math.sin(dlambda / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate initial bearing from point 1 to point 2.
    
    Returns:
        Bearing in degrees (0-360, clockwise from North)
        0° = North, 90° = East, 180° = South, 270° = West
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    
    x = math.sin(dlambda) * math.cos(phi2)
    y = (math.cos(phi1) * math.sin(phi2) - 
         math.sin(phi1) * math.cos(phi2) * math.cos(dlambda))
    
    theta = math.atan2(x, y)
    
    return (math.degrees(theta) + 360) % 360


def angular_diff(angle1: float, angle2: float) -> float:
    """
    Calculate smallest angle between two bearings.
    Handles wrap-around (e.g., 350° to 10° = 20°, not 340°).
    
    Returns:
        Difference in degrees (0-180)
    """
    diff = abs(angle1 - angle2)
    if diff > 180:
        diff = 360 - diff
    return diff


def is_upwind(source_bearing: float, wind_direction: float, tolerance: float = 45) -> bool:
    """
    Check if a source is upwind of the station.
    
    Wind direction = direction wind is coming FROM (meteorological convention).
    Source is upwind if bearing from station to source ≈ wind direction.
    
    Parameters:
        source_bearing: Bearing from station to source (degrees)
        wind_direction: Direction wind is coming FROM (degrees)
        tolerance: Allowed deviation in degrees (default 45°)
    
    Returns:
        True if source is within the upwind cone
    """
    diff = angular_diff(source_bearing, wind_direction)
    return diff <= tolerance


if __name__ == '__main__':
    # Test: Anand Vihar to Sangrur, Punjab
    dist = haversine(28.6469, 77.3164, 30.2331, 75.8406)
    bear = bearing(28.6469, 77.3164, 30.2331, 75.8406)
    print(f"Distance Anand Vihar to Sangrur: {dist:.1f} km")  # ~245 km
    print(f"Bearing: {bear:.1f}°")  # ~315° (NW)
    print(f"Upwind check (wind=290°): {is_upwind(bear, 290, 45)}")  # True
