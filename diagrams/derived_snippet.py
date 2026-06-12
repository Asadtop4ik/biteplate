# Snippet provided for reverse-engineering (Task 2d).
# NOTE: replace with the tutor's Week-2 snippet when issued.
from abc import ABC, abstractmethod

class TableState(ABC):
    @abstractmethod
    def next(self, table: "Table") -> None: ...
    @abstractmethod
    def label(self) -> str: ...

class FreeState(TableState):
    def next(self, table): table.set_state(OccupiedState())
    def label(self): return "Free"

class OccupiedState(TableState):
    def next(self, table): table.set_state(AwaitingBillState())
    def label(self): return "Occupied"

class AwaitingBillState(TableState):
    def next(self, table): table.set_state(FreeState())
    def label(self): return "Awaiting Bill"

class Table:
    def __init__(self, number: int):
        self._number = number
        self._state: TableState = FreeState()
    def set_state(self, state: TableState) -> None:
        self._state = state
    def advance(self) -> None:
        self._state.next(self)
    def status(self) -> str:
        return self._state.label()
