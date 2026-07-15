import asyncio
import json
import os
import logging
from openai import AsyncOpenAI
from agents.base_agent import BaseAgent
from message_bus import MessageBus, MessageType
from data_sources.weather import fetch_weather_alerts
from data_sources.earthquake import fetch_earthquake_alerts

logger = logging.getLogger(__name__)

WEATHER_SYSTEM_PROMPT = """You are a meteorological and seismological risk specialist for RWA Guardian.
You receive raw weather alerts from NOAA and earthquake data from USGS.
Your job is to classify each alert's risk to a real estate property.

For each alert, determine:
- risk_level: "NONE", "LOW", "MEDIUM", "HIGH", or "CRITICAL"
- impact_summary: A brief sentence explaining why this matters for the property

Output a JSON object:
{
  "classified_threats": [
    {
      "source": "<original source>",
      "event": "<event type>",
      "risk_level": "<NONE|LOW|MEDIUM|HIGH|CRITICAL>",
      "impact_summary": "<why this matters for the property>"
    }
  ],
  "overall_environmental_risk": "<NONE|LOW|MEDIUM|HIGH|CRITICAL>",
  "summary": "<one sentence summary of environmental conditions>"
}

Be precise. A distant minor earthquake (mag < 4.0) 80km away is NONE/LOW risk.
A Category 3+ hurricane heading directly for the property is CRITICAL.
Only output valid JSON. No markdown."""


class WeatherSentinelAgent(BaseAgent):
    """
    Agent 1: Weather Sentinel
    Continuously monitors weather alerts and earthquakes for each property.
    Classifies threats using its own LLM persona and publishes to the bus.
    """

    def __init__(self, bus: MessageBus, shared_state: dict):
        super().__init__(name="Weather Sentinel", emoji="🌊", bus=bus, shared_state=shared_state)
        self.api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1"
        ) if self.api_key else None

    async def classify_threats(self, raw_alerts: list, property_info: dict) -> dict:
        """Use LLM to classify raw weather/earthquake alerts."""
        if not self.client or not raw_alerts:
            return {"classified_threats": [], "overall_environmental_risk": "NONE", "summary": "No environmental threats detected."}

        try:
            response = await self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": WEATHER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Property: {property_info['name']} at ({property_info['coordinates']['lat']}, {property_info['coordinates']['lon']})\n\nRaw alerts:\n{json.dumps(raw_alerts, default=str)}"}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Weather LLM classification failed: {e}")
            return {
                "classified_threats": [{"source": a.get("source", "unknown"), "event": a.get("event", "unknown"), "risk_level": "MEDIUM", "impact_summary": "Classification failed, passing raw data."} for a in raw_alerts],
                "overall_environmental_risk": "MEDIUM",
                "summary": f"Classification error: {e}"
            }

    async def run(self):
        """Main loop: poll weather/earthquake APIs, classify, and publish."""
        properties = self.shared_state.get("properties", {})

        await self.log("Weather Sentinel online. Scanning environmental data sources...")

        while self._running:
            for prop_id, prop in properties.items():
                lat = prop["coordinates"]["lat"]
                lon = prop["coordinates"]["lon"]

                await self.log(f"Scanning {prop['name']} ({lat}, {lon})...", prop_id)

                # Fetch raw data
                weather_alerts = await fetch_weather_alerts(lat, lon)
                earthquake_alerts = await fetch_earthquake_alerts(lat, lon)
                raw_alerts = weather_alerts + earthquake_alerts

                # Classify with LLM
                classification = await self.classify_threats(raw_alerts, prop)

                # Publish to bus
                await self.publish(
                    MessageType.THREAT_DATA,
                    prop_id,
                    {
                        "agent": "weather_sentinel",
                        "raw_alerts": raw_alerts,
                        "classification": classification,
                        "summary": f"🌊 {classification.get('summary', 'No environmental threats.')}"
                    }
                )

            await asyncio.sleep(60)
