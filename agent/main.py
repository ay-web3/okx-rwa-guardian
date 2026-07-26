import asyncio
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

from typing import Optional

from message_bus import MessageBus
from agents.weather_sentinel import WeatherSentinelAgent
from agents.news_intel import NewsIntelAgent
from agents.market_intel import MarketIntelAgent
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
market_agent = MarketIntelAgent(bus=bus, shared_state=SHARED_STATE)
risk_agent = RiskAnalystAgent(bus=bus, shared_state=SHARED_STATE)
consensus_agent = ConsensusValidatorAgent(bus=bus, shared_state=SHARED_STATE)
executor_agent = ExecutorAgent(bus=bus, shared_state=SHARED_STATE)

ALL_AGENTS = [weather_agent, news_agent, market_agent, risk_agent, consensus_agent, executor_agent]

# ──────────────────────────────────────────────
# Lifespan: Start/Stop all agents
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 RWA Guardian Multi-Agent System starting...")
    logger.info(f"   Oracle V2 EventBus Mode Initialized. Starting {len(ALL_AGENTS)} agent loops.")
    
    # Start all agent loops in the background
    tasks = [asyncio.create_task(agent.start()) for agent in ALL_AGENTS]

    logger.info("🟢 All agents online. EventBus listening for requests.")
    yield

    logger.info("🔴 Shutting down multi-agent system...")
    for agent in ALL_AGENTS:
        agent.stop()
    for task in tasks:
        task.cancel()
    logger.info("System stopped.")


# ──────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────

description = """
**RWA Guardian** is an autonomous AI Decision Oracle that bridges the physical world and the blockchain.

### OKX.AI Marketplace
- **Agent ID:** `#6007`
- **Role:** `Agentic Service Provider (ASP)`
- **Cost:** `0.05 USDT per query` (via OKX Agent Payments Protocol)

### Core Capabilities
This API allows smart contracts and external Web3 agents to query real-time, multi-dimensional risk assessments for tokenized Real-World Assets. The 4-agent swarm automatically correlates NOAA weather alerts, USGS earthquake data, and Google News sentiment into actionable protocol decisions (e.g., `raiseCollateralRatio`).
"""

app = FastAPI(
    title="RWA Guardian — AI Decision Oracle",
    description=description,
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,  # We will override this to provide a custom dark theme
    redoc_url=None
)

# Custom exception handler to ensure PAYMENT-REQUIRED header is sent on 402 responses
from starlette.requests import Request
from fastapi.responses import JSONResponse as _JSONResponse

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    headers = getattr(exc, "headers", None) or {}
    return _JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers
    )

