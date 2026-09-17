import tempfile
import unittest
from pathlib import Path
from auth import Accounts, password_hash
from views.inventory_view import InventoryView
from views.login_view import LoginView
from test_inventory import PageStub


class AuthTests(unittest.TestCase):
    def test_demo_button_logs_in_as_existing_admin(self):
        with tempfile.TemporaryDirectory() as folder:
            accounts = Accounts(Path(folder) / 'test.db')
            sessions = []
            view = LoginView(PageStub(), accounts, sessions.append)
            view.demo_button.on_click(None)
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].user['username'], 'owner')
            self.assertEqual(sessions[0].user['role'], 'admin')
            self.assertEqual(view.password.value, '')

    def test_admin_login_crud_and_logout(self):
        with tempfile.TemporaryDirectory() as folder:
            accounts = Accounts(Path(folder) / 'test.db')
            for username, password in [('owner', 'wrong'), ('staff', 'Staff@2026')]:
                with self.assertRaises(ValueError):
                    accounts.login(username, password)
            admin = accounts.login('owner', 'Owner@2026')
            self.assertEqual(admin.user['role'], 'admin')
            product = admin.products()[0]
            pid = admin.save(product)
            admin.adjust(pid, 2, 'delivery')
            admin.delete(pid)
            self.assertEqual(len(admin.history()), 3)
            view = InventoryView(PageStub(), store=admin, on_logout=lambda: None)
            self.assertNotIn('users', view.nav_controls)
            self.assertTrue(view.table.rows[0].cells[-1].content.controls[1].visible)
            LoginView(PageStub(), accounts, lambda session: None)
            admin.valid = False
            with self.assertRaises(ValueError):
                admin.products()

    def test_legacy_staff_disabled_and_history_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.db'
            accounts = Accounts(path)
            with accounts.store.connect() as db:
                db.execute("UPDATE users SET role='owner' WHERE username='owner'")
                salt = 'ab' * 16
                db.execute("INSERT INTO users VALUES ('staff','Staff','staff',?,?,1)", (salt, password_hash('Staff@2026', salt)))
                db.execute("INSERT INTO movements(product_id,name,delta,balance,reason,actor) VALUES ('P001','Mouse',1,20,'legacy','staff')")
            migrated = Accounts(path)
            with self.assertRaises(ValueError):
                migrated.login('staff', 'Staff@2026')
            admin = migrated.login('owner', 'Owner@2026')
            self.assertEqual(admin.user['role'], 'admin')
            self.assertEqual(admin.history()[0]['actor'], 'staff')
            self.assertEqual(len(admin.products()), 5)
            with migrated.store.connect() as db:
                self.assertEqual(db.execute("SELECT active FROM users WHERE username='staff'").fetchone()[0], 0)
