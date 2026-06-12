"""Billing service: thin orchestration over the domain BillingFacade and the
STRATEGY pricing engine, rebuilding pure-domain objects from ORM rows."""
from app.config import settings
from app.domain.billing import BillingFacade
from app.domain.orders import OrderStatus
from app.domain.pricing import (
    HappyHourPricing,
    LoyaltyCardPricing,
    StandardPricing,
)
from app.infra.repositories import MenuRepo, OrderRepo, TableRepo

STRATEGIES = {
    "standard": StandardPricing,
    "happy_hour": HappyHourPricing,
    "loyalty": LoyaltyCardPricing,
}


def build(db, order_code, strategy_name="standard", tip=0.0):
    order_row = OrderRepo(db).get(order_code)
    order = OrderRepo(db).to_domain(order_row, MenuRepo(db))
    strat = STRATEGIES.get(strategy_name, StandardPricing)()
    bill = BillingFacade(settings.TAX_RATE).build_bill(order, strategy=strat, tip=tip)
    lines = [
        {"desc": f"{li.qty} x {li.menu_item.name}", "amount": li.line_total()}
        for li in order.items
    ]
    gross = order.total()                       # full price (sum of line items)
    subtotal = bill.subtotal(order)             # after the pricing Strategy
    discount = round(gross - subtotal, 2)       # the Strategy adjustment, if any
    return {
        "order": order_row,
        "strategy_name": strategy_name,
        "strategy_label": strat.name(),
        "lines": lines,
        "gross": gross,
        "discount": discount,
        "subtotal": subtotal,
        "tax": bill.tax(order),
        "tip": tip,
        "total": bill.total(order),
        "strategies": list(STRATEGIES.keys()),
        "bill": bill,
        "order_domain": order,
    }


def split(bill, order_domain, guests):
    return bill.split(order_domain, guests)


def list_billable(db):
    """Orders that have left NEW state and therefore have a bill to view."""
    from app.infra.models import OrderRow

    return (
        db.query(OrderRow)
        .filter(OrderRow.status != OrderStatus.NEW.value)
        .order_by(OrderRow.id.desc())
        .all()
    )


def close(db, order_code):
    order_row = OrderRepo(db).get(order_code)
    repo = TableRepo(db)
    table = repo.to_domain(repo.get(order_row.table_number))
    table.advance()
    repo.save_state(order_row.table_number, table.status())
    db.commit()
    return repo.get(order_row.table_number)
