"""Repository layer: the Singleton OrderHistoryLog becomes a
SqlAlchemyHistoryRepository, and ORM rows are rebuilt into pure domain
objects (Factory/Composite for menu, State for tables, Observer subject
for orders) so the design patterns keep running on top of Postgres."""
from collections import Counter
from datetime import datetime

from app.domain.menu import ComboMeal, MenuFactory
from app.domain.orders import Order, OrderItem, OrderStatus
from app.domain.tables import (
    AwaitingBillState,
    ClearedState,
    FreeState,
    OccupiedState,
    ReservedState,
    Table,
)
from app.infra.models import (
    ComboComponentRow,
    HistoryRow,
    MenuItemRow,
    OrderItemRow,
    OrderRow,
    StaffRow,
    TableRow,
)
from app.services._security import verify_password

_STATE_BY_LABEL = {
    "Free": FreeState,
    "Reserved": ReservedState,
    "Occupied": OccupiedState,
    "Awaiting Bill": AwaitingBillState,
    "Cleared": ClearedState,
}


class StaffRepo:
    def __init__(self, db):
        self._db = db

    def get_by_code(self, code):
        return self._db.query(StaffRow).filter_by(staff_code=code).first()

    def list_all(self):
        return self._db.query(StaffRow).order_by(StaffRow.id).all()

    def authenticate(self, code, password):
        row = self.get_by_code(code)
        if row is None:
            return None
        if not verify_password(password, row.password_hash):
            return None
        return row


class MenuRepo:
    def __init__(self, db):
        self._db = db

    def list_items(self):
        return self._db.query(MenuItemRow).order_by(MenuItemRow.id).all()

    def get(self, item_code):
        return self._db.query(MenuItemRow).filter_by(item_code=item_code).first()

    def build_domain_item(self, row):
        if row.kind == "combo":
            combo = ComboMeal(row.item_code, row.name, float(row.combo_discount))
            components = (
                self._db.query(ComboComponentRow)
                .filter_by(combo_id=row.id)
                .order_by(ComboComponentRow.id)
                .all()
            )
            for comp in components:
                child = self._db.query(MenuItemRow).filter_by(id=comp.child_id).first()
                combo.add(self.build_domain_item(child))
            return combo
        return MenuFactory.create(row.kind, row.item_code, row.name, float(row.base_price))


class TableRepo:
    def __init__(self, db):
        self._db = db

    def list_all(self):
        return self._db.query(TableRow).order_by(TableRow.number).all()

    def get(self, number):
        return self._db.query(TableRow).filter_by(number=number).first()

    def save_state(self, number, label):
        row = self.get(number)
        row.state = label
        self._db.flush()

    def to_domain(self, row):
        table = Table(row.number, row.seats)
        state_cls = _STATE_BY_LABEL[row.state]
        table.set_state(state_cls())
        return table


class OrderRepo:
    def __init__(self, db):
        self._db = db

    def next_code(self):
        max_id = self._db.query(OrderRow.id).order_by(OrderRow.id.desc()).first()
        nxt = (max_id[0] if max_id else 0) + 1
        return f"ORD-{nxt:04d}"

    def create(self, table_number, staff_code):
        row = OrderRow(
            code=self.next_code(),
            table_number=table_number,
            staff_code=staff_code,
            status=OrderStatus.NEW.value,
            created_at=datetime.now(),
        )
        self._db.add(row)
        self._db.flush()
        return row

    def add_item(self, order_row, item_code, qty, notes):
        row = OrderItemRow(
            order_id=order_row.id,
            menu_item_code=item_code,
            qty=qty,
            notes=notes,
        )
        self._db.add(row)
        self._db.flush()
        return row

    def get(self, code):
        return self._db.query(OrderRow).filter_by(code=code).first()

    def set_status(self, code, status_value):
        row = self.get(code)
        row.status = status_value
        self._db.flush()
        return row

    def items_of(self, order_row):
        return (
            self._db.query(OrderItemRow)
            .filter_by(order_id=order_row.id)
            .order_by(OrderItemRow.id)
            .all()
        )

    def to_domain(self, order_row, menu_repo, observers=None):
        order = Order(order_row.table_number, order_row.staff_code)
        for obs in observers or []:
            order.attach(obs)
        for item_row in self.items_of(order_row):
            menu_row = menu_repo.get(item_row.menu_item_code)
            order.add_item(
                OrderItem(
                    menu_repo.build_domain_item(menu_row),
                    item_row.qty,
                    item_row.notes,
                )
            )
        order._status = OrderStatus(order_row.status)
        order.code = order_row.code  # persistence code, used by events/history
        return order


class _HistoryRecord:
    """Lightweight read record mirroring the domain Singleton's record:
    items is a list of (name, qty) tuples."""
    __slots__ = ("order_id", "table_no", "total", "items", "timestamp")

    def __init__(self, row):
        self.order_id = row.order_code
        self.table_no = row.table_no
        self.total = float(row.total)
        self.items = [tuple(pair) for pair in row.items]
        self.timestamp = row.timestamp


class SqlAlchemyHistoryRepository:
    """Postgres-backed implementation of the OrderHistoryLog interface."""

    def __init__(self, db):
        self._db = db

    def append(self, order):
        order_code = getattr(order, "code", None) or order.order_id
        row = HistoryRow(
            order_code=order_code,
            table_no=order.table_no,
            staff_code=order.staff_id,
            total=order.total(),
            items=[[i.menu_item.name, i.qty] for i in order.items],
            timestamp=getattr(order, "created_at", datetime.now()),
        )
        self._db.add(row)
        self._db.commit()

    def _rows(self):
        return self._db.query(HistoryRow).order_by(HistoryRow.id).all()

    def __iter__(self):
        return iter([_HistoryRecord(row) for row in self._rows()])

    def __len__(self):
        return self._db.query(HistoryRow).count()

    def in_range(self, start, end):
        return [r for r in self if start <= r.timestamp <= end]

    def for_table(self, table_no):
        return [r for r in self if r.table_no == table_no]

    def most_frequent_item(self):
        counter = Counter()
        for r in self:
            for name, qty in r.items:
                counter[name] += qty
        return counter.most_common(1)[0] if counter else None

    def top_items(self, n=10):
        counter = Counter()
        for r in self:
            for name, qty in r.items:
                counter[name] += qty
        return counter.most_common(n)

    def total_revenue(self):
        return round(sum(r.total for r in self), 2)
