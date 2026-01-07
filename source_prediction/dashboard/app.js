/**
 * Delhi NCR Pollution Source Attribution Dashboard
 * =================================================
 * Interactive map with source attribution analysis
 */

// Global state
let map;
let stations = [];
let markers = {};
let selectedStation = null;
let attributionChart = null;
let fireLayer = null;
let industryLayer = null;
let industries = [];
let outfallLayer = null;
let outfallAnimationTimer = null;


// Source colors - distinct colors for each source
const SOURCE_COLORS = {
    stubble_burning: '#ff6b35',    // Orange
    traffic: '#3b82f6',             // Blue
    industry: '#64748b',            // Gray
    dust: '#d4a574',                // Tan/Brown
    local_combustion: '#dc2626',    // Red (distinct from traffic)
    secondary_aerosols: '#a855f7'   // Purple
};

const SOURCE_NAMES = {
    stubble_burning: 'Stubble Burning',
    traffic: 'Traffic',
    industry: 'Industry',
    dust: 'Dust',
    local_combustion: 'Local Combustion',
    secondary_aerosols: 'Regional / Background Build-up'
};

// Initialize map
function initMap() {
    map = L.map('map', {
        center: [28.6139, 77.2090], // Delhi center
        zoom: 10,
        zoomControl: true
    });

    // Dark tile layer
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);
}

// India AQI Breakpoints (National Air Quality Index)
// Source: Central Pollution Control Board (CPCB), India
// Reference: https://cpcb.nic.in/AQI/AQI-Revised.pdf
// All concentrations in µg/m³ except CO (mg/m³)
const AQI_BREAKPOINTS = {
    PM25: [ // 24-hour average
        { aqiLow: 0, aqiHigh: 50, concLow: 0, concHigh: 30, color: '#22c55e', label: 'Good' },
        { aqiLow: 51, aqiHigh: 100, concLow: 31, concHigh: 60, color: '#84cc16', label: 'Satisfactory' },
        { aqiLow: 101, aqiHigh: 200, concLow: 61, concHigh: 90, color: '#f59e0b', label: 'Moderate' },
        { aqiLow: 201, aqiHigh: 300, concLow: 91, concHigh: 120, color: '#ef4444', label: 'Poor' },
        { aqiLow: 301, aqiHigh: 400, concLow: 121, concHigh: 250, color: '#a855f7', label: 'Very Poor' },
        { aqiLow: 401, aqiHigh: 500, concLow: 251, concHigh: 500, color: '#7f1d1d', label: 'Severe' }
    ],
    PM10: [ // 24-hour average
        { aqiLow: 0, aqiHigh: 50, concLow: 0, concHigh: 50, color: '#22c55e', label: 'Good' },
        { aqiLow: 51, aqiHigh: 100, concLow: 51, concHigh: 100, color: '#84cc16', label: 'Satisfactory' },
        { aqiLow: 101, aqiHigh: 200, concLow: 101, concHigh: 250, color: '#f59e0b', label: 'Moderate' },
        { aqiLow: 201, aqiHigh: 300, concLow: 251, concHigh: 350, color: '#ef4444', label: 'Poor' },
        { aqiLow: 301, aqiHigh: 400, concLow: 351, concHigh: 430, color: '#a855f7', label: 'Very Poor' },
        { aqiLow: 401, aqiHigh: 500, concLow: 431, concHigh: 600, color: '#7f1d1d', label: 'Severe' }
    ],
    NO2: [ // 24-hour average
        { aqiLow: 0, aqiHigh: 50, concLow: 0, concHigh: 40, color: '#22c55e', label: 'Good' },
        { aqiLow: 51, aqiHigh: 100, concLow: 41, concHigh: 80, color: '#84cc16', label: 'Satisfactory' },
        { aqiLow: 101, aqiHigh: 200, concLow: 81, concHigh: 180, color: '#f59e0b', label: 'Moderate' },
        { aqiLow: 201, aqiHigh: 300, concLow: 181, concHigh: 280, color: '#ef4444', label: 'Poor' },
        { aqiLow: 301, aqiHigh: 400, concLow: 281, concHigh: 400, color: '#a855f7', label: 'Very Poor' },
        { aqiLow: 401, aqiHigh: 500, concLow: 401, concHigh: 500, color: '#7f1d1d', label: 'Severe' }
    ],
    SO2: [ // 24-hour average
        { aqiLow: 0, aqiHigh: 50, concLow: 0, concHigh: 40, color: '#22c55e', label: 'Good' },
        { aqiLow: 51, aqiHigh: 100, concLow: 41, concHigh: 80, color: '#84cc16', label: 'Satisfactory' },
        { aqiLow: 101, aqiHigh: 200, concLow: 81, concHigh: 380, color: '#f59e0b', label: 'Moderate' },
        { aqiLow: 201, aqiHigh: 300, concLow: 381, concHigh: 800, color: '#ef4444', label: 'Poor' },
        { aqiLow: 301, aqiHigh: 400, concLow: 801, concHigh: 1600, color: '#a855f7', label: 'Very Poor' },
        { aqiLow: 401, aqiHigh: 500, concLow: 1601, concHigh: 2000, color: '#7f1d1d', label: 'Severe' }
    ],
    CO: [ // 8-hour average (mg/m³)
        { aqiLow: 0, aqiHigh: 50, concLow: 0, concHigh: 1.0, color: '#22c55e', label: 'Good' },
        { aqiLow: 51, aqiHigh: 100, concLow: 1.1, concHigh: 2.0, color: '#84cc16', label: 'Satisfactory' },
        { aqiLow: 101, aqiHigh: 200, concLow: 2.1, concHigh: 10, color: '#f59e0b', label: 'Moderate' },
        { aqiLow: 201, aqiHigh: 300, concLow: 10.1, concHigh: 17, color: '#ef4444', label: 'Poor' },
        { aqiLow: 301, aqiHigh: 400, concLow: 17.1, concHigh: 34, color: '#a855f7', label: 'Very Poor' },
        { aqiLow: 401, aqiHigh: 500, concLow: 34.1, concHigh: 50, color: '#7f1d1d', label: 'Severe' }
    ],
    O3: [ // 8-hour average
        { aqiLow: 0, aqiHigh: 50, concLow: 0, concHigh: 50, color: '#22c55e', label: 'Good' },
        { aqiLow: 51, aqiHigh: 100, concLow: 51, concHigh: 100, color: '#84cc16', label: 'Satisfactory' },
        { aqiLow: 101, aqiHigh: 200, concLow: 101, concHigh: 168, color: '#f59e0b', label: 'Moderate' },
        { aqiLow: 201, aqiHigh: 300, concLow: 169, concHigh: 208, color: '#ef4444', label: 'Poor' },
        { aqiLow: 301, aqiHigh: 400, concLow: 209, concHigh: 748, color: '#a855f7', label: 'Very Poor' },
        { aqiLow: 401, aqiHigh: 500, concLow: 749, concHigh: 1000, color: '#7f1d1d', label: 'Severe' }
    ],
    PM1: [ // PM1.0 - using similar breakpoints to PM2.5 (finer particles)
        { aqiLow: 0, aqiHigh: 50, concLow: 0, concHigh: 25, color: '#22c55e', label: 'Good' },
        { aqiLow: 51, aqiHigh: 100, concLow: 26, concHigh: 50, color: '#84cc16', label: 'Satisfactory' },
        { aqiLow: 101, aqiHigh: 200, concLow: 51, concHigh: 75, color: '#f59e0b', label: 'Moderate' },
        { aqiLow: 201, aqiHigh: 300, concLow: 76, concHigh: 100, color: '#ef4444', label: 'Poor' },
        { aqiLow: 301, aqiHigh: 400, concLow: 101, concHigh: 200, color: '#a855f7', label: 'Very Poor' },
        { aqiLow: 401, aqiHigh: 500, concLow: 201, concHigh: 400, color: '#7f1d1d', label: 'Severe' }
    ]
};

