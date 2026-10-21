"""Universal Natural Data Collector REST API & Web Dashboard.
FastAPI server providing endpoints for live/historical natural data,
interactive World Map with click-to-inspect down to 2km precision,
dynamic multi-category environmental trend charts (Chart.js),
secret shareable codes, CSV exports, and dashboard monitoring.
"""
from __future__ import annotations

import json
from typing import Any
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from .models import LocationInfo
from .archive import fetch_historical_series
from .collector import get_natural_live_report
from .geocoder import GeocodingError, resolve_location, search_locations, resolve_coordinates
from .hydrology import get_hydrology
from .seismic import get_recent_earthquakes
from .storage import get_storage
from .charts import fetch_chart_data

app = FastAPI(
    title="Universal Natural Data Collector API",
    description="Live & historical environmental indicator collector for any coordinate or village globally. Zero API keys required.",
    version="1.3.0",
)

# Enable CORS for external dashboards and prediction services
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(GeocodingError)
async def geocoding_error_handler(request: Request, exc: GeocodingError):
    """Report geocoding outages as 503 so clients can tell them apart from 'place not found' (404)."""
    return JSONResponse(
        status_code=503,
        content={"detail": "The geocoding service is unreachable right now. Please try again in a moment."},
    )


class CreateCollectionRequest(BaseModel):
    title: str
    locations: list[str]
    description: str = ""
    custom_secret_code: str | None = None


class LocationPayload(BaseModel):
    """An already-resolved location (e.g. one picked from /api/search results)."""
    location_id: str
    name: str
    country: str = ""
    country_code: str = ""
    admin1: str = ""
    admin2: str = ""
    admin3: str = ""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    elevation_m: float = 0.0
    timezone: str = "UTC"

    def to_location(self) -> LocationInfo:
        return LocationInfo(**self.model_dump())


