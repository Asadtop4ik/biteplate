"""Table lifecycle modelled with the STATE pattern."""
from abc import ABC, abstractmethod
from .errors import require_positive_int, IllegalStateTransition


class TableState(ABC):
    @abstractmethod
    def advance(self, table): ...
    @abstractmethod
    def label(self): ...


class FreeState(TableState):
    def advance(self, table): table.set_state(OccupiedState())
    def label(self): return "Free"

class ReservedState(TableState):
    def advance(self, table): table.set_state(OccupiedState())
    def label(self): return "Reserved"

class OccupiedState(TableState):
    def advance(self, table): table.set_state(AwaitingBillState())
    def label(self): return "Occupied"

class AwaitingBillState(TableState):
    def advance(self, table): table.set_state(ClearedState())
    def label(self): return "Awaiting Bill"

class ClearedState(TableState):
    def advance(self, table): table.set_state(FreeState())
    def label(self): return "Cleared"


class Table:
    def __init__(self, number, seats):
        self._number = require_positive_int(number, "number")
        self._seats = require_positive_int(seats, "seats")
        self._state = FreeState()

    @property
    def number(self):
        return self._number

    def set_state(self, state):
        if not isinstance(state, TableState):
            raise IllegalStateTransition("state must be a TableState")
        self._state = state

    def reserve(self):
        if not isinstance(self._state, FreeState):
            raise IllegalStateTransition(f"Cannot reserve a table that is {self.status()}")
        self.set_state(ReservedState())

    def advance(self):
        self._state.advance(self)

    def status(self):
        return self._state.label()
