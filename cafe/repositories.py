from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from typing import Any

from .config import PRODUCTION
from .models import Admin, Category, Customer, Ingredient, MenuItem, Order, RecipeIngredient, User


class Repository(ABC):
    def __init__(self, db):
        self.db = db

    @abstractmethod
    def get(self, identity):
        raise NotImplementedError

    @abstractmethod
    def list(self, **filters):
        raise NotImplementedError

    @abstractmethod
    def save(self, entity):
        raise NotImplementedError

    @abstractmethod
    def delete(self, identity):
        raise NotImplementedError


class UserRepository(Repository):
    def get(self, identity: int) -> User | None:
        row = self.db.execute("SELECT * FROM users WHERE id=?", (identity,)).fetchone()
        return User.from_row(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        row = self.db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return User.from_row(row) if row else None

    def list(self, **filters: Any) -> list[User]:
        if "is_admin" in filters:
            rows = self.db.execute("SELECT * FROM users WHERE is_admin=? ORDER BY id", (int(bool(filters["is_admin"])),)).fetchall()
        else:
            rows = self.db.execute("SELECT * FROM users ORDER BY id").fetchall()
        return [User.from_row(row) for row in rows]

    def save(self, entity: User) -> int:
        if not isinstance(entity, (Customer, Admin)):
            raise TypeError("Only customer and admin accounts can be saved.")
        if entity.id is None:
            if isinstance(entity, Customer):
                cur = self.db.execute(
                    "INSERT INTO users(name,email,phone,password_hash,address,addr_lat,addr_lng,pay_method,pay_account,is_admin) "
                    "VALUES(?,?,?,?,?,?,?,?,?,0)",
                    (entity.name, entity.email, entity.phone, entity.password_hash, entity.address, entity.addr_lat,
                     entity.addr_lng, entity.pay_method, entity.pay_account))
            else:
                cur = self.db.execute("INSERT INTO users(name,email,password_hash,is_admin) VALUES(?,?,?,1)",
                                      (entity.name, entity.email, entity.password_hash))
            entity.id = cur.lastrowid
            return entity.id

        if isinstance(entity, Customer):
            self.db.execute(
                "UPDATE users SET name=?,email=?,phone=?,password_hash=?,address=?,addr_lat=?,addr_lng=?,pay_method=?,pay_account=? "
                "WHERE id=? AND is_admin=0",
                (entity.name, entity.email, entity.phone, entity.password_hash, entity.address, entity.addr_lat,
                 entity.addr_lng, entity.pay_method, entity.pay_account, entity.id))
        else:
            self.db.execute("UPDATE users SET name=?,email=?,password_hash=? WHERE id=? AND is_admin=1",
                            (entity.name, entity.email, entity.password_hash, entity.id))
        return entity.id

    def delete(self, identity: int) -> None:
        self.db.execute("DELETE FROM users WHERE id=?", (identity,))

    def email_exists(self, email: str, exclude_id: int | None = None) -> bool:
        return self.db.execute("SELECT 1 FROM users WHERE email=? AND id<>?",
                               (email, exclude_id if exclude_id is not None else -1)).fetchone() is not None

    def update_profile(self, identity: int, *, name: str, email: str, phone: str, address: str,
                       addr_lat: float | None, addr_lng: float | None, pay_method: str, pay_account: str) -> bool:
        customer = self.get(identity)
        if not isinstance(customer, Customer):
            return False
        customer.name, customer.email, customer.phone = name, email, phone
        customer.address, customer.addr_lat, customer.addr_lng = address, addr_lat, addr_lng
        customer.pay_method, customer.pay_account = pay_method, pay_account
        self.save(customer)
        return True

    def set_password(self, email: str, password: str) -> bool:
        user = self.get_by_email(email)
        if not isinstance(user, Customer):
            return False
        user.set_password(password)
        self.save(user)
        return True

    def ensure_admin(self) -> None:
        if self.db.execute("SELECT 1 FROM users WHERE is_admin=1 LIMIT 1").fetchone():
            return
        email = os.environ.get("ADMIN_EMAIL", "admin@newfoundcafe.com").strip().lower()
        password = os.environ.get("ADMIN_PASSWORD", "")
        if not password:
            if PRODUCTION:
                raise SystemExit("\nThere is no admin account yet. Set ADMIN_EMAIL and ADMIN_PASSWORD, then start the app again.\n")
            password = "admin123"
        existing = self.db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            self.db.execute("UPDATE users SET is_admin=1 WHERE id=?", (existing["id"],))
        else:
            self.save(Admin(None, "Admin", email, User.hash_password(password)))
        print(f"\n  Admin account ready: {email}" +
              ("" if PRODUCTION or os.environ.get("ADMIN_PASSWORD") else " / admin123  (set ADMIN_EMAIL / ADMIN_PASSWORD to change)") + "\n")


class MenuRepository(Repository):
    _SLUG_TABLES = {"menu_items": "item", "categories": "category"}
    _NAMED_TABLES = {"ingredients", "menu_items", "categories"}

    def get(self, identity: str, lock: bool = False) -> MenuItem | None:
        row = self.db.execute(
            "SELECT m.*, c.name AS cat_name, p.version AS photo_version FROM menu_items m "
            "JOIN categories c ON c.id=m.cat_id LEFT JOIN menu_item_images p ON p.item_id=m.id "
            "WHERE m.id=?" + (" FOR UPDATE" if lock else ""),
            (identity,)).fetchone()
        if not row:
            return None
        recipes = self._recipes([identity]).get(identity, [])
        return MenuItem.from_row(row, recipes)

    def list(self, **filters: Any) -> list[MenuItem]:
        ids = filters.get("ids")
        if ids is not None and not ids:
            return []
        sql = ("SELECT m.*, c.name AS cat_name, p.version AS photo_version FROM menu_items m "
               "JOIN categories c ON c.id=m.cat_id LEFT JOIN menu_item_images p ON p.item_id=m.id")
        conditions, params = [], []
        if ids is not None:
            conditions.append(f"m.id IN ({','.join('?' * len(ids))})")
            params.extend(ids)
        if filters.get("active_only"):
            conditions.append("m.active=1")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        rows = self.db.execute(sql + " ORDER BY c.sort, m.sort, m.name", tuple(params)).fetchall()
        recipes = self._recipes([row["id"] for row in rows])
        return [MenuItem.from_row(row, recipes[row["id"]]) for row in rows]

    def save(self, entity: MenuItem) -> str:
        existing = self.db.execute("SELECT 1 FROM menu_items WHERE id=?", (entity.id,)).fetchone()
        if existing:
            self.db.execute("UPDATE menu_items SET name=?,cat_id=?,price=?,img=?,active=? WHERE id=?",
                            (entity.name, entity.cat_id, entity.price, entity.img, int(entity.active), entity.id))
        else:
            self.db.execute("INSERT INTO menu_items(id,name,cat_id,price,img,active,sort) VALUES(?,?,?,?,?,?,?)",
                            (entity.id, entity.name, entity.cat_id, entity.price, entity.img, int(entity.active), entity.sort))
        self.save_recipe(entity.id, [(recipe.ingredient_id, recipe.qty) for recipe in entity.recipe])
        return entity.id

    def delete(self, identity: str) -> None:
        self.db.execute("DELETE FROM menu_items WHERE id=?", (identity,))

    def save_recipe(self, identity: str, rows: list[tuple[int, Any]]) -> None:
        self.db.execute("DELETE FROM menu_item_ingredients WHERE item_id=?", (identity,))
        for ingredient_id, quantity in rows:
            self.db.execute("INSERT INTO menu_item_ingredients(item_id,ingredient_id,qty) VALUES(?,?,?)",
                            (identity, ingredient_id, quantity))

    def categories(self) -> list[Category]:
        rows = self.db.execute("SELECT * FROM categories ORDER BY sort, name").fetchall()
        return [Category.from_row(row) for row in rows]

    def category(self, identity: str, lock: bool = False) -> Category | None:
        row = self.db.execute("SELECT * FROM categories WHERE id=?" + (" FOR UPDATE" if lock else ""),
                              (identity,)).fetchone()
        return Category.from_row(row) if row else None

    def save_category(self, entity: Category) -> str:
        existing = self.db.execute("SELECT 1 FROM categories WHERE id=?", (entity.id,)).fetchone()
        if existing:
            self.db.execute("UPDATE categories SET name=?,group_name=?,color=?,emoji=? WHERE id=?",
                            (entity.name, entity.group, entity.color, entity.emoji, entity.id))
        else:
            self.db.execute("INSERT INTO categories(id,name,group_name,color,emoji,sort) VALUES(?,?,?,?,?,?)",
                            (entity.id, entity.name, entity.group, entity.color, entity.emoji, entity.sort))
        return entity.id

    def delete_category(self, identity: str) -> None:
        self.db.execute("DELETE FROM categories WHERE id=?", (identity,))

    def category_item_count(self, identity: str) -> int:
        return self.db.execute("SELECT COUNT(*) AS n FROM menu_items WHERE cat_id=?", (identity,)).fetchone()["n"]

    def used_in(self) -> dict[int, list[str]]:
        rows = self.db.execute(
            "SELECT r.ingredient_id, m.name FROM menu_item_ingredients r "
            "JOIN menu_items m ON m.id=r.item_id ORDER BY m.name").fetchall()
        out: dict[int, list[str]] = {}
        for row in rows:
            out.setdefault(row["ingredient_id"], []).append(row["name"])
        return out

    def ingredients(self, with_usage: bool = True) -> list[Ingredient]:
        used = self.used_in() if with_usage else {}
        rows = self.db.execute("SELECT * FROM ingredients ORDER BY name").fetchall()
        return [Ingredient.from_row(row, used.get(row["id"], [])) for row in rows]

    def ingredient(self, identity: int, lock: bool = False) -> Ingredient | None:
        row = self.db.execute("SELECT * FROM ingredients WHERE id=?" + (" FOR UPDATE" if lock else ""),
                              (identity,)).fetchone()
        return Ingredient.from_row(row, self.used_in().get(identity, [])) if row else None

    def save_ingredient(self, entity: Ingredient) -> int:
        if entity.id is None:
            cur = self.db.execute("INSERT INTO ingredients(name,unit,stock,low_at) VALUES(?,?,?,?)",
                                  (entity.name, entity.unit, entity.stock, entity.low_at))
            entity.id = cur.lastrowid
        else:
            self.db.execute("UPDATE ingredients SET name=?,unit=?,stock=?,low_at=? WHERE id=?",
                            (entity.name, entity.unit, entity.stock, entity.low_at, entity.id))
        return entity.id

    def restock(self, identity: int, amount) -> None:
        self.db.execute("UPDATE ingredients SET stock=stock+? WHERE id=?", (amount, identity))

    def delete_ingredient(self, identity: int) -> None:
        self.db.execute("DELETE FROM ingredients WHERE id=?", (identity,))

    def save_image(self, identity: str, mime: str, data: bytes, version: str) -> None:
        self.db.execute(
            "INSERT INTO menu_item_images(item_id,mime,data,version,updated_at) VALUES(?,?,?,?,UTC_TIMESTAMP()) "
            "ON DUPLICATE KEY UPDATE mime=VALUES(mime),data=VALUES(data),version=VALUES(version),updated_at=VALUES(updated_at)",
            (identity, mime, data, version))

    def delete_image(self, identity: str) -> None:
        self.db.execute("DELETE FROM menu_item_images WHERE item_id=?", (identity,))

    def image(self, identity: str):
        return self.db.execute("SELECT mime,data,version FROM menu_item_images WHERE item_id=?", (identity,)).fetchone()

    def existing_ingredient_ids(self, identities: set[int]) -> set[int]:
        if not identities:
            return set()
        rows = self.db.execute(
            f"SELECT id FROM ingredients WHERE id IN ({','.join('?' * len(identities))})",
            tuple(identities)).fetchall()
        return {row["id"] for row in rows}

    def name_exists(self, table: str, name: str, exclude_id: str | int | None = None) -> bool:
        if table not in self._NAMED_TABLES:
            raise ValueError(f"Unsupported menu table: {table}")
        return self.db.execute(
            f"SELECT 1 FROM {table} WHERE LOWER(name)=LOWER(?) AND id<>?",
            (name, exclude_id if exclude_id is not None else "")).fetchone() is not None

    def slug(self, table: str, name: str) -> str:
        if table not in self._SLUG_TABLES:
            raise ValueError(f"Unsupported slug table: {table}")
        base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:34] or self._SLUG_TABLES[table]
        slug, suffix = base, 2
        while self.db.execute(f"SELECT 1 FROM {table} WHERE id=?", (slug,)).fetchone():
            slug, suffix = f"{base}-{suffix}", suffix + 1
        return slug

    def next_sort(self, table: str) -> int:
        if table not in self._NAMED_TABLES:
            raise ValueError(f"Unsupported menu table: {table}")
        return self.db.execute(f"SELECT COALESCE(MAX(sort),0) AS s FROM {table}").fetchone()["s"] + 1

    def _recipes(self, item_ids: list[str]) -> dict[str, list[RecipeIngredient]]:
        if not item_ids:
            return {}
        rows = self.db.execute(
            f"SELECT r.item_id, r.ingredient_id, r.qty, i.name, i.unit, i.stock "
            f"FROM menu_item_ingredients r JOIN ingredients i ON i.id=r.ingredient_id "
            f"WHERE r.item_id IN ({','.join('?' * len(item_ids))}) ORDER BY i.name",
            tuple(item_ids)).fetchall()
        result: dict[str, list[RecipeIngredient]] = {}
        for row in rows:
            result.setdefault(row["item_id"], []).append(RecipeIngredient.from_row(row))
        return result


