"""SQLAlchemy 2.x ORM models — single source of truth for persistence.

These are the bridge between the pure domain objects and the database.
Services read these rows and rebuild domain objects (Table state, ComboMeal,
Order + OrderItem) so the design patterns keep running.
"""
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base


class StaffRow(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_code: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)


class MenuItemRow(Base):
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_code: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    base_price: Mapped[float] = mapped_column(Numeric(10, 2))
    combo_discount: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)


class ComboComponentRow(Base):
    __tablename__ = "combo_components"

    id: Mapped[int] = mapped_column(primary_key=True)
    combo_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"))
    child_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"))


class TableRow(Base):
    __tablename__ = "tables"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(unique=True)
    seats: Mapped[int] = mapped_column()
    state: Mapped[str] = mapped_column(String, default="Free")


class OrderRow(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True)
    table_number: Mapped[int] = mapped_column()
    staff_code: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column()


class OrderItemRow(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    menu_item_code: Mapped[str] = mapped_column(String)
    qty: Mapped[int] = mapped_column()
    notes: Mapped[str] = mapped_column(String, default="")


class HistoryRow(Base):
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_code: Mapped[str] = mapped_column(String)
    table_no: Mapped[int] = mapped_column()
    staff_code: Mapped[str] = mapped_column(String)
    total: Mapped[float] = mapped_column(Numeric(10, 2))
    items: Mapped[list] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    timestamp: Mapped[datetime] = mapped_column()