# Embedded responsive dashboard HTML with interactive Leaflet World Map + Chart.js
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Natural Data Collector - Global Environmental Indicators</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    
    <!-- Leaflet.js for Interactive World Map (100% Free, No API Key Required) -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

    <!-- Chart.js for Dynamic Multi-Category Trend Charts -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <style>
        :root {
            --bg: #090d16;
            --surface: #111726;
            --surface-card: rgba(22, 30, 49, 0.78);
            --surface-border: rgba(255, 255, 255, 0.08);
            --primary: #38bdf8;
            --primary-glow: rgba(56, 189, 248, 0.25);
            --accent-green: #34d399;
            --accent-amber: #fbbf24;
            --accent-rose: #f43f5e;
            --accent-indigo: #818cf8;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --radius-lg: 16px;
            --radius-md: 10px;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
        }

        body {
            background-color: var(--bg);
            color: var(--text-main);
            min-height: 100vh;
            background-image: 
                radial-gradient(circle at 15% 15%, rgba(56, 189, 248, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 85% 80%, rgba(129, 140, 248, 0.08) 0%, transparent 45%);
            background-attachment: fixed;
            padding-bottom: 60px;
        }

        header {
            border-bottom: 1px solid var(--surface-border);
            backdrop-filter: blur(12px);
            background: rgba(9, 13, 22, 0.85);
            position: sticky;
            top: 0;
            z-index: 1000;
            padding: 16px 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brand-icon {
            width: 38px;
            height: 38px;
            background: linear-gradient(135deg, #0284c7, #38bdf8);
            border-radius: 10px;
            display: grid;
            place-items: center;
            font-size: 20px;
            box-shadow: 0 0 16px var(--primary-glow);
        }

        .brand h1 {
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: #fff;
        }

        .brand span {
            font-size: 0.75rem;
            color: var(--accent-green);
            background: rgba(52, 211, 153, 0.12);
            padding: 2px 8px;
            border-radius: 20px;
            font-weight: 600;
            margin-left: 8px;
        }

        .nav-links {
            display: flex;
            gap: 12px;
        }

        .nav-btn {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--surface-border);
            color: var(--text-main);
            padding: 8px 16px;
            border-radius: var(--radius-md);
            font-size: 0.85rem;
            text-decoration: none;
            transition: all 0.2s;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .nav-btn:hover {
            background: rgba(255, 255, 255, 0.12);
            border-color: var(--primary);
        }

        .container {
            max-width: 1360px;
            margin: 28px auto;
            padding: 0 24px;
        }

        .hero {
            text-align: center;
            margin-bottom: 24px;
        }

        .hero h2 {
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            margin-bottom: 8px;
            background: linear-gradient(135deg, #ffffff 40%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero p {
            color: var(--text-muted);
            font-size: 1.05rem;
            max-width: 800px;
            margin: 0 auto;
        }

        /* Map Section Card */
        .map-card {
            background: var(--surface-card);
            border: 1px solid var(--surface-border);
            border-radius: var(--radius-lg);
            padding: 16px;
            backdrop-filter: blur(16px);
            box-shadow: 0 14px 40px rgba(0,0,0,0.4);
            margin-bottom: 28px;
            position: relative;
        }

        .map-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 12px;
            padding: 0 4px;
        }

        .map-controls {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
            width: 100%;
        }

        .search-input {
            flex: 1;
            min-width: 280px;
            background: rgba(9, 13, 22, 0.85);
            border: 1px solid var(--surface-border);
            border-radius: var(--radius-md);
            padding: 12px 18px;
            color: #fff;
            font-size: 0.95rem;
            outline: none;
            transition: border-color 0.2s;
        }

        .search-input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 2px var(--primary-glow);
        }

        /* Search suggestions dropdown */
        .search-wrap {
            position: relative;
            flex: 1;
            min-width: 280px;
            display: flex;
        }

        .search-wrap .search-input {
            width: 100%;
            min-width: 0;
        }

        .suggestions {
            display: none;
            position: absolute;
            top: calc(100% + 6px);
            left: 0;
            right: 0;
            z-index: 2000;
            max-height: 320px;
            overflow-y: auto;
            background: rgba(13, 19, 33, 0.97);
            border: 1px solid var(--surface-border);
            border-radius: var(--radius-md);
            box-shadow: 0 16px 40px rgba(0, 0, 0, 0.55);
            backdrop-filter: blur(14px);
            animation: suggestFade 0.14s ease-out;
        }

        @keyframes suggestFade {
            from { opacity: 0; transform: translateY(-4px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .suggestion-item {
            padding: 10px 16px;
            cursor: pointer;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            transition: background 0.12s;
        }

        .suggestion-item:last-child { border-bottom: none; }

        .suggestion-item:hover,
        .suggestion-item.active {
            background: rgba(56, 189, 248, 0.12);
        }

        .suggestion-name {
            font-weight: 600;
            font-size: 0.92rem;
            color: var(--text-main);
        }

        .suggestion-meta {
            font-size: 0.78rem;
            color: var(--text-muted);
            margin-top: 2px;
            font-family: 'JetBrains Mono', monospace;
        }

        .suggestion-empty {
            padding: 12px 16px;
            font-size: 0.85rem;
            color: var(--text-muted);
        }

        .date-input {
            background: rgba(9, 13, 22, 0.85);
            border: 1px solid var(--surface-border);
            border-radius: var(--radius-md);
            color: var(--text-main);
            padding: 8px 10px;
            font-size: 0.82rem;
            font-family: 'JetBrains Mono', monospace;
            color-scheme: dark;
        }

        button:disabled {
            opacity: 0.55;
            cursor: wait !important;
        }

        .btn-primary {
            background: linear-gradient(135deg, #0284c7, #38bdf8);
            border: none;
            color: #fff;
            padding: 12px 22px;
            border-radius: var(--radius-md);
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: 0 4px 14px var(--primary-glow);
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .btn-primary:hover {
            opacity: 0.92;
            transform: translateY(-1px);
        }

        #worldMap {
            width: 100%;
            height: 480px;
            border-radius: var(--radius-md);
            border: 1px solid rgba(255,255,255,0.1);
            background: #0d121f;
            z-index: 10;
        }

        .map-hint-banner {
            position: absolute;
            bottom: 28px;
            left: 28px;
            background: rgba(9, 13, 22, 0.88);
            backdrop-filter: blur(8px);
            border: 1px solid var(--surface-border);
            padding: 8px 16px;
            border-radius: 30px;
            font-size: 0.82rem;
            color: var(--primary);
            z-index: 400;
            display: flex;
            align-items: center;
            gap: 8px;
            pointer-events: none;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }

        /* Location Banner */
        .location-banner {
            background: var(--surface-card);
            border: 1px solid var(--surface-border);
            border-radius: var(--radius-lg);
            padding: 20px 24px;
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }

        /* Vitals Grid */
        .vitals-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
            margin-bottom: 28px;
        }

        .vital-card {
            background: var(--surface-card);
            border: 1px solid var(--surface-border);
            border-radius: var(--radius-lg);
            padding: 22px;
            backdrop-filter: blur(12px);
            position: relative;
            overflow: hidden;
            transition: transform 0.2s, border-color 0.2s;
        }

        .vital-card:hover {
            transform: translateY(-2px);
            border-color: rgba(255, 255, 255, 0.18);
        }

        .vital-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
        }

        .vital-title {
            font-size: 0.82rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .vital-badge {
            font-size: 0.72rem;
            font-family: 'JetBrains Mono', monospace;
            padding: 3px 8px;
            border-radius: 6px;
            background: rgba(255,255,255,0.06);
        }

        .vital-value {
            font-size: 2.1rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin-bottom: 6px;
        }

        .vital-sub {
            font-size: 0.85rem;
            color: var(--text-muted);
        }

        /* ================= Dynamic Charts Card ================= */
        .charts-card {
            background: var(--surface-card);
            border: 1px solid var(--surface-border);
            border-radius: var(--radius-lg);
            padding: 24px;
            backdrop-filter: blur(16px);
            box-shadow: 0 14px 40px rgba(0,0,0,0.4);
            margin-bottom: 28px;
        }

        .charts-toolbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--surface-border);
            padding-bottom: 16px;
        }

        .category-tabs {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .cat-tab {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--surface-border);
            color: var(--text-muted);
            padding: 7px 14px;
            border-radius: 20px;
            font-size: 0.84rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .cat-tab:hover {
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
        }

        .cat-tab.active {
            background: linear-gradient(135deg, rgba(2, 132, 199, 0.35), rgba(56, 189, 248, 0.35));
            border-color: var(--primary);
            color: #fff;
            box-shadow: 0 0 12px var(--primary-glow);
        }

        .range-controls {
            display: flex;
            gap: 6px;
            background: rgba(9, 13, 22, 0.6);
            padding: 4px;
            border-radius: 8px;
            border: 1px solid var(--surface-border);
        }

        .range-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }

        .range-btn.active {
            background: var(--primary);
            color: #090d16;
            font-weight: 700;
        }

        .chart-stats-bar {
            display: flex;
            gap: 20px;
            margin-top: 16px;
            padding-top: 14px;
            border-top: 1px solid var(--surface-border);
            flex-wrap: wrap;
        }

        .stat-item {
            font-size: 0.82rem;
            color: var(--text-muted);
        }

        .stat-item strong {
            color: var(--text-main);
            font-size: 0.95rem;
            font-family: 'JetBrains Mono', monospace;
            margin-left: 4px;
        }

        /* Split Section: Details & Secret Sharing */
        .split-layout {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 36px;
        }

        @media (max-width: 900px) {
            .split-layout {
                grid-template-columns: 1fr;
            }
        }

        .panel-card {
            background: var(--surface-card);
            border: 1px solid var(--surface-border);
            border-radius: var(--radius-lg);
            padding: 24px;
            backdrop-filter: blur(12px);
        }

        .panel-card h3 {
            font-size: 1.15rem;
            font-weight: 700;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .eq-item {
            padding: 12px 14px;
            border-bottom: 1px solid var(--surface-border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 0.88rem;
        }

        .eq-item:last-child {
            border-bottom: none;
        }

        .eq-mag {
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.85rem;
            font-family: 'JetBrains Mono', monospace;
        }

        .mag-low { background: rgba(52, 211, 153, 0.15); color: var(--accent-green); }
        .mag-med { background: rgba(251, 191, 36, 0.15); color: var(--accent-amber); }
        .mag-high { background: rgba(244, 63, 94, 0.18); color: var(--accent-rose); }

        pre.code-block {
            background: #060910;
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: var(--radius-md);
            padding: 14px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            color: #38bdf8;
            overflow-x: auto;
            position: relative;
            margin-top: 10px;
        }

        .copy-btn {
            position: absolute;
            top: 8px;
            right: 8px;
            background: rgba(255,255,255,0.1);
            border: none;
            color: #fff;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.72rem;
            cursor: pointer;
        }

        .copy-btn:hover {
            background: var(--primary);
        }

        .secret-badge {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: rgba(56, 189, 248, 0.12);
            border: 1px dashed var(--primary);
            padding: 10px 18px;
            border-radius: var(--radius-md);
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.2rem;
            font-weight: 700;
            color: var(--primary);
            margin: 12px 0;
            cursor: pointer;
        }

        .form-group {
            margin-bottom: 14px;
        }

        .form-label {
            display: block;
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 6px;
            font-weight: 500;
        }

        .form-control {
            width: 100%;
            background: rgba(9, 13, 22, 0.7);
            border: 1px solid var(--surface-border);
            border-radius: var(--radius-md);
            padding: 10px 14px;
            color: #fff;
            font-size: 0.9rem;
            outline: none;
        }

        .form-control:focus {
            border-color: var(--primary);
        }

        /* Leaflet Dark Customizations */
        .leaflet-container {
            background: #090d16 !important;
        }
        .leaflet-popup-content-wrapper {
            background: #111726 !important;
            color: #fff !important;
            border: 1px solid rgba(255,255,255,0.15) !important;
            border-radius: 10px !important;
        }
        .leaflet-popup-tip {
            background: #111726 !important;
        }
    </style>
</head>
<body>

<header>
    <div class="brand">
        <div class="brand-icon">🌐</div>
        <div>
            <h1>Universal Natural Data Collector</h1>
        </div>
        <span>LIVE GLOBAL MAP READY</span>
    </div>
    <div class="nav-links">
        <a href="/docs" target="_blank" class="nav-btn">📖 API Docs</a>
        <button class="nav-btn" onclick="locateUser()">📍 Locate Me</button>
    </div>
</header>

<div class="container">
    <div class="hero">
        <h2>Interactive Global Environmental Collector</h2>
        <p>Click <strong>any point on Earth</strong> down to a 2 km patch or search any village/coordinates to instantly collect atmospheric, river flood discharge, soil moisture, and USGS earthquakes. Zero API keys required.</p>
    </div>

    <!-- Map Card -->
    <div class="map-card">
        <div class="map-header">
            <div class="map-controls">
                <div class="search-wrap">
                    <input type="text" id="queryInput" class="search-input" placeholder="🔍 Search any village, mountain, or paste GPS coords (e.g. 27.8033, 86.7144)..." value="Tokyo"
                           autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="searchSuggestions">
                    <div id="searchSuggestions" class="suggestions" role="listbox"></div>
                </div>
                <button class="btn-primary" onclick="searchFromInput()">⚡ Search Place</button>
                <button class="nav-btn" onclick="locateUser()">📍 My GPS</button>
            </div>
        </div>

        <!-- The Interactive Map Container -->
        <div id="worldMap"></div>
        <div class="map-hint-banner">
            <span>👆 <strong>Click anywhere on Earth</strong> to drop a 2 km sensor pin and fetch live data</span>
        </div>
    </div>

    <!-- Active Location Banner -->
    <div class="location-banner">
        <div>
            <div style="font-size: 0.78rem; text-transform: uppercase; color: var(--primary); font-weight: 700; letter-spacing: 0.05em; margin-bottom: 4px;">CURRENT OBSERVATION TARGET</div>
            <h3 id="locationHeader" style="font-size: 1.45rem; font-weight: 800;">Tokyo, Japan</h3>
            <p id="locationSub" style="color: var(--text-muted); font-size: 0.88rem; font-family: 'JetBrains Mono', monospace; margin-top: 4px;">Lat: 35.6762° | Lon: 139.6503° | Elev: 40.0m</p>
        </div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
            <button class="nav-btn" id="btnSaveCollection" onclick="saveToCurrentCollection()">💾 Save to Collection</button>
            <span style="display: inline-flex; gap: 6px; align-items: center;">
                <input type="date" id="csvStart" class="date-input" title="Historical export start date" aria-label="Export start date">
                <span style="color: var(--text-muted); font-size: 0.8rem;">to</span>
                <input type="date" id="csvEnd" class="date-input" title="Historical export end date" aria-label="Export end date">
            </span>
            <button class="nav-btn" id="btnExportCsv" onclick="downloadCurrentCSV()">📥 Export Historical CSV</button>
        </div>
    </div>

    <!-- Vitals Cards Grid -->
    <div class="vitals-grid">
        <!-- Card 1: Pressure -->
        <div class="vital-card">
            <div class="vital-header">
                <span class="vital-title">Surface Pressure</span>
                <span class="vital-badge" id="pressureBadge">ATMOSPHERE</span>
            </div>
            <div class="vital-value" id="valPressure">-- <span style="font-size: 1rem; font-weight: 500; color: var(--text-muted);">hPa</span></div>
            <div class="vital-sub" id="subPressure">Barometric sensor baseline</div>
        </div>

        <!-- Card 2: Wind & Gusts -->
        <div class="vital-card">
            <div class="vital-header">
                <span class="vital-title">Wind & Gusts</span>
                <span class="vital-badge">10M AGL</span>
            </div>
            <div class="vital-value" id="valWind">-- <span style="font-size: 1rem; font-weight: 500; color: var(--text-muted);">km/h</span></div>
            <div class="vital-sub" id="subGusts">Gusts: -- km/h</div>
        </div>

        <!-- Card 3: River Discharge (Flood API) -->
        <div class="vital-card">
            <div class="vital-header">
                <span class="vital-title">River Discharge</span>
                <span class="vital-badge" style="color: var(--primary);">FLOOD STREAMFLOW</span>
            </div>
            <div class="vital-value" id="valRiver">-- <span style="font-size: 1rem; font-weight: 500; color: var(--text-muted);">m³/s</span></div>
            <div class="vital-sub" id="subRiver">Open-Meteo Global River Model</div>
        </div>

        <!-- Card 4: Soil Moisture (Landslide / Saturation) -->
        <div class="vital-card">
            <div class="vital-header">
                <span class="vital-title">Soil Moisture</span>
                <span class="vital-badge" style="color: var(--accent-green);">0-1 CM STRATUM</span>
            </div>
            <div class="vital-value" id="valSoil">-- <span style="font-size: 1rem; font-weight: 500; color: var(--text-muted);">m³/m³</span></div>
            <div class="vital-sub" id="subSoilDeep">Root Zone (27-81cm): -- m³/m³</div>
        </div>

        <!-- Card 5: Closest USGS Earthquake -->
        <div class="vital-card">
            <div class="vital-header">
                <span class="vital-title">Nearest Seismic Tremor</span>
                <span class="vital-badge" style="color: var(--accent-amber);">USGS FEED</span>
            </div>
            <div class="vital-value" id="valEarthquake">--</div>
            <div class="vital-sub" id="subEarthquake">Distance: -- km</div>
        </div>

        <!-- Card 6: Temperature & Rain -->
        <div class="vital-card">
            <div class="vital-header">
                <span class="vital-title">Precipitation & Temp</span>
                <span class="vital-badge">SURFACE</span>
            </div>
            <div class="vital-value" id="valPrecip">-- <span style="font-size: 1rem; font-weight: 500; color: var(--text-muted);">mm</span></div>
            <div class="vital-sub" id="subTemp">Temp: -- °C | Humidity: --%</div>
        </div>
    </div>

    <!-- ================= Interactive Charts Panel ================= -->
    <div class="charts-card">
        <div class="charts-toolbar">
            <div class="category-tabs">
                <button class="cat-tab active" onclick="switchChartCategory('pressure')">🌪️ Barometric Pressure</button>
                <button class="cat-tab" onclick="switchChartCategory('river')">🌊 River Flood Flow</button>
                <button class="cat-tab" onclick="switchChartCategory('soil')">🌱 Soil Moisture</button>
                <button class="cat-tab" onclick="switchChartCategory('precip')">🌧️ Rain & Precip</button>
                <button class="cat-tab" onclick="switchChartCategory('wind')">💨 Wind & Gusts</button>
                <button class="cat-tab" onclick="switchChartCategory('seismic')">🌋 Seismic Events</button>
            </div>
            <div class="range-controls">
                <button class="range-btn" onclick="switchChartDays(1, this)">24 Hours</button>
                <button class="range-btn active" onclick="switchChartDays(7, this)">7 Days</button>
                <button class="range-btn" onclick="switchChartDays(14, this)">14 Days</button>
            </div>
        </div>

        <!-- Chart Canvas -->
        <div style="position: relative; width: 100%; height: 320px;">
            <canvas id="naturalChart"></canvas>
        </div>

        <!-- Summary Stat Strip -->
        <div class="chart-stats-bar">
            <div class="stat-item">Category: <strong id="statCategory">Surface Barometric Pressure</strong></div>
            <div class="stat-item">Peak / Max: <strong id="statMax">--</strong></div>
            <div class="stat-item">Lowest / Min: <strong id="statMin">--</strong></div>
            <div class="stat-item">Latest Value: <strong id="statCurrent">--</strong></div>
            <div class="stat-item" style="margin-left: auto;">
                <button class="nav-btn" style="padding: 4px 10px; font-size: 0.78rem;" onclick="exportChartImage()">📷 Save Chart PNG</button>
            </div>
        </div>
    </div>

    <!-- Split Section: Seismic List & Secret Code Integration -->
    <div class="split-layout">
        <!-- Left: USGS Earthquakes List -->
        <div class="panel-card">
            <h3>🌋 Recent Seismic Activity (300 km Radius)</h3>
            <div id="earthquakeList" style="max-height: 380px; overflow-y: auto;">
                <p style="color: var(--text-muted); font-size: 0.9rem;">Click on the map to load seismic activity around any coordinate.</p>
            </div>
        </div>

        <!-- Right: Secret Code Share & MCP Integration -->
        <div class="panel-card">
            <h3>🔑 Secret Code & AI / MCP Integration</h3>
            <p style="color: var(--text-muted); font-size: 0.88rem; margin-bottom: 14px;">
                Create a persistent collection to monitor coordinates or share live streams with prediction pipelines, external dashboards, or AI agents using a secure secret code.
            </p>

            <div style="background: rgba(9, 13, 22, 0.6); padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--surface-border); margin-bottom: 16px;">
                <div class="form-group">
                    <label class="form-label">Collection Title</label>
                    <input type="text" id="newCollTitle" class="form-control" placeholder="e.g. My Monitored Regional Grid" value="My Regional Early Warning Grid">
                </div>
                <button class="btn-primary" id="btnGenerateCode" style="width: 100%; padding: 10px;" onclick="createNewCollection()">✨ Generate Secret Share Code</button>

                <div id="secretCodeBox" style="display: none; margin-top: 14px;">
                    <div style="font-size: 0.8rem; color: var(--text-muted);">Your Secret Share Code:</div>
                    <div class="secret-badge" id="displaySecretCode" onclick="copySecretCode()">NAT-XXXXXX</div>
                    <div style="font-size: 0.78rem; color: var(--text-muted);">Click to copy code. Use this in your prediction project or dashboard!</div>
                </div>
            </div>

            <div style="font-size: 0.85rem; font-weight: 600; margin-bottom: 6px;">🔌 MCP Server Plugin Snippet:</div>
            <pre class="code-block" id="mcpSnippet">{
  "mcpServers": {
    "natural-data-collector": {
      "command": "python",
      "args": ["-m", "data_agent.mcp_server"],
      "env": {
        "PYTHONPATH": "."
      }
    }
  }
}<button class="copy-btn" onclick="copySnippet()">Copy</button></pre>
        </div>
    </div>
</div>

<script>
    let map = null;
    let targetMarker = null;
    let radiusCircle2km = null;
    let seismicCircle300km = null;
    let earthquakeLayer = null;
    let currentLocation = null;
    let currentReport = null;
    let currentSecretCode = null;

    // Chart variables
    let chartInstance = null;
    let currentChartData = null;
    let activeCategory = 'pressure';
    let activeChartDays = 7;

    // Initialize Leaflet Interactive World Map
    function initMap() {
        // 100% Free Open Layers - Zero API keys required
        const streetMap = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>'
        });

        const satelliteMap = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: 19,
            attribution: 'Tiles &copy; Esri, USGS'
        });

        const topoMap = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
            maxZoom: 17,
            attribution: '&copy; OpenTopoMap'
        });

        map = L.map('worldMap', {
            zoomControl: true,
            minZoom: 2,
            maxZoom: 18,
            layers: [streetMap]
        }).setView([35.6762, 139.6503], 7);

        // Layer Switcher (Street, Satellite, Topography)
        const baseMaps = {
            "🗺️ Street & Villages": streetMap,
            "🛰️ Global Satellite": satelliteMap,
            "🏔️ Terrain & Topo": topoMap
        };
        L.control.layers(baseMaps, null, { position: 'topright' }).addTo(map);

        earthquakeLayer = L.layerGroup().addTo(map);

        // Click ANYWHERE on Earth listener
        map.on('click', function(e) {
            const lat = e.latlng.lat;
            const lon = e.latlng.lng;
            loadLiveReportByCoords(lat, lon);
        });

        // Load initial location
        loadLiveReportByCoords(35.6762, 139.6503);
    }

    async function loadLiveReportByCoords(lat, lon) {
        document.getElementById('locationHeader').innerText = `Collecting data for (${lat.toFixed(4)}°, ${lon.toFixed(4)}°)...`;
        document.getElementById('locationSub').innerText = "Querying live atmospheric, river flood discharge, soil moisture & USGS feeds...";

        updateMapMarker(lat, lon);

        try {
            const resp = await fetch(`/api/live?latitude=${lat}&longitude=${lon}&radius_km=300`);
            if (!resp.ok) throw new Error("Could not fetch natural indicators for coordinates.");
            const data = await resp.json();
            currentReport = data;
            currentLocation = data.location;
            renderReport(data);

            // Also load multi-category charts for this exact location!
            loadChartData(lat, lon, activeChartDays);
        } catch (e) {
            document.getElementById('locationHeader').innerText = `Error: ${e.message}`;
        }
    }

    async function errorDetail(resp, fallback) {
        try {
            const j = await resp.json();
            if (j && typeof j.detail === 'string') return j.detail;
        } catch (e) {}
        return fallback;
    }

    function isCoordQuery(q) {
        const parts = q.split(',');
        return parts.length === 2 && parts.every(p => p.trim() !== '' && !isNaN(Number(p.trim())));
    }

    function showReport(data) {
        currentReport = data;
        currentLocation = data.location;
        map.flyTo([data.location.latitude, data.location.longitude], 11, { duration: 1.5 });
        updateMapMarker(data.location.latitude, data.location.longitude);
        renderReport(data);
        loadChartData(data.location.latitude, data.location.longitude, activeChartDays);
    }

    async function searchFromInput() {
        const query = document.getElementById('queryInput').value.trim();
        hideSuggestions();
        if (!query) return;

        // Check if query is "lat, lon"
        if (isCoordQuery(query)) {
            const parts = query.split(',');
            loadLiveReportByCoords(parseFloat(parts[0]), parseFloat(parts[1]));
            return;
        }

        document.getElementById('locationHeader').innerText = `Searching for "${query}"...`;
        try {
            const resp = await fetch(`/api/live?location=${encodeURIComponent(query)}&radius_km=300`);
            if (resp.status === 404) throw new Error(`No place found for "${query}". Check the spelling, or click directly on the map.`);
            if (resp.status === 503) throw new Error("The geocoding service is unreachable right now. Please try again in a moment.");
            if (!resp.ok) throw new Error(await errorDetail(resp, "Something went wrong while fetching data."));
            showReport(await resp.json());
        } catch (e) {
            document.getElementById('locationHeader').innerText = `Error: ${e.message}`;
        }
    }

    async function loadLiveReportForLocation(loc) {
        document.getElementById('locationHeader').innerText = `Collecting data for ${loc.display_name}...`;
        document.getElementById('locationSub').innerText = "Querying live atmospheric, river flood discharge, soil moisture & USGS feeds...";
        try {
            const resp = await fetch('/api/live?radius_km=300', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(loc)
            });
            if (!resp.ok) throw new Error(await errorDetail(resp, "Could not fetch natural indicators for this place."));
            showReport(await resp.json());
        } catch (e) {
            document.getElementById('locationHeader').innerText = `Error: ${e.message}`;
        }
    }

    function locateUser() {
        if (!navigator.geolocation) {
            alert("Geolocation is not supported by your browser.");
            return;
        }
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                map.flyTo([lat, lon], 12, { duration: 1.5 });
                loadLiveReportByCoords(lat, lon);
            },
            () => {
                alert("Could not access your location. Please click directly on the map instead.");
            }
        );
    }

    function updateMapMarker(lat, lon) {
        if (targetMarker) map.removeLayer(targetMarker);
        if (radiusCircle2km) map.removeLayer(radiusCircle2km);
        if (seismicCircle300km) map.removeLayer(seismicCircle300km);

        targetMarker = L.circleMarker([lat, lon], {
            radius: 8,
            color: '#38bdf8',
            fillColor: '#38bdf8',
            fillOpacity: 0.9,
            weight: 2
        }).addTo(map);

        radiusCircle2km = L.circle([lat, lon], {
            radius: 2000,
            color: '#38bdf8',
            fillColor: '#38bdf8',
            fillOpacity: 0.15,
            weight: 1.5,
            dashArray: '4, 4'
        }).addTo(map).bindPopup("<b>Target Zone: 2 km Radius</b>");

        seismicCircle300km = L.circle([lat, lon], {
            radius: 300000,
            color: '#fbbf24',
            fillColor: '#fbbf24',
            fillOpacity: 0.02,
            weight: 1,
            dashArray: '6, 6'
        }).addTo(map);
    }

    function renderReport(data) {
        const loc = data.location;
        const atmo = data.atmosphere;
        const hydro = data.hydrology;
        const eqs = data.recent_earthquakes || [];

        document.getElementById('locationHeader').innerText = `${loc.display_name}`;
        document.getElementById('locationSub').innerText = 
            `Lat: ${loc.latitude.toFixed(4)}° | Lon: ${loc.longitude.toFixed(4)}° | Elevation: ${loc.elevation_m}m | Time: ${atmo.timestamp}`;

        // Pressure
        document.getElementById('valPressure').innerHTML = `${atmo.surface_pressure_hpa.toFixed(1)} <span style="font-size: 1rem; font-weight: 500; color: var(--text-muted);">hPa</span>`;
        if (atmo.surface_pressure_hpa < 995) {
            document.getElementById('subPressure').innerHTML = `<span style="color: var(--accent-rose); font-weight: 600;">⚠️ Rapid low pressure system</span>`;
        } else {
            document.getElementById('subPressure').innerText = `Normal atmospheric gradient`;
        }

        // Wind
        document.getElementById('valWind').innerHTML = `${atmo.wind_speed_10m.toFixed(1)} <span style="font-size: 1rem; font-weight: 500; color: var(--text-muted);">km/h</span>`;
        document.getElementById('subGusts').innerText = `Gusts: ${(atmo.wind_gusts_10m || 0).toFixed(1)} km/h`;

        // River Discharge
        if (hydro.river_discharge_m3s !== null && hydro.river_discharge_m3s !== undefined) {
            document.getElementById('valRiver').innerHTML = `${hydro.river_discharge_m3s} <span style="font-size: 1rem; font-weight: 500; color: var(--text-muted);">m³/s</span>`;
            document.getElementById('subRiver').innerText = `7-Day Max Flow: ${hydro.river_discharge_max_7d || '--'} m³/s`;
        } else {
            document.getElementById('valRiver').innerHTML = `N/A`;
            document.getElementById('subRiver').innerText = `No river discharge data here (no modelled river in this cell, or the flood service did not respond)`;
        }

        // Soil Moisture
        if (hydro.soil_moisture_0_to_1cm !== null && hydro.soil_moisture_0_to_1cm !== undefined) {
            document.getElementById('valSoil').innerHTML = `${hydro.soil_moisture_0_to_1cm.toFixed(3)} <span style="font-size: 1rem; font-weight: 500; color: var(--text-muted);">m³/m³</span>`;
            document.getElementById('subSoilDeep').innerText = `Root Zone (27-81cm): ${hydro.soil_moisture_27_to_81cm ? hydro.soil_moisture_27_to_81cm.toFixed(3) : '--'} m³/m³`;
        } else {
            document.getElementById('valSoil').innerText = `--`;
        }

        // Earthquakes
        if (eqs.length > 0) {
            const nearest = eqs[0];
            document.getElementById('valEarthquake').innerHTML = `M ${nearest.magnitude.toFixed(1)}`;
            document.getElementById('subEarthquake').innerText = `${nearest.distance_km} km away (${nearest.place})`;
        } else {
            document.getElementById('valEarthquake').innerText = `Quiet`;
            document.getElementById('subEarthquake').innerText = `No M1.0+ events within 300 km`;
        }

        // Precip & Temp
        document.getElementById('valPrecip').innerHTML = `${atmo.precipitation_mm.toFixed(1)} <span style="font-size: 1rem; font-weight: 500; color: var(--text-muted);">mm</span>`;
        document.getElementById('subTemp').innerText = `Temp: ${atmo.temperature_2m.toFixed(1)}°C | Humidity: ${atmo.relative_humidity_2m}%`;

        // Render Earthquakes on Map & in List
        earthquakeLayer.clearLayers();
        const eqContainer = document.getElementById('earthquakeList');
        if (eqs.length === 0) {
            eqContainer.innerHTML = `<p style="color: var(--text-muted); padding: 12px;">No seismic events in this radius.</p>`;
        } else {
            eqContainer.innerHTML = eqs.map(eq => {
                let badgeClass = "mag-low";
                let circleColor = "#34d399";
                if (eq.magnitude >= 4.5) {
                    badgeClass = "mag-high";
                    circleColor = "#f43f5e";
                } else if (eq.magnitude >= 3.0) {
                    badgeClass = "mag-med";
                    circleColor = "#fbbf24";
                }

                L.circleMarker([eq.latitude, eq.longitude], {
                    radius: Math.max(4, eq.magnitude * 2.5),
                    color: circleColor,
                    fillColor: circleColor,
                    fillOpacity: 0.6,
                    weight: 1.5
                }).addTo(earthquakeLayer).bindPopup(`
                    <b>M ${eq.magnitude.toFixed(1)} Earthquake</b><br>
                    ${eq.place}<br>
                    Distance: ${eq.distance_km} km<br>
                    Depth: ${eq.depth_km} km<br>
                    <a href="${eq.usgs_url}" target="_blank" style="color: #38bdf8;">USGS Details &rarr;</a>
                `);

                return `
                    <div class="eq-item">
                        <div>
                            <div style="font-weight: 600;">${eq.place}</div>
                            <div style="font-size: 0.78rem; color: var(--text-muted);">${eq.distance_km} km away | Depth: ${eq.depth_km} km | ${new Date(eq.timestamp).toLocaleTimeString()}</div>
                        </div>
                        <a href="${eq.usgs_url}" target="_blank" style="text-decoration: none;">
                            <span class="eq-mag ${badgeClass}">M ${eq.magnitude.toFixed(1)}</span>
                        </a>
                    </div>
                `;
            }).join('');
        }
    }

    // ================= Chart Loading & Rendering Engine =================
    async function loadChartData(lat, lon, days) {
        try {
            const resp = await fetch(`/api/charts?latitude=${lat}&longitude=${lon}&days=${days}`);
            if (!resp.ok) return;
            currentChartData = await resp.json();
            renderActiveChart();
        } catch (e) {
            console.error("Failed to load chart data:", e);
        }
    }

    function switchChartCategory(cat) {
        activeCategory = cat;
        // Update active tab buttons
        document.querySelectorAll('.cat-tab').forEach(b => b.classList.remove('active'));
        const activeBtn = Array.from(document.querySelectorAll('.cat-tab')).find(b => b.getAttribute('onclick').includes(cat));
        if (activeBtn) activeBtn.classList.add('active');

        renderActiveChart();
    }

    function switchChartDays(days, el) {
        activeChartDays = days;
        document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
        el.classList.add('active');

        if (currentLocation) {
            loadChartData(currentLocation.latitude, currentLocation.longitude, activeChartDays);
        }
    }

    function renderActiveChart() {
        if (!currentChartData) return;
        const ctx = document.getElementById('naturalChart').getContext('2d');

        let labels = [];
        let datasets = [];
        let statTitle = "";
        let unit = "";

        const hourly = currentChartData.hourly || {};
        const river = currentChartData.river || {};
        const seismic = currentChartData.seismic || [];

        // Format short timestamp: "Oct 21, 14:00"
        function fmt(isoStr) {
            if (!isoStr) return "";
            const d = new Date(isoStr);
            return `${d.getMonth()+1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:00`;
        }

        function fmtDate(isoStr) {
            if (!isoStr) return "";
            const d = new Date(isoStr);
            return `${d.getMonth()+1}/${d.getDate()}`;
        }

        if (activeCategory === 'pressure') {
            statTitle = "Surface Barometric Pressure (hPa)";
            unit = "hPa";
            labels = (hourly.times || []).map(fmt);
            const vals = (hourly.surface_pressure_hpa || []).map(v => v !== null ? v : null);

            datasets = [{
                label: 'Surface Pressure (hPa)',
                data: vals,
                borderColor: '#38bdf8',
                backgroundColor: 'rgba(56, 189, 248, 0.12)',
                borderWidth: 2,
                fill: true,
                tension: 0.3,
                pointRadius: 0,
                pointHoverRadius: 5,
            }];
            updateStats(vals, unit, statTitle);

        } else if (activeCategory === 'river') {
            statTitle = "Daily River Streamflow Discharge (m³/s)";
            unit = "m³/s";
            labels = (river.times || []).map(fmtDate);
            const vals = (river.discharge_m3s || []).map(v => v !== null ? v : 0);
            const maxVals = (river.discharge_max || []).map(v => v !== null ? v : 0);

            datasets = [
                {
                    label: 'River Discharge (m³/s)',
                    data: vals,
                    borderColor: '#0284c7',
                    backgroundColor: 'rgba(2, 132, 199, 0.25)',
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.2,
                    pointRadius: 4,
                },
                {
                    label: 'Peak Potential Flow (m³/s)',
                    data: maxVals,
                    borderColor: '#f59e0b',
                    borderDash: [4, 4],
                    borderWidth: 1.5,
                    fill: false,
                    tension: 0.2,
                    pointRadius: 3,
                }
            ];
            updateStats(vals, unit, statTitle);

        } else if (activeCategory === 'soil') {
            statTitle = "Multi-Strata Soil Moisture Saturation (m³/m³)";
            unit = "m³/m³";
            labels = (hourly.times || []).map(fmt);
            const surfaceMoist = hourly.soil_moisture_0_to_1cm || [];
            const deepMoist = hourly.soil_moisture_27_to_81cm || [];

            datasets = [
                {
                    label: 'Surface Layer (0-1 cm)',
                    data: surfaceMoist,
                    borderColor: '#34d399',
                    backgroundColor: 'rgba(52, 211, 153, 0.15)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                },
                {
                    label: 'Deep Root Zone (27-81 cm)',
                    data: deepMoist,
                    borderColor: '#10b981',
                    borderDash: [5, 5],
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                }
            ];
            updateStats(surfaceMoist, unit, statTitle);

        } else if (activeCategory === 'precip') {
            statTitle = "Precipitation & Rainfall Rate (mm/h)";
            unit = "mm";
            labels = (hourly.times || []).map(fmt);
            const precips = hourly.precipitation_mm || [];

            datasets = [{
                label: 'Precipitation (mm)',
                data: precips,
                borderColor: '#818cf8',
                backgroundColor: 'rgba(129, 140, 248, 0.4)',
                borderWidth: 1.5,
                type: 'bar',
                borderRadius: 4,
            }];
            updateStats(precips, unit, statTitle);

        } else if (activeCategory === 'wind') {
            statTitle = "Wind Velocity & Peak Gusts (km/h)";
            unit = "km/h";
            labels = (hourly.times || []).map(fmt);
            const winds = hourly.wind_speed_10m || [];
            const gusts = hourly.wind_gusts_10m || [];

            datasets = [
                {
                    label: 'Sustained Wind (10m)',
                    data: winds,
                    borderColor: '#38bdf8',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                },
                {
                    label: 'Peak Gusts (10m)',
                    data: gusts,
                    borderColor: '#fbbf24',
                    backgroundColor: 'rgba(251, 191, 36, 0.12)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                }
            ];
            updateStats(gusts, unit, statTitle);

        } else if (activeCategory === 'seismic') {
            statTitle = "USGS Earthquakes (Magnitude vs Distance Timeline)";
            unit = "M";
            if (seismic.length === 0) {
                labels = ["No events"];
                datasets = [{ label: 'No seismic tremors detected in 300km', data: [0] }];
            } else {
                labels = seismic.map(e => `${new Date(e.timestamp).toLocaleDateString()} ${new Date(e.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`);
                const mags = seismic.map(e => e.magnitude);
                datasets = [{
                    label: 'Tremor Magnitude (M)',
                    data: mags,
                    borderColor: '#f43f5e',
                    backgroundColor: 'rgba(244, 63, 94, 0.25)',
                    borderWidth: 2,
                    pointRadius: 6,
                    pointHoverRadius: 9,
                    showLine: false, // Scatter-style
                }];
                updateStats(mags, unit, statTitle);
            }
        }

        if (chartInstance) {
            chartInstance.destroy();
        }

        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 400 },
                plugins: {
                    legend: {
                        labels: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 12 } }
                    },
                    tooltip: {
                        backgroundColor: '#111726',
                        borderColor: 'rgba(255,255,255,0.15)',
                        borderWidth: 1,
                        titleColor: '#fff',
                        bodyColor: '#38bdf8',
                        padding: 10,
                        bodyFont: { family: 'JetBrains Mono' },
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.04)' },
                        ticks: { color: '#64748b', maxTicksLimit: 12 }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.06)' },
                        ticks: { color: '#94a3b8', font: { family: 'JetBrains Mono' } }
                    }
                }
            }
        });
    }

    function updateStats(values, unit, title) {
        document.getElementById('statCategory').innerText = title;
        const valid = values.filter(v => v !== null && !isNaN(v));
        if (valid.length === 0) {
            document.getElementById('statMax').innerText = `--`;
            document.getElementById('statMin').innerText = `--`;
            document.getElementById('statCurrent').innerText = `--`;
            return;
        }

        const maxVal = Math.max(...valid);
        const minVal = Math.min(...valid);
        const curVal = valid[valid.length - 1];

        document.getElementById('statMax').innerText = `${maxVal.toFixed(2)} ${unit}`;
        document.getElementById('statMin').innerText = `${minVal.toFixed(2)} ${unit}`;
        document.getElementById('statCurrent').innerText = `${curVal.toFixed(2)} ${unit}`;
    }

    function exportChartImage() {
        if (!chartInstance) return;
        const imgUrl = chartInstance.toBase64Image();
        const a = document.createElement('a');
        a.href = imgUrl;
        a.download = `natural_chart_${activeCategory}.png`;
        a.click();
    }

    const SECRET_CODE_STORAGE_KEY = 'natural_data_secret_code';
    let collectionRequestInFlight = false;

    function setCollectionButtonsBusy(busy) {
        collectionRequestInFlight = busy;
        ['btnSaveCollection', 'btnGenerateCode'].forEach(id => {
            const b = document.getElementById(id);
            if (b) b.disabled = busy;
        });
    }

    function setCurrentSecretCode(code) {
        currentSecretCode = code;
        try { localStorage.setItem(SECRET_CODE_STORAGE_KEY, code); } catch (e) {}
        document.getElementById('displaySecretCode').innerText = code;
        document.getElementById('secretCodeBox').style.display = 'block';
    }

    function forgetSecretCode() {
        currentSecretCode = null;
        try { localStorage.removeItem(SECRET_CODE_STORAGE_KEY); } catch (e) {}
        document.getElementById('secretCodeBox').style.display = 'none';
    }

    function restoreSecretCode() {
        let code = null;
        try { code = localStorage.getItem(SECRET_CODE_STORAGE_KEY); } catch (e) {}
        if (code) setCurrentSecretCode(code);
    }

    async function createNewCollection() {
        if (collectionRequestInFlight) return;  // prevents duplicate collections from repeated clicks
        setCollectionButtonsBusy(true);
        const title = document.getElementById('newCollTitle').value.trim() || "Natural Indicators Watch";
        const locName = currentLocation ? `${currentLocation.latitude},${currentLocation.longitude}` : "Tokyo";

        try {
            const resp = await fetch('/api/collections', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    title: title,
                    locations: [locName],
                    description: `Created from interactive map for ${currentLocation ? currentLocation.display_name : 'coordinates'}`
                })
            });
            if (!resp.ok) throw new Error(await errorDetail(resp, "Could not create the collection."));
            const result = await resp.json();
            setCurrentSecretCode(result.secret_code);
            alert(`Collection created! Secret code: ${result.secret_code}\\nShareable URL: ${window.location.origin}/api/share/${result.secret_code}`);
        } catch (e) {
            alert(`Error: ${e.message}`);
        } finally {
            setCollectionButtonsBusy(false);
        }
    }

    function copySecretCode() {
        if (!currentSecretCode) return;
        navigator.clipboard.writeText(currentSecretCode);
        alert(`Secret code "${currentSecretCode}" copied to clipboard!`);
    }

    function copySnippet() {
        const text = document.getElementById('mcpSnippet').innerText.replace('Copy', '').trim();
        navigator.clipboard.writeText(text);
        alert("MCP server configuration copied to clipboard!");
    }

    function downloadCurrentCSV() {
        if (!currentLocation) return;
        const start = document.getElementById('csvStart').value;
        const end = document.getElementById('csvEnd').value;
        if (!start || !end) { alert("Please choose a start and end date for the export."); return; }
        if (start > end) { alert("The start date must be on or before the end date."); return; }
        const url = `/api/past?latitude=${currentLocation.latitude}&longitude=${currentLocation.longitude}&start_date=${start}&end_date=${end}&format=csv`;
        window.open(url, '_blank');
    }

    function initCsvDateRange() {
        // The historical archive lags real time by ~5 days, so default to the 30 days ending 6 days ago
        const end = new Date();
        end.setDate(end.getDate() - 6);
        const start = new Date(end);
        start.setDate(start.getDate() - 30);
        const fmt = d => d.toISOString().slice(0, 10);
        const startEl = document.getElementById('csvStart');
        const endEl = document.getElementById('csvEnd');
        startEl.value = fmt(start);
        endEl.value = fmt(end);
        [startEl, endEl].forEach(el => { el.min = '1940-01-01'; el.max = fmt(end); });
    }

    async function saveToCurrentCollection() {
        if (!currentLocation) return;
        if (!currentSecretCode) { await createNewCollection(); return; }
        if (collectionRequestInFlight) return;
        setCollectionButtonsBusy(true);
        try {
            const resp = await fetch(`/api/share/${encodeURIComponent(currentSecretCode)}/observations`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(currentLocation)
            });
            if (resp.status === 404) {
                // Remembered code no longer exists (e.g. database was reset): start a fresh collection
                forgetSecretCode();
                setCollectionButtonsBusy(false);
                await createNewCollection();
                return;
            }
            if (!resp.ok) throw new Error(await errorDetail(resp, "Could not save the observation."));
            const result = await resp.json();
            alert(`Saved ${currentLocation.display_name} to ${result.secret_code} (${result.total_observations} observations in total).`);
        } catch (e) {
            alert(`Error: ${e.message}`);
        } finally {
            setCollectionButtonsBusy(false);
        }
    }

    // ---------- Search suggestions (autocomplete) ----------
    const queryInputEl = document.getElementById('queryInput');
    const suggestBox = document.getElementById('searchSuggestions');
    let suggestTimer = null;
    let suggestAbort = null;
    let suggestItems = [];
    let suggestIndex = -1;

    function hideSuggestions() {
        clearTimeout(suggestTimer);
        if (suggestAbort) suggestAbort.abort();
        suggestBox.style.display = 'none';
        suggestBox.innerHTML = '';
        suggestItems = [];
        suggestIndex = -1;
        queryInputEl.setAttribute('aria-expanded', 'false');
        queryInputEl.removeAttribute('aria-activedescendant');
    }

    function renderSuggestions(items, message) {
        suggestBox.innerHTML = '';
        suggestItems = items;
        suggestIndex = -1;
        if (message) {
            const div = document.createElement('div');
            div.className = 'suggestion-empty';
            div.textContent = message;
            suggestBox.appendChild(div);
        }
        items.forEach((loc, i) => {
            const div = document.createElement('div');
            div.className = 'suggestion-item';
            div.id = `suggestion-${i}`;
            div.setAttribute('role', 'option');
            const name = document.createElement('div');
            name.className = 'suggestion-name';
            name.textContent = loc.name;
            const meta = document.createElement('div');
            meta.className = 'suggestion-meta';
            const region = [loc.admin2, loc.admin1, loc.country].filter((v, idx, arr) => v && v !== loc.name && arr.indexOf(v) === idx).join(', ');
            meta.textContent = `${region} · ${loc.latitude.toFixed(2)}°, ${loc.longitude.toFixed(2)}°`;
            div.appendChild(name);
            div.appendChild(meta);
            // mousedown (not click) so it fires before the input loses focus
            div.addEventListener('mousedown', (e) => { e.preventDefault(); selectSuggestion(i); });
            suggestBox.appendChild(div);
        });
        const show = items.length > 0 || !!message;
        suggestBox.style.display = show ? 'block' : 'none';
        queryInputEl.setAttribute('aria-expanded', show ? 'true' : 'false');
    }

    async function fetchSuggestions(q) {
        if (suggestAbort) suggestAbort.abort();
        suggestAbort = new AbortController();
        try {
            const resp = await fetch(`/api/search?q=${encodeURIComponent(q)}`, { signal: suggestAbort.signal });
            if (queryInputEl.value.trim() !== q) return;  // user kept typing; ignore stale results
            if (resp.status === 503) { renderSuggestions([], "Geocoding service unreachable. Try again shortly."); return; }
            if (!resp.ok) { hideSuggestions(); return; }
            const data = await resp.json();
            if (data.results.length === 0) renderSuggestions([], `No places match "${q}"`);
            else renderSuggestions(data.results.slice(0, 8));
        } catch (e) {
            if (e.name !== 'AbortError') hideSuggestions();
        }
    }

    function highlightSuggestion(i) {
        suggestIndex = i;
        suggestBox.querySelectorAll('.suggestion-item').forEach((el, idx) => el.classList.toggle('active', idx === i));
        const el = document.getElementById(`suggestion-${i}`);
        if (el) {
            el.scrollIntoView({ block: 'nearest' });
            queryInputEl.setAttribute('aria-activedescendant', el.id);
        }
    }

    function selectSuggestion(i) {
        const loc = suggestItems[i];
        if (!loc) return;
        queryInputEl.value = loc.display_name;
        hideSuggestions();
        loadLiveReportForLocation(loc);
    }

    queryInputEl.addEventListener('input', () => {
        clearTimeout(suggestTimer);
        const q = queryInputEl.value.trim();
        if (q.length < 2 || isCoordQuery(q)) { hideSuggestions(); return; }
        suggestTimer = setTimeout(() => fetchSuggestions(q), 300);
    });

    queryInputEl.addEventListener('keydown', (e) => {
        const open = suggestBox.style.display === 'block' && suggestItems.length > 0;
        if (e.key === 'ArrowDown' && open) {
            e.preventDefault();
            highlightSuggestion(Math.min(suggestIndex + 1, suggestItems.length - 1));
        } else if (e.key === 'ArrowUp' && open) {
            e.preventDefault();
            highlightSuggestion(Math.max(suggestIndex - 1, 0));
        } else if (e.key === 'Escape') {
            hideSuggestions();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (open && suggestIndex >= 0) selectSuggestion(suggestIndex);
            else searchFromInput();
        }
    });

    queryInputEl.addEventListener('blur', () => setTimeout(hideSuggestions, 120));

    // Auto-init on page load
    window.onload = function () {
        initMap();
        initCsvDateRange();
        restoreSecretCode();
    };
