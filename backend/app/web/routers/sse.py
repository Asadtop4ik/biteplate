"""Server-Sent Events bridge: Redis Pub/Sub -> HTMX kitchen cards.

The Order (Observer subject) publishes status changes to ``events.CHANNEL`` via
``RedisPublishObserver``. This endpoint subscribes to that channel and streams
each event as a pre-rendered kitchen card, swapped into the board by the HTMX
SSE extension (``sse-swap='order_update'``).
"""
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.deps import require_permission
from app.infra.db import SessionLocal
from app.infra.events import CHANNEL, render_board_html
from app.services import kitchen
from app.web.htmx import templates

router = APIRouter()


@router.get("/sse/kitchen")
async def sse_kitchen(staff=Depends(require_permission("view_kitchen"))):
    """Stream the live kitchen board. Every published order event (from the
    RedisPublishObserver) triggers a re-render of the FULL active-orders board,
    which the HTMX SSE extension swaps into #kitchen-feed (innerHTML). This keeps
    the board consistent: new orders appear, status changes update in place, and
    served/cancelled orders drop off — without duplicate cards."""
    async def gen():
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe(CHANNEL)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                with SessionLocal() as db:
                    cards = kitchen.active_orders(db)
                html = render_board_html(templates, cards)
                yield {"event": "order_update", "data": html}
        finally:
            await pubsub.unsubscribe(CHANNEL)
            await pubsub.aclose()
            await client.aclose()

    return EventSourceResponse(gen())
