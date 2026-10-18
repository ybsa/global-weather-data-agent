# Global Weather Data Agent

Project 1 collects provenance-labelled weather data worldwide, stores collection runs in SQLite, and exports historical series for downstream models. The default `config/locations.csv` is the Nepal configuration used by the connected Nepal projects. Use `config/world_locations.example.csv` to see a starter configuration spanning several countries.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
weather-agent --database data/weather.sqlite3 collect --locations config/world_locations.example.csv
weather-agent live "London, GB"
weather-agent coverage
```

On macOS or Linux, activate the virtual environment with `source .venv/bin/activate` instead. The commands work from the repository root.

## Configure locations

Create a CSV with these columns: `location_id,name,province,district,latitude,longitude,elevation_m,country_code`. Use decimal WGS84 coordinates, a unique `location_id`, and the two-letter ISO country code. `province` and `district` can hold the first and second administrative-area names for the location. Then collect it with `weather-agent collect --locations path/to/your_locations.csv`.

You can look up a place directly without adding it to a CSV: `weather-agent live "Tokyo, JP"`. When a place name exists in several countries, include the country or region (for example, `Springfield, US`); the agent shows matches when it cannot safely choose. Use country codes to distinguish saved locations with the same name.

The weather API uses each location's local time zone automatically. Current conditions from Open-Meteo are model estimates; hourly values are forecasts, not direct station observations. Follow the local meteorological service for official warnings.

The SQLite database, logs, exports, and secrets are runtime files and are excluded from Git. To export historical data, use `timesfm-export --locations config/world_locations.example.csv --output exports/weather_timeseries.csv`. Give an export to another project as a release asset or through object storage; do not rely on a sibling-folder path.

## License

MIT. See [LICENSE](LICENSE).

