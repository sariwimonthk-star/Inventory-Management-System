import flet as ft

from views.inventory_view import InventoryView


def main(page: ft.Page):
    page.title = "Inventory-Management-System"
    page.padding = 0
    page.bgcolor = "#F6F8FC"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    page.window.min_width = 600
    page.window.min_height = 500
    page.add(InventoryView(page))


ft.run(main)
