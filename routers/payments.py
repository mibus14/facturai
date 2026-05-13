import os
import hmac
import hashlib
import httpx
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from auth import get_current_user
from database import get_db

router = APIRouter(prefix="/payments")

MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
MP_PLAN_BASIC_ID = os.getenv("MP_PLAN_BASIC_ID", "")
MP_PLAN_PRO_ID = os.getenv("MP_PLAN_PRO_ID", "")
MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")

PLAN_IDS = {"basic": MP_PLAN_BASIC_ID, "pro": MP_PLAN_PRO_ID}
PLAN_AMOUNTS = {"basic": 99, "pro": 199}

MP_API = "https://api.mercadopago.com"

# URLs de pago directo del plan (init_point de cada plan de MP)
_PLAN_URLS: dict = {}


def _mp_headers():
    return {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


async def _get_plan_url(plan: str) -> str:
    """Obtiene y cachea el init_point del plan desde la API de MP."""
    if plan in _PLAN_URLS:
        return _PLAN_URLS[plan]
    plan_id = PLAN_IDS.get(plan, "")
    if not plan_id:
        raise HTTPException(503, "Plan no configurado. Contacta al administrador.")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{MP_API}/preapproval_plan/{plan_id}", headers=_mp_headers())
    if resp.status_code != 200:
        raise HTTPException(503, f"Error al obtener el plan de Mercado Pago: {resp.text}")
    url = resp.json().get("init_point", "")
    if not url:
        raise HTTPException(503, "Mercado Pago no devolvió un link de pago.")
    _PLAN_URLS[plan] = url
    return url


@router.post("/checkout/{plan}")
async def create_checkout(plan: str, request: Request, user=Depends(get_current_user)):
    if plan not in PLAN_IDS:
        raise HTTPException(400, "Plan inválido")
    uid = int(user["sub"])
    db = get_db()
    user_row = db.execute("SELECT plan, subscription_status FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    if user_row and user_row["plan"] == plan and user_row["subscription_status"] == "active":
        raise HTTPException(400, "Ya tienes este plan activo. Si quieres cancelar, contáctanos.")
    url = await _get_plan_url(plan)
    return JSONResponse({"url": url})


@router.get("/success")
def payment_success(user=Depends(get_current_user)):
    return RedirectResponse("/dashboard?upgraded=1", status_code=302)


@router.post("/cancel")
async def cancel_subscription(user=Depends(get_current_user)):
    uid = int(user["sub"])
    db = get_db()
    user_row = db.execute(
        "SELECT mp_subscription_id, plan FROM users WHERE id=?", (uid,)
    ).fetchone()
    db.close()

    sub_id = user_row["mp_subscription_id"] if user_row else None
    if sub_id and user_row["plan"] != "free":
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                await client.put(
                    f"{MP_API}/preapproval/{sub_id}",
                    headers=_mp_headers(),
                    json={"status": "cancelled"},
                )
        except Exception:
            pass

    db = get_db()
    db.execute(
        "UPDATE users SET plan='free', subscription_status='cancelled', mp_subscription_id=NULL WHERE id=?",
        (uid,),
    )
    db.commit()
    db.close()
    return RedirectResponse("/dashboard?cancelled=1", status_code=302)


def _verify_mp_signature(request: Request, body: bytes) -> bool:
    if not MP_WEBHOOK_SECRET:
        return True
    sig_header = request.headers.get("x-signature", "")
    ts_header = request.headers.get("x-request-id", "")
    if not sig_header:
        return True
    parts = dict(p.split("=", 1) for p in sig_header.split(";") if "=" in p)
    received = parts.get("v1", "")
    data_id = (request.query_params.get("data.id") or
               request.query_params.get("id") or "")
    manifest = f"id:{data_id};request-id:{ts_header};ts:{parts.get('ts','')};"
    expected = hmac.new(
        MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(received, expected)


@router.post("/webhook")
async def mp_webhook(request: Request):
    body = await request.body()
    if not _verify_mp_signature(request, body):
        raise HTTPException(400, "Firma inválida")
    try:
        import json
        data = json.loads(body)
    except Exception:
        data = {}

    topic = data.get("type") or request.query_params.get("topic", "")
    resource_id = (data.get("data") or {}).get("id") or request.query_params.get("id", "")

    if not resource_id:
        return JSONResponse({"received": True})

    if topic == "subscription_preapproval":
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{MP_API}/preapproval/{resource_id}",
                headers=_mp_headers(),
            )
        if resp.status_code != 200:
            return JSONResponse({"received": True})

        sub = resp.json()
        status = sub.get("status", "")
        payer_email = sub.get("payer_email", "")
        plan_id = sub.get("preapproval_plan_id", "")

        # Determinar el plan por el plan_id de MP
        plan_name = "free"
        if plan_id == MP_PLAN_BASIC_ID:
            plan_name = "basic"
        elif plan_id == MP_PLAN_PRO_ID:
            plan_name = "pro"

        if payer_email:
            db = get_db()
            if status == "authorized":
                db.execute(
                    "UPDATE users SET plan=?, mp_subscription_id=?, subscription_status='active' WHERE email=?",
                    (plan_name, resource_id, payer_email),
                )
            elif status in ("cancelled", "paused"):
                db.execute(
                    "UPDATE users SET plan='free', subscription_status=? WHERE mp_subscription_id=?",
                    (status, resource_id),
                )
            db.commit()
            db.close()

    elif topic == "payment":
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{MP_API}/v1/payments/{resource_id}",
                headers=_mp_headers(),
            )
        if resp.status_code != 200:
            return JSONResponse({"received": True})

        payment = resp.json()
        payer_email = payment.get("payer", {}).get("email", "")
        if payer_email:
            db = get_db()
            user_row = db.execute("SELECT id FROM users WHERE email=?", (payer_email,)).fetchone()
            if user_row:
                db.execute(
                    """INSERT INTO payments (user_id, mp_payment_id, plan, amount, currency, status, payment_method)
                       VALUES (?, ?, ?, ?, 'MXN', ?, ?)""",
                    (
                        user_row["id"],
                        str(resource_id),
                        "subscription",
                        payment.get("transaction_amount", 0),
                        payment.get("status", ""),
                        payment.get("payment_type_id", ""),
                    ),
                )
                db.commit()
            db.close()

    return JSONResponse({"received": True})
