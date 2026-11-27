"""AquaThink location and weather data service.

Uses Open-Meteo geocoding and forecast APIs. Weather values are estimates,
not direct measurements of the user's property.
"""
import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

class WeatherServiceError(Exception):
    """A location or weather lookup failed."""


def _fetch_json(url, params):
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise WeatherServiceError(f"Could not retrieve API data: {exc}") from exc


def get_location(city, country_code=None):
    """Return location details for a city search (not a street address)."""
    if not isinstance(city, str) or not city.strip():
        raise WeatherServiceError("Please enter a city name.")
    params = {"name": city.strip(), "count": 10, "language": "en", "format": "json"}
    if country_code:
        params["countryCode"] = country_code.upper()
    results = _fetch_json(GEOCODING_URL, params).get("results") or []
    if not results:
        raise WeatherServiceError(f"No location found for '{city}'.")
    # The first match is the API's top-ranked result; disambiguate city names
    # using country_code when possible.
    match = results[0]
    return {
        "city": match["name"],
        "state": match.get("admin1"),
        "country": match.get("country"),
        "country_code": match.get("country_code"),
        "latitude": match["latitude"],
        "longitude": match["longitude"],
        "timezone": match.get("timezone"),
    }


def get_weather(latitude, longitude):
    """Return current conditions and a three-day daily forecast.

    Precipitation and ET0 are in millimeters; temperature is in Celsius.
    Soil moisture is a modeled volumetric fraction (m3/m3) and may be null.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation,soil_moisture_0_to_1cm",
        "daily": "precipitation_sum,precipitation_probability_max,et0_fao_evapotranspiration,temperature_2m_max,temperature_2m_min",
        "timezone": "auto",
        "forecast_days": 3,
    }
    data = _fetch_json(FORECAST_URL, params)
    if "current" not in data or "daily" not in data:
        raise WeatherServiceError("Weather API returned incomplete data.")
    current = data["current"]
    daily = data["daily"]
    keys = (
        "precipitation_sum", "precipitation_probability_max",
        "et0_fao_evapotranspiration", "temperature_2m_max", "temperature_2m_min"
    )
    forecast = []
    for index, day in enumerate(daily.get("time", [])):
        forecast.append({"date": day, **{
            key: (daily.get(key) or [None] * len(daily["time"]))[index]
            for key in keys
        }})
    return {
        "observed_at": current.get("time"),
        "temperature_c": current.get("temperature_2m"),
        "humidity_percent": current.get("relative_humidity_2m"),
        "current_precipitation_mm": current.get("precipitation"),
        "soil_moisture_fraction": current.get("soil_moisture_0_to_1cm"),
        "forecast": forecast,
        "units": {
            "temperature_c": "°C",
            "humidity_percent": "%",
            "current_precipitation_mm": "mm (preceding API interval)",
            "soil_moisture_fraction": "m³/m³ (modeled)",
            "precipitation_sum": "mm/day",
            "precipitation_probability_max": "%",
            "et0_fao_evapotranspiration": "mm/day",
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C",
        },
    }


def get_watering_data(city, country_code=None):
    """Public interface for the watering-logic teammate."""
    location = get_location(city, country_code=country_code)
    weather = get_weather(location["latitude"], location["longitude"])
    return {"location": location, "weather": weather}


if __name__ == "__main__":
    import json
    city = input("Enter city (e.g., Dallas): ").strip()
    country = input("Country code (e.g., US, optional): ").strip() or None
    try:
        print(json.dumps(get_watering_data(city, country), indent=2))
    except WeatherServiceError as exc:
        print(f"Error: {exc}")
