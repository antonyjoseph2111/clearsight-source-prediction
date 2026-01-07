import numpy as np

# --- Simple Gaussian-Advection Hybrid Model ---

def wind_to_vector(speed, direction_deg):
    theta = np.deg2rad(direction_deg)
    dx = speed * np.cos(theta)
    dy = speed * np.sin(theta)
    return dx, dy


def simulate_outfall(lat, lon, wind_speed, wind_dir, hours=3):
    """
    Predict where pollution will travel after N hours
    """
    if wind_speed is None or wind_dir is None:
        return []

    dx, dy = wind_to_vector(wind_speed, wind_dir)

    km_per_deg = 111  # Earth approx

    outfall_points = []

    for h in range(1, hours + 1):
        lat_new = lat + (dy * h) / km_per_deg
        lon_new = lon + (dx * h) / km_per_deg

        outfall_points.append({
            "hour": h,
            "latitude": round(lat_new, 5),
            "longitude": round(lon_new, 5),
            "distance_km": round(np.sqrt((dx*h)**2 + (dy*h)**2), 2)
        })

    return outfall_points


def gaussian_intensity(distance_km, wind_speed, blh):
    """
    Predict decay of concentration with distance
    """
    if wind_speed is None or wind_speed == 0:
        wind_speed = 1

    dispersion = max(blh / 800, 0.4) if blh else 0.6

    intensity = np.exp(-distance_km / (3 * dispersion * wind_speed))
    return round(float(intensity), 3)