</script>

</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index_page():
    """Interactive visual dashboard with clickable World Map down to 2km and dynamic charts."""
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "service": "Universal Natural Data Collector",
        "version": "1.3.0",
        "features": [
            "interactive_world_map",
            "click_to_inspect_2km",
            "interactive_charts",
            "atmosphere",
            "seismic_usgs",
            "river_flood_discharge",
            "soil_moisture",
            "historical_timeseries",
            "secret_code_sharing",
            "mcp_protocol",
        ],
    }


@app.get("/api/charts")
def get_charts_endpoint(
    location: str | None = Query(None, description="Location name"),
    latitude: float | None = Query(None, description="Latitude"),
    longitude: float | None = Query(None, description="Longitude"),
    days: int = Query(7, description="Number of past and forecast days (1-14)"),
):
    """Fetch multi-category time-series for dynamic charting."""
    if latitude is not None and longitude is not None:
        lat, lon = latitude, longitude
    elif location:
        loc = resolve_location(location)
        if not loc:
            raise HTTPException(status_code=404, detail=f"Location '{location}' not found.")
        lat, lon = loc.latitude, loc.longitude
    else:
        raise HTTPException(status_code=400, detail="Must provide location or lat/lon.")

    return fetch_chart_data(lat, lon, days=days)


