from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import get_db
from auth import hash_password, verify_password, create_token, get_current_user, get_current_user_optional
import os

router = APIRouter()
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(_BASE, "templates"))

STRIPE_PK = os.getenv("STRIPE_PUBLISHABLE_KEY", "")

REGIMENES = {
    "601": "General de Ley Personas Morales",
    "603": "Personas Morales con Fines no Lucrativos",
    "605": "Sueldos y Salarios e Ingresos Asimilados",
    "606": "Arrendamiento",
    "608": "Demás ingresos",
    "612": "Personas Físicas con Actividades Empresariales y Profesionales",
    "616": "Sin obligaciones fiscales",
    "621": "Incorporación Fiscal",
    "625": "Actividades Empresariales con ingresos en Plataformas Tecnológicas",
    "626": "Régimen Simplificado de Confianza (RESICO)",
}

USOS_CFDI = {
    "G01": "Adquisición de mercancias",
    "G02": "Devoluciones, descuentos o bonificaciones",
    "G03": "Gastos en general",
    "I01": "Construcciones",
    "I02": "Mobilario y equipo de oficina por inversiones",
    "I03": "Equipo de transporte",
    "I04": "Equipo de cómputo y accesorios",
    "I08": "Otra maquinaria y equipo",
    "D01": "Honorarios médicos, dentales y gastos hospitalarios",
    "D03": "Gastos funerales",
    "D04": "Donativo",
    "D07": "Primas por seguros de gastos médicos",
    "D10": "Pagos por servicios educativos (colegiaturas)",
    "S01": "Sin efectos fiscales",
    "CP01": "Pagos",
    "P01": "Por definir",
}

FORMAS_PAGO = {
    "01": "Efectivo",
    "02": "Cheque nominativo",
    "03": "Transferencia electrónica de fondos",
    "04": "Tarjeta de crédito",
    "05": "Monedero electrónico",
    "06": "Dinero electrónico",
    "28": "Tarjeta de débito",
    "29": "Tarjeta de servicios",
    "99": "Por definir",
}


@router.get("/", response_class=HTMLResponse)
def landing(request: Request, user=Depends(get_current_user_optional)):
    return templates.TemplateResponse(request, "landing.html", {"user": user, "stripe_pk": STRIPE_PK})


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"error": None, "regimenes": REGIMENES})


@router.post("/register")
def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    rfc: str = Form(""),
    regimen_fiscal: str = Form("612"),
    cp: str = Form(""),
):
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        db.close()
        return templates.TemplateResponse(request, "register.html", {
            "error": "El email ya está registrado.", "regimenes": REGIMENES
        })
    db.execute(
        "INSERT INTO users (name, email, password_hash, rfc, regimen_fiscal, cp) VALUES (?,?,?,?,?,?)",
        (name, email, hash_password(password), rfc.upper().strip(), regimen_fiscal, cp.strip()),
    )
    db.commit()
    user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    db.close()
    token = create_token({
        "sub": str(user["id"]), "email": user["email"],
        "name": user["name"], "plan": user["plan"],
    })
    resp = RedirectResponse("/dashboard", status_code=302)
    resp.set_cookie("session", token, httponly=True, max_age=60 * 60 * 24 * 7)
    return resp


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    db.close()
    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(request, "login.html", {"error": "Email o contraseña incorrectos."})
    token = create_token({
        "sub": str(user["id"]), "email": user["email"],
        "name": user["name"], "plan": user["plan"],
    })
    resp = RedirectResponse("/dashboard", status_code=302)
    resp.set_cookie("session", token, httponly=True, max_age=60 * 60 * 24 * 7)
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie("session")
    return resp


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user=Depends(get_current_user)):
    uid = int(user["sub"])
    db = get_db()
    user_row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    invoices = db.execute(
        "SELECT * FROM invoices WHERE user_id=? ORDER BY created_at DESC LIMIT 10", (uid,)
    ).fetchall()
    db.close()
    return templates.TemplateResponse(request, "dashboard.html", {
        "user": dict(user_row),
        "invoices": [dict(i) for i in invoices],
    })


@router.get("/perfil", response_class=HTMLResponse)
def perfil_page(request: Request, user=Depends(get_current_user)):
    uid = int(user["sub"])
    db = get_db()
    user_row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    return templates.TemplateResponse(request, "perfil.html", {
        "user": dict(user_row), "regimenes": REGIMENES, "saved": False,
    })


