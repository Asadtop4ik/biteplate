"""Concrete OBSERVERS that react to Order status changes."""

class Observer:
    def update(self, order):  # interface contract
        raise NotImplementedError

class WaiterNotifier(Observer):
    def __init__(self, sink): self._sink = sink
    def update(self, order):
        self._sink.append(f"[Waiter]   {order.order_id} is now {order.status.value}")

class ManagerDashboard(Observer):
    def __init__(self, sink): self._sink = sink
    def update(self, order):
        self._sink.append(f"[Manager]  dashboard updated: {order.order_id} -> {order.status.value}")

class KitchenDisplay(Observer):
    def __init__(self, sink): self._sink = sink
    def update(self, order):
        self._sink.append(f"[Kitchen]  display: {order.order_id} -> {order.status.value}")
