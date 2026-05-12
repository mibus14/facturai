#!/bin/bash
cd "$(dirname "$0")"
echo "Iniciando FacturAI en http://localhost:8000"
./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
