"""
FastAPI application entry point for the RAG Teams Bot.

Provides:
- /health endpoint for monitoring
- /api/messages webhook endpoint for Teams
- Startup/shutdown lifecycle management
"""

import asyncio
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from botbuilder.schema import Activity

from app import config
from app.bot_handler import get_bot, get_adapter
from app.queue_worker import get_request_queue
from app.rag_engine import get_rag_engine

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if config.LOG_LEVEL == "INFO" else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


async def process_question(question: str, user_id: str) -> dict:
    """
    Process a question through the RAG engine.
    This runs in the request queue worker.
    """
    rag_engine = get_rag_engine()
    # Run sync RAG query in thread pool
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, rag_engine.query, question, user_id)
    return result


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting RAG Teams Bot...")

    # Track RAG engine initialization status
    app.state.rag_ready = False

    # Initialize RAG engine
    try:
        logger.info("Initializing RAG engine...")
        rag_engine = get_rag_engine()
        app.state.rag_ready = True
        logger.info("RAG engine initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize RAG engine", error=str(e))
        logger.warning("Bot will start but RAG queries will fail until documents are ingested")

    # Start request queue worker
    queue = get_request_queue()
    queue.set_processor(process_question)
    await queue.start()
    logger.info("Request queue worker started")

    logger.info(
        "RAG Teams Bot started",
        host=config.HOST,
        port=config.PORT,
    )

    yield

    # Shutdown
    logger.info("Shutting down...")
    await queue.stop()
    logger.info("RAG Teams Bot stopped")


app = FastAPI(
    title="RAG Teams Bot",
    description="Company documents Q&A bot for Microsoft Teams",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint."""
    queue = get_request_queue()
    rag_ready = getattr(request.app.state, "rag_ready", False)

    status = "healthy" if rag_ready else "degraded"
    status_code = 200 if rag_ready else 503

    return JSONResponse(
        content={
            "status": status,
            "rag_ready": rag_ready,
            "queue_size": queue.queue_size,
            "is_processing": queue.is_processing,
        },
        status_code=status_code,
    )


@app.get("/")
async def root():
    """Root endpoint with basic info."""
    return {
        "name": "RAG Teams Bot",
        "status": "running",
        "docs": "/docs",
    }


@app.post("/api/messages")
async def messages(request: Request) -> Response:
    """
    Webhook endpoint for Microsoft Teams messages.

    This endpoint receives all bot messages from Teams via the Bot Framework.
    """
    # Verify content type
    if "application/json" not in request.headers.get("content-type", ""):
        raise HTTPException(status_code=415, detail="Unsupported media type")

    # Parse the incoming activity
    try:
        body = await request.json()
        activity = Activity().deserialize(body)
    except Exception as e:
        logger.error("Failed to parse activity", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid request body")

    # Get auth header
    auth_header = request.headers.get("Authorization", "")

    # Process the activity
    adapter = get_adapter()
    bot = get_bot()

    try:
        response = await adapter.process_activity(
            activity,
            auth_header,
            bot.on_turn,
        )

        if response:
            return JSONResponse(
                content=response.body,
                status_code=response.status,
            )

        return Response(status_code=200)

    except Exception as e:
        logger.error("Error processing activity", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/test")
async def test_query(request: Request):
    """
    Test endpoint for direct RAG queries (without Teams).

    Only available when LOG_LEVEL is DEBUG. Disabled in production.

    Body:
        {"question": "your question", "user_id": "test-user"}
    """
    # Only allow test endpoint in DEBUG mode
    if config.LOG_LEVEL.upper() != "DEBUG":
        raise HTTPException(status_code=404, detail="Not found")

    try:
        body = await request.json()
        question = body.get("question", "")
        user_id = body.get("user_id", "test-user")

        if not question:
            raise HTTPException(status_code=400, detail="Question is required")

        queue = get_request_queue()
        result = await queue.enqueue(question, user_id)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error processing test query", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Run the application with uvicorn."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
