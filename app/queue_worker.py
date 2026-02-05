"""
Async request queue for sequential LLM processing.

qwen2.5:14b handles one request at a time efficiently.
This queue ensures requests are processed in order without overwhelming the model.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Any
from datetime import datetime
import structlog

logger = structlog.get_logger()


@dataclass
class QueuedRequest:
    """A request waiting in the queue."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    question: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    future: asyncio.Future = field(init=False, default=None)  # Set after construction in enqueue()


class RequestQueue:
    """
    Async queue for processing RAG requests sequentially.

    Ensures only one request is processed at a time while allowing
    multiple requests to be queued.
    """

    def __init__(self):
        self._queue: asyncio.Queue[QueuedRequest] = asyncio.Queue()
        self._processing = False
        self._worker_task: asyncio.Task | None = None
        self._process_fn: Callable[[str, str], Awaitable[dict]] | None = None

    def set_processor(self, process_fn: Callable[[str, str], Awaitable[dict]]):
        """Set the function to process requests."""
        self._process_fn = process_fn

    async def start(self):
        """Start the queue worker."""
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("Queue worker started")

    async def stop(self):
        """Stop the queue worker."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            logger.info("Queue worker stopped")

    async def _worker(self):
        """Worker coroutine that processes requests from the queue."""
        while True:
            try:
                # Wait for a request
                request = await self._queue.get()

                logger.info(
                    "Processing request",
                    request_id=request.id,
                    user_id=request.user_id,
                    queue_time_ms=int((datetime.now() - request.created_at).total_seconds() * 1000),
                )

                self._processing = True

                try:
                    if self._process_fn:
                        result = await self._process_fn(request.question, request.user_id)
                        request.future.set_result(result)
                    else:
                        request.future.set_exception(
                            RuntimeError("No processor function configured")
                        )
                except Exception as e:
                    logger.error(
                        "Error processing request",
                        request_id=request.id,
                        error=str(e),
                    )
                    request.future.set_exception(e)
                finally:
                    self._processing = False
                    self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Queue worker error", error=str(e))

    async def enqueue(self, question: str, user_id: str) -> dict:
        """
        Add a request to the queue and wait for the result.

        Args:
            question: The user's question
            user_id: The user's ID for conversation tracking

        Returns:
            The RAG response dict
        """
        request = QueuedRequest(
            user_id=user_id,
            question=question,
        )
        # Create future on the running loop
        request.future = asyncio.get_running_loop().create_future()

        await self._queue.put(request)

        logger.info(
            "Request queued",
            request_id=request.id,
            user_id=user_id,
            queue_size=self._queue.qsize(),
        )

        # Wait for processing to complete
        return await request.future

    @property
    def queue_size(self) -> int:
        """Current number of requests waiting."""
        return self._queue.qsize()

    @property
    def is_processing(self) -> bool:
        """Whether a request is currently being processed."""
        return self._processing


# Global queue instance
_request_queue: RequestQueue | None = None


def get_request_queue() -> RequestQueue:
    """Get the global request queue instance."""
    global _request_queue
    if _request_queue is None:
        _request_queue = RequestQueue()
    return _request_queue
