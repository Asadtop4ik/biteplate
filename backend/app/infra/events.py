"""Observer -> Redis Pub/Sub bridge.

RedisPublishObserver implements the domain Observer interface so a domain
Order can notify Redis on status change; the SSE endpoint subscribes to the
channel and renders each event into an HTMX kitchen card.
"""
import json

from app.domain.notifications import Observer

CHANNEL = "orders:events"


def event_dict(order):
    return {
        "order_code": getattr(order, "code", order.order_id),
        "table_no": order.table_no,
        "status": order.status.value,
        "ts": order.created_at.isoformat(),
    }


def publish_event(redis_client, order, channel=CHANNEL):
    redis_client.publish(channel, json.dumps(event_dict(order)))


class RedisPublishObserver(Observer):
    def __init__(self, redis_client, channel=CHANNEL):
        self._redis = redis_client
        self._channel = channel

    def update(self, order):
        publish_event(self._redis, order, self._channel)


def render_event_html(templates, event):
    template = templates.get_template("partials/kitchen_card.html")
    return template.render(card=event)


def render_board_html(templates, cards):
    """Render the full active-orders board (used by the SSE stream so the live
    board always reflects current state: new orders appear, updates replace in
    place, finished orders drop off — no duplicate cards)."""
    template = templates.get_template("partials/kitchen_board.html")
    return template.render(cards=cards)