@app.get("/api/search")
def search_endpoint(
    q: str = Query(..., description="City, village, or 'lat,lon' coordinates"),
    country: str | None = Query(None, description="Optional 2-letter country code"),
):
    """Geocode any village, city, or coordinate globally."""
    results = search_locations(q, count=10, country_code=country)
    return {"query": q, "count": len(results), "results": [loc.to_dict() for loc in results]}


@app.get("/api/live")
def get_live_endpoint(
    location: str | None = Query(None, description="Village or city name"),
    latitude: float | None = Query(None, description="Exact GPS latitude"),
    longitude: float | None = Query(None, description="Exact GPS longitude"),
    country: str | None = Query(None, description="Optional 2-letter country code"),
    radius_km: float = Query(300.0, description="Seismic search radius in km"),
):
    """Get live multi-domain natural indicators snapshot by coordinate or name."""
    if latitude is not None and longitude is not None:
        loc = resolve_coordinates(latitude, longitude)
    elif location:
        loc = resolve_location(location, country_code=country)
    else:
        raise HTTPException(status_code=400, detail="Must provide either 'location' name or 'latitude' and 'longitude'.")

    if not loc:
        raise HTTPException(status_code=404, detail=f"Location '{location}' could not be resolved.")

    report = get_natural_live_report(loc, seismic_radius_km=radius_km)
    return report.to_dict()


