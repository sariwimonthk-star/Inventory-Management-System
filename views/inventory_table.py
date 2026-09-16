"""Inventory grid with a stationary header and independently scrolling rows."""
import flet as ft


class InventoryTable(ft.Column):
    LABELS = ["รหัสสินค้า", "ชื่อสินค้า", "ประเภท", "ราคาต่อหน่วย", "คงเหลือ", "วันที่รับเข้า", "สถานะ", "จัดการ"]
    WEIGHTS = [9, 12, 18, 12, 8, 12, 12, 13]

    def __init__(self):
        self.header = ft.Container(
            content=self.grid_row([ft.Text(label, weight=ft.FontWeight.BOLD) for label in self.LABELS]),
            bgcolor="#E9EEFF", height=52,
        )
        self.body = ft.ListView(height=360, spacing=0)
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
        self.body.controls = [ft.Container(
            content=self.grid_row([cell.content for cell in row.cells]),
            height=60, border=ft.Border.only(bottom=ft.BorderSide(1, "#DFE5ED")),
        ) for row in rows]
