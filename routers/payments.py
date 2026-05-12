from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from auth import get_current_user
from database import get_db
import stripe
import os

router = APIRouter(prefix="/payments")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
PRICE_BASIC = os.getenv("STRIPE_PRICE_BASIC", "")
PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "")

PLAN_PRICES = {"basic": PRICE_BASIC, "pro": PRICE_PRO}


@router.post("/checkout/{plan}")
async def create_checkout(plan: str, request: Request, user=Depends(get_current_user)):
    if plan not in PLAN_PRICES:
        raise HTTPException(400, "Plan inválido")

    db = get_db()
    user_row = db.execute("SELECT * FROM users WHERE id=?", (int(user["sub"]),)).fetchone()

    customer_id = user_row["stripe_customer_id"]
    if not customer_id:
        customer = stripe.Customer.create(email=user["email"], name=user["name"])
        customer_id = customer.id
        db.execute("UPDATE users SET stripe_customer_id=? WHERE id=?", (customer_id, int(user["sub"])))
        db.commit()
    db.close()

    base_url = str(request.base_url).rstrip("/")
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": PLAN_PRICES[plan], "quantity": 1}],
        mode="subscription",
        success_url=f"{base_url}/payments/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/precios",
        metadata={"user_id": str(int(user["sub"])), "plan": plan},
    )
    return JSONResponse({"url": session.url})


@router.get("/success")
def payment_success(session_id: str, user=Depends(get_current_user)):
    session = stripe.checkout.Session.retrieve(session_id)
    plan = session.metadata.get("plan", "basic")
    sub_id = session.subscription

    db = get_db()
    db.execute(
        "UPDATE users SET plan=?, stripe_subscription_id=?, subscription_status='active' WHERE id=?",
        (plan, sub_id, int(user["sub"]))
    )
    db.commit()
    db.close()
    return RedirectResponse("/dashboard?upgraded=1", status_code=302)


@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "Webhook inválido")

    if event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        db = get_db()
        db.execute(
            "UPDATE users SET plan='free', subscription_status='cancelled' WHERE stripe_subscription_id=?",
            (sub["id"],)
        )
        db.commit()
        db.close()

    return JSONResponse({"received": True})
