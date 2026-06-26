# ADR-001: Hybrid Classification Architecture (OpenRouter LLM + Local Heuristics Fallback)

## Status
Accepted

## Date
2026-06-26

## Context
We need to classify customer support messages into specific categories (`wrong_transfer`, `payment_failed`, etc.), determine urgency, and route to the correct department.
Constraints:
- Must handle English, Bengali, and mixed-locale (Banglish) inputs accurately.
- Must remain 100% online under high load without crashing (5xx).
- Must have a backup mechanism if third-party API keys are missing or rate-limited.

## Decision
Implement a hybrid routing coordinator in [classifier.py](file:///home/amir/Documents/sust-mock-preli/classifier.py):
1. If `OPENROUTER_API_KEY` is present, query `google/gemini-2.5-flash-lite` via OpenRouter Chat Completions using structured JSON response mode.
2. If the API key is missing or the request fails (due to rate limits, network issues, or timeout), fall back instantly to a regex-based keyword matching heuristic.

## Alternatives Considered

### Pure Heuristics (Keyword Rules Only)
- *Pros*: Extremely fast (<1ms), zero network dependencies, 100% free.
- *Cons*: Cannot handle complex semantic meanings, colloquial phrasing, or varied sentence structures across multilingual inputs.
- *Rejected*: Too rigid to score well on Stage 1 Hidden Test cases which require evidence reasoning beyond keyword matching.

### Pure LLM Integration
- *Pros*: High semantic understanding of local languages and nuanced tickets.
- *Cons*: Dependent on internet connections, API key availability, and rate quotas. Vulnerable to timeouts.
- *Rejected*: Failing to respond due to API key errors or network downtime would result in a zero score for the request.

## Consequences
- High resilience: The service stays online and responds even if OpenRouter experiences outages.
- Developer-friendly: Allows running tests and debugging locally without needing active API keys.
- Accuracy: Combines deterministic matching for standard patterns with semantic parsing for complex natural language statements.
