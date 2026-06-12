"""Order and OrderItem. Order is also the Observer SUBJECT: it notifies
registered observers (waiter, manager, kitchen display) on status change."""
from datetime import datetime
from enum import Enum
from .errors import require_positive_int, require_non_empty


class OrderStatus(Enum):
    NEW = "new"
    QUEUED = "queued"
    COOKING = "cooking"
    READY = "ready"
    SERVED = "served"
    CANCELLED = "cancelled"


class OrderItem:
    """A line on an order. COMPOSITION: cannot exist without its Order."""
    def __init__(self, menu_item, qty=1, notes=""):
        self.menu_item = menu_item
        self.qty = require_positive_int(qty, "qty")
        self.notes = str(notes or "").strip()

    def line_total(self):
        return round(self.menu_item.get_price() * self.qty, 2)

    def __repr__(self):
        extra = f" [{self.notes}]" if self.notes else ""
        return f"{self.qty} x {self.menu_item.name}{extra} = {self.line_total():.2f}"


class Order:
    """An order placed at a table. Acts as the SUBJECT in the Observer
    pattern so any number of observers can react to status changes
    without the Order knowing who they are."""

    _counter = 0

    def __init__(self, table_no, staff_id):
        Order._counter += 1
        self.order_id = f"ORD-{Order._counter:04d}"
        self.table_no = require_positive_int(table_no, "table_no")
        self.staff_id = require_non_empty(staff_id, "staff_id")
        self.created_at = datetime.now()
        self._items = []
        self._status = OrderStatus.NEW
        self._observers = []

    # --- Observer subject API ---
    def attach(self, observer):
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer):
        if observer in self._observers:
            self._observers.remove(observer)

    def _notify(self):
        for obs in list(self._observers):
            obs.update(self)

    # --- order behaviour ---
    def add_item(self, order_item):
        if self._status != OrderStatus.NEW:
            from .errors import IllegalStateTransition
            raise IllegalStateTransition("Cannot modify an order once it has left NEW state")
        self._items.append(order_item)
        return self

    @property
    def items(self):
        return tuple(self._items)

    @property
    def status(self):
        return self._status

    def set_status(self, status):
        self._status = status
        self._notify()

    def total(self):
        return round(sum(i.line_total() for i in self._items), 2)

    def __repr__(self):
        return f"<{self.order_id} table {self.table_no} {self._status.value} {self.total():.2f}>"
