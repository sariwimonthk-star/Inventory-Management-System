"""Polished inventory dashboard with CRUD and stock alerts."""
from datetime import datetime
import math
import flet as ft
from models import CATEGORIES, SAMPLE_PRODUCTS, calculate_status, filter_products, inventory_summary

APP_HEADING = "Inventory-Management-System"
APP_TAGLINE = "ระบบจัดการคลังสินค้า"


class InventoryView(ft.Container):
    NAVY, INDIGO, SURFACE = "#102A43", "#334EAC", "#F6F8FC"

    def __init__(self, page: ft.Page):
        self._page, self.products, self.editing_id = page, [p.copy() for p in SAMPLE_PRODUCTS], None
        self.id_field = self.field("รหัสสินค้า", "เช่น SKU-001")
        self.name_field = self.field("ชื่อสินค้า", "ระบุชื่อที่ค้นหาได้ง่าย")
        self.category_field = ft.Dropdown(label="ประเภทสินค้า", hint_text="เลือกประเภท", width=180, options=[ft.DropdownOption(key=x, text=x) for x in CATEGORIES])
        self.price_field = self.field("ราคา (บาท)", "0.00", keyboard_type=ft.KeyboardType.NUMBER)
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
        self.summary_values = {"items": self.metric("#102A43"), "quantity": self.metric("#087F5B"), "low_stock": self.metric("#C05621"), "value": self.metric("#6D28D9")}
        self.alert_list = ft.Column(spacing=8)
        self.table = ft.DataTable(columns=[ft.DataColumn(ft.Text(x, weight=ft.FontWeight.BOLD), numeric=x in ("ราคา", "คงเหลือ")) for x in ["รหัสสินค้า", "ชื่อสินค้า", "ประเภท", "ราคา", "คงเหลือ", "วันที่รับเข้า", "สถานะ", "จัดการ"]], rows=[], heading_row_color="#E9EEFF", data_row_min_height=60, show_bottom_border=True, column_spacing=22)
        self.table.rows = self.make_rows(self.products)
        form = self.panel(ft.Column(controls=[self.heading(ft.Icons.EDIT_NOTE, "Product workspace", "เพิ่มหรือปรับข้อมูลสินค้าในคลัง"), ft.Divider(height=1), ft.Text("ข้อมูลสินค้า", weight=ft.FontWeight.W_600, color=self.NAVY), ft.Row(controls=[self.id_field, self.name_field, self.category_field], wrap=True, run_spacing=12), ft.Row(controls=[self.price_field, self.quantity_field, ft.Row(controls=[self.date_field, ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, icon_color=self.INDIGO, tooltip="เลือกวันที่รับเข้า", on_click=self.open_date_picker)], vertical_alignment=ft.CrossAxisAlignment.END, spacing=0)], wrap=True, run_spacing=12), ft.Container(content=ft.Column(controls=[ft.Text("สถานะสินค้า", weight=ft.FontWeight.W_600, color=self.NAVY), ft.Text("คำนวณจากจำนวนคงเหลือโดยอัตโนมัติ", size=12, color=ft.Colors.GREY_700), self.status_group], spacing=4), padding=14, bgcolor="#F7FAFC", border_radius=10), ft.Row(controls=[self.add_button, self.save_button, self.clear_button], wrap=True, spacing=10)], spacing=14), width=660)
        self.form_panel = form
        self.form_dialog = None
        alert_panel = ft.Container(content=ft.Column(controls=[self.heading(ft.Icons.NOTIFICATIONS_ACTIVE, "Stock watch", "สินค้าใกล้หมด"), ft.Divider(height=1), self.alert_list, ft.Container(content=ft.Text("แจ้งเตือนเมื่อคงเหลือน้อยกว่า 10 ชิ้น", size=12, color=ft.Colors.GREY_700), padding=10, bgcolor="#EEF2FF", border_radius=8)], spacing=10), width=330, padding=14, bgcolor="#FAFBFD", border_radius=12)
        catalogue_header = ft.Row(controls=[self.heading(ft.Icons.TABLE_ROWS, "Inventory catalogue", "ค้นหา ตรวจสอบ และจัดการรายการทั้งหมด"), ft.Button(content="เพิ่มสินค้า", icon=ft.Icons.ADD, bgcolor=self.INDIGO, color=ft.Colors.WHITE, on_click=self.open_form)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        catalogue = self.panel(ft.Row(controls=[ft.Column(controls=[catalogue_header, ft.Row(controls=[self.search_field, self.search_button, self.clear_search_button], wrap=True, run_spacing=10), ft.Row(controls=[self.table], scroll=ft.ScrollMode.ADAPTIVE)], spacing=14, expand=True), alert_panel], spacing=20, vertical_alignment=ft.CrossAxisAlignment.START))
        content = ft.Column(controls=[self.hero(), ft.Text("ภาพรวมคลังสินค้า", size=16, weight=ft.FontWeight.W_600, color=self.NAVY), ft.Row(controls=[self.summary_card("สินค้าในระบบ", self.summary_values["items"], ft.Icons.INVENTORY_2, "#E8EEFF", self.INDIGO), self.summary_card("จำนวนคงเหลือ", self.summary_values["quantity"], ft.Icons.STACKED_BAR_CHART, "#E3F9EA", "#087F5B"), self.summary_card("สินค้าใกล้หมด", self.summary_values["low_stock"], ft.Icons.WARNING_AMBER_ROUNDED, "#FFF3DD", "#C05621"), self.summary_card("มูลค่าในคลัง", self.summary_values["value"], ft.Icons.ACCOUNT_BALANCE_WALLET, "#F1EAFF", "#6D28D9")], spacing=12), catalogue], spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        super().__init__(content=content, padding=24, bgcolor=self.SURFACE, expand=True)
        self.update_summary_values(); self.update_alerts()

    def field(self, label, hint, **kwargs): return ft.TextField(label=label, hint_text=hint, width=180, **kwargs)
    def metric(self, color): return ft.Text("0", size=28, weight=ft.FontWeight.BOLD, color=color)
    def hero(self):
        return ft.Container(content=ft.Row(controls=[ft.Container(content=ft.Icon(ft.Icons.WAREHOUSE_ROUNDED, color=self.INDIGO, size=25), padding=10, bgcolor="#E8EEFF", border_radius=12), ft.Column(controls=[ft.Text(APP_HEADING, size=24, weight=ft.FontWeight.BOLD, color=self.NAVY), ft.Text(APP_TAGLINE, size=13, color=ft.Colors.GREY_700)], spacing=1)], spacing=12), padding=ft.Padding.only(bottom=4))
    def panel(self, content, width=None): return ft.Card(content=ft.Container(content=content, padding=20, width=width, border_radius=16), elevation=0, bgcolor=ft.Colors.WHITE)
    def heading(self, icon, title, subtitle): return ft.Row(controls=[ft.Container(content=ft.Icon(icon, color=self.INDIGO, size=22), padding=9, bgcolor="#E8EEFF", border_radius=10), ft.Column(controls=[ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=self.NAVY), ft.Text(subtitle, size=12, color=ft.Colors.GREY_700)], spacing=2)], spacing=10)
    def summary_card(self, label, value, icon, tint, accent): return ft.Card(content=ft.Container(content=ft.Row(controls=[ft.Column(controls=[ft.Text(label, size=13, color=ft.Colors.GREY_700), value], spacing=7, expand=True), ft.Container(content=ft.Icon(icon, color=accent, size=25), padding=12, bgcolor=tint, border_radius=12)], vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=16), elevation=0, bgcolor=ft.Colors.WHITE, expand=1)
    def make_rows(self, products):
        return [ft.DataRow(cells=[ft.DataCell(ft.Text(p["id"], weight=ft.FontWeight.W_600, color=self.INDIGO)), ft.DataCell(ft.Text(p["name"])), ft.DataCell(ft.Text(p["category"])), ft.DataCell(ft.Text(f"฿{p['price']:,.2f}")), ft.DataCell(ft.Text(str(p["quantity"]))), ft.DataCell(ft.Text(p["date"])), ft.DataCell(self.status_badge(calculate_status(p["quantity"]))), ft.DataCell(ft.Row(controls=[ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, icon_color=self.INDIGO, tooltip="แก้ไข", on_click=lambda e, item=p: self.edit_product(item)), ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color="#C53030", tooltip="ลบ", on_click=lambda e, item=p: self.confirm_delete(item))], spacing=0))]) for p in products]
    def status_badge(self, status):
        bg, fg, icon = {"พร้อมขาย": ("#D9FBE8", "#087F5B", ft.Icons.CHECK_CIRCLE), "ใกล้หมด": ("#FFF3DD", "#B45309", ft.Icons.WARNING_AMBER_ROUNDED), "หมด": ("#FEE2E2", "#B91C1C", ft.Icons.ERROR_OUTLINE)}[status]
        return ft.Container(content=ft.Row(controls=[ft.Icon(icon, size=15, color=fg), ft.Text(status, color=fg, size=12)], tight=True, spacing=5), bgcolor=bg, padding=8, border_radius=16)
    def update_alerts(self):
        alerts = [p for p in self.products if p["quantity"] < 10]
        self.alert_list.controls = [ft.Text("ทุกสินค้าอยู่ในระดับปลอดภัย", color="#087F5B")] if not alerts else [ft.Container(content=ft.Row(controls=[ft.Container(width=8, height=38, bgcolor="#F59E0B" if p["quantity"] else "#DC2626", border_radius=6), ft.Column(controls=[ft.Text(p["name"], weight=ft.FontWeight.W_600), ft.Text(f"เหลือ {p['quantity']} ชิ้น • {p['id']}", size=12, color=ft.Colors.GREY_700)], spacing=2)], spacing=10), padding=10, bgcolor="#FAFBFD", border_radius=10) for p in alerts[:4]]
    def open_form(self, e=None):
        self.form_dialog = ft.AlertDialog(modal=True, content=self.form_panel, actions=[ft.Button(content="ปิด", on_click=self.close_form)])
        self._page.show_dialog(self.form_dialog)
    def close_form(self, e=None):
        self._page.pop_dialog(); self.form_dialog = None
    def show_message(self, msg): self._page.show_dialog(ft.AlertDialog(title=ft.Text("แจ้งเตือน"), content=ft.Text(msg), actions=[ft.Button(content="รับทราบ", on_click=lambda e: self._page.pop_dialog())]))
    def update_summary_values(self):
        s = inventory_summary(self.products); self.summary_values["items"].value = str(s["items"]); self.summary_values["quantity"].value = f"{s['quantity']:,}"; self.summary_values["low_stock"].value = str(s["low_stock"]); self.summary_values["value"].value = f"฿{s['value']:,.2f}"
    def refresh_all(self): self.table.rows = self.make_rows(filter_products(self.products, self.search_field.value or "")); self.update_summary_values(); self.update_alerts(); self._page.update()
    def update_status_preview(self, e):
        try: self.status_group.value = calculate_status(max(0, int(self.quantity_field.value or "0")))
        except ValueError: self.status_group.value = "พร้อมขาย"
        self._page.update()
    def open_date_picker(self, e): self._page.show_dialog(self.date_picker)
    def set_received_date(self, e):
        if self.date_picker.value: self.date_field.value = self.date_picker.value.strftime("%d/%m/%Y"); self._page.update()
    def validate_form(self):
        pid, name, category, price_text, qty_text, date = (self.id_field.value or "").strip(), (self.name_field.value or "").strip(), self.category_field.value, (self.price_field.value or "").strip(), (self.quantity_field.value or "").strip(), (self.date_field.value or "").strip()
        if not pid: return None, "กรุณากรอกรหัสสินค้า"
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
        return {"id": pid, "name": name, "category": category, "price": price, "quantity": qty, "date": date}, None
    def add_product(self, e):
        p, error = self.validate_form()
        if error: self.show_message(error); return
        if any(x["id"].casefold() == p["id"].casefold() for x in self.products): self.show_message("รหัสสินค้านี้มีอยู่แล้ว"); return
        self.products.append(p); self.clear_form(refresh=False); self.refresh_all(); self.close_form(); self.show_message("เพิ่มสินค้าสำเร็จ")
    def edit_product(self, p):
        self.editing_id = p["id"]; self.id_field.value, self.name_field.value, self.category_field.value = p["id"], p["name"], p["category"]; self.price_field.value, self.quantity_field.value, self.date_field.value = str(p["price"]), str(p["quantity"]), p["date"]; self.status_group.value = calculate_status(p["quantity"]); self.add_button.disabled, self.save_button.disabled = True, False; self.open_form()
    def save_edit(self, e):
        p, error = self.validate_form()
        if not self.editing_id: self.show_message("กรุณาเลือกรายการที่ต้องการแก้ไข"); return
        if error: self.show_message(error); return
        if any(x["id"].casefold() == p["id"].casefold() and x["id"] != self.editing_id for x in self.products): self.show_message("รหัสสินค้านี้มีอยู่แล้ว"); return
        for i, x in enumerate(self.products):
            if x["id"] == self.editing_id: self.products[i] = p; break
        self.clear_form(refresh=False); self.refresh_all(); self.close_form(); self.show_message("แก้ไขข้อมูลสำเร็จ")
    def confirm_delete(self, p):
        self._page.show_dialog(ft.AlertDialog(modal=True, title=ft.Text("ยืนยันการลบ"), content=ft.Text(f"คุณต้องการลบ {p['name']} ออกจากคลังใช่หรือไม่?"), actions=[ft.Button(content="ยกเลิก", on_click=lambda e: self._page.pop_dialog()), ft.Button(content="ยืนยันการลบ", bgcolor="#C53030", color=ft.Colors.WHITE, on_click=lambda e: self.delete_product(p))]))
    def delete_product(self, p):
        self._page.pop_dialog(); self.products = [x for x in self.products if x is not p]
        if self.editing_id == p["id"]: self.clear_form(refresh=False)
        self.refresh_all(); self.show_message("ลบสินค้าสำเร็จ")
    def search_product(self, e): self.refresh_all()
    def clear_search(self, e): self.search_field.value = ""; self.refresh_all()
    def clear_form(self, e=None, refresh=True):
        self.editing_id = None; self.id_field.value = self.name_field.value = self.price_field.value = self.quantity_field.value = self.date_field.value = ""; self.category_field.value = None; self.status_group.value = "พร้อมขาย"; self.add_button.disabled, self.save_button.disabled = False, True
        if refresh: self._page.update()
