import asyncio
import json
import os
import logging
from openai import AsyncOpenAI
from agents.base_agent import BaseAgent
from message_bus import MessageBus, MessageType, Message

logger = logging.getLogger(__name__)

CONSENSUS_PROMPT = """You are an independent auditor and devil's advocate for RWA Guardian.

The Risk Analyst has produced a verdict recommending an action on a tokenized real estate smart contract. Your job is to CHALLENGE this recommendation before it reaches the blockchain.

You must evaluate:
1. Is the evidence strong enough to justify the recommended action?
2. Could this be a false positive? (e.g., clickbait news, distant earthquake, routine weather advisory)
3. What is the cost of being WRONG?
   - If we pause trading incorrectly: investors are locked out, trust is damaged
   - If we DON'T pause and should have: investors may suffer losses
4. Does the confidence level match the severity of the action?

Rules:
- For PAUSE TRADING recommendations: You must see STRONG, CONFIRMED evidence. A single news headline is NOT enough. Require multiple sources or a genuine NOAA severe weather warning.
- For yield adjustments: Be more lenient. Small adjustments based on moderate evidence are acceptable.
- For health score changes: Be lenient. These are informational and don't affect the contract.
- For "normal" actions (DO NOTHING): If the environment is safe, you MUST output "APPROVED". Only "REJECT" a normal action if you believe a severe risk was dangerously ignored.

Output a JSON object:
{
  "decision": "APPROVED" | "REJECTED",
  "reasoning": "<detailed explanation of why you approve or reject>",
  "modifications": {
    "recommendedAction": <string — your recommended override action, or null to keep original>,
    "overallRisk": <int — your adjusted score, or null to keep original>
  },
  "risk_of_false_positive": <float 0.0-1.0>,
  "summary": "<one sentence verdict>"
}

You are the last line of defense before irreversible on-chain actions. Be thorough.
Only output valid JSON. No markdown."""


class ConsensusValidatorAgent(BaseAgent):
    """
    Agent 4: Consensus Validator
    Subscribes to RISK_VERDICT messages from the Risk Analyst.
    For critical actions (pause trading), runs independent LLM verification.
    For non-critical actions, auto-approves with logging.
    Publishes CONSENSUS_DECISION for the Executor.
    """

    def __init__(self, bus: MessageBus, shared_state: dict):
        super().__init__(name="Consensus Validator", emoji="⚖️", bus=bus, shared_state=shared_state)
        self.api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1"
        ) if self.api_key else None
        self.verdict_inbox = self.subscribe(MessageType.RISK_VERDICT)

    async def validate(self, verdict: dict, source_reports: list, property_info: dict) -> dict:
        """Run independent LLM validation on the Risk Analyst's verdict."""
        if not self.client:
            return {
                "decision": "APPROVED",
                "reasoning": "No API key — auto-approving.",
                "modifications": {},
                "risk_of_false_positive": 0.5,
                "summary": "Auto-approved (no validation API key)."
            }

        try:
            user_content = (
                f"Property: {json.dumps(property_info, default=str)}\n\n"
                f"Risk Analyst Verdict: {json.dumps(verdict, default=str)}\n\n"
                f"Original Source Reports: {json.dumps(source_reports, default=str)}"
            )

            response = await self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": CONSENSUS_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Consensus validation LLM failed: {e}")
            return {
                "decision": "REJECTED" if verdict.get("recommendedAction") in ["pauseNewBorrowing", "freezeTransfers"] else "APPROVED",
                "reasoning": f"Validation failed ({e}). Rejecting critical actions as a safety measure.",
                "modifications": {"recommendedAction": "normal"},
                "risk_of_false_positive": 0.8,
                "summary": "Validation error — critical actions blocked for safety."
            }

    async def run(self):
        """Listen for RISK_VERDICT messages and validate before passing to executor."""
        properties = self.shared_state.get("properties", {})

        await self.log("Consensus Validator online. Standing by to review verdicts...")

        while self._running:
            try:
                msg: Message = await asyncio.wait_for(self.verdict_inbox.get(), timeout=120)

                prop_id = msg.property_id
                prop_info = properties.get(prop_id, {})
                verdict = msg.payload.get("verdict", {})
                source_reports = msg.payload.get("source_reports", [])

                is_critical = verdict.get("recommendedAction") in ["pauseNewBorrowing", "freezeTransfers"]

                if is_critical:
                    # Critical action: run full independent validation
                    await self.log(f"⚠️ CRITICAL ACTION requested for {prop_info.get('name', prop_id)}: {verdict.get('recommendedAction')}. Running independent validation...", prop_id)
                    validation = await self.validate(verdict, source_reports, prop_info)
                else:
                    # Non-critical: auto-approve with logging
                    await self.log(f"Non-critical verdict for {prop_info.get('name', prop_id)}. Auto-approving.", prop_id)
                    validation = {
                        "decision": "APPROVED",
                        "reasoning": "Non-critical action auto-approved.",
                        "modifications": {},
                        "risk_of_false_positive": 0.0,
                        "summary": "Auto-approved (non-critical)."
                    }

                # Apply any modifications from the validator
                modifications = validation.get("modifications", {})
                final_verdict = verdict.copy()
                if modifications.get("recommendedAction") is not None:
                    final_verdict["recommendedAction"] = modifications["recommendedAction"]
                if modifications.get("overallRisk") is not None:
                    final_verdict["overallRisk"] = modifications["overallRisk"]

                decision = validation.get("decision", "APPROVED")
                await self.log(
                    f"Verdict {decision} for {prop_info.get('name', prop_id)} | FP Risk: {validation.get('risk_of_false_positive', 0):.0%} | {validation.get('summary', '')}",
                    prop_id
                )

                # Publish consensus decision
                await self.publish(
                    MessageType.CONSENSUS_DECISION,
                    prop_id,
                    {
                        "decision": decision,
                        "final_verdict": final_verdict,
                        "validation": validation,
                        "source_reports": source_reports,
                        "summary": f"⚖️ {decision} | {validation.get('summary', 'No summary')}"
                    }
                )

            except asyncio.TimeoutError:
                continue
