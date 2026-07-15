import asyncio
import json
import os
import logging
from openai import AsyncOpenAI
from agents.base_agent import BaseAgent
from message_bus import MessageBus, MessageType
from data_sources.news import fetch_news_alerts

logger = logging.getLogger(__name__)

NEWS_SYSTEM_PROMPT = """You are a financial news intelligence analyst for RWA Guardian.
You receive news headlines about real estate markets and local economies.
Your job is to classify each headline's actual impact on a tokenized real estate property.

CRITICAL RULE: Most news is routine market reporting. Do NOT overreact.
- A headline about "housing prices rising" is POSITIVE, not a threat.
- A headline about "market trends" is NEUTRAL.
- Only classify as NEGATIVE if there's a genuine regulatory crackdown, market crash, or severe economic downturn.
- Only classify as CATASTROPHIC if there's an imminent, confirmed disaster (not speculation).

Output a JSON object:
{
  "classified_news": [
    {
      "headline": "<original headline>",
      "sentiment": "POSITIVE" | "NEUTRAL" | "NEGATIVE" | "CATASTROPHIC",
      "relevance": "HIGH" | "MEDIUM" | "LOW",
      "impact_summary": "<why this matters or doesn't matter>"
    }
  ],
  "overall_news_sentiment": "POSITIVE" | "NEUTRAL" | "NEGATIVE" | "CATASTROPHIC",
  "market_moving": <true if any headline is genuinely market-moving, false otherwise>,
  "summary": "<one sentence summary of the news landscape>"
}

Be skeptical. Financial media thrives on fear. Filter the signal from the noise.
Only output valid JSON. No markdown."""


class NewsIntelAgent(BaseAgent):
    """
    Agent 2: News Intelligence
    Monitors Google News RSS feeds for property-relevant news.
    Classifies sentiment and filters clickbait before publishing to the bus.
    """

    def __init__(self, bus: MessageBus, shared_state: dict):
        super().__init__(name="News Intel", emoji="📰", bus=bus, shared_state=shared_state)
        self.api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1"
        ) if self.api_key else None

    async def classify_news(self, news_alerts: list, property_info: dict) -> dict:
        """Use LLM to classify news sentiment and filter clickbait."""
        if not self.client or not news_alerts:
            return {"classified_news": [], "overall_news_sentiment": "NEUTRAL", "market_moving": False, "summary": "No news to report."}

        try:
            response = await self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": NEWS_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Property: {property_info['name']}\n\nNews headlines:\n{json.dumps(news_alerts, default=str)}"}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"News LLM classification failed: {e}")
            return {
                "classified_news": [],
                "overall_news_sentiment": "NEUTRAL",
                "market_moving": False,
                "summary": f"Classification error: {e}"
            }

    async def run(self):
        """Main loop: poll news feeds, classify sentiment, and publish."""
        properties = self.shared_state.get("properties", {})

        await self.log("News Intelligence online. Scanning media sources...")

        while self._running:
            for prop_id, prop in properties.items():
                await self.log(f"Scanning news for {prop['name']}...", prop_id)

                # Fetch raw news + any mock news injected from frontend
                real_news = await fetch_news_alerts(prop_id)
                mock_news = self.shared_state.get("mock_news", {}).get(prop_id, [])
                all_news = real_news + mock_news

                # Classify with LLM
                classification = await self.classify_news(all_news, prop)

                # Publish to bus
                await self.publish(
                    MessageType.THREAT_DATA,
                    prop_id,
                    {
                        "agent": "news_intel",
                        "raw_alerts": all_news,
                        "classification": classification,
                        "summary": f"📰 {classification.get('summary', 'No significant news.')}"
                    }
                )

            await asyncio.sleep(60)
