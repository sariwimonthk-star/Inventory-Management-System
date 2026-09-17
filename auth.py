"""Local accounts and permission-checked sessions for the classroom app."""
import hashlib
import hmac
import secrets
from storage import InventoryStore


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 200_000).hex()


class Accounts:
    def __init__(self, path=None):
        self.store = InventoryStore(path)
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY COLLATE NOCASE, name TEXT NOT NULL, role TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1)')
            if not db.execute("SELECT 1 FROM settings WHERE key='accounts_seeded'").fetchone():
                for username, name, role, password in [('owner', 'ผู้ดูแลคลัง', 'admin', 'Owner@2026')]:
                    salt = secrets.token_hex(16)
                    db.execute('INSERT INTO users VALUES (?,?,?,?,?,1)', (username, name, role, salt, password_hash(password, salt),))
                db.execute("INSERT INTO settings VALUES ('accounts_seeded')")

            db.execute("UPDATE users SET role='admin', name=CASE WHEN name='เจ้าของคลัง' THEN 'ผู้ดูแลคลัง' ELSE name END WHERE role='owner'")
            db.execute("UPDATE users SET active=0 WHERE role!='admin'")

    def login(self, username, password):
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM users WHERE username=? AND active=1 AND role='admin'", (username.strip(),)).fetchone()
        if row is None or not hmac.compare_digest(row['password_hash'], password_hash(password, row['salt'])):
            raise ValueError('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
        return Session(self.store.path, dict(row))


class Session(InventoryStore):
    def __init__(self, path, user):
        super().__init__(path)
        self.user = {key: user[key] for key in ('username', 'name', 'role')}
        self.actor = self.user['username']
        self.valid = True

    def require(self):
        with self.connect() as db:
            row = db.execute('SELECT active,role FROM users WHERE username=?', (self.actor,)).fetchone()
        if not self.valid or not row or not row['active'] or row['role'] != 'admin':
            raise ValueError('ไม่มีสิทธิ์ใช้งาน กรุณาเข้าสู่ระบบด้วยบัญชีที่มีสิทธิ์')

    def products(self):
        self.require()
        return super().products()

    def save(self, *args, **kwargs):
        self.require()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.require()
        return super().delete(*args, **kwargs)

    def adjust(self, *args, **kwargs):
        self.require()
        return super().adjust(*args, **kwargs)

    def history(self):
        self.require()
        return super().history()
