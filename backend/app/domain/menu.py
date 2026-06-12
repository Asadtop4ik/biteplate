"""Menu items (Inheritance, Polymorphism, Abstraction),
ComboMeal (Composite) and MenuFactory (Factory Method)."""
from abc import ABC, abstractmethod
from .errors import require_non_empty, require_money, ValidationError


class MenuItem(ABC):
    """Abstract base for everything that can appear on an order.

    Demonstrates ENCAPSULATION: price/name are protected and exposed
    only through methods, and ABSTRACTION: subclasses must define how
    they are priced and which kitchen station prepares them.
    """

    def __init__(self, item_id, name, base_price):
        self._id = require_non_empty(item_id, "item_id")
        self._name = require_non_empty(name, "name")
        self._base_price = require_money(base_price, "base_price")

    @property
    def name(self):
        return self._name

    @property
    def id(self):
        return self._id

    @abstractmethod
    def get_price(self):
        """Return the price of this item (polymorphic)."""

    @abstractmethod
    def station(self):
        """Return the kitchen station that prepares this item."""

    def describe(self):
        return f"{self._name} ({self.station()}) - {self.get_price():.2f}"


class Starter(MenuItem):
    def get_price(self):
        return self._base_price
    def station(self):
        return "cold"


class MainCourse(MenuItem):
    def get_price(self):
        return self._base_price
    def station(self):
        return "hot"


class Dessert(MenuItem):
    def get_price(self):
        return self._base_price
    def station(self):
        return "dessert"


class Beverage(MenuItem):
    def get_price(self):
        return self._base_price
    def station(self):
        return "cold"


class ComboMeal(MenuItem):
    """COMPOSITE: a combo is treated uniformly as a MenuItem but is
    composed of several child MenuItems, with a combo discount."""

    def __init__(self, item_id, name, combo_discount=0.10):
        super().__init__(item_id, name, 0.0)
        if not 0 <= combo_discount < 1:
            raise ValidationError("combo_discount must be between 0 and 1")
        self._discount = combo_discount
        self._items = []

    def add(self, item):
        if not isinstance(item, MenuItem):
            raise ValidationError("ComboMeal can only contain MenuItem objects")
        self._items.append(item)
        return self

    def get_price(self):
        raw = sum(child.get_price() for child in self._items)
        return round(raw * (1 - self._discount), 2)

    def station(self):
        # a combo touches every station of its children
        return "+".join(sorted({c.station() for c in self._items})) or "n/a"

    @property
    def items(self):
        return tuple(self._items)


class MenuFactory:
    """FACTORY METHOD: hides concrete MenuItem construction so callers
    (and franchise branches) ask for a *kind* rather than a class."""

    _registry = {
        "starter": Starter,
        "main": MainCourse,
        "dessert": Dessert,
        "beverage": Beverage,
    }

    @classmethod
    def create(cls, kind, item_id, name, base_price):
        kind = require_non_empty(kind, "kind").lower()
        if kind not in cls._registry:
            raise ValidationError(f"Unknown menu item kind: {kind!r}")
        return cls._registry[kind](item_id, name, base_price)
