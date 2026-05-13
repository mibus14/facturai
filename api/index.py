import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import app
from database import init_db

try:
    init_db()
except Exception as e:
    print(f"[FacturAI] init_db warning: {e}", flush=True)