class OrderRepository(Repository):
    def get(self, identity: int, user_id: int | None = None, lock: bool = False) -> Order | None:
        sql, params = "SELECT * FROM orders WHERE id=?", [identity]
        if user_id is not None:
            sql += " AND user_id=?"
            params.append(user_id)
        row = self.db.execute(sql + (" FOR UPDATE" if lock else ""), tuple(params)).fetchone()
        return Order.from_row(row) if row else None

    def list(self, **filters: Any) -> list[Order]:
        conditions, params = [], []
        if "user_id" in filters:
            conditions.append("user_id=?")
            params.append(filters["user_id"])
        if "status" in filters:
            conditions.append("status=?")
            params.append(filters["status"])
        if filters.get("pending_payment"):
            conditions.append("pay_status='pending'")
        sql = "SELECT * FROM orders" + (" WHERE " + " AND ".join(conditions) if conditions else "") + " ORDER BY id DESC"
        limit = filters.get("limit")
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        rows = self.db.execute(sql, tuple(params)).fetchall()
        return [Order.from_row(row) for row in rows]

    def save(self, entity: Order) -> int:
        values = (entity.user_id, entity.customer_name, entity.order_type, entity.table_no, entity.payment, entity.note,
                  entity.items_json, entity.subtotal, entity.coupon, entity.discount, entity.total, entity.status,
                  entity.status_at, entity.dest_lat, entity.dest_lng, entity.cur_lat, entity.cur_lng, entity.pay_status,
                  entity.pay_ref, entity.pay_at, entity.dest_address, entity.created_at, entity.stock_json,
                  entity.stock_returned)
        if entity.id is None:
            cur = self.db.execute(
                "INSERT INTO orders(user_id,customer_name,order_type,table_no,payment,note,items_json,subtotal,coupon,discount,total,"
                "status,status_at,dest_lat,dest_lng,cur_lat,cur_lng,pay_status,pay_ref,pay_at,dest_address,created_at,stock_json,stock_returned) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
            entity.id = cur.lastrowid
        else:
            self.db.execute(
                "UPDATE orders SET user_id=?,customer_name=?,order_type=?,table_no=?,payment=?,note=?,items_json=?,subtotal=?,coupon=?,"
                "discount=?,total=?,status=?,status_at=?,dest_lat=?,dest_lng=?,cur_lat=?,cur_lng=?,pay_status=?,pay_ref=?,pay_at=?,"
                "dest_address=?,created_at=?,stock_json=?,stock_returned=? WHERE id=?",
                values + (entity.id,))
        return entity.id

    def delete(self, identity: int) -> None:
        raise ValueError("Orders are retained for history and cannot be deleted.")

    def update_location(self, identity: int, latitude: float, longitude: float) -> None:
        self.db.execute("UPDATE orders SET cur_lat=?,cur_lng=? WHERE id=?", (latitude, longitude, identity))
