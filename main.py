from dotenv import load_dotenv
load_dotenv()

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from database import init_db
from routers import pages, payments, ai

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="FacturAI", description="Facturación electrónica mexicana CFDI 4.0")

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

app.include_router(pages.router)
app.include_router(payments.router)
app.include_router(ai.router)


@app.on_event("startup")
def startup():
    init_db()
