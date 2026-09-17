"""Transactional SQLite inventory and durable movement history."""
import os
import sqlite3
import re
import math
import tempfile
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path

from models import CATEGORIES, SAMPLE_PRODUCTS

MAX_QUANTITY = 2**63 - 1

def default_database_path():
    """Keep mutable data outside the source tree watched by `flet run -r`."""
    root = Path(__file__).resolve().parent
    target = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share')) / 'Inventory-Management-System' / 'inventory.db'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return target
    candidates = [root / '.flet' / 'storage' / 'data' / 'inventory.db', root / 'storage' / 'inventory.db']
    if os.environ.get('FLET_APP_STORAGE_DATA'):
        candidates.insert(0, Path(os.environ['FLET_APP_STORAGE_DATA']) / 'inventory.db')
    source = next((path for path in candidates if path.exists()), None)
    if source is not None:
        # SQLite backup also includes committed journal/WAL data. Keep the
        # original database untouched; publish only a complete backup.
        fd, name = tempfile.mkstemp(suffix='.db', dir=target.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            src = sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)
            dst = sqlite3.connect(temporary)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass  # Another instance already published its backup.
        finally:
            temporary.unlink(missing_ok=True)
    return target


def validate_product(product):
    if not isinstance(product.get('name'), str) or not product['name'].strip():
        raise ValueError("กรุณากรอกชื่อสินค้า")
    if product.get('category') not in CATEGORIES:
        raise ValueError("กรุณาเลือกประเภทสินค้าที่ถูกต้อง")
    price, quantity = product.get('price'), product.get('quantity')
    if type(price) not in (int, float) or not math.isfinite(price) or price <= 0:
        raise ValueError("ราคาต้องเป็นตัวเลขที่มากกว่า 0")
    if type(quantity) is not int or not 0 <= quantity <= MAX_QUANTITY:
        raise ValueError("จำนวนคงเหลือต้องเป็นจำนวนเต็มที่ไม่ติดลบและไม่เกินขอบเขตฐานข้อมูล")
    if not math.isfinite(price * quantity):
        raise ValueError("มูลค่าสินค้าสูงเกินขอบเขตที่รองรับ")
    try:
        datetime.strptime(product.get('date', ''), '%d/%m/%Y')
    except (ValueError, TypeError):
        raise ValueError("วันที่รับเข้าไม่ถูกต้อง") from None


class InventoryStore:
    def __init__(self, path=None):
        self.actor = None
        self.path = Path(path) if path is not None else default_database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY COLLATE NOCASE, name TEXT NOT NULL, category TEXT NOT NULL, price REAL NOT NULL CHECK(price > 0), quantity INTEGER NOT NULL CHECK(quantity >= 0), date TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS movements (seq INTEGER PRIMARY KEY, product_id TEXT NOT NULL, name TEXT NOT NULL, delta INTEGER NOT NULL, balance INTEGER NOT NULL, reason TEXT NOT NULL, created TEXT NOT NULL DEFAULT (datetime('now','localtime')))")
            if 'actor' not in {row['name'] for row in db.execute("PRAGMA table_info(movements)")}:
                db.execute("ALTER TABLE movements ADD COLUMN actor TEXT")
            db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY)")
            if not db.execute("SELECT 1 FROM settings WHERE key='seeded'").fetchone():
                for p in SAMPLE_PRODUCTS:
                    db.execute("INSERT INTO products VALUES (:id,:name,:category,:price,:quantity,:date)", p)
                db.execute("INSERT INTO settings VALUES ('seeded')")
            db.execute("CREATE TABLE IF NOT EXISTS product_sequence (singleton INTEGER PRIMARY KEY CHECK(singleton=1), last_number INTEGER NOT NULL)")
            used = db.execute("SELECT id FROM products UNION SELECT product_id FROM movements").fetchall()
            highest = max((int(match[1]) for row in used if (match := re.fullmatch(r'P([0-9]+)', row[0], re.IGNORECASE))), default=0)
            db.execute("INSERT INTO product_sequence VALUES (1, ?) ON CONFLICT(singleton) DO UPDATE SET last_number=MAX(last_number, excluded.last_number)", (highest,))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def products(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM products ORDER BY id")]

    def save(self, product, original_id=None, expected=None):
        product = dict(product)
        validate_product(product)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM products WHERE id=?", (original_id,)).fetchone() if original_id else None
            if original_id and old is None:
                raise ValueError("ไม่พบสินค้านี้ กรุณาโหลดข้อมูลใหม่")
            if old:
                if expected is not None and dict(old) != expected:
                    raise ValueError("สินค้าถูกเปลี่ยนแปลงหลังเปิดฟอร์ม กรุณาปิดแล้วเปิดแก้ไขใหม่")
                if product.get('id') != old['id']:
                    raise ValueError("ไม่สามารถเปลี่ยนรหัสสินค้าหลังสร้างได้")
                db.execute("UPDATE products SET name=:name,category=:category,price=:price,quantity=:quantity,date=:date WHERE id=:original", {**product, "original": original_id})
            else:
                db.execute("UPDATE product_sequence SET last_number=last_number+1 WHERE singleton=1")
                number = db.execute("SELECT last_number FROM product_sequence WHERE singleton=1").fetchone()[0]
                product['id'] = f"P{number:03d}"
                db.execute("INSERT INTO products VALUES (:id,:name,:category,:price,:quantity,:date)", product)
            delta = product['quantity'] - (old['quantity'] if old else 0)
            if delta or not old:
                db.execute("INSERT INTO movements(product_id,name,delta,balance,reason,actor) VALUES (?,?,?,?,?,?)", (product['id'], product['name'], delta, product['quantity'], "ปรับยอดจากฟอร์ม" if old else "ยอดเริ่มต้น", self.actor))
        return product['id']

    def adjust(self, pid, delta, reason):
        if type(delta) is not int or delta == 0 or not isinstance(reason, str) or not reason.strip():
            raise ValueError("กรุณาระบุจำนวนเต็มมากกว่า 0 และเหตุผล")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            if p is None:
                raise ValueError("ไม่พบสินค้านี้")
            balance = p['quantity'] + delta
            if balance < 0:
                raise ValueError(f"เบิกเกินยอดคงเหลือ {p['quantity']} ชิ้นไม่ได้")
            validate_product({**dict(p), 'quantity': balance})
            db.execute("UPDATE products SET quantity=? WHERE id=?", (balance, pid))
            db.execute("INSERT INTO movements(product_id,name,delta,balance,reason,actor) VALUES (?,?,?,?,?,?)", (pid, p['name'], delta, balance, reason.strip(), self.actor))

    def delete(self, pid):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            if p:
                db.execute("INSERT INTO movements(product_id,name,delta,balance,reason,actor) VALUES (?,?,?,?,?,?)", (pid, p['name'], -p['quantity'], 0, "ลบสินค้า", self.actor))
                db.execute("DELETE FROM products WHERE id=?", (pid,))

    def history(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM movements ORDER BY seq DESC LIMIT 200")]
