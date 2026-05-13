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
PLAN_AMOUNTS = {"basic": 199, "pro": 399}

MP_API = "https://api.mercadopago.com"


def _mp_headers():
    return {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


@router.post("/checkout/{plan}")
async def create_checkout(plan: str, request: Request, user=Depends(get_current_user)):
    if plan not in PLAN_IDS:
        raise HTTPException(400, "Plan inválido")

    plan_id = PLAN_IDS.get(plan)
    if not plan_id:
        raise HTTPException(503, "Plan de MP no configurado. Contacta al administrador.")

    base_url = str(request.base_url).rstrip("/")

    payload = {
        "preapproval_plan_id": plan_id,
        "payer_email": user["email"],
        "back_url": f"{base_url}/payments/success",
        "external_reference": f"{user['sub']}|{plan}",
        "status": "pending",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{MP_API}/preapproval",
            json=payload,
            headers=_mp_headers(),
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(500, f"Error Mercado Pago: {resp.text}")

    data = resp.json()
    sub_id = data["id"]
    init_point = data["init_point"]

    db = get_db()
    db.execute(
        "UPDATE users SET mp_subscription_id=? WHERE id=?",
        (sub_id, int(user["sub"])),
    )
    db.commit()
    db.close()

    return JSONResponse({"url": init_point})


@router.get("/success")
def payment_success(user=Depends(get_current_user)):
    return RedirectResponse("/dashboard?upgraded=1", status_code=302)


def _verify_mp_signature(request: Request, body: bytes) -> bool:
    """Verifica la firma x-signature que manda Mercado Pago."""
    if not MP_WEBHOOK_SECRET:
        return True  # Sin secret configurado, aceptar (para desarrollo)
    sig_header = request.headers.get("x-signature", "")
    ts_header = request.headers.get("x-request-id", "")
    if not sig_header:
        return True
    # Formato: ts=<timestamp>;v1=<hash>
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
        external_ref = sub.get("external_reference", "")
        status = sub.get("status", "")

        if "|" in external_ref:
            user_id, plan = external_ref.split("|", 1)
            db = get_db()
            if status == "authorized":
                db.execute(
                    "UPDATE users SET plan=?, mp_subscription_id=?, subscription_status='active' WHERE id=?",
                    (plan, resource_id, int(user_id)),
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
        external_ref = payment.get("external_reference", "")
        if "|" in external_ref:
            user_id, plan = external_ref.split("|", 1)
            db = get_db()
            db.execute(
                """INSERT INTO payments (user_id, mp_payment_id, plan, amount, currency, status, payment_method)
                   VALUES (?, ?, ?, ?, 'MXN', ?, ?)""",
                (
                    int(user_id),
                    str(resource_id),
                    plan,
                    payment.get("transaction_amount", 0),
                    payment.get("status", ""),
                    payment.get("payment_type_id", ""),
                ),
            )
            db.commit()
            db.close()

    return JSONResponse({"received": True})
