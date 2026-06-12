"""Kitchen Action Queue implemented with the COMMAND pattern, with undo."""
from abc import ABC, abstractmethod
from .orders import OrderStatus


class Command(ABC):
    @abstractmethod
    def execute(self): ...
    @abstractmethod
    def undo(self): ...
    @abstractmethod
    def label(self): ...


class PrepareOrderCommand(Command):
    """Receiver = Chef; encapsulates 'start preparing this order'."""
    def __init__(self, chef, order):
        self._chef = chef
        self._order = order
        self._prev = None

    def execute(self):
        self._prev = self._order.status
        self._chef.require("prepare")
        self._order.set_status(OrderStatus.COOKING)

    def undo(self):
        if self._prev is not None:
            self._order.set_status(self._prev)

    def label(self):
        return f"Prepare {self._order.order_id}"


class CancelOrderCommand(Command):
    def __init__(self, chef, order):
        self._chef = chef
        self._order = order
        self._prev = None

    def execute(self):
        self._prev = self._order.status
        self._order.set_status(OrderStatus.CANCELLED)

    def undo(self):
        if self._prev is not None:
            self._order.set_status(self._prev)

    def label(self):
        return f"Cancel {self._order.order_id}"


class ExpediteOrderCommand(Command):
    def __init__(self, chef, order):
        self._chef = chef
        self._order = order
        self._prev = None

    def execute(self):
        self._prev = self._order.status
        self._order.set_status(OrderStatus.READY)

    def undo(self):
        if self._prev is not None:
            self._order.set_status(self._prev)

    def label(self):
        return f"Expedite {self._order.order_id}"


class KitchenQueue:
    """INVOKER: stores a command history and supports undo of the last action."""
    def __init__(self):
        self._history = []

    def execute_command(self, command):
        if not isinstance(command, Command):
            from .errors import ValidationError
            raise ValidationError("KitchenQueue only accepts Command objects")
        command.execute()
        self._history.append(command)

    def undo_last(self):
        if not self._history:
            return None
        command = self._history.pop()
        command.undo()
        return command.label()

    def pending(self):
        return [c.label() for c in self._history]
