import flet as ft


class LoginView(ft.Container):
    def __init__(self, page, accounts, on_login):
        self.username = ft.TextField(label="ชื่อผู้ใช้", prefix_icon=ft.Icons.PERSON)
        self.password = ft.TextField(label="รหัสผ่าน", password=True, can_reveal_password=True)
        self.error = ft.Text(color="#B91C1C")
        def submit(e):
            try:
                session = accounts.login(self.username.value or '', self.password.value or '')
            except ValueError as error:
                self.error.value = str(error)
                page.update()
                return
            self.password.value = ''
            on_login(session)
        self.password.on_submit = submit
        def demo_login(e):
            self.username.value = 'owner'
            self.password.value = 'Owner@2026'
            submit(e)
        self.demo_button = ft.Button(
            content="เข้าระบบผู้ดูแลคลัง (สาธิต)",
            icon=ft.Icons.PLAY_ARROW_ROUNDED,
            on_click=demo_login, bgcolor="#FFF3CD", color="#785000", width=350,
        )
        super().__init__(expand=True, alignment=ft.Alignment.CENTER, bgcolor="#F6F8FC", padding=24,
            content=ft.Container(width=420, padding=32, bgcolor="#FFFFFF", border_radius=20,
                content=ft.Column(controls=[
                    ft.Icon(ft.Icons.WAREHOUSE_ROUNDED, size=48, color="#334EAC"),
                    ft.Text("เข้าสู่ระบบคลังสินค้า", size=26, weight=ft.FontWeight.BOLD),
                    ft.Text("สำหรับผู้ดูแลคลังสินค้า", color="#64748B"),
                    self.username, self.password, self.error,
                    ft.Button(content="เข้าสู่ระบบ", icon=ft.Icons.LOGIN, on_click=submit, bgcolor="#334EAC", color="#FFFFFF", width=350),
                    ft.Divider(height=1),
                    self.demo_button,
                    ft.Text("สำหรับพรีเซน · ใช้บัญชี owner โดยไม่ต้องพิมพ์", size=12, color="#64748B"),
                ], tight=True, spacing=18)))
