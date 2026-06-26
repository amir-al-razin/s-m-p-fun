import time
import json
import logging
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from schemas import TicketRequest, TicketResponse
from classifier import classify_ticket
from config import PORT, HOST
from cache import global_cache

# Configure local logger for observability
logger = logging.getLogger("api_observability")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="QueueStorm Warmup API",
    description="Mock Preliminary Task - Support Ticket Classification and Routing",
    version="1.0.0"
)

@app.middleware("http")
async def log_transaction_performance(request: Request, call_next):
    """
    Structured logging middleware that tracks route performance, latency,
    and returns processing headers.
    """
    start_time = time.time()
    response = await call_next(request)
    
    # Audit trail for core endpoints
    if request.url.path in ["/sort-ticket", "/health"]:
        duration_ms = (time.time() - start_time) * 1000
        logger.info(json.dumps({
            "event": "triage_api_transaction",
            "path": request.url.path,
            "method": request.method,
            "latency_ms": round(duration_ms, 2),
            "status_code": response.status_code
        }))
        
    return response

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """
    Serves the premium diagnostic testing web portal from the root path.
    """
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

# Custom error handler for request validation validation
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Unprocessable Entity",
            "message": "Input request validation failed",
            "details": exc.errors()
        }
    )

# Custom error handler for general/server exceptions
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled server exception occurred", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred during processing"
        }
    )

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint.
    Must respond within 10 seconds.
    Includes active cache execution statistics.
    """
    return {
        "status": "ok",
        "cache_stats": global_cache.get_stats()
    }

@app.post("/sort-ticket", response_model=TicketResponse, status_code=status.HTTP_200_OK)
async def sort_ticket(request: TicketRequest):
    """
    Ticket classification and routing endpoint.
    Must respond within 30 seconds.
    """
    response = classify_ticket(request)
    return response

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
