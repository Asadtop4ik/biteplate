"""Idempotent seed data: staff, menu (incl. combo), tables.

Run with: python -m app.infra.seed
"""
from app.infra.db import SessionLocal
from app.infra.models import (
    ComboComponentRow,
    MenuItemRow,
    StaffRow,
    TableRow,
)
from app.services._security import hash_password

STAFF = [
    ("W01", "Aziz", "waiter"),
    ("C01", "Bek", "chef"),
    ("K01", "Lola", "cashier"),
    ("M01", "Sardor", "manager"),
]

MENU = [
    ("M10", "BBQ Burger", "main", 8.50, None),
    ("S10", "Garden Salad", "starter", 4.00, None),
    ("B10", "Cola", "beverage", 2.00, None),
    ("D10", "Cheesecake", "dessert", 5.00, None),
    ("CB1", "Lunch Combo", "combo", 0.00, 0.10),
]

COMBO_COMPONENTS = [("CB1", "M10"), ("CB1", "B10")]


def seed(db):
    for code, name, role in STAFF:
        if db.query(StaffRow).filter_by(staff_code=code).first():
            continue
        db.add(StaffRow(
            staff_code=code,
            name=name,
            role=role,
            password_hash=hash_password(role),
        ))

    for item_code, name, kind, base_price, combo_discount in MENU:
        if db.query(MenuItemRow).filter_by(item_code=item_code).first():
            continue
        db.add(MenuItemRow(
            item_code=item_code,
            name=name,
            kind=kind,
            base_price=base_price,
            combo_discount=combo_discount,
        ))
    db.flush()

    for combo_code, child_code in COMBO_COMPONENTS:
        combo = db.query(MenuItemRow).filter_by(item_code=combo_code).first()
        child = db.query(MenuItemRow).filter_by(item_code=child_code).first()
        exists = db.query(ComboComponentRow).filter_by(
            combo_id=combo.id, child_id=child.id
        ).first()
        if exists:
            continue
        db.add(ComboComponentRow(combo_id=combo.id, child_id=child.id))

    for number in range(1, 9):
        if db.query(TableRow).filter_by(number=number).first():
            continue
        seats = 2 if number % 2 == 1 else 4
        db.add(TableRow(number=number, seats=seats, state="Free"))


def main():
    with SessionLocal() as db:
        seed(db)
        db.commit()


if __name__ == "__main__":
    main()
