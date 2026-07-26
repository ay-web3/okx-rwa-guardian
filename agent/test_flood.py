import asyncio
import json
import logging
from pydantic import BaseModel

class DynamicEvaluatePayload(BaseModel):
    asset_name: str
    lat: float
    lon: float

# Import the core evaluation function directly
from main import _core_risk_evaluation

async def run_test():
    payload = DynamicEvaluatePayload(
        asset_name="Texas Flood Zone",
        lat=28.65,
        lon=-99.11
    )
    result = await _core_risk_evaluation(payload)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    asyncio.run(run_test())
