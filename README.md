# QueueStorm Warmup: Mock Preliminary Task

This repository contains the backend classification and routing service for **QueueStorm**, built for the mock preliminary round of the **SUST CSE Carnival 2026 Codex Community Hackathon**. 

## Project Overview

The service acts as an automated CRM ticket triage engine. It processes raw customer complaints (written in English, Bengali, or code-mixed Banglish), classifies their problem type, assigns a severity, routes the ticket to the correct department, and generates a two-second agent summary.

### Core Features

1. **Interactive Diagnostic Dashboard**: A premium, responsive web interface served directly from the root path (`http://localhost:8000/`) featuring sample ticket loaders, loading indicators, visual routing tags, and raw JSON inspect panel.
2. **Hybrid Classification Engine**:
   - **OpenRouter LLM Engine**: Utilizes `google/gemini-2.5-flash-lite` via OpenRouter Chat Completions API for semantic understanding, contextual classification, and summarizing messages in English, Bengali, and mixed language formats.
   - **Rules Engine (Fallback)**: Seamlessly falls back to a regex-based keyword matching heuristic when `OPENROUTER_API_KEY` is not provided or if the API is offline. This guarantees 100% service uptime and local testing capabilities without API keys.
3. **Pydantic Validation**: Ensures exact structural alignment with JSON request/response contracts.
4. **Safety Guardrails**: Implements a safety verification filter preventing the `agent_summary` field from requesting or containing customer credentials (such as PIN, OTP, password, or card numbers).
5. **Sub-second Response Times**:
   - `/health` responds in < 100ms (Requirement: < 10s).
   - `/sort-ticket` responds in < 200ms on Heuristics fallback and < 2s on LLM (Requirement: < 30s).
6. **Robust Error Handling**: Standardized JSON responses for all internal/validation errors. No raw 500 HTML pages.

---

## Tech Stack
- **Runtime**: Python 3.12+
- **API Framework**: FastAPI & Uvicorn
- **Data Validation**: Pydantic v2
- **Testing**: pytest & pytest-cov
- **Linting**: Ruff

---

## Local Deployment & Runbook

### 1. Clone & Setup Directory
```bash
git clone <your-repository-url>
cd sust-mock-preli
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory (based on `.env.example`):
```bash
cp .env.example .env
```
Open `.env` and fill in the parameters:
```ini
# Optional: Add your OpenRouter API key. If left blank, the local heuristics engine will take over.
OPENROUTER_API_KEY="your-openrouter-api-key-here"

PORT=8000
HOST="0.0.0.0"
```

### 3. Option A: Local Setup (Native)
Set up a virtual environment and install the required dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the Uvicorn application server:
```bash
uvicorn main:app --reload --port 8000
```
The server will start on `http://localhost:8000`. You can access the interactive Swagger API documentation at `http://localhost:8000/docs`.

### 4. Option B: Containerized Setup (Docker - Recommended)
Build and run the entire application containerized:
```bash
docker compose up --build
```
This loads `.env` values and exposes the server on `http://localhost:8000`.

---

## Testing & Verification

### Running Automated Tests
Run the test suite using `pytest`:
```bash
pytest
```

### Running Test Coverage
Measure code coverage (expected ~88%+):
```bash
pytest --cov=.
```

### Running Linter
Check code formatting and conventions with Ruff:
```bash
ruff check .
```

---

## API Specifications

### 1. Health Check
- **Method**: `GET`
- **Path**: `/health`
- **Response**: `200 OK`
```json
{
  "status": "ok"
}
```

### 2. Sort Ticket
- **Method**: `POST`
- **Path**: `/sort-ticket`
- **Request Body**:
```json
{
  "ticket_id": "T-001",
  "channel": "app",
  "locale": "en",
  "message": "I sent 5000 taka to a wrong number this morning, please help me get it back"
}
```
- **Response Body**:
```json
{
  "ticket_id": "T-001",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports sending 5000 BDT to a wrong number and requests recovery.",
  "human_review_required": true,
  "confidence": 0.85
}
```

### Manual Testing with Curl
To test the endpoint manually:
```bash
curl -X POST http://localhost:8000/sort-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "T-001",
    "channel": "app",
    "locale": "en",
    "message": "I sent 3000 to wrong number"
  }'
```

---

## Submission Details & Hackathon Checklist

### 🤖 AI / Model Usage Explanation
- **Architecture**: A hybrid Rules + AI system.
- **Primary Engine**: Uses `google/gemini-2.5-flash-lite` via the OpenRouter Chat Completions API. It uses structured JSON response generation to contextually analyze semantic inputs, locale variations (en/bn/mixed), and generate natural language summaries.
- **Fallback Engine**: If `OPENROUTER_API_KEY` is not present, or if OpenRouter is offline, the system drops back to a robust keyword-regex parser. This fallback runs locally in <1ms and guarantees that the server stays active.

### 🛡️ Safety & Guardrails Logic
A defensive post-processor intercepts and sanitizes the `agent_summary` field before returning it to the user:
1. **Credentials Scrubbing**: Any attempt to ask the customer to share their secret credentials (`PIN`, `OTP`, `password`, `card number`) is intercepted and sanitized.
2. **Unauthorized Decisions / Promises**: To prevent the API from acting as an unauthorized authority, any summary that promises direct action (such as *"We will refund your BDT..."* or *"Agent has reversed the transaction"*) is rewritten to represent the customer's request (*"Customer requests refund/recovery"*).
3. **Suspicious Third Party Redirects**: Any direction urging the customer to call or contact external, unauthorized number/agents is redirected to official support channels.

### ⚠️ Known Limitations
- **Slang and Lexicon**: Extraneous Banglish or Bengali slang words not covered by the heuristics dictionary or LLM semantic weights may result in lower routing confidence.
- **Timeout Fallback**: If the OpenRouter completions API responds in > 4.5 seconds, the circuit breaker triggers fallback mode. In this case, classification uses heuristics (meaning summaries are template-based rather than dynamically generated).

### 🔒 Secrets & Security Confirmation
- [x] No API keys, passwords, or credentials are baked into the Docker image, code files, or repository.
- [x] `.env` is gitignored (template provided in `.env.example`). Deployed environments load secrets via standard environment variables.
