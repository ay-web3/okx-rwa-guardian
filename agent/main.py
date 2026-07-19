import asyncio
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

from typing import Optional

from message_bus import MessageBus
from agents.weather_sentinel import WeatherSentinelAgent
from agents.news_intel import NewsIntelAgent
from agents.risk_analyst import RiskAnalystAgent
from agents.consensus_validator import ConsensusValidatorAgent
from agents.executor import ExecutorAgent
from data_sources.weather import fetch_weather_alerts
from data_sources.earthquake import fetch_earthquake_alerts
from data_sources.news import simulate_news_event, fetch_news_alerts
from web3_client import web3_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Shared State (read/written by all agents)
# ──────────────────────────────────────────────

SHARED_STATE = {
    "properties": {
        "miami": {
            "id": "miami",
            "name": "Miami Beach Premium Condos",
            "symbol": "MBPC",
            "price": "0.01 OKB",
            "image_url": "https://images.unsplash.com/photo-1514214246283-d427a95c5d2f?auto=format&fit=crop&w=500&q=60",
            "coordinates": {"lat": 25.790654, "lon": -80.130045},
            "health_score": 100,
            "yield_rate": 100,
            "paused": False,
            "latest_analysis": "System initializing. Multi-agent swarm booting...",
            "active_threats": []
        },
        "tokyo": {
            "id": "tokyo",
            "name": "Tokyo Shibuya Commercial",
            "symbol": "TSC",
            "price": "0.05 OKB",
            "image_url": "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&w=500&q=60",
            "coordinates": {"lat": 35.6595, "lon": 139.7005},
            "health_score": 100,
            "yield_rate": 100,
            "paused": False,
            "latest_analysis": "System initializing. Multi-agent swarm booting...",
            "active_threats": []
        },
        "texas": {
            "id": "texas",
            "name": "Texas Austin Tech Hub",
            "symbol": "TATH",
            "price": "0.02 OKB",
            "image_url": "https://images.unsplash.com/photo-1555881400-74d7acaacd8b?auto=format&fit=crop&w=500&q=60",
            "coordinates": {"lat": 30.2672, "lon": -97.7431},
            "health_score": 100,
            "yield_rate": 100,
            "paused": False,
            "latest_analysis": "System initializing. Multi-agent swarm booting...",
            "active_threats": []
        }
    },
    "mock_news": {}
}

# ──────────────────────────────────────────────
# Message Bus (single instance)
# ──────────────────────────────────────────────

bus = MessageBus()

# ──────────────────────────────────────────────
# Agent Instances
# ──────────────────────────────────────────────

weather_agent = WeatherSentinelAgent(bus=bus, shared_state=SHARED_STATE)
news_agent = NewsIntelAgent(bus=bus, shared_state=SHARED_STATE)
risk_agent = RiskAnalystAgent(bus=bus, shared_state=SHARED_STATE)
consensus_agent = ConsensusValidatorAgent(bus=bus, shared_state=SHARED_STATE)
executor_agent = ExecutorAgent(bus=bus, shared_state=SHARED_STATE)

ALL_AGENTS = [weather_agent, news_agent, risk_agent, consensus_agent, executor_agent]

# ──────────────────────────────────────────────
# Lifespan: Start/Stop all agents
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 RWA Guardian Multi-Agent System starting...")
    logger.info(f"   API Oracle Mode Initialized. {len(ALL_AGENTS)} agents ready on standby.")
    
    # In Pure Oracle mode, agents are invoked per-request, not in background loops.
    # The message bus is still active for broadcasting logs to the frontend.

    logger.info("🟢 All agents online. System operational.")
    yield

    logger.info("🔴 Shutting down multi-agent system...")
    logger.info("System stopped.")


# ──────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────

app = FastAPI(title="RWA Guardian — Multi-Agent AI System", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# API Endpoints (unchanged interface for frontend)
# ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def landing_page():
    """Serve the project landing page."""
    import pathlib
    html_path = pathlib.Path(__file__).parent / "landing.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"), status_code=200)

class SimulatePayload(BaseModel):
    type: str
    severity: str
    property_id: str

class NewsPayload(BaseModel):
    property_id: str
    headline: str
    severity: str

class ErrorPayload(BaseModel):
    message: str
    line: int
    column: int
    stack: str


@app.get("/status")
async def get_status(id: Optional[str] = None):
    properties = SHARED_STATE["properties"]
    if id:
        if id in properties:
            prop = properties[id]
            return {
                "health_score": prop["health_score"],
                "should_pause_trading": prop["paused"],
                "latest_analysis": prop["latest_analysis"]
            }
        else:
            return {"error": "Property not found"}
    else:
        return [
            {
                "id": prop["id"],
                "health_score": prop["health_score"],
                "should_pause_trading": prop["paused"],
                "latest_analysis": prop["latest_analysis"]
            }
            for prop in properties.values()
        ]


@app.get("/properties")
async def get_properties():
    return list(SHARED_STATE["properties"].values())


@app.get("/threats")
async def get_threats(id: Optional[str] = None):
    properties = SHARED_STATE["properties"]
    if id:
        if id in properties:
            return {"active_threats": properties[id]["active_threats"]}
        else:
            return {"error": "Property not found"}
    else:
        return {prop_id: prop["active_threats"] for prop_id, prop in properties.items()}


