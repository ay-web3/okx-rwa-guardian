import httpx
import logging

logger = logging.getLogger(__name__)

async def fetch_weather_alerts(lat: float, lon: float) -> list:
    url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
    # NOAA API requires a User-Agent
    headers = {
        "User-Agent": "RWAGuardian/1.0 (admin@rwaguardian.com)"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            features = data.get("features", [])
            alerts = []
            for feature in features:
                props = feature.get("properties", {})
                alerts.append({
                    "source": "NOAA Weather",
                    "event": props.get("event"),
                    "severity": props.get("severity"),
                    "headline": props.get("headline"),
                    "description": props.get("description")
                })
            return alerts
    except Exception as e:
        logger.error(f"Error fetching weather alerts: {e}")
        return []
