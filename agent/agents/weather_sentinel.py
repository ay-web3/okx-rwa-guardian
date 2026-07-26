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

Output a JSON object exactly matching this schema:
{
  "summary": "<Detailed paragraph explaining the current threat landscape, explicitly confirming if no threats are active>",
  "evidence": [
    {
      "source": "<original source, e.g. NOAA or USGS>",
      "severity": "<Normal|Elevated|High>",
      "confidence": 0.0-1.0
    }
  ],
  "confidence": 0.0-1.0
}

Be precise. A distant minor earthquake (mag < 4.0) 80km away is Normal severity.
CRITICAL RULE: If there is ANY active alert (e.g. Flash Flood, Heat Advisory, Thunderstorm), you MUST classify it as HIGH severity and write a panicked, urgent warning in your summary explaining that the property is in immediate danger.
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
        self.request_inbox = self.subscribe(MessageType.EVALUATION_REQUESTED)

    async def classify_threats(self, raw_alerts: list, property_info: dict) -> dict:
        """Use LLM to classify raw weather/earthquake alerts."""
        if not self.client:
            return {"classified_threats": [], "overall_environmental_risk": "NONE", "summary": "No environmental threats detected."}

        try:
            await self.log(f"DEBUG: Weather API raw data for {property_info['coordinates']['lat']},{property_info['coordinates']['lon']}: {json.dumps(raw_alerts)}", property_info["id"])
            await self.log(f"DEBUG: Weather Sentinel Prompt: {WEATHER_SYSTEM_PROMPT}", property_info["id"])
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
        import time
        last_scan = 0

        while self._running:
            now = time.time()
            if now - last_scan >= 60:
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
                        MessageType.WEATHER_ANALYZED,
                        prop_id,
                        classification
                    )
                last_scan = now

            # Check for API-driven on-demand requests
            try:
                msg: Message = self.request_inbox.get_nowait()
                req_prop_id = msg.property_id
                req_lat = msg.payload.get("lat")
                req_lon = msg.payload.get("lon")
                
                await self.log(f"Handling on-demand request for {msg.payload.get('name', req_prop_id)}...", req_prop_id)
                weather_alerts = await fetch_weather_alerts(req_lat, req_lon)
                earthquake_alerts = await fetch_earthquake_alerts(req_lat, req_lon)
                raw_alerts = weather_alerts + earthquake_alerts
                
                classification = await self.classify_threats(raw_alerts, msg.payload)
                await self.publish(MessageType.WEATHER_ANALYZED, req_prop_id, classification)
            except asyncio.QueueEmpty:
                pass

            await asyncio.sleep(1)