@app.post("/api/live")
def post_live_endpoint(
    location: LocationPayload,
    radius_km: float = Query(300.0, description="Seismic search radius in km"),
):
    """Live report for an already-resolved location (e.g. a picked search suggestion), without re-geocoding."""
    report = get_natural_live_report(location.to_location(), seismic_radius_km=radius_km)
    return report.to_dict()


@app.get("/api/past")
def get_past_endpoint(
    location: str | None = Query(None, description="Village or city name"),
    latitude: float | None = Query(None, description="Exact GPS latitude"),
    longitude: float | None = Query(None, description="Exact GPS longitude"),
    start_date: str = Query("2023-01-01", description="Start date (YYYY-MM-DD)"),
    end_date: str = Query("2023-01-31", description="End date (YYYY-MM-DD)"),
    format: str = Query("json", description="Output format: json or csv"),
):
    """Fetch historical environmental time-series for ML training."""
    if latitude is not None and longitude is not None:
        loc = resolve_coordinates(latitude, longitude)
    elif location:
        loc = resolve_location(location)
    else:
        raise HTTPException(status_code=400, detail="Must provide either 'location' name or 'latitude' and 'longitude'.")

    if not loc:
        raise HTTPException(status_code=404, detail=f"Location '{location}' not found.")

    try:
        records = fetch_historical_series(loc, start_date=start_date, end_date=end_date)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Historical archive request failed for {start_date} to {end_date}. "
                   f"Archive data starts in 1940 and lags real time by about 5 days. ({exc})",
        )

    if format.lower() == "csv":
        import io, csv
        if not records:
            return Response(content="", media_type="text/csv")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{loc.location_id}_{start_date}_{end_date}.csv"'},
        )

    return {
        "location": loc.to_dict(),
        "start_date": start_date,
        "end_date": end_date,
        "record_count": len(records),
        "records": records,
    }


