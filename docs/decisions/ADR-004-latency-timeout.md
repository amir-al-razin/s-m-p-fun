# ADR-004: Fast-Circuit Timeout & Fallback (4.5-Second Threshold)

## Status
Accepted

## Date
2026-06-26

## Context
The preliminary rubric grants *full latency credit* only at `p95 <= 5 seconds`.
OpenRouter requests occasionally experience network congestion, queuing delays, or rate limits that can push response times up to 10–30 seconds.
If our endpoint consistently takes > 5 seconds, we lose valuable latency performance points.

## Decision
Configure a strict timeout threshold of **4.5 seconds** on the `httpx.Client()` inside [classifier.py](file:///home/amir/Documents/sust-mock-preli/classifier.py#L214).
- If the OpenRouter completion does not return within 4.5 seconds, the request raises a timeout exception.
- The coordinator intercepts this exception and immediately triggers the heuristics fallback, returning a result in < 5ms.
- This guarantees that the final API response is delivered to the client in under 5.0 seconds.

## Alternatives Considered

### Standard 30s HTTP Timeout
- *Pros*: Gives the model maximum time to complete processing.
- *Cons*: Breaches the p95 latency rubric, resulting in reduced performance points.
- *Rejected*: Sub-optimal for competitive scoring.

## Consequences
- Guaranteed sub-5s response latency for all requests under all circumstances (network degradation, rate limit, etc.).
- Keeps the system responsive and resilient under the automated judge's bulk grading harness.
