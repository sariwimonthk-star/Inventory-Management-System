"""Polished inventory dashboard with CRUD and stock alerts."""
from datetime import datetime
import math
import sqlite3
from storage import InventoryStore, validate_product
from views.inventory_table import InventoryTable
import flet as ft
from models import CATEGORIES, calculate_status, filter_products, inventory_summary

APP_HEADING = "คลังสินค้า"
APP_TAGLINE = "จัดการสินค้าและติดตามสต็อกในที่เดียว"


class InventoryView(ft.Container):
    NAVY, INDIGO, SURFACE = "#102A43", "#334EAC", "#F6F8FC"
    SIDEBAR = "#172033"

    def __init__(self, page: ft.Page, store=None, on_logout=None):
        self.editing_snapshot = None
        self.store = store or InventoryStore()
        self.on_logout = on_logout
        self._page, self.products, self.editing_id = page, self.store.products(), None
        self.id_field = self.field("รหัสสินค้า (อัตโนมัติ)", "สร้างเมื่อบันทึกสำเร็จ", read_only=True)
        self.name_field = self.field("ชื่อสินค้า", "ระบุชื่อที่ค้นหาได้ง่าย")
        self.category_field = ft.Dropdown(label="ประเภทสินค้า", hint_text="เลือกประเภท", width=180, options=[ft.DropdownOption(key=x, text=x) for x in CATEGORIES])
        self.price_field = self.field("ราคาต่อหน่วย (บาท)", "0.00", keyboard_type=ft.KeyboardType.NUMBER)
        self.quantity_field = self.field("จำนวนคงเหลือ", "0", keyboard_type=ft.KeyboardType.NUMBER, on_change=self.update_status_preview)
        self.date_field = ft.TextField(label="วันที่รับเข้า", hint_text="คลิกเพื่อเลือกวันที่", width=180, read_only=True, on_click=self.open_date_picker)
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
        alert_panel = ft.Container(content=ft.Column(controls=[self.heading(ft.Icons.NOTIFICATIONS_ACTIVE, "แจ้งเตือนสต็อก", "คลิกรายการเพื่อเติมสต็อก"), ft.Divider(height=1), self.alert_count, self.alert_list, ft.Button(content="ดูรายการที่ต้องเติมทั้งหมด", on_click=self.show_low_stock), ft.Container(content=ft.Text("แจ้งเตือนเมื่อคงเหลือน้อยกว่า 10 ชิ้น", size=12, color=ft.Colors.GREY_700), padding=10, bgcolor="#EEF2FF", border_radius=8)], spacing=10), col={"xs": 12, "xl": 3}, padding=14, bgcolor="#FAFBFD", border_radius=12)
        catalogue_header = ft.Row(controls=[ft.Container(content=self.heading(ft.Icons.TABLE_ROWS, "รายการสินค้า", "ค้นหา ตรวจสอบ และจัดการรายการทั้งหมด"), expand=True), ft.Button(content="เพิ่มสินค้า", icon=ft.Icons.ADD, bgcolor=self.INDIGO, color=ft.Colors.WHITE, on_click=self.new_product)], vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.table.width = self.table_width(page.width)
        self.table_area = ft.Row(controls=[self.table], scroll=ft.ScrollMode.ADAPTIVE)
        self.search_field.width = 280
        self.category_filter.width = 180
        self.status_filter.width = 160
        for control in (self.search_field, self.category_filter, self.status_filter):
            control.border_color = "#DCE3EF"
            control.focused_border_color = self.INDIGO
            control.border_radius = 12
            control.filled = True
            control.fill_color = "#F8FAFD"
            control.text_size = 14
        self.result_count.size = 12
        self.result_count.color = "#64748B"
        toolbar = ft.Row(controls=[self.search_field, self.category_filter, self.status_filter, self.search_button, self.clear_search_button], wrap=True, run_spacing=10)
        catalogue = self.panel(ft.ResponsiveRow(controls=[ft.Column(controls=[catalogue_header, toolbar, ft.Row(controls=[self.result_count, ft.Button(content="ประวัติสต็อก", icon=ft.Icons.HISTORY, on_click=self.show_history)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), self.table_area], spacing=12, col={"xs": 12, "xl": 9}), alert_panel], spacing=20, run_spacing=20))
        self.summary_cards = ft.ResponsiveRow(controls=[
            self.summary_card("สินค้าในระบบ", self.summary_values["items"], ft.Icons.INVENTORY_2, "#E8EEFF", self.INDIGO),
            self.summary_card("จำนวนคงเหลือ", self.summary_values["quantity"], ft.Icons.STACKED_BAR_CHART, "#E3F9EA", "#087F5B"),
            self.summary_card("สินค้าที่ต้องเติม", self.summary_values["low_stock"], ft.Icons.WARNING_AMBER_ROUNDED, "#FFF3DD", "#C05621"),
            self.summary_card("มูลค่าสินค้าคงเหลือ", self.summary_values["value"], ft.Icons.ACCOUNT_BALANCE_WALLET, "#F1EAFF", "#6D28D9"),
        ], spacing=12)
        self.catalogue = catalogue
        self.main_content = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, expand=True)
        self.active_nav = "dashboard"
        self.nav_controls = {}
        sidebar = self.build_sidebar()
        super().__init__(content=ft.Row(controls=[sidebar, ft.Container(content=self.main_content, padding=20, bgcolor=self.SURFACE, expand=True)], spacing=0, expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH), bgcolor=self.SURFACE, expand=True)
        self.update_summary_values(); self.update_alerts()
        self.render_dashboard()
        page.on_resize = self.on_resize

    def field(self, label, hint, **kwargs): return ft.TextField(label=label, hint_text=hint, width=180, **kwargs)
    def metric(self, color): return ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=color)
    def build_sidebar(self):
        menu = [
            ("dashboard", "ภาพรวม", ft.Icons.GRID_VIEW_ROUNDED, self.show_dashboard),
            ("inventory", "สินค้าคงคลัง", ft.Icons.INVENTORY_2_OUTLINED, self.show_inventory),
            ("low_stock", "สินค้าใกล้หมด", ft.Icons.WARNING_AMBER_ROUNDED, self.show_low_stock),
            ("history", "ประวัติสต็อก", ft.Icons.HISTORY_ROUNDED, self.show_history_page),
        ]
        nav = [self.nav_item(*item) for item in menu]
        if self.on_logout:
            user = self.store.user
            nav.extend([ft.Container(content=ft.Text(f"{user['name']} · ผู้ดูแลคลัง", color="#C7D2E3", size=12), padding=16), ft.Button(content="ออกจากระบบ", icon=ft.Icons.LOGOUT, on_click=lambda e: self.on_logout())])
        return ft.Container(
            content=ft.Column(controls=[
                ft.Container(content=ft.Row(controls=[
                    ft.Container(content=ft.Icon(ft.Icons.INVENTORY_2_ROUNDED, color="#FFFFFF", size=23), bgcolor="#FBBF24", padding=9, border_radius=10),
                    ft.Column(controls=[ft.Text("INVENTORY", size=16, weight=ft.FontWeight.BOLD, color="#FFFFFF"), ft.Text("MANAGEMENT SYSTEM", size=9, color="#9AA8BF")], spacing=1),
                ], spacing=10), padding=ft.Padding.only(left=16, right=16, top=22, bottom=22)),
                ft.Divider(height=1, color="#2A3851"),
                ft.Container(content=ft.Text("เมนูหลัก", size=12, weight=ft.FontWeight.BOLD, color="#93A4BE"), padding=ft.Padding.only(left=18, top=18, bottom=7)),
                *nav,
                ft.Container(expand=True),
                ft.Divider(height=1, color="#2A3851"),
                ft.Container(content=ft.Text("ระบบจัดการคลังสินค้า", size=11, color="#93A4BE"), padding=16),
            ], spacing=3, expand=True), width=245, bgcolor=self.SIDEBAR,
        )

    def nav_item(self, key, label, icon, action):
        item = ft.Container(content=ft.Row(controls=[ft.Icon(icon, size=21), ft.Text(label, size=14, weight=ft.FontWeight.W_600)], spacing=13), padding=ft.Padding.symmetric(horizontal=16, vertical=13), margin=ft.Margin.symmetric(horizontal=10), border_radius=10, on_click=action, ink=True)
        self.nav_controls[key] = item
        self.paint_nav()
        return item

    def paint_nav(self):
        for key, item in self.nav_controls.items():
            selected = key == self.active_nav
            item.bgcolor = "#FBBF24" if selected else None
            item.content.controls[0].color = "#172033" if selected else "#C7D2E3"
            item.content.controls[1].color = "#172033" if selected else "#E5EAF2"

    def set_page(self, key, controls):
        self.active_nav = key
        self.paint_nav()
        self.main_content.controls = controls
        self._page.update()

    def render_dashboard(self):
        self.main_content.controls = [self.hero("ภาพรวมคลังสินค้า"), self.summary_cards, self.dashboard_panel(), self.dashboard_details()]

    def show_dashboard(self, e=None):
        self.clear_search(None)
        self.set_page("dashboard", [self.hero("ภาพรวมคลังสินค้า"), self.summary_cards, self.dashboard_panel(), self.dashboard_details()])

    def show_inventory(self, e=None):
        self.clear_search(None)
        self.set_page("inventory", [self.hero(), self.catalogue])

    def show_low_stock(self, e=None):
        self.products = self.store.products()
        self.set_page("low_stock", [self.hero(), self.back_to_inventory(), self.low_stock_panel()])

    def back_to_inventory(self):
        return ft.Row(controls=[ft.Button(content="กลับหน้าสินค้าคงคลัง", icon=ft.Icons.ARROW_BACK, on_click=self.show_inventory)])

    def show_history_page(self, e=None):
        entries = self.store.history()
        history = self.panel(ft.Column(controls=[
            self.heading(ft.Icons.HISTORY_ROUNDED, "ประวัติสต็อก", "รายการเคลื่อนไหวล่าสุด 200 รายการ"),
            ft.Divider(height=1),
            ft.ListView(controls=[ft.Container(content=ft.Text(f"{r['created']} | {r['product_id']} {r['name']} | {r['delta']:+} ชิ้น → เหลือ {r['balance']} | {r['reason']} | ผู้ทำรายการ: {r.get('actor') or 'ข้อมูลเดิม'}"), padding=10, border=ft.Border.only(bottom=ft.BorderSide(1, "#EDF1F7"))) for r in entries] or [ft.Container(content=ft.Text("ยังไม่มีประวัติการเคลื่อนไหว", color="#64748B"), padding=16)], height=510, spacing=0),
        ], spacing=12))
        self.set_page("history", [self.hero(), self.back_to_inventory(), history])

    def dashboard_panel(self):
        summary = inventory_summary(self.products)
        message = "ทุกสินค้าอยู่ในระดับปลอดภัย" if summary["needs_stock"] == 0 else f"มีสินค้า {summary['needs_stock']} รายการที่ต้องตรวจสอบหรือเติมสต็อก"
        color = "#087F5B" if summary["needs_stock"] == 0 else "#B45309"
        return self.panel(ft.Column(controls=[
            ft.Container(content=ft.Row(controls=[ft.Icon(ft.Icons.CHECK_CIRCLE if summary["needs_stock"] == 0 else ft.Icons.WARNING_AMBER_ROUNDED, color=color), ft.Text(message, weight=ft.FontWeight.W_600, color=color, expand=True), ft.Button(content="ดูรายละเอียด", icon=ft.Icons.ARROW_FORWARD, on_click=self.show_low_stock)], vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=10, bgcolor="#ECFDF5" if summary["needs_stock"] == 0 else "#FFFBEB", border_radius=12),
        ], spacing=12))

    def dashboard_details(self):
        counts = {category: 0 for category in CATEGORIES}
        for product in self.products:
            counts[product['category']] = counts.get(product['category'], 0) + 1
        total = len(self.products)
        categories = self.panel(ft.Column(controls=[
            self.heading(ft.Icons.CATEGORY, "สินค้าตามหมวดหมู่", "จำนวนรายการสินค้า ไม่ใช่จำนวนชิ้น"),
            ft.Divider(height=1),
            *[ft.Column(controls=[
                ft.Row(controls=[ft.Text(category, expand=True, color=self.NAVY), ft.Text(f"{count} รายการ", color="#64748B")]),
                ft.ProgressBar(value=count / total if total else 0, color=self.INDIGO, bgcolor="#EDF1F7", height=8, border_radius=4),
            ], spacing=7) for category, count in counts.items()],
            ft.Text(f"รวม {total} รายการ", size=12, color="#64748B"),
        ], spacing=16))
        entries = self.store.history()[:5]
        rows = []
        for entry in entries:
            positive = entry['delta'] > 0
            color = "#087F5B" if positive else "#B45309"
            rows.append(ft.Container(content=ft.Row(controls=[
                ft.Icon(ft.Icons.ARROW_DOWNWARD if positive else ft.Icons.ARROW_UPWARD, color=color, size=20),
                ft.Column(controls=[
                    ft.Text(f"{entry['product_id']} · {entry['name']}", weight=ft.FontWeight.W_600, color=self.NAVY),
                    ft.Text(f"{entry['reason']} · {entry.get('actor') or 'ข้อมูลเดิม'}", size=12, color="#64748B"),
                    ft.Text(entry['created'], size=11, color="#64748B"),
                ], spacing=3, expand=True),
                ft.Text(f"{entry['delta']:+,} ชิ้น", weight=ft.FontWeight.BOLD, color=color),
            ], spacing=12), padding=10, border=ft.Border.only(bottom=ft.BorderSide(1, "#EDF1F7"))))
        history = self.panel(ft.Column(controls=[
            self.heading(ft.Icons.HISTORY, "ความเคลื่อนไหวล่าสุด", "5 รายการล่าสุดจากประวัติสต็อก"),
            ft.Divider(height=1),
            *(rows or [ft.Container(content=ft.Text("ยังไม่มีประวัติการเคลื่อนไหว", color="#64748B"), padding=20)]),
            ft.Button(content="ดูประวัติทั้งหมด", icon=ft.Icons.ARROW_FORWARD, on_click=self.show_history_page),
        ], spacing=10))
        categories.col = {"xs": 12, "lg": 6}
        history.col = {"xs": 12, "lg": 6}
        return ft.ResponsiveRow(controls=[categories, history], spacing=16, run_spacing=16)

    def low_stock_panel(self):
        alerts = sorted((p for p in self.products if p["quantity"] < 10), key=lambda p: p["quantity"])
        cards = [ft.Container(
            content=ft.Row(controls=[
                ft.Container(width=9, height=54, bgcolor="#DC2626" if p["quantity"] == 0 else "#F59E0B", border_radius=8),
                ft.Column(controls=[ft.Text(p["name"], size=16, weight=ft.FontWeight.BOLD, color=self.NAVY), ft.Text(f"{p['id']} · {p['category']} · เหลือ {p['quantity']} ชิ้น", size=13, color="#64748B")], spacing=4, expand=True),
                ft.Button(content="รับเข้า / เบิกออก", icon=ft.Icons.SWAP_VERT, on_click=lambda e, item=p: self.open_movement(item)),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=14, bgcolor="#FFF1F2" if p["quantity"] == 0 else "#FFFAEB", border_radius=12,
        ) for p in alerts]
        if not cards:
            cards = [ft.Container(content=ft.Text("ทุกสินค้าอยู่ในระดับปลอดภัย", color="#087F5B"), padding=16, bgcolor="#ECFDF5", border_radius=10)]
        return self.panel(ft.Column(controls=[
            self.heading(ft.Icons.WARNING_AMBER_ROUNDED, "สินค้าใกล้หมด", "รายการที่เหลือน้อยกว่า 10 ชิ้น"),
            ft.Divider(height=1),
            *cards,
        ], spacing=10))
    def hero(self, title=None):
        return ft.Container(content=ft.Row(controls=[
            ft.Container(content=ft.Icon(ft.Icons.WAREHOUSE_ROUNDED, color="#FFFFFF", size=27), padding=12, bgcolor=self.INDIGO, border_radius=14),
            ft.Column(controls=[ft.Text(title or APP_HEADING, size=26, weight=ft.FontWeight.BOLD, color=self.NAVY), ft.Text(APP_TAGLINE, size=13, color="#64748B")], spacing=2, expand=True),
            ft.Container(content=ft.Row(controls=[ft.Icon(ft.Icons.CALENDAR_MONTH, size=16, color="#64748B"), ft.Text(datetime.now().strftime("%d/%m/%Y"), size=12, color="#64748B")], tight=True), padding=10, bgcolor="#FFFFFF", border_radius=10),
        ], spacing=14), padding=ft.Padding.only(bottom=8))
    def panel(self, content, width=None): return ft.Card(content=ft.Container(content=content, padding=16, width=width, border_radius=16, border=ft.Border.all(1, "#E7ECF4")), elevation=0, bgcolor=ft.Colors.WHITE)
    def heading(self, icon, title, subtitle): return ft.Row(controls=[ft.Container(content=ft.Icon(icon, color=self.INDIGO, size=22), padding=9, bgcolor="#E8EEFF", border_radius=10), ft.Column(controls=[ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=self.NAVY), ft.Text(subtitle, size=12, color=ft.Colors.GREY_700)], spacing=2)], spacing=10)
    def summary_card(self, label, value, icon, tint, accent):
        needs_stock = value is self.summary_values["low_stock"]
        details = [ft.Text(label, size=13, color=ft.Colors.GREY_700), value]
        if needs_stock:
            details.append(self.stock_breakdown)
        return ft.Card(content=ft.Container(
            content=ft.Row(controls=[ft.Column(controls=details, spacing=5, expand=True), ft.Container(content=ft.Icon(icon, color=accent, size=25), padding=12, bgcolor=tint, border_radius=12)], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            height=104, padding=16, border_radius=14, border=ft.Border.all(1, "#E7ECF4"),
            tooltip="ผลรวมราคาต่อหน่วย × จำนวนคงเหลือของสินค้าทั้งหมด" if value is self.summary_values["value"] else None,
            on_click=self.show_low_stock if needs_stock else self.show_inventory),
            elevation=0, bgcolor=ft.Colors.WHITE, width=270, col={"xs": 12, "sm": 6, "xl": 3})
    def make_rows(self, products):
        return [ft.DataRow(cells=[ft.DataCell(ft.Text(p["id"], weight=ft.FontWeight.W_600, color=self.INDIGO)), ft.DataCell(ft.Text(p["name"], weight=ft.FontWeight.W_600, color=self.NAVY)), ft.DataCell(ft.Text(p["category"])), ft.DataCell(ft.Text(f"฿{p['price']:,.2f}")), ft.DataCell(ft.Text(str(p["quantity"]), weight=ft.FontWeight.BOLD, color="#B91C1C" if p["quantity"] == 0 else "#B45309" if p["quantity"] < 10 else self.NAVY)), ft.DataCell(ft.Text(p["date"])), ft.DataCell(self.status_badge(calculate_status(p["quantity"]))), ft.DataCell(ft.Row(controls=[ft.IconButton(icon=ft.Icons.SWAP_VERT, icon_color=self.INDIGO, tooltip="รับเข้า / เบิกออก", on_click=lambda e, item=p: self.open_movement(item)), ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, icon_color=self.INDIGO, tooltip="แก้ไข", on_click=lambda e, item=p: self.edit_product(item)), ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color="#C53030", tooltip="ลบ", on_click=lambda e, item=p: self.confirm_delete(item))], spacing=0))]) for p in products]
    def status_badge(self, status):
        bg, fg, icon = {"พร้อมขาย": ("#D9FBE8", "#087F5B", ft.Icons.CHECK_CIRCLE), "ใกล้หมด": ("#FFF3DD", "#B45309", ft.Icons.WARNING_AMBER_ROUNDED), "หมด": ("#FEE2E2", "#B91C1C", ft.Icons.ERROR_OUTLINE)}[status]
        return ft.Container(content=ft.Row(controls=[ft.Icon(icon, size=15, color=fg), ft.Text(status, color=fg, size=12)], tight=True, spacing=5), bgcolor=bg, padding=8, border_radius=16)
    def update_alerts(self):
        alerts = sorted([p for p in self.products if p["quantity"] < 10], key=lambda p: p["quantity"])
        self.alert_count.value = f"ใกล้หมด {sum(0 < p['quantity'] < 10 for p in alerts)} / หมด {sum(p['quantity'] == 0 for p in alerts)} รายการ"
        self.alert_list.controls = [ft.Text("ทุกสินค้าอยู่ในระดับปลอดภัย", color="#087F5B")] if not alerts else [ft.Container(content=ft.Row(controls=[ft.Container(width=8, height=38, bgcolor="#F59E0B" if p["quantity"] else "#DC2626", border_radius=6), ft.Column(controls=[ft.Text(p["name"], weight=ft.FontWeight.W_600), ft.Text(f"เหลือ {p['quantity']} ชิ้น • {p['id']}", size=12, color=ft.Colors.GREY_700)], spacing=2)], spacing=10), padding=12, bgcolor="#FFF1F2" if p["quantity"] == 0 else "#FFFAEB", border_radius=10, on_click=lambda e, item=p: self.open_movement(item), tooltip="รับเข้า / เบิกออก") for p in alerts[:4]]
    def open_form(self, e=None):
        if self.form_dialog is not None and self.form_dialog.open:
            return
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
        if self.active_nav == "dashboard":
            self.render_dashboard()
        elif self.active_nav == "low_stock":
            self.main_content.controls = [self.hero(), self.back_to_inventory(), self.low_stock_panel()]
        self._page.update()

    def filter_status(self, status):
        self.search_field.value = ""
        self.category_filter.value = "ทั้งหมด"
        self.status_filter.value = status
        self.refresh_all()

    @staticmethod
    def table_width(width):
        width = width or 1280
        # Leave room for the persistent left navigation and the alert panel.
        return max(900, round((width - 380) * (0.75 if width >= 1500 else 1)))

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
        completed = False
        def save(e):
            nonlocal completed
            if completed:
                return
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
                completed = True
                self._page.pop_dialog()
                self.refresh_all()
                self.show_message("บันทึกการเคลื่อนไหวสต็อกแล้ว")
        self._page.show_dialog(ft.AlertDialog(modal=True, title=ft.Text(f"รับเข้า / เบิกออก: {product['name']}"), content=ft.Column(controls=[ft.Text(f"คงเหลือ {product['quantity']} ชิ้น"), kind, amount, reason], tight=True, width=400), actions=[ft.Button(content="ยกเลิก", on_click=lambda e: self._page.pop_dialog()), ft.Button(content="บันทึก", on_click=save)]))

    def show_history(self, e=None):
        self.show_history_page(e)

    def update_status_preview(self, e):
        try: self.status_group.value = calculate_status(max(0, int(self.quantity_field.value or "0")))
        except ValueError: self.status_group.value = "พร้อมขาย"
        self._page.update(self.status_group)
    def open_date_picker(self, e):
        if self.date_picker.open:
            return
        try:
            selected = datetime.strptime(self.date_field.value or "", "%d/%m/%Y")
        except ValueError:
            selected = datetime.now()
        # A dismissed dialog can remain mounted during its closing animation.
        # A fresh picker avoids reopening that same managed dialog instance.
        self.date_picker = ft.DatePicker(
            value=selected, first_date=datetime(2020, 1, 1),
            last_date=datetime(2035, 12, 31), modal=True,
            on_change=self.set_received_date,
            on_dismiss=self.dismiss_date_picker,
            help_text="เลือกวันที่รับสินค้าเข้าคลัง", confirm_text="เลือก", cancel_text="ยกเลิก",
        )
        self._page.show_dialog(self.date_picker)

    def dismiss_date_picker(self, e):
        picker = getattr(e, 'control', None) or self.date_picker
        picker.open = False

    def set_received_date(self, e):
        picker = getattr(e, 'control', None) or self.date_picker
        picker.open = False
        if picker.value:
            self.date_field.value = picker.value.strftime("%d/%m/%Y")
            self._page.update(self.date_field)
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
        # Reload before editing: the table can predate another stock movement.
        current = next((item for item in self.store.products() if item['id'] == p['id']), None)
        if current is None:
            self.refresh_all()
            self.show_message("สินค้านี้ถูกลบแล้ว กรุณาเลือกรายการใหม่")
            return
        p = current
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
