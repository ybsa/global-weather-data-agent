# Universal Global Weather Data Agent

Free, open-source global weather scraping, dynamic geocoding, and machine-learning dataset export engine.
Works for any city, village, mountain, or landmark worldwide with **zero API keys required**.

Powered by Open-Meteo's open atmospheric models and global elevation APIs.

---

## ⚡ Quick Start

### 1. Installation

```bash
git clone https://github.com/ybsa/global-weather-data-agent.git
cd global-weather-data-agent
pip install -e .
```

### 2. Search Any Location Globally

Resolves names to exact latitude, longitude, elevation, and time zone:

```bash
data-agent search "Tokyo"
data-agent search "Namche Bazaar" --country NP
data-agent search "Zurich"
```

### 3. Fetch Real-Time Weather

```bash
data-agent live "New York"
data-agent live "London" --country GB
data-agent live "Kyoto"
```

### 4. Fetch Multi-Day Hourly Forecast

```bash
data-agent forecast "Paris" --days 3
```

### 5. Export Historical Datasets for Machine Learning (TimesFM)

Export multi-location hourly time series directly into a formatted CSV ready for time-series foundation models:

```bash
data-agent export "Tokyo" "London" "New York" --start 2023-01-01 --end 2023-12-31 --output datasets/global_weather.csv
```

---

## 🐍 Python API

You can also use `data_agent` as a modular Python library:

```python
from data_agent import resolve_location, get_current_weather, get_hourly_forecast, export_from_queries

# 1. Geocode
loc = resolve_location("Reykjavik", country_code="IS")

# 2. Live snapshot
weather = get_current_weather(loc)
print(f"{loc.name}: {weather.temperature_2m}°C, {weather.relative_humidity_2m}% humidity")

# 3. Hourly forecast
forecast = get_hourly_forecast(loc, forecast_days=5)
print(f"Next 24h temps: {forecast.temperatures[:24]}")

# 4. Generate ML training dataset
export_from_queries(["Tokyo", "Zurich"], output_path="training_data.csv", start_date="2023-01-01", end_date="2023-06-30")
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
