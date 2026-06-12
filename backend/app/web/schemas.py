"""Pydantic v2 form DTOs (optional helpers for routers).

Routers may instead read raw `Form(...)` values; these mirror the same fields
for validation/typing convenience.
"""
from pydantic import BaseModel


class LoginForm(BaseModel):
    code: str
    password: str


class StartOrderForm(BaseModel):
    table_number: int


class AddItemForm(BaseModel):
    item_code: str
    qty: int = 1
    notes: str = ""


class BillForm(BaseModel):
    strategy: str = "standard"
    tip: float = 0.0
    guests: int = 1
