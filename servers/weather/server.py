"""Weather MCP server — Open-Meteo (no API key)."""

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Weather")
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


async def _geocode(city: str) -> tuple[float, float, str]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            GEOCODE_URL,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
        )
        resp.raise_for_status()
        data = resp.json()
    results = data.get("results") or []
    if not results:
        raise ValueError(f"City not found: {city}")
    loc = results[0]
    return loc["latitude"], loc["longitude"], loc.get("name", city)


async def _fetch_weather(lat: float, lon: float, *, forecast_days: int = 1) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum",
        "timezone": "auto",
        "forecast_days": forecast_days,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(FORECAST_URL, params=params)
        resp.raise_for_status()
        return resp.json()


def _weather_code_label(code: int) -> str:
    labels = {
        0: "Clear",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        80: "Rain showers",
        95: "Thunderstorm",
    }
    return labels.get(code, f"Code {code}")


@mcp.tool()
async def get_current(city: str) -> str:
    """Get current weather for a city."""
    lat, lon, name = await _geocode(city)
    data = await _fetch_weather(lat, lon, forecast_days=1)
    cur = data.get("current", {})
    temp = cur.get("temperature_2m")
    humidity = cur.get("relative_humidity_2m")
    wind = cur.get("wind_speed_10m")
    code = cur.get("weather_code", 0)
    return (
        f"Current weather in {name}:\n"
        f"  Temperature: {temp}°C\n"
        f"  Conditions: {_weather_code_label(code)}\n"
        f"  Humidity: {humidity}%\n"
        f"  Wind: {wind} km/h"
    )


@mcp.tool()
async def get_forecast(city: str, days: int = 7) -> str:
    """Get a multi-day weather forecast for a city (1–14 days)."""
    days = max(1, min(14, days))
    lat, lon, name = await _geocode(city)
    data = await _fetch_weather(lat, lon, forecast_days=days)
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    codes = daily.get("weather_code", [])
    precip = daily.get("precipitation_sum", [])

    lines = [f"Weather forecast for {name} ({days} days):"]
    for i, date in enumerate(dates):
        hi = highs[i] if i < len(highs) else "?"
        lo = lows[i] if i < len(lows) else "?"
        cond = _weather_code_label(codes[i]) if i < len(codes) else "?"
        rain = precip[i] if i < len(precip) else 0
        lines.append(f"  {date}: {lo}°–{hi}°C, {cond}, precip {rain} mm")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
