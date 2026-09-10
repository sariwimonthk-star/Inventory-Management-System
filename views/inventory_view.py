"""The interactive inventory dashboard and product form."""

from datetime import datetime
import math

import flet as ft

from models import CATEGORIES, SAMPLE_PRODUCTS, calculate_status, filter_products, inventory_summary


class InventoryView(ft.Container):
    """Single-screen inventory system backed by an in-memory list of dictionaries."""

    def __init__(self, page: ft.Page):
        self._page = page
        self.products = [product.copy() for product in SAMPLE_PRODUCTS]
        self.editing_id: str | None = None

        self.id_field = ft.TextField(label="รหัสสินค้า", width=260)
        self.name_field = ft.TextField(label="ชื่อสินค้า", width=260)
        self.category_field = ft.Dropdown(
            label="ประเภทสินค้า",
            width=260,
            options=[ft.DropdownOption(key=category, text=category) for category in CATEGORIES],
        )
        self.price_field = ft.TextField(label="ราคา (บาท)", width=260, keyboard_type=ft.KeyboardType.NUMBER)
        self.quantity_field = ft.TextField(
            label="จำนวนคงเหลือ", width=260, keyboard_type=ft.KeyboardType.NUMBER, on_change=self.update_status_preview
        )
        self.date_field = ft.TextField(label="วันที่รับเข้า", width=260, read_only=True)
        self.status_group = ft.RadioGroup(
            value="พร้อมขาย",
            disabled=True,
            content=ft.Row(
                controls=[
                    ft.Radio(value="พร้อมขาย", label="พร้อมขาย"),
                    ft.Radio(value="ใกล้หมด", label="ใกล้หมด"),
                    ft.Radio(value="หมด", label="หมด"),
                ],
                wrap=True,
            ),
        )
        self.date_picker = ft.DatePicker(
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2035, 12, 31),
            on_change=self.set_received_date,
            help_text="เลือกวันที่รับเข้า",
            confirm_text="เลือก",
            cancel_text="ยกเลิก",
        )

        self.add_button = ft.Button(
            content="เพิ่มสินค้า", icon=ft.Icons.ADD, bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE, on_click=self.add_product
        )
        self.save_button = ft.Button(
            content="บันทึกการแก้ไข", icon=ft.Icons.EDIT, bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE,
            on_click=self.save_edit, disabled=True,
        )
        self.clear_button = ft.Button(content="ล้างข้อมูล", icon=ft.Icons.FORMAT_CLEAR, on_click=self.clear_form)
        self.search_field = ft.TextField(label="ค้นหาจากรหัส ชื่อ หรือประเภท", width=360, on_submit=self.search_product)
        self.search_button = ft.Button(content="ค้นหา", icon=ft.Icons.SEARCH, bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE, on_click=self.search_product)
        self.clear_search_button = ft.Button(content="ล้างการค้นหา", icon=ft.Icons.FORMAT_CLEAR, on_click=self.clear_search)

        self.summary_values = {
            "items": ft.Text("0", size=26, color=ft.Colors.BLUE_700),
            "quantity": ft.Text("0", size=26, color=ft.Colors.GREEN_700),
            "low_stock": ft.Text("0", size=26, color=ft.Colors.ORANGE_700),
            "value": ft.Text("฿0.00", size=26, color=ft.Colors.BLUE_700),
        }
        self.table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("รหัสสินค้า")),
                ft.DataColumn(ft.Text("ชื่อสินค้า")),
                ft.DataColumn(ft.Text("ประเภท")),
                ft.DataColumn(ft.Text("ราคา"), numeric=True),
                ft.DataColumn(ft.Text("คงเหลือ"), numeric=True),
                ft.DataColumn(ft.Text("วันที่รับเข้า")),
                ft.DataColumn(ft.Text("สถานะ")),
                ft.DataColumn(ft.Text("การจัดการ")),
            ],
            rows=[],
            heading_row_color=ft.Colors.BLUE_50,
            show_bottom_border=True,
            column_spacing=24,
        )
        self.table.rows = self.make_rows(self.products)

        form_card = self.panel(
            ft.Column(
                controls=[
                    ft.Text("เพิ่ม / แก้ไขสินค้า", size=21, color=ft.Colors.BLUE_800),
                    ft.Row(
                        controls=[self.id_field, self.name_field, self.category_field], wrap=True, run_spacing=12
                    ),
                    ft.Row(
                        controls=[
                            self.price_field,
                            self.quantity_field,
                            ft.Row(controls=[self.date_field, ft.Button(content="เลือกวันที่", icon=ft.Icons.DATE_RANGE, on_click=self.open_date_picker)], vertical_alignment=ft.CrossAxisAlignment.END),
                        ],
                        wrap=True,
                        run_spacing=12,
                    ),
                    ft.Text("สถานะสินค้า (คำนวณอัตโนมัติจากจำนวนคงเหลือ)"),
                    self.status_group,
                    ft.Row(controls=[self.add_button, self.save_button, self.clear_button], wrap=True),
                ],
                spacing=14,
            )
        )

        content = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text("ระบบจัดการคลังสินค้า", size=30, color=ft.Colors.BLUE_800),
                            ft.Text("Inventory Management System", size=16, color=ft.Colors.GREY_700),
                        ],
                        spacing=3,
                    ),
                    padding=20,
                    bgcolor=ft.Colors.BLUE_50,
                    border_radius=ft.BorderRadius.all(14),
                ),
                ft.Row(
                    controls=[
                        self.summary_card("สินค้าทั้งหมด", self.summary_values["items"]),
                        self.summary_card("จำนวนสินค้าคงเหลือ", self.summary_values["quantity"]),
                        self.summary_card("สินค้าใกล้หมด", self.summary_values["low_stock"]),
                        self.summary_card("มูลค่าสินค้าในคลัง", self.summary_values["value"]),
                    ],
                    wrap=True,
                    run_spacing=12,
                ),
                form_card,
                self.panel(
                    ft.Column(
                        controls=[
                            ft.Text("ค้นหาและรายการสินค้า", size=21, color=ft.Colors.BLUE_800),
                            ft.Row(controls=[self.search_field, self.search_button, self.clear_search_button], wrap=True),
                            self.table,
                        ],
                        spacing=14,
                    )
                ),
            ],
            spacing=18,
            scroll=ft.ScrollMode.ADAPTIVE,
        )
        super().__init__(content=content, padding=24, bgcolor=ft.Colors.GREY_50, expand=True)
        self.update_summary_values()

    def panel(self, content: ft.Control) -> ft.Card:
        return ft.Card(
            content=ft.Container(content=content, padding=20, border_radius=ft.BorderRadius.all(14)),
            elevation=3,
            bgcolor=ft.Colors.WHITE,
        )

    def summary_card(self, label: str, value: ft.Text) -> ft.Card:
        return ft.Card(
            content=ft.Container(content=ft.Column(controls=[ft.Text(label), value], spacing=6), padding=18, width=230),
            elevation=2,
            bgcolor=ft.Colors.WHITE,
        )

    def make_rows(self, products: list[dict]) -> list[ft.DataRow]:
        return [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(product["id"])),
                    ft.DataCell(ft.Text(product["name"])),
                    ft.DataCell(ft.Text(product["category"])),
                    ft.DataCell(ft.Text(f"{product['price']:,.2f}")),
                    ft.DataCell(ft.Text(str(product["quantity"]))),
                    ft.DataCell(ft.Text(product["date"])),
                    ft.DataCell(self.status_badge(calculate_status(product["quantity"]))),
                    ft.DataCell(
                        ft.Row(
                            controls=[
                                ft.IconButton(icon=ft.Icons.EDIT, icon_color=ft.Colors.BLUE_700, tooltip="แก้ไข", on_click=lambda e, item=product: self.edit_product(item)),
                                ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.RED_700, tooltip="ลบ", on_click=lambda e, item=product: self.confirm_delete(item)),
                            ],
                            spacing=0,
                        )
                    ),
                ]
            )
            for product in products
        ]

    def status_badge(self, status: str) -> ft.Container:
        colors = {
            "พร้อมขาย": (ft.Colors.GREEN_100, ft.Colors.GREEN_800),
            "ใกล้หมด": (ft.Colors.ORANGE_100, ft.Colors.ORANGE_800),
            "หมด": (ft.Colors.RED_100, ft.Colors.RED_800),
        }
        background, foreground = colors[status]
        return ft.Container(
            content=ft.Text(status, color=foreground), bgcolor=background,
            padding=8, border_radius=ft.BorderRadius.all(12),
        )

    def show_message(self, message: str) -> None:
        self._page.show_dialog(ft.SnackBar(content=ft.Text(message), show_close_icon=True))

    def update_summary_values(self) -> None:
        summary = inventory_summary(self.products)
        self.summary_values["items"].value = str(summary["items"])
        self.summary_values["quantity"].value = f"{summary['quantity']:,}"
        self.summary_values["low_stock"].value = str(summary["low_stock"])
        self.summary_values["value"].value = f"฿{summary['value']:,.2f}"

    def refresh_all(self) -> None:
        self.table.rows = self.make_rows(filter_products(self.products, self.search_field.value or ""))
        self.update_summary_values()
        self._page.update()

    def update_status_preview(self, e) -> None:
        try:
            quantity = int(self.quantity_field.value or "0")
            self.status_group.value = calculate_status(max(0, quantity))
        except ValueError:
            self.status_group.value = "พร้อมขาย"
        self._page.update()

    def open_date_picker(self, e) -> None:
        self._page.show_dialog(self.date_picker)

    def set_received_date(self, e) -> None:
        if self.date_picker.value:
            self.date_field.value = self.date_picker.value.strftime("%d/%m/%Y")
            self._page.update()

    def validate_form(self) -> tuple[dict | None, str | None]:
        product_id = (self.id_field.value or "").strip()
        name = (self.name_field.value or "").strip()
        category = self.category_field.value
        price_text = (self.price_field.value or "").strip()
        quantity_text = (self.quantity_field.value or "").strip()
        date = (self.date_field.value or "").strip()
        if not product_id:
            return None, "กรุณากรอกรหัสสินค้า"
        if not name:
            return None, "กรุณากรอกชื่อสินค้า"
        if not category:
            return None, "กรุณาเลือกประเภทสินค้า"
        if not price_text:
            return None, "กรุณากรอกราคา"
        if not quantity_text:
            return None, "กรุณากรอกจำนวนคงเหลือ"
        if not date:
            return None, "กรุณาเลือกวันที่รับเข้า"
        try:
            price = float(price_text)
            if not math.isfinite(price) or price <= 0:
                raise ValueError
        except ValueError:
            return None, "ราคาต้องเป็นตัวเลขที่มากกว่า 0"
        try:
            quantity = int(quantity_text)
            if quantity < 0:
                raise ValueError
        except ValueError:
            return None, "จำนวนคงเหลือต้องเป็นจำนวนเต็มที่ไม่น้อยกว่า 0"
        return {"id": product_id, "name": name, "category": category, "price": price, "quantity": quantity, "date": date}, None

    def add_product(self, e) -> None:
        product, error = self.validate_form()
        if error:
            self.show_message(error)
            return
        if any(item["id"].casefold() == product["id"].casefold() for item in self.products):
            self.show_message("รหัสสินค้านี้มีอยู่แล้ว")
            return
        self.products.append(product)
        self.clear_form(refresh=False)
        self.refresh_all()
        self.show_message("เพิ่มสินค้าสำเร็จ")

    def edit_product(self, product: dict) -> None:
        self.editing_id = product["id"]
        self.id_field.value = product["id"]
        self.name_field.value = product["name"]
        self.category_field.value = product["category"]
        self.price_field.value = str(product["price"])
        self.quantity_field.value = str(product["quantity"])
        self.date_field.value = product["date"]
        self.status_group.value = calculate_status(product["quantity"])
        self.add_button.disabled = True
        self.save_button.disabled = False
        self._page.update()
        self.show_message("เลือกสินค้าแล้ว แก้ไขข้อมูลและกดบันทึกการแก้ไข")

    def save_edit(self, e) -> None:
        if not self.editing_id:
            self.show_message("กรุณาเลือกรายการที่ต้องการแก้ไข")
            return
        product, error = self.validate_form()
        if error:
            self.show_message(error)
            return
        duplicate = any(
            item["id"].casefold() == product["id"].casefold() and item["id"] != self.editing_id
            for item in self.products
        )
        if duplicate:
            self.show_message("รหัสสินค้านี้มีอยู่แล้ว")
            return
        for index, item in enumerate(self.products):
            if item["id"] == self.editing_id:
                self.products[index] = product
                break
        self.clear_form(refresh=False)
        self.refresh_all()
        self.show_message("แก้ไขข้อมูลสำเร็จ")

    def confirm_delete(self, product: dict) -> None:
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("ยืนยันการลบ"),
            content=ft.Text("คุณต้องการลบสินค้านี้ใช่หรือไม่?"),
            actions=[
                ft.Button(content="ยกเลิก", on_click=lambda e: self._page.pop_dialog()),
                ft.Button(content="ยืนยันการลบ", bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE, on_click=lambda e: self.delete_product(product)),
            ],
        )
        self._page.show_dialog(dialog)

    def delete_product(self, product: dict) -> None:
        self._page.pop_dialog()
        self.products = [item for item in self.products if item is not product]
        if self.editing_id == product["id"]:
            self.clear_form(refresh=False)
        self.refresh_all()
        self.show_message("ลบสินค้าสำเร็จ")

    def search_product(self, e) -> None:
        self.refresh_all()

    def clear_search(self, e) -> None:
        self.search_field.value = ""
        self.refresh_all()

    def clear_form(self, e=None, refresh: bool = True) -> None:
        self.editing_id = None
        self.id_field.value = ""
        self.name_field.value = ""
        self.category_field.value = None
        self.price_field.value = ""
        self.quantity_field.value = ""
        self.date_field.value = ""
        self.status_group.value = "พร้อมขาย"
        self.add_button.disabled = False
        self.save_button.disabled = True
        if refresh:
            self._page.update()
