# Universal Natural Disaster Data Collector 🌐⚡

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Zero API Keys](https://img.shields.io/badge/API%20Keys-Zero%20Required-success.svg)](#-why-use-this)

An open-source, zero-API-key environmental intelligence engine that collects **live and past natural disaster indicators** for **any country, city, village, mountain, or 2 km GPS patch on Earth**.

Built specifically to serve as a high-fidelity data feed for early warning systems, disaster prediction models, dashboards, and AI agents via **REST API**, **Secret Share Codes**, **Interactive World Map**, and **Model Context Protocol (MCP)**.

---

## 🎯 Why Use This?

Most weather and disaster tools have critical shortcomings:
1. **API Key & Credit Walls**: Services charge heavily or require credit cards to query multi-strata soil or historical archives.
2. **Missing Disaster Indicators**: Standard weather APIs report temperature and rain, but omit **river discharge rates**, **multi-depth root-zone soil saturation**, and **USGS seismic activity**.
3. **Coarse Resolution**: Remote villages and mountain areas fail to geocode.
4. **Disconnected Data Silos**: Fetching atmosphere, hydrology, and earthquakes usually requires orchestrating 3+ completely separate client libraries.

**This engine solves all four problems:**
- **Zero API Keys**: Built entirely on open scientific feeds (Open-Meteo Land-Surface & Flood Models, USGS Earthquake Hazards, Nominatim).
- **All-In-One Unified Schema**: Atmospheric vitals, river discharge, soil moisture, and earthquakes unified in one JSON payload.
- **Micro-Location Precision**: Resolves any remote village, mountain pass, or raw GPS coordinates down to a 2 km grid cell.
- **Ready for ML & AI**: Instant CSV export for machine learning training and native MCP integration for AI models.

---

## 🌟 What This System Collects ("All Natural" Indicators)

1. **Atmospheric & Weather**:
   - Temperature (°C) & relative humidity (%)
   - Surface barometric pressure (hPa) & rapid low-pressure warning (vital for cyclone, storm, and hurricane tracking)
   - Precipitation (mm) & rain rates
   - Wind speed (10m) & dangerous wind gusts (km/h)
2. **Hydrology & River Flood Streamflow**:
   - Live river discharge rates ($m^3/s$) from global river models
   - 7-day mean and 7-day maximum river flow volume for flood detection
   - Clear `N/A` designation when a cell is not situated on a modelled river basin
3. **Multi-Strata Soil Moisture (Landslide & Flash Flood Warning)**:
   - Surface layer ($0-1\text{ cm}$) saturation
   - Intermediate root layers ($1-3\text{ cm}$ and $9-27\text{ cm}$)
   - Deep root zone ($27-81\text{ cm}$) saturation
4. **Real-Time Seismic & Earthquake Feeds (USGS)**:
   - Live tremors within configurable radius ($10 - 20,000\text{ km}$) of any target
   - Magnitude, focal depth (km), exact distance to village (km), and tsunami alert flags
5. **Continuous Historical Time-Series (Back to 1940)**:
   - Multi-year hourly time-series exports for training machine learning prediction models

---

## ⚡ Quick Start

### 1. Installation

```bash
git clone https://github.com/ybsa/global-weather-data-agent.git
cd global-weather-data-agent
pip install -e .
```

Requirements: Python 3.10+ (dependencies: `fastapi`, `uvicorn`, `pydantic`).

---

### 2. Launch the Interactive World Map & Web Dashboard

```bash
data-agent serve --port 8000
```

Open your browser to:
- **Interactive World Map**: [http://localhost:8000](http://localhost:8000)
  - 🗺️ **Click Anywhere on Earth**: Click any spot on the globe down to a 2 km patch to drop a sensor pin and fetch live indicators.
  - 🔍 **Live Autocomplete Search**: Type any village or city name with instant search suggestions, keyboard navigation (`↑`/`↓`), and case-insensitive matching.
  - 🌋 **Live Earthquake Epicenters**: Nearby USGS tremors plotted directly on the map with magnitude color-coding and focal depth popups.
  - 📍 **GPS One-Click**: One-click "My GPS" to inspect your current surroundings.
  - 📥 **Custom CSV Export**: Export historical archives with user-selected start and end dates directly from the dashboard.
- **Interactive OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## 💻 CLI Commands & Usage Examples

The CLI tool `data-agent` works out of the box with UTF-8 support for international place names:

### 1. Search Any Village, Town, or Mountain
```bash
data-agent search "Namche Bazaar"
data-agent search "Valparaíso"
data-agent search "Sendai" --country JP
```

### 2. Fetch Live Vitals for Any Location
```bash
# By name (case-insensitive, supports village, city, mountain):
data-agent live "Namche Bazaar"
data-agent live "Sendai" --radius 300
data-agent live "Lahaina, HI"

# By exact GPS coordinates:
data-agent live "27.8033, 86.7144"
```

### 3. Check Live USGS Earthquakes Near a City
```bash
data-agent seismic "Tokyo" --radius 250 --min-mag 2.5
```

### 4. Export Historical ML Training Dataset to CSV
```bash
data-agent export "Tokyo" "Sendai" --start 2023-01-01 --end 2023-12-31 --output datasets/training_data.csv
```

### 5. Create a Monitored Collection with a Secret Share Code
```bash
data-agent collect "Sendai" "Namche Bazaar" --name "Himalaya & Pacific Grid"
```

---

## 🔑 Secret Share Codes & Dataset Sharing

You can group locations into a monitored collection. Each collection generates a unique **Secret Code** (e.g. `NAT-82690C91`):

```bash
# Query live snapshots for any shared collection:
curl http://localhost:8000/api/share/NAT-82690C91

# Download entire collection history as CSV:
curl http://localhost:8000/api/share/NAT-82690C91/download?format=csv -o dataset.csv

# Append a new observation to an existing collection:
curl -X POST http://localhost:8000/api/share/NAT-82690C91/snapshot
```

---

## 🔌 AI & Model Context Protocol (MCP) Integration

Connect this collector directly to **Claude Desktop**, **Antigravity**, **Cursor**, or any MCP-compatible client.

### Run MCP Server
```bash
data-agent mcp
# or
python -m data_agent.mcp_server
```

### MCP Configuration (`mcp_config.json`)
```json
{
  "mcpServers": {
    "natural-data-collector": {
      "command": "python",
      "args": ["-m", "data_agent.mcp_server"]
    }
  }
}
```

### Available MCP Tools for AI Models
| Tool | Description |
| :--- | :--- |
| `search_global_locations(query, country_code)` | Geocode any village, city, or coordinate globally |
| `get_live_natural_indicators(location_name, country_code)` | Real-time atmosphere, hydrology, and USGS earthquakes |
| `get_past_natural_time_series(location_name, start_date, end_date)` | Continuous hourly historical series for ML training |
| `get_nearby_earthquakes(location_name, radius_km, min_magnitude)` | Real-time USGS earthquake feed within radius |

---

## 🐍 Python SDK Usage

```python
from data_agent import resolve_location, get_natural_live_report, fetch_historical_series

# 1. Geocode any remote village or coordinate
loc = resolve_location("Namche Bazaar", country_code="NP")

# 2. Collect live multi-domain indicators
report = get_natural_live_report(loc, seismic_radius_km=300.0)
print(f"Location: {report.location.display_name}")
print(f"Temperature: {report.atmosphere.temperature_2m} °C")
print(f"Surface Pressure: {report.atmosphere.surface_pressure_hpa} hPa")
if report.hydrology.river_discharge_m3s is not None:
    print(f"River Discharge: {report.hydrology.river_discharge_m3s} m³/s")
print(f"Nearby Earthquakes (300km): {len(report.recent_earthquakes)}")

# 3. Fetch hourly historical archive for model training
history = fetch_historical_series(loc, start_date="2023-01-01", end_date="2023-01-07")
print(f"Fetched {len(history)} hourly observations.")
```

---

## 🧪 Running Tests

```bash
python -m unittest discover -s tests
```

---

## 🛡️ License

This project is open-source under the [MIT License](LICENSE). Free for academic, personal, and commercial disaster-preparedness workflows.