// Calculate AQI for a single pollutant using linear interpolation formula:
// AQI = ((AQI_high - AQI_low) / (Conc_high - Conc_low)) * (Conc - Conc_low) + AQI_low
function calculatePollutantAQI(concentration, pollutant) {
    if (!concentration || concentration < 0 || !AQI_BREAKPOINTS[pollutant]) {
        return null;
    }

    const breakpoints = AQI_BREAKPOINTS[pollutant];
    for (const bp of breakpoints) {
        if (concentration <= bp.concHigh) {
            const aqi = ((bp.aqiHigh - bp.aqiLow) / (bp.concHigh - bp.concLow)) *
                (concentration - bp.concLow) + bp.aqiLow;
            return { aqi: Math.round(aqi), color: bp.color, label: bp.label, pollutant };
        }
    }
    // Above max - return 500
    return { aqi: 500, color: '#7f1d1d', label: 'Severe', pollutant };
}

// Calculate overall AQI from readings (uses worst sub-index)
// Fallback order: PM2.5 > PM1.0 > PM10 > NO2 > SO2 > CO > O3
function calculateAQI(readings) {
    const pollutants = ['PM25', 'PM1', 'PM10', 'NO2', 'SO2', 'CO', 'O3'];
    let maxAqi = { aqi: null, color: '#6b7280', label: 'No Data', pollutant: null };

    for (const poll of pollutants) {
        const conc = readings[poll] || readings[poll.toLowerCase()];
        if (conc && conc > 0) {
            const result = calculatePollutantAQI(conc, poll);
            if (result && (maxAqi.aqi === null || result.aqi > maxAqi.aqi)) {
                maxAqi = result;
            }
        }
    }

    return maxAqi;
}

// Convert degrees to compass direction (N, NE, E, SE, ...)
function degToCompass(deg) {
    if (deg == null || isNaN(deg)) return '--';
    const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    const i = Math.round((((deg % 360) + 360) % 360) / 45) % 8;
    return dirs[i];
}

// Update Outfall Forecast panel
function updateOutfallPanel(outfallPoints, meteorology) {
    const card = document.getElementById('outfall-card');
    const container = document.getElementById('outfall-list');

    if (!card || !container) return;

    if (!outfallPoints || outfallPoints.length === 0) {
        container.innerHTML = '<p class="industries-placeholder">No dispersion forecast available for this time.</p>';
        return;
    }

    // Use wind direction if available for direction text
    const windDir = meteorology && meteorology.wind_dir != null
        ? parseFloat(meteorology.wind_dir)
        : null;
    const windCompass = degToCompass(windDir);

    container.innerHTML = '';

    outfallPoints.forEach(p => {
        const pm = p.predicted_PM25 ?? 0;
        const aqiInfo = calculatePollutantAQI(pm, 'PM25') || {
            aqi: null,
            label: 'Unknown',
            color: '#6b7280'
        };

        const row = document.createElement('div');
        row.className = 'industry-item'; // reuse nice styling

        row.innerHTML = `
            <div class="industry-rank" style="background: #22d3ee;">+${p.hour}h</div>
            <div class="industry-info">
                <div class="industry-name">
                    ${p.distance_km.toFixed(1)} km downwind
                    ${windCompass !== '--' ? ` (${windCompass})` : ''}
                </div>
                <div class="industry-details">
                    <span class="industry-type">
                        PM2.5 ≈ ${pm.toFixed(0)} µg/m³
                    </span>
                    <span class="industry-distance" style="color:${aqiInfo.color}">
                        ${aqiInfo.label}
                    </span>
                </div>
            </div>
        `;

        container.appendChild(row);
    });
}