@app.get("/api/seismic")
def get_seismic_endpoint(
    latitude: float = Query(..., description="Latitude"),
    longitude: float = Query(..., description="Longitude"),
    radius_km: float = Query(300.0, description="Radius in km"),
    min_mag: float = Query(1.0, description="Minimum magnitude"),
    limit: int = Query(25, description="Max results"),
):
    """Query live USGS earthquake events."""
    events = get_recent_earthquakes(latitude, longitude, radius_km=radius_km, min_magnitude=min_mag, limit=limit)
    return {
        "latitude": latitude,
        "longitude": longitude,
        "radius_km": radius_km,
        "count": len(events),
        "events": [e.to_dict() for e in events],
    }


@app.get("/api/hydrology")
def get_hydrology_endpoint(
    latitude: float = Query(..., description="Latitude"),
    longitude: float = Query(..., description="Longitude"),
):
    """Query river discharge & soil moisture."""
    hydro = get_hydrology(latitude, longitude)
    return hydro.to_dict()


@app.post("/api/collections")
def create_collection_endpoint(req: CreateCollectionRequest):
    """Create a persistent collection and generate a secret code."""
    storage = get_storage()
    resolved_locations = []

    for item in req.locations:
        # Check if coordinates
        parts = item.split(",")
        if len(parts) == 2 and not is_non_float(parts[0]) and not is_non_float(parts[1]):
            loc = resolve_coordinates(float(parts[0]), float(parts[1]))
            resolved_locations.append(loc)
        else:
            loc = resolve_location(item)
            if loc:
                resolved_locations.append(loc)

    if not resolved_locations:
        raise HTTPException(status_code=400, detail="None of the specified locations could be geocoded.")

    record = storage.create_collection(
        title=req.title,
        locations=resolved_locations,
        description=req.description,
        custom_secret_code=req.custom_secret_code,
    )

    # Trigger initial snapshot
    for loc in resolved_locations:
        rep = get_natural_live_report(loc)
        storage.save_live_report(record.secret_code, rep)

    return {
        "status": "created",
        "secret_code": record.secret_code,
        "collection_id": record.collection_id,
        "title": record.title,
        "share_url": f"/api/share/{record.secret_code}",
        "locations": [loc.to_dict() for loc in resolved_locations],
    }


