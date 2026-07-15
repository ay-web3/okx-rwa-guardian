import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages that flow between agents."""
    THREAT_DATA = "THREAT_DATA"
    RISK_VERDICT = "RISK_VERDICT"
    CONSENSUS_DECISION = "CONSENSUS_DECISION"
    EXECUTE_ACTION = "EXECUTE_ACTION"
    AGENT_LOG = "AGENT_LOG"


@dataclass
class Message:
    """A message passed between agents via the bus."""
    type: MessageType
    sender: str
    property_id: str
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    id: str = field(default_factory=lambda: f"msg-{datetime.utcnow().timestamp()}")


class MessageBus:
    """
    Lightweight async message bus for inter-agent communication.
    Agents subscribe to message types and receive copies of matching messages.
    """

    def __init__(self):
        self._subscribers: Dict[MessageType, List[asyncio.Queue]] = {}
        self._log: List[Message] = []
        self._log_limit = 500

    def subscribe(self, message_type: MessageType) -> asyncio.Queue:
        """Subscribe to a message type. Returns a queue that will receive matching messages."""
        queue = asyncio.Queue(maxsize=100)
        if message_type not in self._subscribers:
            self._subscribers[message_type] = []
        self._subscribers[message_type].append(queue)
        logger.info(f"New subscriber for {message_type.value}")
        return queue

    async def publish(self, message: Message):
        """Publish a message to all subscribers of its type."""
        # Store in log
        self._log.append(message)
        if len(self._log) > self._log_limit:
            self._log = self._log[-self._log_limit:]

        # Deliver to subscribers
        queues = self._subscribers.get(message.type, [])
        for queue in queues:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning(f"Queue full for {message.type.value}, dropping message")

        logger.debug(f"[BUS] {message.sender} -> {message.type.value} for {message.property_id}")

    def get_recent_logs(self, limit: int = 50) -> List[Dict]:
        """Return recent messages for the frontend AI Analysis terminal."""
        return [
            {
                "timestamp": msg.timestamp,
                "sender": msg.sender,
                "type": msg.type.value,
                "property_id": msg.property_id,
                "summary": msg.payload.get("summary", str(msg.payload)[:200])
            }
            for msg in self._log[-limit:]
        ]