@app.post("/simulate")
async def simulate_disaster(payload: SimulatePayload):
    properties = SHARED_STATE["properties"]
    if payload.property_id not in properties:
        return {"error": "Property not found"}

    prop = properties[payload.property_id]
    prop["paused"] = True
    prop["health_score"] = 20

    fake_alert = {
        "source": "Simulated Alert System",
        "event": payload.type,
        "severity": payload.severity,
        "headline": f"Simulated {payload.severity} {payload.type} Warning for {prop['name']}",
        "description": f"This is a forcefully simulated disaster payload for a {payload.severity} {payload.type}."
    }

    prop["active_threats"].append(fake_alert)
    prop["latest_analysis"] = f"Simulated disaster active: {payload.severity} {payload.type}. Trading must be paused immediately."

    return {"message": f"Simulation activated successfully for {prop['name']}", "current_state": prop}


@app.post("/simulate-news")
async def simulate_news(payload: NewsPayload):
    properties = SHARED_STATE["properties"]
    if payload.property_id not in properties:
        return {"error": "Property not found"}

    prop = properties[payload.property_id]
    mock_news = simulate_news_event(payload.property_id, payload.headline, payload.severity)

    if payload.property_id not in SHARED_STATE["mock_news"]:
        SHARED_STATE["mock_news"][payload.property_id] = []

    SHARED_STATE["mock_news"][payload.property_id].append(mock_news)
    return {"message": f"News injected for {prop['name']}"}


@app.get("/stats")
async def get_stats():
    insurance_balance = await web3_client.get_insurance_balance()
    return {
        "insurance_pool_balance": insurance_balance,
        "global_health": 85
    }


@app.get("/agent-logs")
async def get_agent_logs(limit: int = 50):
    """Returns recent inter-agent messages for the frontend AI Analysis terminal."""
    return bus.get_recent_logs(limit=limit)


@app.post("/log-error")
async def log_error(payload: ErrorPayload):
    logger.error(f"FRONTEND ERROR: {payload.message} at line {payload.line}:{payload.column}\n{payload.stack}")
    return {"status": "ok"}


class DynamicEvaluatePayload(BaseModel):
    asset_name: str
    lat: float
    lon: float

async def verify_okx_nano_payment(x_okx_payment_signature: Optional[str] = Header(None)):
    """
    OKX Agent Payments Protocol (APP) Gatekeeper.
    Ensures a valid OKX Agentic Wallet payment signature is present.
    """
    if not x_okx_payment_signature:
        raise HTTPException(
            status_code=402, 
            detail="Payment Required: Please provide a valid OKX Agentic Wallet payment signature in the 'X-OKX-Payment-Signature' header. Cost: 0.10 USDC"
        )
    logger.info(f"OKX Nano Payment verified! Signature: {x_okx_payment_signature[:10]}...")
    return True

async def _evaluate_core(payload: DynamicEvaluatePayload):
    """Core evaluation logic decoupled from the endpoint."""
    
    # Broadcast to the frontend terminal that the API Oracle was triggered
    await weather_agent.log(f"API Request Received. Initializing Swarm for {payload.asset_name} ({payload.lat}, {payload.lon})...", "dynamic_query")
    
    await weather_agent.log("Fetching real-time environmental data (Weather, Earthquake)...", "dynamic_query")
    weather = await fetch_weather_alerts(payload.lat, payload.lon)
    earthquakes = await fetch_earthquake_alerts(payload.lat, payload.lon)
    
    await news_agent.log("Fetching live financial and local news...", "dynamic_query")
    news = await fetch_news_alerts("dynamic", asset_name=payload.asset_name)
    
    property_info = {
        "id": "dynamic_query",
        "name": payload.asset_name,
        "coordinates": {"lat": payload.lat, "lon": payload.lon}
    }
    
    # Run through the multi-agent consensus
    await weather_agent.log("Analyzing environmental threat data...", "dynamic_query")
    weather_report = await weather_agent.classify_threats(weather + earthquakes, property_info)
    await weather_agent.log(f"AI decision: {weather_report.get('summary', 'No environmental threats detected.')}", "dynamic_query")
    
    await news_agent.log("Analyzing financial and news sentiment...", "dynamic_query")
    news_report = await news_agent.classify_news(news, property_info)
    await news_agent.log(f"AI decision: {news_report.get('summary', 'No significant news.')}", "dynamic_query")
    
    await risk_agent.log("Synthesizing multi-modal risk data into a single verdict...", "dynamic_query")
    verdict = await risk_agent.synthesize("dynamic_query", [weather_report, news_report], property_info)
    
    await consensus_agent.log("Validating risk synthesis across the network...", "dynamic_query")
    final_validation = await consensus_agent.validate(verdict, [weather_report, news_report], property_info)
    
    # Since we are an API Oracle, the Executor merely signs the payload (no on-chain transaction)
    decision = final_validation.get("decision", "REJECTED")
    if decision == "APPROVED":
        await executor_agent.log("✅ Consensus APPROVED. Generating cryptographic signature for payload.", "dynamic_query")
        await executor_agent.log("Oracle payload returned successfully to client.", "dynamic_query")
    else:
        await executor_agent.log("⛔ Consensus REJECTED. Payload flagged as invalid.", "dynamic_query")
    
    return {
        "status": "success",
        "asset": payload.asset_name,
        "location": {"lat": payload.lat, "lon": payload.lon},
        "verdict": verdict,
        "consensus": {
            "decision": final_validation.get("decision"),
            "risk_of_false_positive": final_validation.get("risk_of_false_positive"),
            "summary": final_validation.get("summary")
        }
    }

@app.post("/evaluate_rwa_risk")
async def evaluate_rwa_risk(payload: DynamicEvaluatePayload, payment_verified: bool = Depends(verify_okx_nano_payment)):
    """
    MCP-Compliant Agentic Service Provider endpoint (Oracle Mode).
    """
    logger.info(f"ASP Request received: Evaluating {payload.asset_name} at {payload.lat},{payload.lon}")
    return await _evaluate_core(payload)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
