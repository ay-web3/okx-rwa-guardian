"""
💀 Hack My Contract — FastAPI Application

Adversarial smart contract security analysis API. Exposes endpoints for
static analysis, LLM-powered adversarial review, and on-chain contract
fetching from block explorers.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.utils.explorer_client import ExplorerClient

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if get_settings().debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("hack_my_contract")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="💀 Hack My Contract",
    description="Adversarial Smart Contract Security Agent",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Middleware — CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Middleware — Request timing
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    """Inject an ``X-Process-Time`` header with the wall-clock duration."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{elapsed:.4f}s"
    logger.info(
        "%s %s completed in %.4fs",
        request.method,
        request.url.path,
        elapsed,
    )
    return response


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    """Payload for source-code analysis endpoints."""

    source_code: str = Field(
        ...,
        min_length=1,
        description="Raw Solidity source code to analyse.",
    )
    contract_name: str = Field(
        default="UnknownContract",
        description="Human-readable name for the contract under review.",
    )


class AddressAnalyzeRequest(BaseModel):
    """Payload for address-based analysis."""

    address: str = Field(
        ...,
        pattern=r"^0x[a-fA-F0-9]{40}$",
        description="EVM contract address (0x-prefixed, 40 hex chars).",
    )
    chain: str = Field(
        default="ethereum",
        description="Target chain: ethereum, xlayer, bsc, arbitrum.",
    )


class HealthResponse(BaseModel):
    """Health-check response."""

    status: str = "healthy"
    version: str = "1.0.0"
    service: str = "Hack My Contract"


# ---------------------------------------------------------------------------
# Helper — run the full analysis pipeline
# ---------------------------------------------------------------------------
async def _run_analysis(
    source_code: str,
    contract_name: str,
    *,
    include_llm: bool = True,
) -> dict[str, Any]:
    """Execute the analysis pipeline and return a structured report.

    Args:
        source_code: Raw Solidity source code.
        contract_name: Display name for the contract.
        include_llm: When ``True`` the adversarial LLM analyser is run
            in addition to static checks.  Set to ``False`` for the
            free / quick tier.

    Returns:
        A dictionary containing the full analysis report.
    """
    # Lazy imports so the app can still start even if the analyzer package
    # is not fully installed yet (useful during incremental development).
    from backend.analyzer.static_analysis import StaticAnalyzer
    from backend.analyzer.report_generator import ReportGenerator

    # 1. Static analysis
    static_analyzer = StaticAnalyzer()
    static_findings = static_analyzer.analyze(source_code)

    # 2. (Optional) LLM adversarial analysis
    llm_findings: list[dict[str, Any]] = []
    if include_llm:
        from backend.analyzer.llm_adversarial import AdversarialAnalyzer

        settings = get_settings()
        adversarial = AdversarialAnalyzer(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        llm_findings = await adversarial.analyze(
            source_code,
            static_findings=static_findings,
        )

    # 3. Generate combined report
    report_gen = ReportGenerator()
    report = report_gen.generate(
        contract_name=contract_name,
        source_code=source_code,
        static_findings=static_findings,
        llm_findings=llm_findings,
    )

    return report


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/", tags=["General"])
async def root() -> dict[str, Any]:
    """Welcome endpoint with API overview."""
    return {
        "message": "💀 Welcome to Hack My Contract",
        "description": "Adversarial Smart Contract Security Agent",
        "version": "1.0.0",
        "endpoints": {
            "POST /analyze": "Full analysis (static + LLM adversarial)",
            "POST /analyze/quick": "Quick static-only analysis (free tier)",
            "POST /analyze/address": "Fetch & analyse contract by on-chain address",
            "GET /health": "Health check",
            "GET /docs": "Interactive API documentation (Swagger UI)",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check() -> HealthResponse:
    """Lightweight health-check for monitoring and load-balancers."""
    return HealthResponse()


@app.post("/analyze", tags=["Analysis"])
async def analyze_contract(payload: AnalyzeRequest) -> dict[str, Any]:
    """Run full analysis pipeline: static analysis + LLM adversarial review.

    This endpoint invokes the static analyser to detect common
    vulnerability patterns, then passes those findings to the
    adversarial LLM agent which attempts to craft exploit scenarios.
    Finally, a combined report is generated.

    Returns:
        A JSON report containing vulnerabilities, risk scores, and
        recommended mitigations.
    """
    try:
        report = await _run_analysis(
            source_code=payload.source_code,
            contract_name=payload.contract_name,
            include_llm=True,
        )
        return {"status": "success", "report": report}
    except Exception as exc:
        logger.exception("Full analysis failed for %s", payload.contract_name)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {exc}",
        ) from exc


@app.post("/analyze/quick", tags=["Analysis"])
async def analyze_contract_quick(payload: AnalyzeRequest) -> dict[str, Any]:
    """Run quick static-only analysis (no LLM — fast and free).

    Performs regex-based pattern matching and heuristic checks against
    known vulnerability classes.  No external API calls are made.

    Returns:
        A JSON report with static analysis findings only.
    """
    try:
        report = await _run_analysis(
            source_code=payload.source_code,
            contract_name=payload.contract_name,
            include_llm=False,
        )
        return {"status": "success", "report": report}
    except Exception as exc:
        logger.exception("Quick analysis failed for %s", payload.contract_name)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {exc}",
        ) from exc


@app.post("/analyze/address", tags=["Analysis"])
async def analyze_by_address(payload: AddressAnalyzeRequest) -> dict[str, Any]:
    """Fetch verified source code from a block explorer, then analyse.

    Supported chains: ``ethereum``, ``xlayer``, ``bsc``, ``arbitrum``.

    The endpoint first queries the relevant chain's block explorer API
    to retrieve verified source code for the given contract address.
    If the contract is verified, it runs the full analysis pipeline.

    Returns:
        A JSON report containing the analysis results, or an error if
        the contract is not verified.
    """
    try:
        async with ExplorerClient() as explorer:
            contract_source = await explorer.fetch_source(
                address=payload.address,
                chain=payload.chain,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Explorer fetch failed for %s on %s",
            payload.address,
            payload.chain,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch contract source: {exc}",
        ) from exc

    if not contract_source.is_verified:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Contract {payload.address} on {payload.chain} is not "
                "verified or has no source code available."
            ),
        )

    try:
        report = await _run_analysis(
            source_code=contract_source.source_code,
            contract_name=contract_source.contract_name or payload.address,
            include_llm=True,
        )
        return {
            "status": "success",
            "address": payload.address,
            "chain": payload.chain,
            "contract_name": contract_source.contract_name,
            "compiler_version": contract_source.compiler_version,
            "report": report,
        }
    except Exception as exc:
        logger.exception(
            "Analysis failed for on-chain contract %s", payload.address
        )
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Entrypoint (for local development: `python -m backend.main`)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
