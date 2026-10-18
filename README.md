# Global Weather Data Agent

Project 1 collects provenance-labelled weather data worldwide, stores collection runs in SQLite, and exports historical series for downstream models. Its included Nepal locations file is only an example configuration; replace it with locations anywhere in the world.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
weather-agent collect
timesfm-export --output exports/nepal_timesfm_train.csv
```

The SQLite database, exports, logs, and secrets are intentionally excluded from Git. Give the exported CSV to the model repository as a release asset or through object storage; do not rely on a sibling-folder path.

## License

MIT. See [LICENSE](LICENSE).

