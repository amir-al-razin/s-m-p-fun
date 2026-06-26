# Project: QueueStorm Warmup: Mock Preliminary Task (sust-mock-preli)

## Tech Stack
- Python 3.12+ (FastAPI, Uvicorn)
- Pydantic for validation
- `pytest` for unit testing
- Optional: `google-generativeai` for optional LLM-based categorization

## Commands
- Start Dev Server: `uvicorn main:app --reload --port 8000`
- Run Tests: `pytest`
- Run Tests with Coverage: `pytest --cov=.`
- Run Linter: `flake8 .` or `ruff check .`

## Code Conventions
- Fast API application structured in clean modules:
  - `main.py`: Application entry point, routing, and dependency injection.
  - `schemas.py`: Pydantic models for request/response validation.
  - `classifier.py`: Classification logic (hybrid rules + optional Gemini LLM).
  - `config.py`: Environment variables and configuration.
  - `test_main.py`: Automated test cases checking standard requirements.
- Strictly adhere to standard responses:
  - Return exact HTTP status codes.
  - Use `pydantic` to ensure strict matching with requested input/output JSON schemas.
- Robust error handling: all endpoints must return structured JSON, never 500 HTML error pages.

## Boundaries
- Never commit `.env` or secrets.
- Never ask the customer to share PIN, OTP, password, or full card number in the `agent_summary` field (Safety Rule).
- `/health` response time must be within 10 seconds.
- `/sort-ticket` response time must be within 30 seconds.
- GPU dependency is not allowed.
- Follow the exact severity, case_type, and department enums.
