from dotenv import load_dotenv
load_dotenv()

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from database import init_db
from routers import pages, payments, ai

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_VERCEL = bool(os.getenv("VERCEL"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as e:
        print(f"[FacturAI] init_db warning: {e}", flush=True)
    yield


app = FastAPI(title="FacturAI", description="Facturación electrónica mexicana CFDI 4.0", lifespan=lifespan)

if not IS_VERCEL:
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

app.include_router(pages.router)
app.include_router(payments.router)
app.include_router(ai.router)
