import httpx
import logging

logger = logging.getLogger(__name__)

async def fetch_earthquake_alerts(lat: float, lon: float) -> list:
    url = f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&latitude={lat}&longitude={lon}&maxradiuskm=100&minmagnitude=3"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            
            # HTTP 204 implies no content found matching criteria
            if response.status_code == 204:
                return []
                
            response.raise_for_status()
            data = response.json()
            features = data.get("features", [])
            alerts = []
            for feature in features:
                props = feature.get("properties", {})
                alerts.append({
                    "source": "USGS Earthquake",
                    "title": props.get("title"),
                    "magnitude": props.get("mag"),
                    "place": props.get("place"),
                    "time": props.get("time")
                })
            return alerts
    except Exception as e:
        logger.error(f"Error fetching earthquake alerts: {e}")
        return []