def is_non_float(val: str) -> bool:
    try:
        float(val.strip())
        return False
    except ValueError:
        return True


@app.get("/api/collections")
def list_collections_endpoint():
    """List active collections."""
    storage = get_storage()
    records = storage.list_collections(limit=50)
    return {"collections": [r.to_dict() for r in records]}


@app.get("/api/share/{secret_code}")
def get_share_endpoint(secret_code: str):
    """Access live & saved collection data using a secret share code."""
    storage = get_storage()
    coll = storage.get_collection_by_secret(secret_code)
    if not coll:
        raise HTTPException(status_code=404, detail=f"No collection found for secret code '{secret_code}'")

    observations = storage.get_observations(secret_code, limit=100)

    live_vitals = []
    for loc_dict in coll.locations:
        loc = LocationInfo(**{k: v for k, v in loc_dict.items() if k != "display_name"})
        try:
            live_vitals.append(get_natural_live_report(loc).to_dict())
        except Exception:
            pass

    return {
        "secret_code": coll.secret_code,
        "collection_id": coll.collection_id,
        "title": coll.title,
        "description": coll.description,
        "created_at": coll.created_at,
        "updated_at": coll.updated_at,
        "total_saved_observations": coll.record_count,
        "live_snapshots": live_vitals,
        "recent_saved_observations": observations,
        "download_csv_url": f"/api/share/{coll.secret_code}/download?format=csv",
        "download_json_url": f"/api/share/{coll.secret_code}/download?format=json",
    }


