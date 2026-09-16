"""Polished inventory dashboard with CRUD and stock alerts."""
from datetime import datetime
import math
import sqlite3
from storage import InventoryStore, validate_product
from views.inventory_table import InventoryTable
import flet as ft
from models import CATEGORIES, calculate_status, filter_products, inventory_summary

APP_HEADING = "Inventory-Management-System"
APP_TAGLINE = "ระบบจัดการคลังสินค้า"


class InventoryView(ft.Container):
    NAVY, INDIGO, SURFACE = "#102A43", "#334EAC", "#F6F8FC"

    def __init__(self, page: ft.Page):
        self.editing_snapshot = None
        self.store = InventoryStore()
        self._page, self.products, self.editing_id = page, self.store.products(), None
        self.id_field = self.field("รหัสสินค้า (อัตโนมัติ)", "สร้างเมื่อบันทึกสำเร็จ", read_only=True)
        self.name_field = self.field("ชื่อสินค้า", "ระบุชื่อที่ค้นหาได้ง่าย")
        self.category_field = ft.Dropdown(label="ประเภทสินค้า", hint_text="เลือกประเภท", width=180, options=[ft.DropdownOption(key=x, text=x) for x in CATEGORIES])
        self.price_field = self.field("ราคาต่อหน่วย (บาท)", "0.00", keyboard_type=ft.KeyboardType.NUMBER)
        self.quantity_field = self.field("จำนวนคงเหลือ", "0", keyboard_type=ft.KeyboardType.NUMBER, on_change=self.update_status_preview)
        self.date_field = ft.TextField(label="วันที่รับเข้า", hint_text="เลือกวันที่", width=180, read_only=True)
        self.status_group = ft.RadioGroup(value="พร้อมขาย", disabled=True, content=ft.Row(controls=[ft.Radio(value="พร้อมขาย", label="พร้อมขาย"), ft.Radio(value="ใกล้หมด", label="ใกล้หมด"), ft.Radio(value="หมด", label="หมด")], wrap=True, spacing=12))
        self.date_picker = ft.DatePicker(first_date=datetime(2020, 1, 1), last_date=datetime(2035, 12, 31), on_change=self.set_received_date, help_text="เลือกวันที่รับสินค้าเข้าคลัง", confirm_text="เลือก", cancel_text="ยกเลิก")
        self.add_button = ft.Button(content="เพิ่มสินค้าเข้าคลัง", icon=ft.Icons.ADD, bgcolor=self.INDIGO, color=ft.Colors.WHITE, on_click=self.add_product)
        self.save_button = ft.Button(content="บันทึกการแก้ไข", icon=ft.Icons.CHECK, bgcolor="#087F5B", color=ft.Colors.WHITE, on_click=self.save_edit, disabled=True)
        self.clear_button = ft.Button(content="ล้างฟอร์ม", icon=ft.Icons.REFRESH, on_click=self.clear_form)
        self.search_field = ft.TextField(label="ค้นหาสินค้า", hint_text="รหัสสินค้า, ชื่อ หรือประเภท", width=360, prefix_icon=ft.Icons.SEARCH, on_submit=self.search_product)
        self.search_button = ft.Button(content="ค้นหา", icon=ft.Icons.SEARCH, bgcolor=self.INDIGO, color=ft.Colors.WHITE, on_click=self.search_product)
        self.clear_search_button = ft.Button(content="แสดงทั้งหมด", icon=ft.Icons.FILTER_ALT_OFF, on_click=self.clear_search)
        self.category_filter = ft.Dropdown(label="หมวดหมู่", value="ทั้งหมด", width=210, options=[ft.DropdownOption(x) for x in ["ทั้งหมด", *CATEGORIES]], on_select=self.search_product)
        self.status_filter = ft.Dropdown(label="สถานะ", value="ทั้งหมด", width=180, options=[ft.DropdownOption(x) for x in ["ทั้งหมด", "พร้อมขาย", "ใกล้หมด", "หมด", "ต้องเติมสต็อก"]], on_select=self.search_product)
        self.result_count = ft.Text(f"พบ {len(self.products)} จาก {len(self.products)} รายการ")
        self.alert_count = ft.Text()
        self.summary_values = {"items": self.metric("#102A43"), "quantity": self.metric("#087F5B"), "low_stock": self.metric("#C05621"), "value": self.metric("#6D28D9")}
        self.stock_breakdown = ft.Text(size=12, color="#8A4B12")
        self.alert_list = ft.Column(spacing=8)
        self.table = InventoryTable()
        self.table.rows = self.make_rows(self.products)
        form = self.panel(ft.Column(controls=[self.heading(ft.Icons.EDIT_NOTE, "ข้อมูลสินค้า", "เพิ่มหรือปรับข้อมูลสินค้าในคลัง"), ft.Divider(height=1), ft.Text("ข้อมูลสินค้า", weight=ft.FontWeight.W_600, color=self.NAVY), ft.Row(controls=[self.id_field, self.name_field, self.category_field], wrap=True, run_spacing=12), ft.Row(controls=[self.price_field, self.quantity_field, ft.Row(controls=[self.date_field, ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, icon_color=self.INDIGO, tooltip="เลือกวันที่รับเข้า", on_click=self.open_date_picker)], vertical_alignment=ft.CrossAxisAlignment.END, spacing=0)], wrap=True, run_spacing=12), ft.Container(content=ft.Column(controls=[ft.Text("สถานะสินค้า", weight=ft.FontWeight.W_600, color=self.NAVY), ft.Text("คำนวณจากจำนวนคงเหลือโดยอัตโนมัติ", size=12, color=ft.Colors.GREY_700), self.status_group], spacing=4), padding=14, bgcolor="#F7FAFC", border_radius=10), ft.Row(controls=[self.add_button, self.save_button, self.clear_button], wrap=True, spacing=10)], spacing=14, scroll=ft.ScrollMode.AUTO, height=460), width=660)
        self.form_panel = form
        self.form_dialog = None
        alert_panel = ft.Container(content=ft.Column(controls=[self.heading(ft.Icons.NOTIFICATIONS_ACTIVE, "แจ้งเตือนสต็อก", "รายการที่ต้องเติมสินค้า"), ft.Divider(height=1), self.alert_count, self.alert_list, ft.Button(content="ดูรายการที่ต้องเติมทั้งหมด", on_click=lambda e: self.filter_status("ต้องเติมสต็อก")), ft.Container(content=ft.Text("แจ้งเตือนเมื่อคงเหลือน้อยกว่า 10 ชิ้น", size=12, color=ft.Colors.GREY_700), padding=10, bgcolor="#EEF2FF", border_radius=8)], spacing=10), col={"xs": 12, "xl": 3}, padding=14, bgcolor="#FAFBFD", border_radius=12)
        catalogue_header = ft.Row(controls=[ft.Container(content=self.heading(ft.Icons.TABLE_ROWS, "รายการสินค้า", "ค้นหา ตรวจสอบ และจัดการรายการทั้งหมด"), expand=True), ft.Button(content="เพิ่มสินค้า", icon=ft.Icons.ADD, bgcolor=self.INDIGO, color=ft.Colors.WHITE, on_click=self.new_product)], vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.table.width = self.table_width(page.width)
        self.table_area = ft.Row(controls=[self.table], scroll=ft.ScrollMode.ADAPTIVE)
        self.search_field.width = 280
        self.category_filter.width = 180
        self.status_filter.width = 160
        toolbar = ft.Row(controls=[self.search_field, self.category_filter, self.status_filter, self.search_button, self.clear_search_button], wrap=True, run_spacing=10)
        catalogue = self.panel(ft.ResponsiveRow(controls=[ft.Column(controls=[catalogue_header, toolbar, ft.Row(controls=[self.result_count, ft.Button(content="ประวัติสต็อก", icon=ft.Icons.HISTORY, on_click=self.show_history)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), self.table_area], spacing=12, col={"xs": 12, "xl": 9}), alert_panel], spacing=20, run_spacing=20))
        content = ft.Column(controls=[self.hero(), ft.Text("ภาพรวมคลังสินค้า", size=16, weight=ft.FontWeight.W_600, color=self.NAVY), ft.ResponsiveRow(controls=[self.summary_card("สินค้าในระบบ", self.summary_values["items"], ft.Icons.INVENTORY_2, "#E8EEFF", self.INDIGO), self.summary_card("จำนวนคงเหลือ", self.summary_values["quantity"], ft.Icons.STACKED_BAR_CHART, "#E3F9EA", "#087F5B"), self.summary_card("สินค้าที่ต้องเติม", self.summary_values["low_stock"], ft.Icons.WARNING_AMBER_ROUNDED, "#FFF3DD", "#C05621"), self.summary_card("มูลค่าสินค้าคงเหลือ", self.summary_values["value"], ft.Icons.ACCOUNT_BALANCE_WALLET, "#F1EAFF", "#6D28D9")], spacing=12), catalogue], scroll=ft.ScrollMode.AUTO, spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        super().__init__(content=content, padding=24, bgcolor=self.SURFACE, expand=True)
        self.update_summary_values(); self.update_alerts()
        page.on_resize = self.on_resize

    def field(self, label, hint, **kwargs): return ft.TextField(label=label, hint_text=hint, width=180, **kwargs)
    def metric(self, color): return ft.Text("0", size=28, weight=ft.FontWeight.BOLD, color=color)
    def hero(self):
        return ft.Container(content=ft.Row(controls=[ft.Container(content=ft.Icon(ft.Icons.WAREHOUSE_ROUNDED, color=self.INDIGO, size=25), padding=10, bgcolor="#E8EEFF", border_radius=12), ft.Column(controls=[ft.Text(APP_HEADING, size=24, weight=ft.FontWeight.BOLD, color=self.NAVY), ft.Text(APP_TAGLINE, size=13, color=ft.Colors.GREY_700)], spacing=1)], spacing=12), padding=ft.Padding.only(bottom=4))
    def panel(self, content, width=None): return ft.Card(content=ft.Container(content=content, padding=20, width=width, border_radius=16), elevation=0, bgcolor=ft.Colors.WHITE)
    def heading(self, icon, title, subtitle): return ft.Row(controls=[ft.Container(content=ft.Icon(icon, color=self.INDIGO, size=22), padding=9, bgcolor="#E8EEFF", border_radius=10), ft.Column(controls=[ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=self.NAVY), ft.Text(subtitle, size=12, color=ft.Colors.GREY_700)], spacing=2)], spacing=10)
    def summary_card(self, label, value, icon, tint, accent):
        needs_stock = value is self.summary_values["low_stock"]
        details = [ft.Text(label, size=13, color=ft.Colors.GREY_700), value]
        if needs_stock:
            details.append(self.stock_breakdown)
        return ft.Card(content=ft.Container(
            content=ft.Row(controls=[ft.Column(controls=details, spacing=5, expand=True), ft.Container(content=ft.Icon(icon, color=accent, size=25), padding=12, bgcolor=tint, border_radius=12)], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            height=120, padding=16,
            tooltip="ผลรวมราคาต่อหน่วย × จำนวนคงเหลือของสินค้าทั้งหมด" if value is self.summary_values["value"] else None,
            on_click=lambda e: self.filter_status("ต้องเติมสต็อก" if needs_stock else "ทั้งหมด")),
            elevation=0, bgcolor=ft.Colors.WHITE, col={"xs": 12, "sm": 6, "xl": 3})
    def make_rows(self, products):
        return [ft.DataRow(cells=[ft.DataCell(ft.Text(p["id"], weight=ft.FontWeight.W_600, color=self.INDIGO)), ft.DataCell(ft.Text(p["name"])), ft.DataCell(ft.Text(p["category"])), ft.DataCell(ft.Text(f"฿{p['price']:,.2f}")), ft.DataCell(ft.Text(str(p["quantity"]))), ft.DataCell(ft.Text(p["date"])), ft.DataCell(self.status_badge(calculate_status(p["quantity"]))), ft.DataCell(ft.Row(controls=[ft.IconButton(icon=ft.Icons.SWAP_VERT, tooltip="รับเข้า / เบิกออก", on_click=lambda e, item=p: self.open_movement(item)), ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, icon_color=self.INDIGO, tooltip="แก้ไข", on_click=lambda e, item=p: self.edit_product(item)), ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color="#C53030", tooltip="ลบ", on_click=lambda e, item=p: self.confirm_delete(item))], spacing=0))]) for p in products]
    def status_badge(self, status):
        bg, fg, icon = {"พร้อมขาย": ("#D9FBE8", "#087F5B", ft.Icons.CHECK_CIRCLE), "ใกล้หมด": ("#FFF3DD", "#B45309", ft.Icons.WARNING_AMBER_ROUNDED), "หมด": ("#FEE2E2", "#B91C1C", ft.Icons.ERROR_OUTLINE)}[status]
        return ft.Container(content=ft.Row(controls=[ft.Icon(icon, size=15, color=fg), ft.Text(status, color=fg, size=12)], tight=True, spacing=5), bgcolor=bg, padding=8, border_radius=16)
    def update_alerts(self):
        alerts = [p for p in self.products if p["quantity"] < 10]
        self.alert_count.value = f"ใกล้หมด {sum(0 < p['quantity'] < 10 for p in alerts)} / หมด {sum(p['quantity'] == 0 for p in alerts)} รายการ"
        self.alert_list.controls = [ft.Text("ทุกสินค้าอยู่ในระดับปลอดภัย", color="#087F5B")] if not alerts else [ft.Container(content=ft.Row(controls=[ft.Container(width=8, height=38, bgcolor="#F59E0B" if p["quantity"] else "#DC2626", border_radius=6), ft.Column(controls=[ft.Text(p["name"], weight=ft.FontWeight.W_600), ft.Text(f"เหลือ {p['quantity']} ชิ้น • {p['id']}", size=12, color=ft.Colors.GREY_700)], spacing=2)], spacing=10), padding=10, bgcolor="#FAFBFD", border_radius=10) for p in alerts[:4]]
    def open_form(self, e=None):
        self.form_dialog = ft.AlertDialog(modal=True, content=self.form_panel, actions=[ft.Button(content="ปิด", on_click=self.close_form)])
        self._page.show_dialog(self.form_dialog)
    def close_form(self, e=None):
        if self.form_dialog is not None:
            self.form_dialog.open = False
            # Dialogs live in a separate Flet control tree. Updating only the
            # page does not reliably send the dialog's changed open state.
            self._page.update(self.form_dialog)
            self.form_dialog = None
        self.clear_form()

    def finish_save(self, message):
        self.close_form()
        self.refresh_all()
        self._page.show_dialog(ft.SnackBar(content=ft.Text(message), duration=2500))
    def show_message(self, msg): self._page.show_dialog(ft.AlertDialog(title=ft.Text("แจ้งเตือน"), content=ft.Text(msg), actions=[ft.Button(content="รับทราบ", on_click=lambda e: self._page.pop_dialog())]))
    def update_summary_values(self):
        s = inventory_summary(self.products); self.summary_values["items"].value = f"{s['items']} รายการ"; self.summary_values["quantity"].value = f"{s['quantity']:,} ชิ้น"; self.summary_values["low_stock"].value = f"{s['needs_stock']} รายการ"; self.summary_values["value"].value = f"฿{s['value']:,.2f}"
        self.stock_breakdown.value = f"ใกล้หมด {s['low_stock']} · หมดแล้ว {s['out_of_stock']}"
    def refresh_all(self):
        self.products = self.store.products()
        products = filter_products(self.products, self.search_field.value or "")
        if self.category_filter.value != "ทั้งหมด":
            products = [p for p in products if p["category"] == self.category_filter.value]
        status = self.status_filter.value
        if status != "ทั้งหมด":
            products = [p for p in products if (p["quantity"] < 10 if status == "ต้องเติมสต็อก" else calculate_status(p["quantity"]) == status)]
        self.table.rows = self.make_rows(products)
        self.result_count.value = f"พบ {len(products)} จาก {len(self.products)} รายการ" if products else "ไม่พบสินค้า — ลองเปลี่ยนคำค้นหาหรือกดแสดงทั้งหมด"
        self.update_summary_values()
        self.update_alerts()
        self._page.update()

    def filter_status(self, status):
        self.search_field.value = ""
        self.category_filter.value = "ทั้งหมด"
        self.status_filter.value = status
        self.refresh_all()

    @staticmethod
    def table_width(width):
        width = width or 1280
        return max(1000, round((width - 110) * (0.75 if width >= 1200 else 1)))

    def on_resize(self, e):
        # Layout notifications can repeat without the available width changing.
        # Only repaint the table when its target width actually changes.
        width = self.table_width(self._page.width)
        if self.table.width == width:
            return
        self.table.width = width
        self.table.update()

    def new_product(self, e):
        self.clear_form(refresh=False)
        self.open_form()

    def persist(self, action):
        try:
            action()
            return True
        except sqlite3.IntegrityError:
            self.show_message("รหัสสินค้าซ้ำ หรือข้อมูลสินค้าไม่ถูกต้อง")
        except (sqlite3.Error, ValueError) as error:
            self.show_message(f"บันทึกไม่สำเร็จ: {error}")
        return False

    def open_movement(self, product):
        kind = ft.Dropdown(label="รายการ", value="รับเข้า", options=[ft.DropdownOption(x) for x in ["รับเข้า", "เบิกออก"]])
        amount = ft.TextField(label="จำนวน (ชิ้น)", keyboard_type=ft.KeyboardType.NUMBER)
        reason = ft.TextField(label="เหตุผล / เลขที่เอกสาร")
        def save(e):
            try:
                qty = int(amount.value or "")
                if qty <= 0:
                    raise ValueError
            except ValueError:
                amount.error_text = "กรอกจำนวนเต็มมากกว่า 0"
                self._page.update(amount)
                return
            amount.error_text = None
            self._page.update(amount)
            if self.persist(lambda: self.store.adjust(product['id'], qty if kind.value == "รับเข้า" else -qty, reason.value or "")):
                self._page.pop_dialog()
                self.refresh_all()
                self.show_message("บันทึกการเคลื่อนไหวสต็อกแล้ว")
        self._page.show_dialog(ft.AlertDialog(modal=True, title=ft.Text(f"รับเข้า / เบิกออก: {product['name']}"), content=ft.Column(controls=[ft.Text(f"คงเหลือ {product['quantity']} ชิ้น"), kind, amount, reason], tight=True, width=400), actions=[ft.Button(content="ยกเลิก", on_click=lambda e: self._page.pop_dialog()), ft.Button(content="บันทึก", on_click=save)]))

    def show_history(self, e):
        rows = self.store.history()
        entries = [ft.Text(f"{r['created']} | {r['product_id']} {r['name']} | {r['delta']:+} ชิ้น → เหลือ {r['balance']} | {r['reason']}") for r in rows]
        self._page.show_dialog(ft.AlertDialog(title=ft.Text("ประวัติสต็อก (ล่าสุด 200 รายการ)"), content=ft.Column(controls=entries or [ft.Text("ยังไม่มีประวัติการเคลื่อนไหว")], width=760, height=400, scroll=ft.ScrollMode.AUTO), actions=[ft.Button(content="ปิด", on_click=lambda e: self._page.pop_dialog())]))

    def update_status_preview(self, e):
        try: self.status_group.value = calculate_status(max(0, int(self.quantity_field.value or "0")))
        except ValueError: self.status_group.value = "พร้อมขาย"
        self._page.update(self.status_group)
    def open_date_picker(self, e): self._page.show_dialog(self.date_picker)
    def set_received_date(self, e):
        if self.date_picker.value: self.date_field.value = self.date_picker.value.strftime("%d/%m/%Y"); self._page.update(self.date_field)
    def validate_form(self):
        pid, name, category, price_text, qty_text, date = (self.id_field.value or "").strip(), (self.name_field.value or "").strip(), self.category_field.value, (self.price_field.value or "").strip(), (self.quantity_field.value or "").strip(), (self.date_field.value or "").strip()
        pid = self.editing_id or ""
        if not name: return None, "กรุณากรอกชื่อสินค้า"
        if not category: return None, "กรุณาเลือกประเภทสินค้า"
        if not price_text: return None, "กรุณากรอกราคา"
        if not qty_text: return None, "กรุณากรอกจำนวนคงเหลือ"
        if not date: return None, "กรุณาเลือกวันที่รับเข้า"
        try:
            price = float(price_text)
            if not math.isfinite(price) or price <= 0: raise ValueError
        except ValueError: return None, "ราคาต้องเป็นตัวเลขที่มากกว่า 0"
        try:
            qty = int(qty_text)
            if qty < 0: raise ValueError
        except ValueError: return None, "จำนวนคงเหลือต้องเป็นจำนวนเต็มที่ไม่น้อยกว่า 0"
        product = {"id": pid, "name": name, "category": category, "price": price, "quantity": qty, "date": date}
        try:
            validate_product(product)
        except ValueError as error:
            return None, str(error)
        return product, None
    def add_product(self, e):
        p, error = self.validate_form()
        if error: self.show_message(error); return
        if not self.persist(lambda: self.store.save(p)): return
        self.finish_save("เพิ่มสินค้าสำเร็จ")
    def edit_product(self, p):
        self.editing_snapshot = p.copy()
        self.editing_id = p["id"]; self.id_field.value, self.name_field.value, self.category_field.value = p["id"], p["name"], p["category"]; self.price_field.value, self.quantity_field.value, self.date_field.value = str(p["price"]), str(p["quantity"]), p["date"]; self.status_group.value = calculate_status(p["quantity"]); self.add_button.disabled, self.save_button.disabled = True, False; self.open_form()
    def save_edit(self, e):
        p, error = self.validate_form()
        if not self.editing_id: self.show_message("กรุณาเลือกรายการที่ต้องการแก้ไข"); return
        if error: self.show_message(error); return
        if any(x["id"].casefold() == p["id"].casefold() and x["id"] != self.editing_id for x in self.products): self.show_message("รหัสสินค้านี้มีอยู่แล้ว"); return
        if not self.persist(lambda: self.store.save(p, self.editing_id, expected=self.editing_snapshot)): return
        self.finish_save("แก้ไขข้อมูลสำเร็จ")
    def confirm_delete(self, p):
        self._page.show_dialog(ft.AlertDialog(modal=True, title=ft.Text("ยืนยันการลบ"), content=ft.Text(f"คุณต้องการลบ {p['name']} ออกจากคลังใช่หรือไม่?"), actions=[ft.Button(content="ยกเลิก", on_click=lambda e: self._page.pop_dialog()), ft.Button(content="ยืนยันการลบ", bgcolor="#C53030", color=ft.Colors.WHITE, on_click=lambda e: self.delete_product(p))]))
    def delete_product(self, p):
        self._page.pop_dialog()
        if not self.persist(lambda: self.store.delete(p["id"])): return
        if self.editing_id == p["id"]: self.clear_form(refresh=False)
        self.refresh_all(); self.show_message("ลบสินค้าสำเร็จ")
    def search_product(self, e): self.refresh_all()
    def clear_search(self, e): self.filter_status("ทั้งหมด")
    def clear_form(self, e=None, refresh=True):
        self.editing_snapshot = None
        self.editing_id = None; self.id_field.value = self.name_field.value = self.price_field.value = self.quantity_field.value = self.date_field.value = ""; self.category_field.value = None; self.status_group.value = "พร้อมขาย"; self.add_button.disabled, self.save_button.disabled = False, True
        if refresh:
            if self.form_dialog is not None:
                self._page.update(self.form_dialog)
            else:
                self._page.update()
