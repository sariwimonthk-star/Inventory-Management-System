"""Inventory grid with a stationary header and independently scrolling rows."""
import flet as ft


class InventoryTable(ft.Column):
    LABELS = ["รหัสสินค้า", "ชื่อสินค้า", "ประเภท", "ราคาต่อหน่วย", "คงเหลือ", "วันที่รับเข้า", "สถานะ", "จัดการ"]
    WEIGHTS = [8, 12, 16, 12, 7, 12, 12, 17]

    def __init__(self):
        self.header = ft.Container(
            content=self.grid_row([ft.Text(label, weight=ft.FontWeight.BOLD) for label in self.LABELS]),
            bgcolor="#F0F4FA", height=44, border_radius=8,
        )
        self.body = ft.ListView(height=390, spacing=0)
        super().__init__(controls=[self.header, self.body], spacing=0)
        self._rows = []

    def grid_row(self, cells):
        return ft.Row(controls=[
            ft.Container(content=cell, expand=weight, padding=8,
                         alignment=ft.Alignment.CENTER_RIGHT if i in (3, 4) else ft.Alignment.CENTER_LEFT)
            for i, (cell, weight) in enumerate(zip(cells, self.WEIGHTS))
        ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    @property
    def rows(self):
        return self._rows

    @rows.setter
    def rows(self, rows):
        self._rows = rows
        if not rows:
            self.body.controls = [ft.Container(
                content=ft.Column(controls=[
                    ft.Icon(ft.Icons.SEARCH_OFF, size=36, color="#94A3B8"),
                    ft.Text("ไม่พบสินค้า", size=16, weight=ft.FontWeight.W_600, color="#334155"),
                    ft.Text("ลองเปลี่ยนคำค้นหา หรือล้างตัวกรองด้วยปุ่มแสดงทั้งหมด", size=13, color="#64748B"),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                padding=40, alignment=ft.Alignment.CENTER,
            )]
            return
        self.body.controls = [ft.Container(
            content=self.grid_row([cell.content for cell in row.cells]),
            height=52, bgcolor="#FFFFFF" if index % 2 == 0 else "#F8FAFD",
            border=ft.Border.only(bottom=ft.BorderSide(1, "#EDF1F7")),
        ) for index, row in enumerate(rows)]
