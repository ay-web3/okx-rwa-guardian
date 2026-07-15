import asyncio
import logging
from agents.base_agent import BaseAgent
from message_bus import MessageBus, MessageType, Message
from web3_client import web3_client

logger = logging.getLogger(__name__)


class ExecutorAgent(BaseAgent):
    """
    Agent 5: Executor (On-Chain Signer)
    The ONLY agent with access to the private key and web3_client.
    Subscribes to CONSENSUS_DECISION messages and executes approved on-chain actions.
    Never reasons about risk — pure execution of pre-approved commands.
    """

    def __init__(self, bus: MessageBus, shared_state: dict):
        super().__init__(name="Executor", emoji="🔐", bus=bus, shared_state=shared_state)
        self.decision_inbox = self.subscribe(MessageType.CONSENSUS_DECISION)

    async def execute_verdict(self, prop_id: str, verdict: dict) -> str:
        """Execute approved on-chain actions based on the final verdict."""
        properties = self.shared_state.get("properties", {})
        prop = properties.get(prop_id)
        if not prop:
            return "Property not found"

        tx_logs = ""
        new_paused = verdict.get("should_pause_trading", prop["paused"])
        new_yield = verdict.get("recommended_yield_rate", prop.get("yield_rate", 100))
        new_health = verdict.get("recommended_health_score", prop.get("health_score", 100))

        # Update yield if changed and not pausing
        if new_yield != prop.get("yield_rate", 100) and not new_paused:
            await self.log(f"Executing: SET YIELD {new_yield}% for {prop['name']}", prop_id)
            tx_hash = await web3_client.set_yield_rate(new_yield)
            tx_logs += f"\n[TxHash: {tx_hash}] Yield Rate set to {new_yield}%."

        # Pause if transitioning to paused
        if new_paused and not prop["paused"]:
            await self.log(f"🚨 Executing: PAUSE TRADING for {prop['name']}", prop_id)
            tx_hash = await web3_client.pause_trading()
            tx_logs += f"\n[TxHash: {tx_hash}] Contract PAUSED."

        # Unpause if threat cleared
        if not new_paused and prop["paused"]:
            await self.log(f"✅ Executing: UNPAUSE TRADING for {prop['name']}", prop_id)
            tx_hash = await web3_client.unpause_trading()
            tx_logs += f"\n[TxHash: {tx_hash}] Contract UNPAUSED. Trading resumed."

        # Update shared state
        prop["paused"] = new_paused
        prop["yield_rate"] = new_yield
        prop["health_score"] = new_health
        prop["latest_analysis"] = verdict.get("analysis", "No analysis provided.") + tx_logs

        await self.log(
            f"State updated: Health={new_health}, Yield={new_yield}%, Paused={new_paused}. {tx_logs}",
            prop_id
        )

        return tx_logs or "No on-chain actions needed."

    async def run(self):
        """Listen for CONSENSUS_DECISION messages and execute approved actions."""
        await self.log("Executor online. Wallet connected. Awaiting approved commands...")

        while self._running:
            try:
                msg: Message = await asyncio.wait_for(self.decision_inbox.get(), timeout=120)

                prop_id = msg.property_id
                decision = msg.payload.get("decision", "REJECTED")
                final_verdict = msg.payload.get("final_verdict", {})
                properties = self.shared_state.get("properties", {})
                prop = properties.get(prop_id, {})

                if decision == "APPROVED":
                    await self.log(f"Consensus APPROVED for {prop.get('name', prop_id)}. Executing...", prop_id)
                    result = await self.execute_verdict(prop_id, final_verdict)

                    # Collect raw threats from source reports for the frontend
                    source_reports = msg.payload.get("source_reports", [])
                    all_raw_threats = []
                    for report in source_reports if isinstance(source_reports, list) else []:
                        raw = report.get("raw_alerts", [])
                        if isinstance(raw, list):
                            all_raw_threats.extend(raw)
                    prop["active_threats"] = all_raw_threats

                elif decision == "REJECTED":
                    await self.log(
                        f"⛔ Consensus REJECTED action for {prop.get('name', prop_id)}. No on-chain action taken.",
                        prop_id
                    )
                    # Still update informational state (health, analysis) but NOT paused status
                    if prop:
                        prop["health_score"] = final_verdict.get("recommended_health_score", prop.get("health_score", 100))
                        prop["latest_analysis"] = f"[BLOCKED BY CONSENSUS] {final_verdict.get('analysis', 'Action rejected.')}"

            except asyncio.TimeoutError:
                continue
