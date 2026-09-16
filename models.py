"""In-memory inventory data and business rules (no Flet dependency)."""

CATEGORIES = [
    "อุปกรณ์คอมพิวเตอร์",
    "อุปกรณ์เสริม",
    "เครื่องใช้ไฟฟ้า",
    "เครื่องเขียน",
    "อื่น ๆ",
]

SAMPLE_PRODUCTS = [
    {"id": "P001", "name": "Mouse", "category": "อุปกรณ์คอมพิวเตอร์", "price": 250.0, "quantity": 20, "date": "08/08/2026"},
    {"id": "P002", "name": "Keyboard", "category": "อุปกรณ์คอมพิวเตอร์", "price": 590.0, "quantity": 8, "date": "08/08/2026"},
    {"id": "P003", "name": "USB Cable", "category": "อุปกรณ์เสริม", "price": 120.0, "quantity": 0, "date": "08/08/2026"},
    {"id": "P004", "name": "Powerbank", "category": "อุปกรณ์เสริม", "price": 490.0, "quantity": 25, "date": "09/08/2026"},
    {"id": "P005", "name": "TV", "category": "อุปกรณ์ไฟฟ้า", "price": 5990.0, "quantity": 20, "date": "09/08/2026"},
]


def calculate_status(quantity: int) -> str:
    """Return the stock status calculated from current quantity."""
    if quantity == 0:
        return "หมด"
    if quantity < 10:
        return "ใกล้หมด"
    return "พร้อมขาย"


def inventory_summary(products: list[dict]) -> dict[str, float | int]:
    """Create the four dashboard values from products."""
    return {
        "items": len(products),
        "quantity": sum(product["quantity"] for product in products),
        "low_stock": sum(0 < product["quantity"] < 10 for product in products),
        "value": sum(product["price"] * product["quantity"] for product in products),
    }


def filter_products(products: list[dict], keyword: str) -> list[dict]:
    """Search by product id, name, or category."""
    term = keyword.strip().casefold()
    if not term:
        return products
    return [
        product for product in products
        if term in product["id"].casefold()
        or term in product["name"].casefold()
        or term in product["category"].casefold()
    ]