// Clear panel when no outfall
function clearOutfallPanel() {
    const container = document.getElementById('outfall-list');
    if (!container) return;
    container.innerHTML = '<p class="industries-placeholder">No dispersion forecast available.</p>';
}

// Get marker color based on readings (uses best available pollutant)
function getMarkerColor(pm25, readings = null) {
    if (readings) {
        const result = calculateAQI(readings);
        return result.color;
    }
    // Fallback to PM2.5 only
    const result = calculatePollutantAQI(pm25, 'PM25');
    return result ? result.color : '#6b7280';
}

// Create custom marker
function createMarker(station) {
    const color = getMarkerColor(null); // Default color

    const icon = L.divIcon({
        className: '',
        html: `<div class="custom-marker" style="background-color: ${color};" data-station-id="${station.station_id}"></div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    });

    const marker = L.marker([station.lat, station.lon], { icon })
        .addTo(map)
        .on('click', () => selectStation(station));

    markers[station.station_id] = marker;
    return marker;
}

// Load stations from API
async function loadStations() {
    try {
        const response = await fetch('/stations');
        const data = await response.json();
        stations = data.stations;

        // Create markers for all stations
        stations.forEach(station => {
            createMarker(station);
        });

        console.log(`Loaded ${stations.length} stations`);

        // Also load industries
        await loadIndustries();
    } catch (error) {
        console.error('Error loading stations:', error);
    }
}

// Load industries from API
async function loadIndustries() {
    try {
        const response = await fetch('/industries');
        const data = await response.json();
        industries = data.industries || [];
        console.log(`Loaded ${industries.length} industries`);
    } catch (error) {
        console.error('Error loading industries:', error);
    }
}

// Show fires on map for time-lagged attribution (past 24 hours)
async function showFires(timestamp) {
    // Clear existing fires
    if (fireLayer) {
        map.removeLayer(fireLayer);
    }

    try {
        // Use timestamp for 24-hour lookback (fires that could be "arriving" now)
        const response = await fetch(`/fires?timestamp=${encodeURIComponent(timestamp)}&lookback=24`);
        const data = await response.json();

        if (data.fires && data.fires.length > 0) {
            const fireMarkers = data.fires.map(fire => {
                const frp = fire.frp || 10;
                const radius = Math.min(8, Math.max(3, frp / 10));

                // Display fire timestamp if available
                const fireTime = fire.timestamp || fire.acq_date || 'Unknown';

                return L.circleMarker([fire.latitude, fire.longitude], {
                    radius: radius,
                    fillColor: '#ff6b35',
                    color: '#ff4500',
                    weight: 1,
                    opacity: 0.8,
                    fillOpacity: 0.6
                }).bindPopup(`
                    <strong>🔥 Fire Hotspot</strong><br>
                    FRP: ${frp.toFixed(1)} MW<br>
                    Time: ${fireTime}
                `);
            });

            fireLayer = L.layerGroup(fireMarkers).addTo(map);
            console.log(`Showing ${data.fires.length} fires from past 24h (mode: ${data.mode})`);

            // Update Top Fires List in sidebar
            updateTopFiresList(data.fires);
        } else {
            // Hide fires list if no fires
            updateTopFiresList([]);
        }
    } catch (error) {
        console.error('Error loading fires:', error);
        updateTopFiresList([]);
    }
}

// Show industries on map (major emitters near selected station)
function showIndustries(stationLat, stationLon) {
    // Clear existing industries
    if (industryLayer) {
        map.removeLayer(industryLayer);
    }

    if (!industries || industries.length === 0) return;

    // Filter to major industries (emission_weight >= 10) within 50km
    const nearbyIndustries = industries.filter(ind => {
        const dist = haversine(stationLat, stationLon, ind.latitude, ind.longitude);
        return ind.emission_weight >= 10 && dist <= 50;
    });

    const industryMarkers = nearbyIndustries.map(ind => {
        const weight = ind.emission_weight || 10;
        // Scale radius: weight 10 = 5px, weight 100 = 20px
        const radius = Math.min(20, Math.max(5, 5 + (weight / 10) * 1.5));

        return L.circleMarker([ind.latitude, ind.longitude], {
            radius: radius,
            originalRadius: radius, // Store for highlight reset
            fillColor: '#64748b',
            color: '#475569',
            weight: 2,
            opacity: 0.9,
            fillOpacity: 0.7
        }).bindPopup(`
            <strong>🏭 ${ind.name || 'Industry'}</strong><br>
            Category: ${ind.category || 'Unknown'}<br>
            Emission Weight: ${weight}
        `);
    });

    industryLayer = L.layerGroup(industryMarkers).addTo(map);
    console.log(`Showing ${nearbyIndustries.length} industries`);
}

// Haversine distance calculation
function haversine(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Select station and show attribution
async function selectStation(station) {
    if (outfallLayer) {
        map.removeLayer(outfallLayer);
        outfallLayer = null;
    }
    console.log('selectStation called:', station.station_id, station.station_name);
    selectedStation = station;

    // Update marker styles
    Object.values(markers).forEach(m => {
        m.getElement().querySelector('.custom-marker').classList.remove('selected');
    });
    markers[station.station_id].getElement().querySelector('.custom-marker').classList.add('selected');

    // Show loading state
    document.querySelector('.panel-placeholder').style.display = 'none';
    document.getElementById('panel-content').style.display = 'block';
    document.getElementById('station-name').textContent = station.station_name;

    // Get timestamp from date and hour inputs
    const dateInput = document.getElementById('date-input');
    const hourInput = document.getElementById('hour-input');
    let date = dateInput.value;
    let hour = hourInput.value;

    if (!date) {
        // Default to current date
        const now = new Date();
        date = now.toISOString().slice(0, 10);
        dateInput.value = date;
    }

    // Construct timestamp in ISO format
    const timestamp = `${date}T${hour.padStart(2, '0')}:00`;

    // Show fires and industries on map
    await showFires(timestamp);
    showIndustries(station.lat, station.lon);

    // Load contributing industries in sidebar
    await loadContributingIndustries(station.station_id);

    // Fetch latest station data
    await loadStationData(station, timestamp);
}

// Load and display contributing industries for a station
async function loadContributingIndustries(stationId) {
    const container = document.getElementById('industries-list');
    container.innerHTML = '<p class="loading">Loading industries...</p>';

    console.log('Loading industries for station:', stationId);

    try {
        const url = `/station/${stationId}/industries`;
        console.log('Fetching:', url);
        const response = await fetch(url);
        console.log('Response status:', response.status);
        const data = await response.json();
        console.log('Industries data:', data);

        if (data.error) {
            container.innerHTML = '<p class="industries-placeholder">No industry data available</p>';
            return;
        }

        if (!data.industries || data.industries.length === 0) {
            container.innerHTML = '<p class="industries-placeholder">No significant industries nearby</p>';
            return;
        }

        container.innerHTML = '';
        data.industries.forEach((ind, i) => {
            const item = document.createElement('div');
            item.className = 'industry-item';
            // Add click handler to highlight industry
            item.onclick = () => highlightIndustry(ind.latitude, ind.longitude);
            item.style.cursor = 'pointer';

            item.innerHTML = `
                <div class="industry-rank">${i + 1}</div>
                <div class="industry-info">
                    <div class="industry-name">${ind.name || 'Industrial Unit'}</div>
                    <div class="industry-details">
                        <span class="industry-type">${ind.type || 'Industrial'}</span>
                        <span class="industry-distance">${ind.distance_km} km away</span>
                        ${ind.is_upwind ? '<span class="upwind-badge">🌬️ Upwind</span>' : ''}
                    </div>
                </div>
                <div class="industry-score" title="Contribution Score">
                    ${ind.contribution_score}
                </div>
            `;
            container.appendChild(item);
        });
    } catch (error) {
        console.error('Error loading industries:', error);
        container.innerHTML = '<p class="industries-placeholder">Failed to load industries</p>';
    }
}

// Highlight industry on map
function highlightIndustry(lat, lon) {
    if (!industryLayer) return;

    industryLayer.eachLayer(layer => {
        const latLng = layer.getLatLng();
        // Check if this is the target industry (small tolerance for float precision)
        if (Math.abs(latLng.lat - lat) < 0.0001 && Math.abs(latLng.lng - lon) < 0.0001) {
            layer.openPopup();
            layer.setStyle({
                color: '#ef4444', // Red border
                fillColor: '#f87171', // Red fill
                weight: 3,
                radius: 12 // Larger radius
            });
            // Pan map to industry if needed, but maybe keep station in view? 
            // Let's just pan to it for clarity
            map.panTo(latLng);
        } else {
            // Reset others
            layer.setStyle({
                color: '#475569',
                fillColor: '#64748b',
                weight: 2,
                radius: layer.options.originalRadius || layer.getRadius() // Use original radius if stored, else current (might be buggy if not stored, but showIndustries sets it)
            });
            // Re-calculate radius based on weight if we don't store it? 
            // Simplified: just reset to default-ish or keep current if we didn't change it.
            // Better: in showIndustries, store original radius in options.
            if (layer.options.originalRadius) {
                layer.setRadius(layer.options.originalRadius);
            }
        }
    });
}

// Update Top Fires List
function updateTopFiresList(fires) {
    const container = document.getElementById('fires-list');
    const card = document.getElementById('fires-card');

    if (!fires || fires.length === 0) {
        card.style.display = 'none';
        return;
    }

    // Sort by FRP descending
    const topFires = [...fires].sort((a, b) => (b.frp || 0) - (a.frp || 0)).slice(0, 10);

    container.innerHTML = '';
    topFires.forEach((fire, i) => {
        const item = document.createElement('div');
        item.className = 'industry-item'; // Reuse industry item styling
        item.style.cursor = 'pointer';

        // Click to zoom to fire
        item.onclick = () => {
            map.setView([fire.latitude, fire.longitude], 10);
            // Find and open popup
            if (fireLayer) {
                fireLayer.eachLayer(layer => {
                    const latLng = layer.getLatLng();
                    if (Math.abs(latLng.lat - fire.latitude) < 0.0001 && Math.abs(latLng.lng - fire.longitude) < 0.0001) {
                        layer.openPopup();
                    }
                });
            }
        };

        const fireTime = fire.timestamp ? new Date(fire.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : (fire.acq_time || 'N/A');

        item.innerHTML = `
            <div class="industry-rank" style="background: #ff6b35;">${i + 1}</div>
            <div class="industry-info">
                <div class="industry-name">Fire Hotspot</div>
                <div class="industry-details">
                    <span class="industry-type">FRP: ${fire.frp ? fire.frp.toFixed(1) : 'N/A'} MW</span>
                    <span class="industry-distance">Time: ${fireTime}</span>
                </div>
            </div>
        `;
        container.appendChild(item);
    });

    card.style.display = 'block';
}

// Load station data and calculate attribution
async function loadStationData(station, timestamp) {
    try {
        // Get the date from timestamp for filtering
        const selectedDate = timestamp.split('T')[0];
        const selectedHour = parseInt(timestamp.split('T')[1]?.split(':')[0] || '9');

        // Fetch station data filtered by date
        const dataResponse = await fetch(`/station/${station.station_id}/data?start_date=${selectedDate}&end_date=${selectedDate}&limit=100`);
        const stationData = await dataResponse.json();

        // Default readings
        let readings = {
            PM25: 150,
            PM10: 250,
            NO2: 60,
            SO2: 20,
            CO: 1.5
        };

        if (stationData.data && stationData.data.length > 0) {
            // Find reading closest to the selected hour
            let bestMatch = stationData.data[0];
            let bestDiff = 24;

            for (const record of stationData.data) {
                if (record.timestamp) {
                    const recordHour = new Date(record.timestamp).getHours();
                    const diff = Math.abs(recordHour - selectedHour);
                    if (diff < bestDiff) {
                        bestDiff = diff;
                        bestMatch = record;
                    }
                }
            }

            // Get max values from the day's data for each pollutant (when hourly is missing)
            const getMax = (field) => {
                const values = stationData.data
                    .map(r => r[field])
                    .filter(v => v != null && !isNaN(v));
                return values.length > 0 ? Math.max(...values) : null;
            };

            readings = {
                PM25: bestMatch.PM25 ?? bestMatch.pm25 ?? getMax('PM25') ?? getMax('pm25'),
                PM10: bestMatch.PM10 ?? bestMatch.pm10 ?? getMax('PM10') ?? getMax('pm10'),
                NO2: bestMatch.NO2 ?? bestMatch.no2 ?? getMax('NO2') ?? getMax('no2'),
                SO2: bestMatch.SO2 ?? bestMatch.so2 ?? getMax('SO2') ?? getMax('so2'),
                CO: bestMatch.CO ?? bestMatch.co ?? getMax('CO') ?? getMax('co')
            };

            console.log(`Found readings for ${selectedDate} hour ${selectedHour}:`, readings);
        } else {
            console.log(`No data for ${selectedDate}, using defaults`);
        }

        // Calculate attribution
        const attrResponse = await fetch('/attribution', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                station: station.station_name,
                timestamp: timestamp,
                readings: readings
            })
        });

        const attribution = await attrResponse.json();

        if (attribution.error) {
            console.error('Attribution error:', attribution.error);
            return;
        }

        // Update UI with the readings we fetched
        updateReadings(readings);
        updateChart(attribution.contributions);
        updateSourcesList(attribution.contributions);
        updateMeteorology(attribution.meteorology);
        updateSummary(attribution);
        updateConfidence(attribution.confidence);
        updateActions(attribution.contributions);

        // Pick top contributor and show targeted solutions
        function updateActions(contributions) {
            const container = document.getElementById('actions-content');
            if (!container || !contributions) return;

            const entries = Object.entries(contributions);
            if (!entries.length) {
                container.innerHTML = `
            <p class="industries-placeholder">
                No source breakdown available for this time.
            </p>
        `;
                return;
            }

            // Find source with highest percentage
            const [topKey, topData] = entries.reduce((best, curr) =>
                curr[1].percentage > best[1].percentage ? curr : best
            );

            const friendlyName = SOURCE_NAMES[topKey] || topKey.replace(/_/g, ' ');

            // Short, judge-friendly solution suggestions for each source
            const SUGGESTIONS = {
                traffic: [
                    "Tighten peak-hour restrictions and promote staggered office/school timings.",
                    "Prioritize public transport & metro feeders on this corridor.",
                    "Enforce PUC checks and phase-out high-emitting, older vehicles."
                ],
                industry: [
                    "Audit nearby industries for stack emissions and fuel type.",
                    "Upgrade to cleaner fuels / scrubbers where possible.",
                    "Strengthen night-time monitoring and surprise inspections."
                ],
                dust: [
                    "Continuous mechanical sweeping and water sprinkling on main roads.",
                    "Strict covering of construction material and debris transport.",
                    "Mandate wind-barriers and green cover around construction hotspots."
                ],
                stubble_burning: [
                    "Target crop-residue management support in upwind districts.",
                    "Incentivise in-situ management (Happy Seeder, mulching, etc.).",
                    "Use real-time fire alerts to trigger emergency advisories in NCR."
                ],
                local_combustion: [
                    "Control DG set usage with stricter norms and backup alternatives.",
                    "Promote clean cooking/heating fuels in nearby neighbourhoods.",
                    "Limit fireworks and open burning through local enforcement."
                ],
                secondary_aerosols: [
                    "Reduce primary precursors (NOx, SO2, NH3) across traffic and industry.",
                    "Tighten emission norms during low BLH / inversion days.",
                    "Use graded response plans that trigger early when trapping is predicted."
                ]
            };

            const suggestions = SUGGESTIONS[topKey] || [
                "Reduce emissions from major local sources in this zone.",
                "Strengthen monitoring and enforcement during high-pollution hours.",
                "Combine long-term control measures with short-term emergency actions."
            ];

            container.innerHTML = `
        <p class="actions-headline">
            <strong>Major contributor now: ${friendlyName}</strong>
            (~${topData.percentage.toFixed(0)}%)
        </p>
        <ul class="actions-list">
            ${suggestions.map(s => `<li>${s}</li>`).join('')}
        </ul>
        <p class="actions-note">
            These are high-level levers—actual policy design would use full inventory & dispersion modelling.
        </p>
    `;
        }

        // Update marker color
        // Update marker color
        // Update marker color
        updateMarkerColor(station.station_id, readings.PM25);

        // Outfall (map + side panel)
        if (attribution.outfall && attribution.outfall.length > 0) {
            drawOutfall(attribution.outfall);
            updateOutfallPanel(attribution.outfall, attribution.meteorology);
        } else {
            if (outfallLayer) {
                map.removeLayer(outfallLayer);
                outfallLayer = null;
            }
            clearOutfallPanel();
        }




    } catch (error) {
        console.error('Error loading station data:', error);
    }
}

// Update readings display
function updateReadings(readings) {
    const format = (val) => {
        if (val === null || val === undefined || val === '--') return '--';
        const num = parseFloat(val);
        return isNaN(num) ? '--' : num.toFixed(1);
    };

    document.getElementById('reading-pm25').textContent = format(readings.pm25 || readings.PM25);
    document.getElementById('reading-pm10').textContent = format(readings.pm10 || readings.PM10);
    document.getElementById('reading-no2').textContent = format(readings.no2 || readings.NO2);
    document.getElementById('reading-so2').textContent = format(readings.so2 || readings.SO2);
    document.getElementById('reading-co').textContent = format(readings.co || readings.CO);
}

// Update pie chart
function updateChart(contributions) {
    const ctx = document.getElementById('attribution-chart').getContext('2d');

    const labels = Object.keys(contributions).map(k => SOURCE_NAMES[k] || k);
    const data = Object.values(contributions).map(c => c.percentage);
    const colors = Object.keys(contributions).map(k => SOURCE_COLORS[k] || '#888');

    if (attributionChart) {
        attributionChart.destroy();
    }

    attributionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderColor: 'rgba(0,0,0,0.3)',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        color: '#a0a0b0',
                        font: { size: 11 },
                        padding: 15,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(25, 25, 35, 0.9)',
                    titleColor: '#fff',
                    bodyColor: '#a0a0b0',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    callbacks: {
                        label: (context) => ` ${context.parsed.toFixed(1)}%`
                    }
                }
            }
        }
    });
}

// Update sources list
function updateSourcesList(contributions) {
    const container = document.getElementById('sources-list');
    container.innerHTML = '';

    // Sort by percentage
    const sorted = Object.entries(contributions)
        .sort((a, b) => b[1].percentage - a[1].percentage);

    sorted.forEach(([key, data]) => {
        const color = SOURCE_COLORS[key] || '#888888';
        const item = document.createElement('div');
        item.className = 'source-item';
        item.innerHTML = `
            <div class="source-color" style="background-color: ${color} !important;"></div>
            <div class="source-info">
                <div class="source-name">${SOURCE_NAMES[key] || key}</div>
                <div class="source-explanation">${data.explanation || ''}</div>
            </div>
            <div>
                <span class="source-percentage">${data.percentage.toFixed(1)}%</span>
                <span class="source-level ${data.level?.toLowerCase() || 'low'}">${data.level || 'N/A'}</span>
            </div>
        `;
        container.appendChild(item);
    });
}

// Update meteorology
function updateMeteorology(met) {
    if (!met) return;

    // Parse values as numbers (API may return strings)
    const windDir = parseFloat(met.wind_dir);
    const windSpeed = parseFloat(met.wind_speed);
    const blh = parseFloat(met.blh);

    document.getElementById('met-wind-dir').textContent = !isNaN(windDir) ? `${windDir.toFixed(0)}°` : '--';
    document.getElementById('met-wind-speed').textContent = !isNaN(windSpeed) ? `${windSpeed.toFixed(1)} m/s` : '--';
    document.getElementById('met-blh').textContent = !isNaN(blh) ? `${blh.toFixed(0)} m` : '--';
    document.getElementById('blh-note').textContent = met.blh_note || '';
}

// Update summary
function updateSummary(attribution) {
    document.getElementById('summary-text').textContent = attribution.summary || '';

    // Special highlight for Diwali
    const summaryCard = document.getElementById('summary-card');
    if (attribution.contributions?.local_combustion?.is_diwali) {
        summaryCard.style.borderColor = '#ef4444';
        summaryCard.style.borderWidth = '2px';
    } else {
        summaryCard.style.borderColor = '';
        summaryCard.style.borderWidth = '';
    }
}

// Update confidence badge
function updateConfidence(confidence) {
    const badge = document.getElementById('confidence-badge');
    badge.textContent = `${confidence} Confidence`;
    badge.className = `confidence-badge ${confidence?.toLowerCase() || 'medium'}`;
}

// Update marker color based on PM2.5
function updateMarkerColor(stationId, pm25) {
    const marker = markers[stationId];
    if (!marker) return;

    const color = getMarkerColor(pm25);
    const markerEl = marker.getElement().querySelector('.custom-marker');
    if (markerEl) {
        markerEl.style.backgroundColor = color;
    }
}

// Style for outfall point based on *relative* intensity
function getOutfallStyle(pm, maxPm) {
    if (!maxPm || maxPm <= 0 || pm == null || isNaN(pm)) {
        return {
            color: '#6b7280',
            radius: 6,
            fillOpacity: 0.25
        };
    }

    // Normalized intensity 0–1
    const norm = pm / maxPm;

    let color;
    if (norm > 0.8) {
        color = '#7f1d1d';   // very intense
    } else if (norm > 0.6) {
        color = '#ef4444';   // red
    } else if (norm > 0.4) {
        color = '#f97316';   // orange
    } else if (norm > 0.2) {
        color = '#eab308';   // yellow
    } else {
        color = '#22c55e';   // green / weak tail
    }

    // Bigger & more opaque near source, smaller & faint far away
    const radius = 6 + norm * 10;          // 6–16 px
    const fillOpacity = 0.25 + norm * 0.5; // 0.25–0.75

    return { color, radius, fillOpacity };
}

// Style for outfall point based on *relative* intensity
function getOutfallStyle(pm, maxPm) {
    if (!maxPm || maxPm <= 0 || pm == null || isNaN(pm)) {
        return {
            color: '#6b7280',
            radius: 6,
            fillOpacity: 0.2
        };
    }

    const norm = pm / maxPm; // 0–1

    let color;
    if (norm > 0.8) {
        color = '#7f1d1d';   // maroon
    } else if (norm > 0.6) {
        color = '#ef4444';   // red
    } else if (norm > 0.4) {
        color = '#f97316';   // orange
    } else if (norm > 0.2) {
        color = '#eab308';   // yellow
    } else {
        color = '#22c55e';   // green
    }

    const radius = 6 + norm * 10;          // 6–16 px
    const fillOpacity = 0.25 + norm * 0.5; // 0.25–0.75

    return { color, radius, fillOpacity };
}


// =====================
// OUTFALL VISUALIZATION
// =====================
function drawOutfall(outfallPoints) {
    // Clear previous outfall layer
    if (outfallLayer) {
        map.removeLayer(outfallLayer);
        outfallLayer = null;
    }

    // Clear previous animation
    if (outfallAnimationTimer) {
        clearInterval(outfallAnimationTimer);
        outfallAnimationTimer = null;
    }

    if (!outfallPoints || outfallPoints.length === 0) return;

    const path = outfallPoints.map(p => [p.latitude, p.longitude]);

    // Base polyline showing plume path
    const polyline = L.polyline(path, {
        weight: 3,
        opacity: 0.5,
        color: '#22d3ee'
    });

    // Max PM for relative intensity
    const maxPm = Math.max(
        ...outfallPoints.map(p => (p.predicted_PM25 ?? 0))
    );

    // Create all circles with very low initial opacity
    const circles = outfallPoints.map(p => {
        const pm = p.predicted_PM25 ?? 0;
        const base = getOutfallStyle(pm, maxPm);

        return L.circleMarker([p.latitude, p.longitude], {
            radius: base.radius,
            weight: 1,
            color: base.color,
            fillColor: base.color,
            opacity: 0.0,       // start hidden
            fillOpacity: 0.0    // start hidden
        }).bindPopup(`
            <strong>Outfall +${p.hour}h</strong><br>
            Distance: ${p.distance_km.toFixed(1)} km<br>
            Predicted PM2.5: ${pm.toFixed(0)} µg/m³
        `);
    });

    outfallLayer = L.layerGroup([polyline, ...circles]).addTo(map);

    // Auto-zoom for plume
    try {
        const bounds = outfallLayer.getBounds();
        if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [40, 40] });
        }
    } catch (e) {
        console.warn('Could not fit bounds for outfall:', e);
    }

    // 🎬 ANIMATION: make intensity "flow" along the plume
    let step = 0;
    const N = circles.length;

    outfallAnimationTimer = setInterval(() => {
        circles.forEach((circle, i) => {
            const pm = outfallPoints[i].predicted_PM25 ?? 0;
            const base = getOutfallStyle(pm, maxPm);

            if (i === step) {
                // Current head: bright & opaque
                circle.setStyle({
                    opacity: 1.0,
                    fillOpacity: 0.9,
                    color: base.color,
                    fillColor: base.color,
                    radius: base.radius + 2
                });
            } else if (i < step) {
                // Tail behind: dim but visible
                circle.setStyle({
                    opacity: 0.4,
                    fillOpacity: 0.35,
                    color: base.color,
                    fillColor: base.color,
                    radius: base.radius
                });
            } else {
                // Future points: almost invisible
                circle.setStyle({
                    opacity: 0.0,
                    fillOpacity: 0.0
                });
            }
        });

        step += 1;

        // Loop the flow animation
        if (step >= N) {
            step = 0;
        }
    }, 600); // ms per step – tweak for faster/slower flow
}


// Get color for outfall point based on predicted PM2.5
function getOutfallColor(pm) {
    if (pm == null || isNaN(pm)) return '#6b7280'; // neutral gray

    if (pm < 75) return '#22c55e'; // green - lower intensity
    if (pm < 150) return '#eab308'; // yellow
    if (pm < 250) return '#f97316'; // orange
    if (pm < 350) return '#ef4444'; // red
    return '#7f1d1d';               // maroon - extreme
}


// Refresh button handler - reload data when date changes
async function handleRefresh() {
    const date = document.getElementById('date-input').value;
    const hour = document.getElementById('hour-input').value;
    const timestamp = `${date}T${hour.padStart(2, '0')}:00`;

    // Reload fires for the new date
    await showFires(timestamp);

    // Update all station colors for the selected date
    await loadAllStationColors(timestamp);

    // If a station is selected, reload its data and industries
    if (selectedStation) {
        showIndustries(selectedStation.lat, selectedStation.lon);
        await loadStationData(selectedStation, timestamp);
    }
}

// Load AQI for all stations and update marker colors
async function loadAllStationColors(timestamp) {
    const selectedDate = timestamp.split('T')[0];

    for (const station of stations) {
        try {
            const response = await fetch(`/station/${station.station_id}/data?start_date=${selectedDate}&end_date=${selectedDate}&limit=24`);
            const data = await response.json();

            if (data.data && data.data.length > 0) {
                // Get average readings for all pollutants
                const getAvg = (field) => {
                    const values = data.data.map(r => r[field]).filter(v => v != null && !isNaN(v));
                    return values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : null;
                };

                const readings = {
                    PM25: getAvg('PM25') || getAvg('pm25'),
                    PM1: getAvg('PM1') || getAvg('pm1'),
                    PM10: getAvg('PM10') || getAvg('pm10'),
                    NO2: getAvg('NO2') || getAvg('no2'),
                    SO2: getAvg('SO2') || getAvg('so2'),
                    CO: getAvg('CO') || getAvg('co'),
                    O3: getAvg('O3') || getAvg('o3')
                };

                // Calculate AQI using all available pollutants
                const aqiResult = calculateAQI(readings);
                if (aqiResult.aqi !== null) {
                    const marker = markers[station.station_id];
                    if (marker) {
                        const markerEl = marker.getElement().querySelector('.custom-marker');
                        if (markerEl) {
                            markerEl.style.backgroundColor = aqiResult.color;
                        }
                    }
                }
            }
        } catch (error) {
            console.error(`Error loading data for station ${station.station_id}:`, error);
        }
    }

    console.log('Updated all station colors');
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    loadStations();

    // Set default date to today and hour to current hour
    const now = new Date();
    document.getElementById('date-input').value = now.toISOString().slice(0, 10);
    document.getElementById('hour-input').value = now.getHours().toString();

    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', handleRefresh);

    // Live button - fetch real-time data from CPCB RSS feed
    document.getElementById('live-btn').addEventListener('click', handleLiveData);
});

// Global to store live data
let liveData = null;

// Handle live data fetch
async function handleLiveData() {
    const liveBtn = document.getElementById('live-btn');
    liveBtn.classList.add('loading');
    liveBtn.textContent = '⏳ Loading...';

    try {
        const response = await fetch('/live');
        const data = await response.json();

        if (!data.success) {
            alert('Failed to fetch live data: ' + (data.error || 'Unknown error'));
            return;
        }

        liveData = data;
        console.log(`Live data received: ${data.count} stations, timestamp: ${data.timestamp}`);

        // Update date/hour inputs to match live data
        if (data.timestamp) {
            const ts = new Date(data.timestamp);
            document.getElementById('date-input').value = ts.toISOString().slice(0, 10);
            document.getElementById('hour-input').value = ts.getHours().toString();
        }

        // Update all station markers with live AQI
        for (const liveStation of data.stations) {
            const marker = markers[liveStation.station_id];
            if (!marker) continue;

            const readings = liveStation.readings;
            const aqiResult = calculateAQI({
                PM25: readings.PM25,
                PM10: readings.PM10,
                NO2: readings.NO2,
                SO2: readings.SO2,
                CO: readings.CO,
                O3: readings.O3
            });

            if (aqiResult.aqi !== null) {
                const markerEl = marker.getElement()?.querySelector('.custom-marker');
                if (markerEl) {
                    markerEl.style.backgroundColor = aqiResult.color;
                }
            }
        }

        // If a station is selected, update it with live data
        if (selectedStation) {
            const liveStationData = data.stations.find(s => s.station_id === selectedStation.station_id);
            if (liveStationData) {
                await selectStationWithLiveData(selectedStation, liveStationData);
            }
        }

        liveBtn.textContent = '🔴 Live (' + new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) + ')';

    } catch (error) {
        console.error('Error fetching live data:', error);
        alert('Failed to fetch live data. Check your internet connection.');
    } finally {
        liveBtn.classList.remove('loading');
    }
}

// Select station with live data (bypass CSV lookup)
async function selectStationWithLiveData(station, liveStationData) {
    selectedStation = station;

    // Show side panel loading state
    document.getElementById('side-panel').style.display = 'block';
    document.getElementById('station-name').textContent = station.station_name;

    const timestamp = liveStationData.timestamp;
    const readings = liveStationData.readings;

    // Update readings display
    updateReadings(readings);

    // Get live meteorology and fires from the global liveData
    const liveMet = liveData?.meteorology || {};
    const liveFires = liveData?.fires || {};

    // Calculate attribution with live readings AND live meteorology
    try {
        const attrResponse = await fetch('/attribution/modulated', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                timestamp: new Date().toISOString(),
                readings: {
                    PM25: readings.PM25,
                    PM10: readings.PM10,
                    NO2: readings.NO2,
                    SO2: readings.SO2,
                    CO: readings.CO
                },
                // Pass live weather data
                wind_dir: liveMet.wind_dir,
                wind_speed: liveMet.wind_speed,
                blh: liveMet.blh,
                fire_count: liveFires.nw_count || liveFires.count || 0
            })
        });

        const attribution = await attrResponse.json();

        if (attribution.error) {
            console.error('Attribution error:', attribution.error);
            return;
        }

        // Update chart and sources
        updateChart(attribution.contributions);
        updateSources(attribution.contributions);
        updateSummary(attribution);

        // Use live meteorology for display
        const displayMeteo = {
            wind_dir: liveMet.wind_dir,
            wind_speed: liveMet.wind_speed,
            blh: liveMet.blh,
            blh_note: liveMet.blh < 200 ? 'Severe Inversion' :
                liveMet.blh < 400 ? 'Low' :
                    liveMet.blh < 800 ? 'Moderate' : 'Good'
        };
        updateMeteorology(displayMeteo);
        updateActions(attribution.contributions);

        // Update outfall using live data
        if (attribution.outfall) {
            updateOutfallPanel(attribution.outfall, displayMeteo);
            displayOutfallOnMap(attribution.outfall || []);
        }

        // Update confidence badge
        const badge = document.getElementById('confidence-badge');
        if (badge) {
            badge.textContent = '🔴 LIVE';
            badge.className = 'confidence-badge confidence-high';
        }

        // Show fire info in console
        console.log(`Live attribution: Wind ${liveMet.wind_dir}° @ ${liveMet.wind_speed} m/s, BLH ${liveMet.blh}m, ${liveFires.nw_count || 0} NW fires`);

    } catch (error) {
        console.error('Error calculating attribution:', error);
    }
}


