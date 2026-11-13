from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from urllib.parse import quote

from werkzeug.security import check_password_hash, generate_password_hash

MAX_STOCK = Decimal("999999999")


@dataclass(slots=True)
class User:
    id: int | None
    name: str
    email: str
    _password_hash: str = field(repr=False)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> User:
        common = (row["id"], row["name"], row["email"], row["password_hash"])
        if row.get("is_admin"):
            return Admin(*common)
        return Customer(*common, phone=row.get("phone") or "", address=row.get("address") or "",
                        addr_lat=row.get("addr_lat"), addr_lng=row.get("addr_lng"),
                        pay_method=row.get("pay_method") or "cash", pay_account=row.get("pay_account") or "")

    @property
    def password_hash(self) -> str:
        return self._password_hash

    @staticmethod
    def hash_password(password: str) -> str:
        return generate_password_hash(password)

    def verify_password(self, password: str) -> bool:
        return check_password_hash(self._password_hash, password)

    def set_password(self, password: str) -> None:
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters.")
        self._password_hash = self.hash_password(password)

    @property
    def is_admin(self) -> bool:
        return False


@dataclass(slots=True)
class Customer(User):
    phone: str = ""
    address: str = ""
    addr_lat: float | None = None
    addr_lng: float | None = None
    pay_method: str = "cash"
    pay_account: str = ""


@dataclass(slots=True)
class Admin(User):
    @property
    def is_admin(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class Category:
    id: str
    name: str
    group: str
    color: str
    emoji: str
    sort: int

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Category:
        return cls(row["id"], row["name"], row["group_name"], row["color"], row["emoji"], row["sort"])

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "group": self.group, "color": self.color, "emoji": self.emoji, "sort": self.sort}


@dataclass(slots=True)
class Ingredient:
    id: int | None
    name: str
    unit: str
    _stock: Decimal = field(repr=False)
    low_at: Decimal
    used_in: list[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: Mapping[str, Any], used_in: list[str] | None = None) -> Ingredient:
        return cls(row["id"], row["name"], row["unit"], Decimal(str(row["stock"])), Decimal(str(row["low_at"])), used_in or [])

    @property
    def stock(self) -> Decimal:
        return self._stock

    def set_stock(self, value: Decimal | int | float | str) -> None:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError("In stock must be a number.") from None
        if not amount.is_finite() or amount < 0 or amount > MAX_STOCK:
            raise ValueError("In stock must be between 0 and 999999999.")
        self._stock = amount

    def restock(self, amount: Decimal | int | float | str) -> None:
        try:
            quantity = Decimal(str(amount))
        except (InvalidOperation, ValueError):
            raise ValueError("Amount must be a number.") from None
        if not quantity.is_finite() or quantity <= 0:
            raise ValueError("Amount must be greater than 0.")
        self.set_stock(self._stock + quantity)

    def to_dict(self, include_usage: bool = True) -> dict[str, Any]:
        data = {"id": self.id, "name": self.name, "unit": self.unit, "stock": float(self.stock), "low_at": float(self.low_at)}
        if include_usage:
            data["used_in"] = self.used_in
        return data


@dataclass(frozen=True, slots=True)
class RecipeIngredient:
    ingredient_id: int
    name: str
    unit: str
    qty: Decimal
    stock: Decimal

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> RecipeIngredient:
        return cls(row["ingredient_id"], row["name"], row["unit"], Decimal(str(row["qty"])), Decimal(str(row["stock"])))

    def to_dict(self) -> dict[str, Any]:
        return {"ingredient_id": self.ingredient_id, "name": self.name, "unit": self.unit, "qty": float(self.qty)}


