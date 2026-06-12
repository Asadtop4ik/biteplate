"""Staff roles (Inheritance) with a simple permission model so
permission-checks are easy to extend as new roles are added."""
from abc import ABC, abstractmethod
from .errors import require_non_empty, PermissionDenied


class Staff(ABC):
    def __init__(self, staff_id, name):
        self._staff_id = require_non_empty(staff_id, "staff_id")
        self._name = require_non_empty(name, "name")

    @property
    def staff_id(self):
        return self._staff_id

    @property
    def name(self):
        return self._name

    @abstractmethod
    def permissions(self):
        """Return the set of permission strings this role holds."""

    @abstractmethod
    def role(self):
        ...

    def require(self, permission):
        if permission not in self.permissions():
            raise PermissionDenied(f"{self.role()} '{self._name}' may not '{permission}'")


class Waiter(Staff):
    def permissions(self):
        return {"take_order", "serve", "view_kitchen"}
    def role(self):
        return "Waiter"

class Chef(Staff):
    def permissions(self):
        return {"view_kitchen", "reprioritise_kitchen", "prepare"}
    def role(self):
        return "Head Chef"

class Cashier(Staff):
    def permissions(self):
        return {"view_bill", "close_bill"}
    def role(self):
        return "Cashier"

class Manager(Staff):
    def permissions(self):
        return {"take_order", "serve", "view_kitchen", "reprioritise_kitchen",
                "prepare", "view_bill", "close_bill", "run_report"}
    def role(self):
        return "Manager"
