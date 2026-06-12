"""Discount / pricing engine implemented with the STRATEGY pattern."""
from abc import ABC, abstractmethod


class PricingStrategy(ABC):
    @abstractmethod
    def calculate_total(self, order): ...
    @abstractmethod
    def name(self): ...


class StandardPricing(PricingStrategy):
    def calculate_total(self, order):
        return order.total()
    def name(self):
        return "Standard"


class HappyHourPricing(PricingStrategy):
    """20% off (e.g. Quiet Hours 3pm-5pm)."""
    RATE = 0.20
    def calculate_total(self, order):
        return round(order.total() * (1 - self.RATE), 2)
    def name(self):
        return "Happy Hour (-20%)"


class LoyaltyCardPricing(PricingStrategy):
    """10% off plus a free drink credit."""
    RATE = 0.10
    FREE_DRINK = 2.00
    def calculate_total(self, order):
        discounted = order.total() * (1 - self.RATE)
        return round(max(discounted - self.FREE_DRINK, 0), 2)
    def name(self):
        return "Loyalty Card (-10% + free drink)"
