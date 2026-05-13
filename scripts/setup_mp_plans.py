"""
Run once to create the Mercado Pago subscription plans.
Usage: MP_ACCESS_TOKEN=... python scripts/setup_mp_plans.py

Copy the returned IDs to your .env or Vercel environment variables:
  MP_PLAN_BASIC_ID=...
  MP_PLAN_PRO_ID=...
"""
import httpx
import os
import json

ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
if not ACCESS_TOKEN:
    raise SystemExit("Falta MP_ACCESS_TOKEN en el entorno")

MP_API = "https://api.mercadopago.com"
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}

PLANS = [
    {
        "reason": "FacturAI Básico",
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": 199,
            "currency_id": "MXN",
        },
        "back_url": "https://facturai-three.vercel.app/payments/success",
        "status": "active",
    },
    {
        "reason": "FacturAI Pro",
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": 399,
            "currency_id": "MXN",
        },
        "back_url": "https://facturai-three.vercel.app/payments/success",
        "status": "active",
    },
]

plan_names = ["basic", "pro"]

for name, plan in zip(plan_names, PLANS):
    resp = httpx.post(f"{MP_API}/preapproval_plan", json=plan, headers=HEADERS)
    if resp.status_code in (200, 201):
        plan_id = resp.json()["id"]
        key = f"MP_PLAN_{name.upper()}_ID"
        print(f"{key}={plan_id}")
    else:
        print(f"Error creando plan {name}: {resp.status_code} {resp.text}")