@router.post("/perfil")
def perfil_save(
    request: Request,
    user=Depends(get_current_user),
    name: str = Form(...),
    rfc: str = Form(""),
    regimen_fiscal: str = Form("612"),
    cp: str = Form(""),
):
    uid = int(user["sub"])
    db = get_db()
    db.execute(
        "UPDATE users SET name=?, rfc=?, regimen_fiscal=?, cp=? WHERE id=?",
        (name, rfc.upper().strip(), regimen_fiscal, cp.strip(), uid),
    )
    db.commit()
    user_row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    return templates.TemplateResponse(request, "perfil.html", {
        "user": dict(user_row), "regimenes": REGIMENES, "saved": True,
    })


@router.get("/facturas/nueva", response_class=HTMLResponse)
def nueva_factura(request: Request, user=Depends(get_current_user)):
    uid = int(user["sub"])
    db = get_db()
    user_row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    plan = user_row["plan"]
    count = user_row["invoices_created"]
    if plan == "free" and count >= 1:
        return RedirectResponse("/precios?upgrade=1", status_code=302)
    return templates.TemplateResponse(request, "nueva_factura.html", {
        "user": dict(user_row),
        "regimenes": REGIMENES,
        "usos_cfdi": USOS_CFDI,
        "formas_pago": FORMAS_PAGO,
    })


@router.post("/facturas/nueva")
def crear_factura(
    request: Request,
    user=Depends(get_current_user),
    client_name: str = Form(...),
    client_email: str = Form(""),
    client_address: str = Form(""),
    rfc_receptor: str = Form(""),
    regimen_fiscal_receptor: str = Form("616"),
    cp_receptor: str = Form(""),
    uso_cfdi: str = Form("G03"),
    forma_pago: str = Form("03"),
    metodo_pago: str = Form("PUE"),
    issue_date: str = Form(...),
    due_date: str = Form(""),
    items_json: str = Form(...),
    subtotal: float = Form(...),
    tax_rate: float = Form(16),
    tax_amount: float = Form(0),
    total: float = Form(...),
    notes: str = Form(""),
):
    import json
    uid = int(user["sub"])
    db = get_db()
    user_row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    plan = user_row["plan"]
    count = user_row["invoices_created"]
    if plan == "free" and count >= 1:
        db.close()
        return RedirectResponse("/precios?upgrade=1", status_code=302)

    invoice_number = f"A-{uid:04d}{count + 1:04d}"
    db.execute("""
        INSERT INTO invoices (
            user_id, invoice_number, client_name, client_email, client_address,
            rfc_receptor, regimen_fiscal_receptor, cp_receptor,
            uso_cfdi, forma_pago, metodo_pago, moneda,
            issue_date, due_date, items, subtotal, tax_rate, tax_amount, total, notes, status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'MXN',?,?,?,?,?,?,?,?,'sent')
    """, (
        uid, invoice_number, client_name, client_email, client_address,
        rfc_receptor.upper().strip(), regimen_fiscal_receptor, cp_receptor.strip(),
        uso_cfdi, forma_pago, metodo_pago,
        issue_date, due_date, items_json, subtotal, tax_rate, tax_amount, total, notes,
    ))
    db.execute("UPDATE users SET invoices_created=invoices_created+1 WHERE id=?", (uid,))
    db.commit()
    inv_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()
    return RedirectResponse(f"/facturas/{inv_id}", status_code=302)


@router.get("/facturas/{inv_id}", response_class=HTMLResponse)
def ver_factura(inv_id: int, request: Request, user=Depends(get_current_user)):
    uid = int(user["sub"])
    db = get_db()
    inv = db.execute("SELECT * FROM invoices WHERE id=? AND user_id=?", (inv_id, uid)).fetchone()
    user_row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    if not inv:
        raise HTTPException(404)
    import json
    items = json.loads(inv["items"])
    inv_dict = dict(inv)
    return templates.TemplateResponse(request, "ver_factura.html", {
        "inv": inv_dict,
        "items": items,
        "user": dict(user_row),
        "regimenes": REGIMENES,
        "usos_cfdi": USOS_CFDI,
        "formas_pago": FORMAS_PAGO,
    })


@router.get("/precios", response_class=HTMLResponse)
def precios(request: Request, upgrade: int = 0, user=Depends(get_current_user_optional)):
    return templates.TemplateResponse(request, "precios.html", {
        "user": user, "stripe_pk": STRIPE_PK, "upgrade": upgrade,
    })
