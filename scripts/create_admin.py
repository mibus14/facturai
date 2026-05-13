"""
Crea o actualiza tu usuario admin en la BD local.
Uso: python scripts/create_admin.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db, get_db
from auth import hash_password
import getpass

init_db()

email = input("Email: ").strip()
name = input("Nombre: ").strip()
password = getpass.getpass("Contraseña: ")

db = get_db()
existing = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()

if existing:
    db.execute(
        "UPDATE users SET is_admin=1, password_hash=?, name=? WHERE email=?",
        (hash_password(password), name, email),
    )
    print(f"✅ Usuario actualizado como admin: {email}")
else:
    db.execute(
        """INSERT INTO users (name, email, password_hash, plan, subscription_status, is_admin)
           VALUES (?, ?, ?, 'free', 'inactive', 1)""",
        (name, email, hash_password(password)),
    )
    print(f"✅ Admin creado: {email}")

db.commit()
db.close()
