"""Order History Repository implemented as a thread-safe SINGLETON with an
ITERATOR for traversal and helper queries for analytics."""
import threading
from collections import Counter
from datetime import datetime


class _HistoryRecord:
    __slots__ = ("order_id", "table_no", "staff_id", "items", "total", "timestamp")
    def __init__(self, order_id, table_no, staff_id, items, total, timestamp):
        self.order_id = order_id
        self.table_no = table_no
        self.staff_id = staff_id
        self.items = items        # list of (name, qty)
        self.total = total
        self.timestamp = timestamp


class OrderHistoryLog:
    """One global, audit-safe log. Double-checked locking makes
    getInstance() safe even if called from multiple threads."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        if OrderHistoryLog._instance is not None:
            raise RuntimeError("Use OrderHistoryLog.get_instance() instead of constructing directly")
        self._records = []

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls.__new__(cls)
                    cls._instance._records = []
        return cls._instance

    def append(self, order):
        rec = _HistoryRecord(
            order_id=order.order_id,
            table_no=order.table_no,
            staff_id=order.staff_id,
            items=[(i.menu_item.name, i.qty) for i in order.items],
            total=order.total(),
            timestamp=getattr(order, "created_at", datetime.now()),
        )
        self._records.append(rec)

    # ITERATOR: traversal independent of internal storage
    def __iter__(self):
        return iter(tuple(self._records))

    def __len__(self):
        return len(self._records)

    # --- analytics queries (used by reporting) ---
    def in_range(self, start, end):
        return [r for r in self._records if start <= r.timestamp <= end]

    def for_table(self, table_no):
        return [r for r in self._records if r.table_no == table_no]

    def most_frequent_item(self):
        counter = Counter()
        for r in self._records:
            for name, qty in r.items:
                counter[name] += qty
        return counter.most_common(1)[0] if counter else None

    def top_items(self, n=10):
        counter = Counter()
        for r in self._records:
            for name, qty in r.items:
                counter[name] += qty
        return counter.most_common(n)

    def total_revenue(self):
        return round(sum(r.total for r in self._records), 2)

    @classmethod
    def _reset_for_tests(cls):
        cls._instance = None
