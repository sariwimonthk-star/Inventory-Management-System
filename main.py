import flet as ft

from views.inventory_view import InventoryView


def main(page: ft.Page):
    page.title = "Inventory-Management-System"
    page.padding = 0
    page.bgcolor = "#F6F8FC"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    page.window_min_width = 980
    page.window_min_height = 720
    page.add(InventoryView(page))


ft.run(main)
