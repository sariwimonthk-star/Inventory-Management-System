import flet as ft

from views.inventory_view import InventoryView
from views.login_view import LoginView
from auth import Accounts


def main(page: ft.Page):
    page.title = "คลังสินค้า | Inventory Management"
    page.padding = 0
    page.bgcolor = "#F6F8FC"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    page.window.min_width = 600
    page.window.min_height = 500
    accounts = Accounts()
    session = None
    def login(current):
        nonlocal session
        session = current
        page.controls.clear()
        page.add(InventoryView(page, store=session, on_logout=logout))

    def logout():
        nonlocal session
        if session:
            session.valid = False
        session = None
        page.on_resize = None
        while page.pop_dialog() is not None:
            pass
        page.controls.clear()
        page.add(LoginView(page, accounts, login))

    logout()


ft.run(main)