@app.get("/api/share/{secret_code}/download")
def download_share_endpoint(secret_code: str, format: str = Query("csv")):
    """Download full dataset for a collection via secret share code."""
    storage = get_storage()
    coll = storage.get_collection_by_secret(secret_code)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")

    if format.lower() == "csv":
        csv_data = storage.export_csv(secret_code)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{secret_code}_data.csv"'},
        )

    obs = storage.get_observations(secret_code, limit=5000)
    return JSONResponse(content={"collection": coll.to_dict(), "observations": obs})


@app.post("/api/share/{secret_code}/snapshot")
def trigger_snapshot_endpoint(secret_code: str):
    """Trigger a live collection run for all locations in the collection."""
    storage = get_storage()
    coll = storage.get_collection_by_secret(secret_code)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")

    saved = []
    for loc_dict in coll.locations:
        loc = LocationInfo(**{k: v for k, v in loc_dict.items() if k != "display_name"})
        rep = get_natural_live_report(loc)
        row_id = storage.save_live_report(secret_code, rep)
        saved.append({"location": loc.name, "observation_id": row_id})

    return {
        "status": "success",
        "secret_code": secret_code,
        "saved_count": len(saved),
        "details": saved,
    }


@app.post("/api/share/{secret_code}/observations")
def add_observation_endpoint(secret_code: str, location: LocationPayload):
    """Save a live observation for one location into an existing collection,
    adding the location to the collection's monitored list if it isn't tracked yet.
    """
    storage = get_storage()
    coll = storage.get_collection_by_secret(secret_code)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")

    loc = location.to_location()
    added = storage.add_location_to_collection(coll.secret_code, loc)
    report = get_natural_live_report(loc)
    row_id = storage.save_live_report(coll.secret_code, report)
    updated = storage.get_collection_by_secret(coll.secret_code)

    return {
        "status": "saved",
        "secret_code": coll.secret_code,
        "observation_id": row_id,
        "location": loc.to_dict(),
        "location_newly_tracked": added,
        "total_observations": updated.record_count if updated else None,
    }