@dataclass(slots=True)
class MenuItem:
    id: str
    name: str
    cat_id: str
    cat_name: str
    price: Decimal
    active: bool
    img: str
    sort: int
    recipe: list[RecipeIngredient] = field(default_factory=list)
    photo_version: str | None = None

    @classmethod
    def from_row(cls, row: Mapping[str, Any], recipe: list[RecipeIngredient] | None = None) -> MenuItem:
        return cls(row["id"], row["name"], row["cat_id"], row.get("cat_name") or "", Decimal(str(row["price"])),
                   bool(row["active"]), row.get("img") or "", row.get("sort", 0), recipe or [], row.get("photo_version"))

    def servings(self) -> int:
        return min((int(part.stock // part.qty) for part in self.recipe), default=0)

    def photo_url(self) -> str:
        if self.photo_version:
            return f"/media/items/{quote(self.id)}.webp?v={self.photo_version}"
        return self.img

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "cat_id": self.cat_id, "price": float(self.price), "active": self.active,
                "img": self.photo_url(), "img_url": self.img, "has_photo": bool(self.photo_version),
                "recipe": [part.to_dict() for part in self.recipe]}

    def to_record(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "cat_id": self.cat_id, "cat_name": self.cat_name, "price": self.price,
                "active": self.active, "img": self.img, "sort": self.sort, "photo_version": self.photo_version,
                "recipe": [{"ingredient_id": part.ingredient_id, "name": part.name, "unit": part.unit,
                            "qty": part.qty, "stock": part.stock} for part in self.recipe]}

    def to_customer_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "price": float(self.price), "img": self.photo_url(), "cat": self.cat_name,
                "sold_out": self.servings() < 1}


@dataclass(slots=True)
class Order:
    id: int | None
    order_type: str
    _status: str
    _pay_status: str
    stock_json: str | None = None
    stock_returned: int = 0
    user_id: int | None = None
    customer_name: str = ""
    table_no: str | None = None
    payment: str = "cash"
    note: str = ""
    items_json: str = "[]"
    subtotal: Decimal | float = Decimal("0")
    coupon: str = ""
    discount: Decimal | float = Decimal("0")
    total: Decimal | float = Decimal("0")
    status_at: str = ""
    dest_lat: float | None = None
    dest_lng: float | None = None
    cur_lat: float | None = None
    cur_lng: float | None = None
    pay_ref: str | None = None
    pay_at: str | None = None
    dest_address: str | None = None
    created_at: str = ""

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Order:
        return cls(
            id=row.get("id"), order_type=row["order_type"], _status=row["status"],
            _pay_status=row.get("pay_status") or "unpaid", stock_json=row.get("stock_json"),
            stock_returned=row.get("stock_returned") or 0, user_id=row.get("user_id"),
            customer_name=row.get("customer_name") or "", table_no=row.get("table_no"),
            payment=row.get("payment") or "cash", note=row.get("note") or "", items_json=row.get("items_json") or "[]",
            subtotal=row.get("subtotal") or 0, coupon=row.get("coupon") or "", discount=row.get("discount") or 0,
            total=row.get("total") or 0, status_at=row.get("status_at") or "", dest_lat=row.get("dest_lat"),
            dest_lng=row.get("dest_lng"), cur_lat=row.get("cur_lat"), cur_lng=row.get("cur_lng"),
            pay_ref=row.get("pay_ref"), pay_at=row.get("pay_at"), dest_address=row.get("dest_address"),
            created_at=row.get("created_at") or "")

    @property
    def status(self) -> str:
        return self._status

    @property
    def pay_status(self) -> str:
        return self._pay_status

    @staticmethod
    def stages_for(order_type: str) -> list[str]:
        steps = ["Received", "Preparing", "Ready"]
        return steps + (["Out for delivery", "Delivered"] if order_type == "delivery" else ["Completed"])

    def set_status(self, status: str) -> None:
        if status not in self.stages_for(self.order_type) + ["Cancelled"]:
            raise ValueError("Invalid status")
        self._status = status

    def set_payment_status(self, status: str) -> None:
        if status not in ("paid", "rejected"):
            raise ValueError("Invalid payment status")
        self._pay_status = status

    def to_record(self) -> dict[str, Any]:
        return {"id": self.id, "user_id": self.user_id, "customer_name": self.customer_name, "order_type": self.order_type,
                "table_no": self.table_no, "payment": self.payment, "note": self.note, "items_json": self.items_json,
                "subtotal": self.subtotal, "coupon": self.coupon, "discount": self.discount, "total": self.total,
                "status": self.status, "status_at": self.status_at, "dest_lat": self.dest_lat, "dest_lng": self.dest_lng,
                "cur_lat": self.cur_lat, "cur_lng": self.cur_lng, "pay_status": self.pay_status, "pay_ref": self.pay_ref,
                "pay_at": self.pay_at, "dest_address": self.dest_address, "created_at": self.created_at,
                "stock_json": self.stock_json, "stock_returned": self.stock_returned}
