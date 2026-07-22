import asyncio
import json
import os
import logging
from openai import AsyncOpenAI
from agents.base_agent import BaseAgent
from message_bus import MessageBus, MessageType, Message

logger = logging.getLogger(__name__)

RISK_ANALYST_PROMPT = """You are the Senior Risk Analyst (Reasoning Agent) for RWA Guardian, a multi-agent AI system protecting tokenized real estate assets.

You receive classified threat data from the Data Collector agent:
1. Weather Sentinel — environmental threats (hurricanes, earthquakes, floods)
2. News Intelligence — market/economic/regulatory threats

Your job is to SYNTHESIZE all incoming intelligence and produce a multi-dimensional risk verdict for the property.

Consider:
- Cross-correlation: Does the news CONFIRM the weather threat, or is it unrelated?
- Cumulative risk: Multiple LOW threats can compound into MEDIUM overall risk.
- Actionable Intelligence: Don't just output a risk number. Recommend a specific action the protocol should take based on the overall risk level:
    - Normal (0-20): "normal"
    - Elevated (21-50): "increaseMonitoring"
    - High (51-80): "raiseCollateralRatio"
    - Critical (81-90): "pauseNewBorrowing"
    - Extreme (91-100): "freezeTransfers"

IMPORTANT — overallRisk MUST be computed as a weighted average, not a simple mean:
  overallRisk = round(physicalRisk * 0.5 + economicRisk * 0.3 + liquidityRisk * 0.2)
Always use these exact weights. Include a "riskWeights" key showing the weights used.

Output a JSON object exactly like this:
{
  "physicalRisk": <int 0-100>,
  "economicRisk": <int 0-100>,
  "liquidityRisk": <int 0-100>,
  "overallRisk": <int 0-100, computed as physicalRisk*0.5 + economicRisk*0.3 + liquidityRisk*0.2>,
  "riskWeights": {"physical": 0.5, "economic": 0.3, "liquidity": 0.2},
  "recommendedAction": "normal" | "increaseMonitoring" | "raiseCollateralRatio" | "pauseNewBorrowing" | "freezeTransfers",
  "confidence": <float 0.0-1.0, how confident you are in this verdict>,
  "analysis": "<detailed reasoning explaining your synthesis of all agent inputs>",
  "caveats": "<any factors that argue AGAINST your verdict — hedges, uncertainties, or mitigating circumstances>"
}

IMPORTANT: You are recommending, not executing. The Verification Agent will review your verdict before any on-chain action is taken. Be honest about uncertainty.
Only output valid JSON. No markdown."""


class RiskAnalystAgent(BaseAgent):
    """
    Agent 3: Risk Analyst (Senior Reasoner)
    Subscribes to THREAT_DATA from Weather Sentinel and News Intel.
    Synthesizes all incoming intelligence into a single risk verdict per property.
    Publishes RISK_VERDICT for the Consensus Validator to review.
    """

    def __init__(self, bus: MessageBus, shared_state: dict):
        super().__init__(name="Risk Analyst", emoji="🧠", bus=bus, shared_state=shared_state)
        self.api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1"
        ) if self.api_key else None
        self.threat_inbox = self.subscribe(MessageType.THREAT_DATA)
        # Buffer to collect data from multiple agents before synthesizing
        self._threat_buffer: dict[str, list] = {}

    async def synthesize(self, property_id: str, threat_reports: list, property_info: dict) -> dict:
        """Run senior LLM analysis on all collected threat data."""
        if not self.client:
            return {
                "physicalRisk": 0,
                "economicRisk": 0,
                "liquidityRisk": 0,
                "overallRisk": 0,
                "riskWeights": {"physical": 0.5, "economic": 0.3, "liquidity": 0.2},
                "recommendedAction": "normal",
                "confidence": 0.0,
                "analysis": "No API key configured.",
                "caveats": "N/A"
            }

        try:
            user_content = f"Property: {json.dumps(property_info, default=str)}\n\nAgent Reports:\n{json.dumps(threat_reports, default=str)}"

            response = await self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": RISK_ANALYST_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            
            # LLMs often hallucinate basic arithmetic, so we enforce the formula deterministically
            weights = result.get("riskWeights", {"physical": 0.5, "economic": 0.3, "liquidity": 0.2})
            p_weight = weights.get("physical", 0.5)
            e_weight = weights.get("economic", 0.3)
            l_weight = weights.get("liquidity", 0.2)
            
            result["overallRisk"] = round(
                result.get("physicalRisk", 0) * p_weight +
                result.get("economicRisk", 0) * e_weight +
                result.get("liquidityRisk", 0) * l_weight
            )
            
            return result
        except Exception as e:
            logger.error(f"Risk Analyst LLM synthesis failed: {e}")
            return {
                "physicalRisk": 0,
                "economicRisk": 0,
                "liquidityRisk": 0,
                "overallRisk": 0,
                "riskWeights": {"physical": 0.5, "economic": 0.3, "liquidity": 0.2},
                "recommendedAction": "normal",
                "confidence": 0.0,
                "analysis": f"Synthesis error: {e}",
                "caveats": "Analysis failed"
            }

    async def run(self):
        """Listen for THREAT_DATA messages, buffer them, and synthesize when all agents report."""
        properties = self.shared_state.get("properties", {})
        num_data_agents = 2  # Weather Sentinel + News Intel

        await self.log("Risk Analyst online. Awaiting intelligence from field agents...")

        while self._running:
            try:
                # Wait for incoming threat data (with timeout to prevent deadlock)
                msg: Message = await asyncio.wait_for(self.threat_inbox.get(), timeout=120)

                prop_id = msg.property_id
                agent_name = msg.payload.get("agent", "unknown")

                # Buffer the report
                if prop_id not in self._threat_buffer:
                    self._threat_buffer[prop_id] = []
                self._threat_buffer[prop_id].append(msg.payload)

                await self.log(f"Received intel from {agent_name} for {properties.get(prop_id, {}).get('name', prop_id)}", prop_id)

                # Once we have reports from all data agents, synthesize
                if len(self._threat_buffer[prop_id]) >= num_data_agents:
                    prop_info = properties.get(prop_id, {})
                    await self.log(f"All agents reported for {prop_info.get('name', prop_id)}. Synthesizing...", prop_id)

                    verdict = await self.synthesize(prop_id, self._threat_buffer[prop_id], prop_info)

                    # Publish the verdict
                    await self.publish(
                        MessageType.RISK_VERDICT,
                        prop_id,
                        {
                            "verdict": verdict,
                            "source_reports": self._threat_buffer[prop_id],
                            "summary": f"🧠 Risk: {verdict.get('overallRisk', 0)}/100 | Action: {verdict.get('recommendedAction', 'normal')} | Confidence: {verdict.get('confidence', 0):.0%}"
                        }
                    )

                    # Clear the buffer for this property
                    self._threat_buffer[prop_id] = []

            except asyncio.TimeoutError:
                # No messages for 120s, that's fine
                continue
