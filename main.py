import flet as ft

from views.inventory_view import InventoryView


def main(page: ft.Page):
    page.title = "ระบบจัดการคลังสินค้า"
    page.padding = 0
    page.add(InventoryView(page))


ft.run(main)
