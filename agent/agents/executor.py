import asyncio
import logging
import json
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
        self.decision_inbox = self.subscribe(MessageType.CONSENSUS_REACHED)

    async def execute_verdict(self, prop_id: str, verdict: dict) -> str:
        """Execute approved on-chain actions based on the final verdict."""
        properties = self.shared_state.get("properties", {})
        prop = properties.get(prop_id)
        if not prop:
            return "Property not found"

        tx_logs = ""
        new_paused = verdict.get("recommendedAction") in ["pauseNewBorrowing", "freezeTransfers"]
        
        # Map recommended action to visual yield penalty for the demo
        new_yield = 100
        if verdict.get("recommendedAction") == "raiseCollateralRatio":
            new_yield = 50
            
        # Map overall risk (0-100) to health score (100-0)
        overall_risk = verdict.get("overallRisk", 0)
        new_health = 100 - overall_risk

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

                elif decision in ["OVERRULED", "MANUAL_REVIEW"]:
                    await self.log(
                        f"⛔ Consensus {decision} for {prop.get('name', prop_id)}.",
                        prop_id
                    )
                    if prop:
                        overall_risk = final_verdict.get("overallRisk", 0)
                        prop["health_score"] = 100 - overall_risk
                        prop["latest_analysis"] = f"[{decision}] {final_verdict.get('analysis', 'Action rejected.')}"

                # --- ORACLE V2 PAYLOAD GENERATION ---
                import uuid
                import time
                from datetime import datetime, timedelta
                from eth_account import Account
                from eth_account.messages import encode_defunct
                from web3_client import PRIVATE_KEY
                
                # We determine the action deterministically here in python based on final risk
                final_risk = final_verdict.get("overallRisk", 0)
                
                if decision == "MANUAL_REVIEW":
                    final_action = "MANUAL_REVIEW"
                    action_code = 99
                elif final_risk > 80:
                    final_action = "pauseNewBorrowing"
                    action_code = 3
                elif final_risk > 50:
                    final_action = "raiseCollateralRatio"
                    action_code = 2
                elif final_risk > 20:
                    final_action = "increaseMonitoring"
                    action_code = 1
                else:
                    final_action = "normal"
                    action_code = 0

                timestamp_unix = int(time.time())
                
                oracle_payload = {
                    "asset_name": prop.get("name", prop_id),
                    "onchain_data": {
                        "risk_score": final_risk,
                        "action_code": action_code,
                        "timestamp": timestamp_unix,
                        "expiration": timestamp_unix + 300,
                        "nonce": int(uuid.uuid4().int >> 192) # Random uint64
                    }
                }

                if PRIVATE_KEY:
                    # In a real app this would be keccak256(abi.encode(...))
                    message_encoded = encode_defunct(text=json.dumps(oracle_payload["onchain_data"], sort_keys=True))
                    signed_message = Account.sign_message(message_encoded, private_key=PRIVATE_KEY)
                    oracle_payload["signature"] = signed_message.signature.hex()
                    
                oracle_payload["ai_metadata"] = {
                    "oracle_version": "2.0.0",
                    "action_human_readable": final_action,
                    "evidence": [
                        ev for r in (msg.payload.get("source_reports") or []) 
                        for ev in r.get("evidence", [])
                    ],
                    "agent_trace": self.bus.get_trace(prop_id)
                }

                await self.publish(MessageType.PAYLOAD_SIGNED, prop_id, oracle_payload)
                await self.log(f"Oracle V2 payload signed and published.", prop_id)

            except asyncio.TimeoutError:
                continue