@app.get("/docs", include_in_schema=False)
async def scalar_html():
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{app.title} - API Docs</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
            body {{ margin: 0; padding: 0; background-color: #0c0c14; }}
            .zoom-controls {{
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: rgba(12, 12, 22, 0.9);
                border: 1px solid rgba(0, 212, 255, 0.2);
                border-radius: 8px;
                display: flex;
                gap: 8px;
                padding: 8px;
                z-index: 9999;
                backdrop-filter: blur(10px);
            }}
            .zoom-btn {{
                background: transparent;
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: #c8c8d8;
                width: 32px;
                height: 32px;
                border-radius: 4px;
                cursor: pointer;
                font-family: monospace;
                font-size: 16px;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s;
            }}
            .zoom-btn:hover {{
                background: rgba(0, 212, 255, 0.1);
                border-color: #00d4ff;
                color: #00d4ff;
            }}
            /* Remove height limits on scalar response box so it doesn't scroll inside a small window */
            .scalar-api-client__response {{ max-height: none !important; height: auto !important; }}
            .scalar-api-client__response-body {{ max-height: none !important; height: auto !important; }}
        </style>
    </head>
    <body>
        <div class="zoom-controls">
            <button class="zoom-btn" onclick="zoomCode(1)" title="Zoom In">A+</button>
            <button class="zoom-btn" onclick="zoomCode(-1)" title="Zoom Out">A-</button>
        </div>
        <script id="api-reference" data-url="/openapi.json" data-theme="moon"></script>
        <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
        <script>
            let currentSize = 13; // Default Scalar font size
            function zoomCode(direction) {{
                currentSize += direction * 2;
                if (currentSize < 10) currentSize = 10;
                if (currentSize > 32) currentSize = 32;
                
                document.documentElement.style.setProperty('--scalar-font-size-2', currentSize + 'px', 'important');
                document.documentElement.style.setProperty('--scalar-font-size-3', currentSize + 'px', 'important');
                document.documentElement.style.setProperty('--scalar-font-code', currentSize + 'px', 'important');
                
                // Force all pre/code blocks and CodeMirror editors to take the new size
                const styleId = 'zoom-style-override';
                let style = document.getElementById(styleId);
                if (!style) {{
                    style = document.createElement('style');
                    style.id = styleId;
                    document.head.appendChild(style);
                }}
                style.innerHTML = `
                    .scalar-api-client pre, 
                    .scalar-api-client code,
                    .cm-editor,
                    .cm-content,
                    .cm-line,
                    .cm-gutterElement {{ 
                        font-size: ${{currentSize}}px !important; 
                        line-height: 1.8 !important; 
                    }}
                `;
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)

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



@app.get("/agent-logs")
async def get_agent_logs(limit: int = 50):
    """Returns recent inter-agent messages. Great for demonstrating the AI swarm's internal reasoning to hackathon judges."""
    return bus.get_recent_logs(limit=limit)

class DynamicEvaluatePayload(BaseModel):
    asset_name: str = "Miami Condo"
    lat: float = 25.79
    lon: float = -80.13

# ──────────────────────────────────────────────
# x402 Payment Middleware Configuration
# ──────────────────────────────────────────────
from fastapi import Depends
try:
    from x402 import x402ResourceServer
    from x402.http import OKXFacilitatorClient, OKXFacilitatorConfig, OKXAuthConfig, PaymentOption, RouteConfig
    from x402.http.middleware.fastapi import payment_middleware
    from x402.mechanisms.evm.exact.server import ExactEvmScheme
    from x402.schemas import AssetAmount

    # 1. Configure the OKX API Auth for the Facilitator
    # We use .strip() to remove any accidental spaces or quotes copied into Render
    auth_config = OKXAuthConfig(
        api_key=os.getenv("OKX_API_KEY", "").strip(' \'"\n\r\t'),
        secret_key=os.getenv("OKX_SECRET_KEY", "").strip(' \'"\n\r\t'),
        passphrase=os.getenv("OKX_PASSPHRASE", "").strip(' \'"\n\r\t')
    )
    
    # 2. Initialize the Facilitator and Resource Server
    facilitator_client = OKXFacilitatorClient(OKXFacilitatorConfig(auth=auth_config))
    resource_server = x402ResourceServer(facilitator_clients=[facilitator_client])
    resource_server.register("eip155:196", ExactEvmScheme())
    
    route_config = {
        "POST /api/v1/consumer/risk_report": RouteConfig(
            accepts=[
                PaymentOption(
                    scheme="exact",
                    network="eip155:196",
                    price=AssetAmount(amount="50000", asset="0x779Ded0c9e1022225f8E0630b35a9b54bE713736"),
                    pay_to="0x1fd66d9e94a16db5a55bc03400282484962e2e8b",
                    extra={"name": "Tether USD", "version": "1"}
                )
            ],
            resource="/api/v1/consumer/risk_report"
        ),
        "POST /api/v1/oracle/risk_verdict": RouteConfig(
            accepts=[
                PaymentOption(
                    scheme="exact",
                    network="eip155:196",
                    price=AssetAmount(amount="50000", asset="0x779Ded0c9e1022225f8E0630b35a9b54bE713736"),
                    pay_to="0x1fd66d9e94a16db5a55bc03400282484962e2e8b",
                    extra={"name": "Tether USD", "version": "1"}
                )
            ],
            resource="/api/v1/oracle/risk_verdict"
        )
    }
    
    # Add the FastAPI middleware
    from x402.http.middleware.fastapi import PaymentMiddlewareASGI
    app.add_middleware(
        PaymentMiddlewareASGI,
        server=resource_server,
        routes=route_config
    )
except Exception as e:
    raise RuntimeError(f"Failed to initialize OKX SDK: {e}")

import traceback


async def _core_risk_evaluation(payload: DynamicEvaluatePayload):
    """
    Internal helper to run the multi-agent AI pipeline using the Event Bus.
    """
    prop_id = "dynamic_query"
    property_info = {
        "id": prop_id,
        "name": payload.asset_name,
        "coordinates": {"lat": payload.lat, "lon": payload.lon}
    }
    logger.info(f"Emitting evaluation request for: {payload.asset_name} at {payload.lat},{payload.lon}")
    
    # Broadcast to the frontend terminal
    await weather_agent.log(f"API Request Received. Initializing Swarm for {payload.asset_name}...", prop_id)
    
    # Subscribe to the final result before triggering
    result_queue = shared_bus.subscribe(MessageType.PAYLOAD_SIGNED)

    from message_bus import Message
    # Trigger the pipeline
    await shared_bus.publish(Message(
        type=MessageType.EVALUATION_REQUESTED,
        sender="API Gateway",
        property_id=prop_id,
        payload=property_info
    ))
    
    # Wait for the Executor to publish the final signed payload
    try:
        while True:
            msg: Message = await asyncio.wait_for(result_queue.get(), timeout=60)
            if msg.property_id == prop_id:
                return msg.payload
    except asyncio.TimeoutError:
        logger.error("Pipeline timed out waiting for PAYLOAD_SIGNED.")
        return {"error": "Timeout waiting for consensus."}

@app.post("/api/v1/consumer/risk_report")
async def evaluate_rwa_consumer(payload: DynamicEvaluatePayload):
    """
    Consumer endpoint for retail traders or basic UI clients.
    Returns a simplified summary of the asset's risk profile without heavy cryptographic data.
    Requires 0.05 USDT via x402.
    """
    try:
        core = await _core_risk_evaluation(payload)
        if "error" in core:
            return {"status": "error", "message": core["error"]}
            
        risk_score = core.get("overallRisk")
        if risk_score is None:
            risk_score = 0
            
        if risk_score > 80: risk_level = "CRITICAL"
        elif risk_score > 50: risk_level = "HIGH"
        elif risk_score > 20: risk_level = "MEDIUM"
        else: risk_level = "LOW"
        
        # Return a richer, human-readable summary for consumers
        return {
            "status": "success",
            "asset": payload.asset_name,
            "location": {"lat": payload.lat, "lon": payload.lon},
            "riskScore": risk_score,
            "riskLevel": risk_level,
            "recommendedAction": core.get("recommendedAction"),
            "consumerSummary": f"The overall risk score is {risk_score}/100. The underlying AI agent network recommends: {core.get('recommendedAction')}.",
            "evidence": core.get("evidence", [])
        }
    except Exception as e:
        logger.error(f"Consumer endpoint error: {e}", exc_info=True)
        return {"status": "error", "message": f"Internal Error: {e}", "traceback": traceback.format_exc()}

@app.post("/api/v1/oracle/risk_verdict")
async def evaluate_rwa_oracle(payload: DynamicEvaluatePayload):
    """
    Developer / Smart Contract endpoint for on-chain protocols.
    Returns the exact numeric scores, full trace, and cryptographic signature for on-chain verification.
    Requires 0.05 USDT via x402.
    """
    try:
        core = await _core_risk_evaluation(payload)
        if "error" in core:
            return {"status": "error", "message": core["error"]}
            
        # Return the full verbose payload intended for automated systems
        return {
            "status": "success",
            "oraclePayload": core
        }
    except Exception as e:
        logger.error(f"Oracle endpoint error: {e}", exc_info=True)
        return {"status": "error", "message": f"Internal Error: {e}", "traceback": traceback.format_exc()}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
