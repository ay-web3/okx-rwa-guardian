# 🛡️ RWA Guardian — AI Decision Oracle for Tokenized Real-World Assets

> **Agent #6007** on the [OKX.AI Marketplace](https://okx.ai) · Live & Earning

**RWA Guardian** is an autonomous, multi-agent AI swarm that acts as a **Reasoning Oracle** — bridging the physical world and the blockchain. It continuously monitors real-world data sources for environmental and economic threats, reaches multi-agent consensus, and delivers cryptographically signed (EIP-191) risk verdicts to smart contracts and DeFi protocols via the OKX X402 Agent Payments Protocol.

🌐 **Live Demo:** [okx-rwa-guardian.onrender.com](https://okx-rwa-guardian.onrender.com)
📄 **API Docs:** [okx-rwa-guardian.onrender.com/docs](https://okx-rwa-guardian.onrender.com/docs)

---

## 🏆 OKX.AI Genesis Hackathon

This project was built for the **OKX.AI Genesis Hackathon**. It demonstrates the full power of the Agent Economy:

1. **Machine-to-Machine Commerce** — Uses the OKX X402 Agent Payments Protocol to charge 0.05 USDT per query. Autonomous agents pay each other for high-value reasoning in real time.
2. **Multi-Agent Swarm Architecture** — A 5-agent hierarchical pipeline with consensus validation to eliminate AI hallucinations and false positives.
3. **Reasoning Oracle** — Goes beyond raw data feeds. Correlates weather, seismic, and news intelligence to produce actionable protocol directives that smart contracts can verify and execute on-chain.

---

## 🧠 The 5-Agent Swarm Architecture

No single AI makes a critical decision. Five specialized agents collaborate through an asynchronous message bus:

| # | Agent | Role |
|---|---|---|
| 1 | 📡 **Weather Sentinel** | Ingests live environmental data from NOAA and USGS — severe weather, seismic activity, climate threats |
| 2 | 📰 **News Intelligence** | Scans global news feeds via Google News, filtering noise to surface genuine regulatory and economic risks |
| 3 | 🧠 **Senior Risk Analyst** | Synthesizes raw intelligence into a multi-dimensional risk score using dynamic weighting |
| 4 | ⚖️ **Consensus Validator** | Independent auditor and devil's advocate — challenges the Analyst's findings to block false positives |
| 5 | 🔐 **Executor** | Finalizes the consensus verdict and cryptographically signs the payload with an EIP-191 signature |

---

## ⚙️ How It Works

RWA Guardian operates as an **Agentic Service Provider (ASP)** in the OKX.AI ecosystem. When an external DeFi protocol, trading bot, or AI agent queries the API, they're met with a `402 Payment Required` challenge. Using their OKX Agentic Wallet, the consumer pays a **0.05 USDT nano-fee** — settled instantly on X Layer — to unlock the analysis.

### Dual Endpoints

#### 1. Consumer Risk Report
**`POST /api/v1/consumer/risk_report`**

Rich, detailed JSON for human users, dashboards, and frontends.

```json
{
  "status": "success",
  "asset": "Miami Beach Condo",
  "location": { "lat": 25.79, "lon": -80.13 },
  "riskLevel": "MODERATE",
  "overallScore": { "score": 42, "max": 100 },
  "recommendedAction": "increaseMonitoring",
  "consumerSummary": "The property is currently assessed as MODERATE risk.",
  "report": {
    "executiveSummary": "Asset risk score is 42/100.",
    "keyFindings": ["Tropical storm activity detected in the region"],
    "detailedAnalysis": "...",
    "caveats": "..."
  }
}
```

#### 2. Oracle Risk Verdict
**`POST /api/v1/oracle/risk_verdict`**

Concise, optimized JSON for smart contracts with an EIP-191 cryptographic signature.

```json
{
  "status": "success",
  "asset": "Miami Beach Condo",
  "risk_score": 42,
  "action_code": 1,
  "action_label": "increaseMonitoring",
  "timestamp": "2026-07-27T21:00:00Z",
  "oracle_address": "0x1fd66d9e94a16db5a55bc03400282484962e2e8b",
  "signature": "0x3a8f...c4e1",
  "message_hash": "0x7b2c...9d3f"
}
```

### Action Space

| Risk Score | Action Code | Action Label | Protocol Effect |
|---|---|---|---|
| 0–20 | `0` | `normalOperations` | No action needed |
| 21–50 | `1` | `increaseMonitoring` | Increase polling frequency |
| 51–80 | `2` | `raiseCollateralRatio` | Increase collateral requirements |
| 81–100 | `3` | `pauseNewBorrowing` | Halt new loan origination |

### Request Body

All endpoints accept the same payload:

```json
{
  "asset_name": "Miami Beach Condo",
  "lat": 25.79,
  "lon": -80.13
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `asset_name` | string | ✅ | Max 100 characters |
| `lat` | float | ✅ | -90.0 to 90.0 |
| `lon` | float | ✅ | -180.0 to 180.0 |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3 · FastAPI · Asyncio (Custom Message Bus) |
| **Blockchain** | Solidity · X Layer (Chain ID 196) |
| **Frontend** | Vanilla JS · CSS3 · HTML5 |
| **Payments** | OKX X402 Agent Payments Protocol |
| **Data Sources** | NOAA Weather API · USGS Earthquake API · Google News |
| **Cryptography** | EIP-191 Signed Payloads |
| **Hosting** | Render (Auto-deploy from GitHub) |

---

## 🚀 How to Run Locally

### Prerequisites
* Python 3.9+
* Node.js 18+ (for testing scripts)
* OKX Agentic Wallet (via `onchainos` CLI)

### 1. Setup the Backend

```bash
cd agent
python -m venv venv
source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

Create a `.env` file in the `agent` directory:

```env
PRIVATE_KEY=your_wallet_private_key
```

Start the server:

```bash
uvicorn main:app --host 0.0.0.0 --port 10000
```

### 2. Start the Frontend

```bash
cd frontend
python -m http.server 8081
```

Visit `http://127.0.0.1:8081` in your browser.

---

## 🤖 OKX.AI Marketplace

| Field | Value |
|---|---|
| **Agent ID** | #6007 |
| **Name** | RWA Guardian |
| **Role** | Agentic Service Provider (ASP) |
| **Status** | Active ✅ |
| **Approval** | Listed — eligible for task recommendations |
| **Cost** | 0.05 USDT per query |
| **Chain** | X Layer (`eip155:196`) |
| **Wallet** | `0x1fd66d9e94a16db5a55bc03400282484962e2e8b` |

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

## 🤝 Team

Built by [**@Ay-web3**](https://github.com/ay-web3) for the OKX.AI Genesis Hackathon.
