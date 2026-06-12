"""Billing & POS exposed through a FACADE over pricing, tax, tip and split."""
from .errors import require_money, require_positive_int
from .pricing import PricingStrategy, StandardPricing


class Printable:
    """Simple interface (REALISATION) for anything that can be printed."""
    def print_doc(self):  # pragma: no cover - interface contract
        raise NotImplementedError


class BillLineItem:
    def __init__(self, desc, amount):
        self.desc = desc
        self.amount = require_money(amount, "amount")


class Bill(Printable):
    """CONTEXT for the pricing Strategy; composed of BillLineItems."""
    def __init__(self, tax_rate):
        self._tax_rate = require_money(tax_rate, "tax_rate")
        self._lines = []
        self._tip = 0.0
        self._strategy = StandardPricing()

    def set_strategy(self, strategy):
        if not isinstance(strategy, PricingStrategy):
            from .errors import ValidationError
            raise ValidationError("strategy must be a PricingStrategy")
        self._strategy = strategy

    def add_line(self, line):
        self._lines.append(line)

    def set_tip(self, tip):
        self._tip = require_money(tip, "tip")

    def subtotal(self, order):
        return self._strategy.calculate_total(order)

    def tax(self, order):
        return round(self.subtotal(order) * self._tax_rate, 2)

    def total(self, order):
        return round(self.subtotal(order) + self.tax(order) + self._tip, 2)

    def split(self, order, n):
        n = require_positive_int(n, "guests")
        return round(self.total(order) / n, 2)

    def print_doc(self, order):
        lines = [f"  {li.desc:<28}{li.amount:>8.2f}" for li in self._lines]
        body = "\n".join(lines)
        return (f"Strategy: {self._strategy.name()}\n{body}\n"
                f"  {'Subtotal':<28}{self.subtotal(order):>8.2f}\n"
                f"  {'Tax':<28}{self.tax(order):>8.2f}\n"
                f"  {'Tip':<28}{self._tip:>8.2f}\n"
                f"  {'TOTAL':<28}{self.total(order):>8.2f}")


class BillingFacade:
    """Single simple entry point over the complex billing subsystem."""
    def __init__(self, tax_rate):
        self._tax_rate = require_money(tax_rate, "tax_rate")

    def build_bill(self, order, strategy=None, tip=0.0):
        bill = Bill(self._tax_rate)
        if strategy is not None:
            bill.set_strategy(strategy)
        for item in order.items:
            bill.add_line(BillLineItem(f"{item.qty} x {item.menu_item.name}", item.line_total()))
        bill.set_tip(tip)
        return bill
