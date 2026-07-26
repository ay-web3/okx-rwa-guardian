import asyncio
import logging
from abc import ABC, abstractmethod
from message_bus import MessageBus, Message, MessageType

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all RWA Guardian agents.
    Provides message bus integration, logging, and lifecycle management.
    """

    def __init__(self, name: str, emoji: str, bus: MessageBus, shared_state: dict):
        self.name = name
        self.emoji = emoji
        self.bus = bus
        self.shared_state = shared_state
        self._subscriptions: dict[MessageType, asyncio.Queue] = {}
        self._running = False
        self.logger = logging.getLogger(f"agent.{name}")

    def subscribe(self, message_type: MessageType) -> asyncio.Queue:
        """Subscribe to a message type on the bus."""
        queue = self.bus.subscribe(message_type)
        self._subscriptions[message_type] = queue
        return queue

    async def publish(self, msg_type: MessageType, property_id: str, payload: dict):
        """Publish a message to the bus."""
        message = Message(
            type=msg_type,
            sender=f"{self.emoji} {self.name}",
            property_id=property_id,
            payload=payload
        )
        await self.bus.publish(message)

    async def log(self, message: str, property_id: str = "default"):
        """Logs action to console and pushes to the web UI if connected, and adds to trace."""
        log_entry = f"[{self.name}] {message}"
        self.logger.info(log_entry)
        
        # Append to the shared trace via the event bus
        await self.bus.append_trace(property_id, self.name, message)
        
        # In a real system, you might push this to a Redis pub/sub or WebSockets
        # For this demo, we simulate the network delay
        await asyncio.sleep(0.5)

    @abstractmethod
    async def run(self):
        """Main agent loop. Must be implemented by subclasses."""
        pass

    async def start(self):
        """Start the agent's run loop with error recovery."""
        self._running = True
        self.logger.info(f"{self.emoji} {self.name} agent started.")
        while self._running:
            try:
                await self.run()
            except asyncio.CancelledError:
                self.logger.info(f"{self.emoji} {self.name} agent cancelled.")
                break
            except Exception as e:
                self.logger.error(f"{self.emoji} {self.name} agent error: {e}")
                await asyncio.sleep(5)  # Brief pause before retry

    def stop(self):
        """Signal the agent to stop."""
        self._running = False
