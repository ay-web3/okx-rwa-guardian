import json
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

async def analyze_threats(threat_data: list, property_info: dict, api_key: str) -> dict:
    """
    Calls OpenAI GPT-4o-mini to act as a catastrophe analyst.
    Returns a dict with:
    - threat_level: str (NONE/LOW/MEDIUM/HIGH/CRITICAL)
    - recommended_health_score: int
    - should_pause_trading: bool
    - analysis: str
    """
    if not api_key:
        logger.warning("No API key provided. Returning default analysis.")
        return {
            "threat_level": "UNKNOWN",
            "recommended_health_score": 100,
            "should_pause_trading": False,
            "analysis": "No API key configured to analyze threats."
        }

    client = AsyncOpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    
    system_prompt = (
        "You are an AI Sentinel for RWA Guardian, a smart contract real-world asset (RWA) management system. "
        "Analyze the provided news/threat data and property info, and output a JSON object with the following schema exactly:\n"
        "{\n"
        '  "threat_level": "NONE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | "POSITIVE",\n'
        '  "recommended_health_score": <int from 0 to 100>,\n'
        '  "recommended_yield_rate": <int from 0 to 200 (100 = 100% normal yield, lower if risks detected, higher if positive catalysts exist)>,\n'
        '  "should_pause_trading": <bool>,\n'
        '  "analysis": "<detailed string explaining the reasoning>"\n'
        "}\n"
        "If there is positive news (e.g. tech hub investment, tax cuts, infrastructure upgrades), you should INCREASE the recommended_yield_rate above 100.\n"
        "Only output valid JSON. Do not include markdown code blocks or any other text."
    )
    
    user_prompt = f"Property Info: {json.dumps(property_info)}\nThreat Data: {json.dumps(threat_data)}"
    
    try:
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        result = json.loads(content)
        
        return {
            "threat_level": result.get("threat_level", "UNKNOWN"),
            "recommended_health_score": result.get("recommended_health_score", 100),
            "recommended_yield_rate": result.get("recommended_yield_rate", 100),
            "should_pause_trading": result.get("should_pause_trading", False),
            "analysis": result.get("analysis", "No analysis provided.")
        }
    except Exception as e:
        logger.error(f"Error during LLM analysis: {e}")
        return {
            "threat_level": "ERROR",
            "recommended_health_score": 100,
            "should_pause_trading": False,
            "analysis": f"Error during analysis: {str(e)}"
        }
