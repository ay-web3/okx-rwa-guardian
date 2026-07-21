# 🛡️ RWA Guardian (OKX.AI Hackathon Submission)

**RWA Guardian** is an autonomous, multi-agent AI risk management system designed for tokenized Real-World Assets (RWAs) on the **OKX X Layer**. 

Acting as an **Agentic Service Provider (ASP)**, RWA Guardian bridges the physical world and the blockchain. It continuously monitors real-world APIs for environmental and economic threats, reaches a multi-agent consensus, and delivers cryptographically signed instruction payloads to developers and traders via OKX Nano-payments.

![RWA Guardian Dashboard](https://images.unsplash.com/photo-1639762681485-074b7f4ec651?auto=format&fit=crop&w=1200&q=80)

## 🏆 OKX.AI Hackathon Fit

This project was built specifically for the **OKX.AI Genesis Hackathon**. It perfectly demonstrates the power of Agentic Service Providers in DeFi:
1. **Agent-to-Agent Commerce:** Uses the OKX Agent Payments Protocol (APP) to charge nano-payments (0.05 USDT) to external bots in exchange for AI risk intelligence.
2. **Multi-Agent Swarm Architecture:** Instead of a monolithic LLM script, we implemented a robust 4-agent pipeline to eliminate AI hallucinations and false positives.
3. **Real-World Integration:** Brings off-chain physical data (NOAA, USGS) on-chain via AI reasoning rather than traditional, rigid oracles.

---

## 🧠 The Multi-Agent Swarm Architecture

To ensure the safety of on-chain assets, no single AI makes a critical decision. We built an asynchronous message bus where 4 distinct roles collaborate:

1. 📡 **Data Collector:** Gathers raw environmental (NOAA/USGS) and economic (Google News) JSON data.
2. 🧠 **Reasoning Agent (Risk Analyst):** Synthesizes the heterogenous data to produce multi-dimensional physical, economic, and liquidity risk scores, and recommends protocol actions (e.g., `raiseCollateralRatio`).
3. ⚖️ **Verification Agent:** Acts as an independent auditor. It actively checks the Reasoning Agent's evidence, confidence, and consistency before approving critical actions.
4. 🔐 **Signer:** The agent holding the ASP's private keys. It cryptographically signs the final consensus payload (the "Signal"). This signature allows protocols to verify the payload originated from RWA Guardian and was not modified in transit, ensuring strict provenance and authenticity.

---

## ⚙️ How It Works (The "Signal vs. Action" Model)

RWA Guardian is fully integrated with the **OKX Agent Payments Protocol (APP)** and the **OKX Agentic Wallet**. We operate as a **Pure AI Decision Oracle**, selling our 4-agent consensus directly to other Web3 agents via nano-payments.

By splitting the architecture into "Signal" (Our API) and "Action" (The Client's Wallet), we achieve 100% security with zero gas-abstraction issues.

### The Target Markets

**1. Protocol Developers (Smart Contract Security)**
A DeFi protocol developer connects their own local OKX Agentic Wallet to our ASP. They pay us **0.05 USDT** via the APP header to hit our `POST /api/v1/oracle/risk_verdict` endpoint. Our AI swarm processes the real-world data and returns a cryptographically signed instruction payload with structured actions. The developer's *own* local Agentic Wallet verifies the signature and executes the transaction.

**2. Algorithmic Traders & Retail Users (Informational Risk)**
Traders pay us **0.05 USDT** to feed our risk assessments directly into their terminal via our `POST /api/v1/consumer/risk_report` endpoint. They get a human-readable executive summary of the real-world threats and can quickly dump the token or open a short position on a DEX.

---

## 🛠️ Tech Stack

*   **AI/LLM:** Llama 3 (via Groq API) for ultra-fast, low-latency multi-agent reasoning.
*   **Backend:** Python 3, FastAPI, Asyncio (Custom Zero-Dependency Message Bus).
*   **Blockchain Integration:** Web3.py, Ethers.js, Solidity.
*   **Network:** OKX X Layer Testnet (Chain ID 1952).
*   **Frontend:** Vanilla JS, CSS3 (Glassmorphism UI), HTML5.
*   **Data Oracles:** NOAA Weather API, USGS Earthquake API, Google News RSS.

---

## 📡 API Endpoints & Sample Responses

🔗 **Live API:** [`https://okx-rwa-guardian.onrender.com`](https://okx-rwa-guardian.onrender.com)

Both endpoints require a **0.05 USDT** X402 Nano-Payment signature in the `X-OKX-Payment-Signature` header.

### 1. Consumer Risk Report
**`POST /api/v1/consumer/risk_report`**

Provides a highly readable, nested analysis for retail investors and dashboards.

```json
{
  "asset_name": "Tokyo Commercial Plaza",
  "consumerSummary": "🚨 High Risk: 72/100 | Action: raiseCollateralRatio",
  "report": {
    "executiveSummary": "The asset faces a significant threat from a 7.2 magnitude earthquake near Tokyo.",
    "detailedAnalysis": "...",
    "riskFactors": {
      "physicalRisk": 74,
      "economicRisk": 61,
      "liquidityRisk": 49
    },
    "caveats": "Insurance costs remain stable; no regulatory changes detected.",
    "auditorNotes": "Approved by Verification Agent."
  }
}
```

### 2. Oracle Risk Verdict
**`POST /api/v1/oracle/risk_verdict`**

Provides a structured, cryptographically signed payload for on-chain smart contracts.

```json
{
  "asset_name": "Tokyo Commercial Plaza",
  "overallRisk": 68,
  "recommendedAction": "raiseCollateralRatio",
  "confidence": 0.94,
  "signature": "0x3a8f...c4e1",
  "auditor_trace": "...",
  "raw_scores": {
    "physicalRisk": 74,
    "economicRisk": 61,
    "liquidityRisk": 49
  }
}
```

### Action Space

| Overall Risk | Recommended Action | Protocol Effect |
|---|---|---|
| 0–20 | `normal` | No action needed |
| 21–50 | `increaseMonitoring` | Increase polling frequency |
| 51–80 | `raiseCollateralRatio` | Increase collateral requirements |
| 81–90 | `pauseNewBorrowing` | Halt new loan origination |
| 91–100 | `freezeTransfers` | Emergency freeze all transfers |

---

## 🚀 How to Run Locally

### Prerequisites
* Python 3.9+
* A Groq API Key (or OpenAI API Key)

### 1. Setup the Backend (Multi-Agent Swarm)
```bash
cd agent
python -m venv venv
source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

Create a `.env` file in the `agent` directory:
```env
GROQ_API_KEY=your_groq_api_key
PRIVATE_KEY=your_wallet_private_key_with_xlayer_testnet_funds
```

Start the orchestration server:
```bash
python main.py
```

### 2. Start the Frontend Dashboard
Open a new terminal:
```bash
cd frontend
python -m http.server 8081
```

Visit `http://127.0.0.1:8081` in your browser. 
Click **"SIMULATE DISASTER"** to watch the multi-agent swarm detect the anomaly, debate it, and lock down the smart contract in real-time!

---

## 📜 Smart Contract

The `RWAToken.sol` contract is currently deployed and verified on the **OKX X Layer Testnet**.
* **Contract Address:** `0xbbAd97DabBa50807F38F9cF3812F2E7B1305b7E6`

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

## 🤝 Team

Built by [**@Ay-web3**](https://github.com/ay-web3) for the OKX.AI Genesis Hackathon.

