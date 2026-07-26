import json

result = {
    "physicalRisk": 90,
    "economicRisk": 0,
    "liquidityRisk": 0,
    "riskWeights": {
        "physical": 0.5,
        "economic": 0.3,
        "liquidity": 0.2
    }
}

weights = result.get("riskWeights", {"physical": 0.5, "economic": 0.3, "liquidity": 0.2})
p_weight = weights.get("physical", 0.5)
e_weight = weights.get("economic", 0.3)
l_weight = weights.get("liquidity", 0.2)

result["overallRisk"] = round(
    result.get("physicalRisk", 0) * p_weight +
    result.get("economicRisk", 0) * e_weight +
    result.get("liquidityRisk", 0) * l_weight
)

print("Calculated overallRisk:", result["overallRisk"])
