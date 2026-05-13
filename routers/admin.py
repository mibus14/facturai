import os
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from auth import verify_password, create_token, decode_token, hash_password
from database import get_db
from typing import Optional

router = APIRouter(prefix="/api/admin")

SETUP_KEY = os.getenv("ADMIN_SETUP_KEY", "")


@router.post("/first-setup")
def first_setup(body: dict):
    """Endpoint temporal: marca un usuario como admin. Requiere ADMIN_SETUP_KEY."""
    if not SETUP_KEY or body.get("key") != SETUP_KEY:
        raise HTTPException(403, "Clave inválida")
    email = body.get("email", "")
    if not email:
        raise HTTPException(400, "Email requerido")
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        db.execute("UPDATE users SET is_admin=1 WHERE email=?", (email,))
        db.commit()
        db.close()
        return {"ok": True, "msg": f"{email} ahora es admin"}
    # Si no existe, lo crea
    password = body.get("password", "")
    name = body.get("name", "Admin")
    if not password:
        raise HTTPException(400, "El usuario no existe, incluye 'password' para crearlo")
    db.execute(
        """INSERT INTO users (name, email, password_hash, plan, subscription_status, is_admin)
           VALUES (?, ?, ?, 'free', 'inactive', 1)""",
        (name, email, hash_password(password)),
    )
    db.commit()
    db.close()
    return {"ok": True, "msg": f"Admin creado: {email}"}


def _get_admin(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Token requerido")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(401, "Token inválido o expirado")

    db = get_db()
    row = db.execute("SELECT is_admin FROM users WHERE id=?", (int(payload["sub"]),)).fetchone()
    db.close()

    if not row or not row["is_admin"]:
        raise HTTPException(403, "Acceso denegado")
    return payload


@router.post("/login")
def admin_login(body: dict):
    email = body.get("email", "")
    password = body.get("password", "")
    if not email or not password:
        raise HTTPException(400, "Email y contraseña requeridos")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    db.close()

    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Credenciales incorrectas")
    if not user["is_admin"]:
        raise HTTPException(403, "No tienes acceso de administrador")

    token = create_token({"sub": str(user["id"]), "email": user["email"], "name": user["name"]})
    return JSONResponse({"token": token, "name": user["name"]})


@router.get("/stats")
def get_stats(admin=Depends(_get_admin)):
    db = get_db()
    total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active_subs = db.execute(
        "SELECT COUNT(*) FROM users WHERE subscription_status='active'"
    ).fetchone()[0]
    basic_subs = db.execute(
        "SELECT COUNT(*) FROM users WHERE plan='basic' AND subscription_status='active'"
    ).fetchone()[0]
    pro_subs = db.execute(
        "SELECT COUNT(*) FROM users WHERE plan='pro' AND subscription_status='active'"
    ).fetchone()[0]
    total_invoices = db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
    revenue_row = db.execute(
        "SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='approved'"
    ).fetchone()
    db.close()

    monthly_revenue = (basic_subs * 199) + (pro_subs * 399)
    return {
        "total_users": total_users,
        "active_subscriptions": active_subs,
        "basic_subscriptions": basic_subs,
        "pro_subscriptions": pro_subs,
        "total_invoices": total_invoices,
        "total_revenue": float(revenue_row[0]),
        "monthly_revenue": monthly_revenue,
    }


@router.get("/users")
def get_users(admin=Depends(_get_admin)):
    db = get_db()
    rows = db.execute(
        """SELECT id, name, email, plan, subscription_status, invoices_created,
                  mp_subscription_id, created_at
           FROM users ORDER BY created_at DESC"""
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.get("/payments")
def get_payments(admin=Depends(_get_admin)):
    db = get_db()
    rows = db.execute(
        """SELECT p.id, u.name as user_name, u.email, p.plan, p.amount, p.currency,
                  p.status, p.payment_method, p.mp_payment_id, p.created_at
           FROM payments p
           LEFT JOIN users u ON p.user_id = u.id
           ORDER BY p.created_at DESC LIMIT 200"""
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]


@router.post("/users/{user_id}/plan")
def update_user_plan(user_id: int, body: dict, admin=Depends(_get_admin)):
    plan = body.get("plan", "")
    if plan not in ("free", "basic", "pro"):
        raise HTTPException(400, "Plan inválido")
    db = get_db()
    db.execute("UPDATE users SET plan=? WHERE id=?", (plan, user_id))
    db.commit()
    db.close()
    return {"ok": True}
