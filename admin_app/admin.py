"""
FacturAI Admin — app de escritorio para gestionar usuarios y suscripciones.
Requiere: pip install customtkinter requests

Uso: python admin_app/admin.py
"""
import customtkinter as ctk
import requests
import threading
from tkinter import ttk, messagebox
import tkinter as tk
from datetime import datetime

API_URL = "https://facturai-three.vercel.app"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg": "#0f1117",
    "card": "#1a1d2e",
    "accent": "#6c63ff",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "text": "#e2e8f0",
    "muted": "#64748b",
    "border": "#2d3148",
}


class FacturAIAdmin(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.token = None
        self.title("FacturAI Admin")
        self.geometry("1200x750")
        self.minsize(900, 600)
        self.configure(fg_color=COLORS["bg"])
        self._show_login()

    # ──────────────────────────────── LOGIN ────────────────────────────────

    def _show_login(self):
        self._clear()
        frame = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=16, width=400)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        frame.grid_propagate(False)
        frame.configure(width=400, height=440)

        ctk.CTkLabel(frame, text="⚡ FacturAI", font=("Inter", 28, "bold"),
                     text_color=COLORS["accent"]).place(relx=0.5, rely=0.15, anchor="center")
        ctk.CTkLabel(frame, text="Panel de Administración",
                     font=("Inter", 13), text_color=COLORS["muted"]).place(relx=0.5, rely=0.27, anchor="center")

        self._email_var = ctk.StringVar()
        self._pass_var = ctk.StringVar()
        self._err_var = ctk.StringVar()

        ctk.CTkEntry(frame, textvariable=self._email_var, placeholder_text="Correo electrónico",
                     width=300, height=42, corner_radius=8).place(relx=0.5, rely=0.44, anchor="center")
        ctk.CTkEntry(frame, textvariable=self._pass_var, placeholder_text="Contraseña",
                     show="•", width=300, height=42, corner_radius=8).place(relx=0.5, rely=0.58, anchor="center")

        self._err_label = ctk.CTkLabel(frame, textvariable=self._err_var,
                                       text_color=COLORS["danger"], font=("Inter", 11))
        self._err_label.place(relx=0.5, rely=0.68, anchor="center")

        self._login_btn = ctk.CTkButton(frame, text="Entrar", width=300, height=42,
                                        corner_radius=8, fg_color=COLORS["accent"],
                                        command=self._do_login)
        self._login_btn.place(relx=0.5, rely=0.80, anchor="center")
        self.bind("<Return>", lambda _: self._do_login())

    def _do_login(self):
        self._login_btn.configure(state="disabled", text="Verificando...")
        self._err_var.set("")
        threading.Thread(target=self._login_thread, daemon=True).start()

    def _login_thread(self):
        try:
            resp = requests.post(
                f"{API_URL}/api/admin/login",
                json={"email": self._email_var.get(), "password": self._pass_var.get()},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data["token"]
                self.admin_name = data.get("name", "Admin")
                self.after(0, self._show_dashboard)
            else:
                msg = resp.json().get("detail", "Error de autenticación")
                self.after(0, lambda: self._login_error(msg))
        except Exception as e:
            self.after(0, lambda: self._login_error(f"Sin conexión: {e}"))

    def _login_error(self, msg):
        self._err_var.set(msg)
        self._login_btn.configure(state="normal", text="Entrar")

    # ──────────────────────────────── DASHBOARD ────────────────────────────────

    def _show_dashboard(self):
        self._clear()
        self._build_sidebar()
        self._content = ctk.CTkFrame(self, fg_color=COLORS["bg"])
        self._content.place(x=220, y=0, relwidth=1.0, relheight=1.0)
        self._content.configure(width=self.winfo_width() - 220)
        self._show_tab("inicio")

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, fg_color=COLORS["card"], width=210, corner_radius=0)
        sidebar.place(x=0, y=0, relheight=1.0)
        sidebar.pack_propagate(False)

        ctk.CTkLabel(sidebar, text="⚡ FacturAI", font=("Inter", 20, "bold"),
                     text_color=COLORS["accent"]).pack(pady=(28, 4))
        ctk.CTkLabel(sidebar, text="Admin Panel", font=("Inter", 11),
                     text_color=COLORS["muted"]).pack(pady=(0, 28))

        self._nav_btns = {}
        tabs = [
            ("inicio", "🏠  Inicio"),
            ("usuarios", "👥  Usuarios"),
            ("pagos", "💳  Pagos"),
        ]
        for key, label in tabs:
            btn = ctk.CTkButton(
                sidebar, text=label, width=180, height=40, anchor="w",
                fg_color="transparent", hover_color=COLORS["border"],
                text_color=COLORS["text"], font=("Inter", 13),
                command=lambda k=key: self._show_tab(k),
            )
            btn.pack(pady=2, padx=12)
            self._nav_btns[key] = btn

        ctk.CTkButton(
            sidebar, text="🚪  Salir", width=180, height=36, anchor="w",
            fg_color="transparent", hover_color="#3d1515",
            text_color=COLORS["muted"], font=("Inter", 12),
            command=self._logout,
        ).pack(side="bottom", pady=20, padx=12)

        ctk.CTkLabel(sidebar, text=f"Hola, {getattr(self, 'admin_name', 'Admin')}",
                     font=("Inter", 11), text_color=COLORS["muted"]).pack(side="bottom", pady=4)

    def _show_tab(self, tab: str):
        for k, btn in self._nav_btns.items():
            btn.configure(fg_color=COLORS["accent"] if k == tab else "transparent")
        for widget in self._content.winfo_children():
            widget.destroy()
        if tab == "inicio":
            self._render_inicio()
        elif tab == "usuarios":
            self._render_usuarios()
        elif tab == "pagos":
            self._render_pagos()

    # ──────────────────────────────── INICIO (Stats) ────────────────────────────────

    def _render_inicio(self):
        frame = self._content
        ctk.CTkLabel(frame, text="Dashboard", font=("Inter", 22, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=30, pady=(28, 20))

        self._stat_vars = {
            "total_users": ctk.StringVar(value="—"),
            "active_subscriptions": ctk.StringVar(value="—"),
            "monthly_revenue": ctk.StringVar(value="—"),
            "total_invoices": ctk.StringVar(value="—"),
        }
        stat_cards = [
            ("total_users", "👥 Usuarios", COLORS["accent"]),
            ("active_subscriptions", "✅ Suscripciones activas", COLORS["success"]),
            ("monthly_revenue", "💰 Ingresos mensuales", COLORS["warning"]),
            ("total_invoices", "🧾 Facturas generadas", COLORS["muted"]),
        ]

        cards_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cards_frame.pack(fill="x", padx=30)
        for i, (key, label, color) in enumerate(stat_cards):
            card = ctk.CTkFrame(cards_frame, fg_color=COLORS["card"], corner_radius=12, height=110)
            card.grid(row=0, column=i, padx=8, pady=4, sticky="ew")
            cards_frame.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(card, text=label, font=("Inter", 11), text_color=COLORS["muted"]).pack(anchor="w", padx=16, pady=(16, 4))
            ctk.CTkLabel(card, textvariable=self._stat_vars[key],
                         font=("Inter", 26, "bold"), text_color=color).pack(anchor="w", padx=16)

        self._refresh_btn = ctk.CTkButton(frame, text="↻  Actualizar", width=140, height=36,
                                          fg_color=COLORS["accent"], corner_radius=8,
                                          command=self._load_stats)
        self._refresh_btn.pack(anchor="w", padx=30, pady=20)

        self._plan_label = ctk.CTkLabel(frame, text="", font=("Inter", 12), text_color=COLORS["muted"])
        self._plan_label.pack(anchor="w", padx=30)

        self._load_stats()

    def _load_stats(self):
        threading.Thread(target=self._stats_thread, daemon=True).start()

    def _stats_thread(self):
        try:
            resp = requests.get(
                f"{API_URL}/api/admin/stats",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                d = resp.json()
                self.after(0, lambda: self._update_stats(d))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _update_stats(self, d):
        self._stat_vars["total_users"].set(str(d["total_users"]))
        self._stat_vars["active_subscriptions"].set(str(d["active_subscriptions"]))
        self._stat_vars["monthly_revenue"].set(f"${d['monthly_revenue']:,.0f} MXN")
        self._stat_vars["total_invoices"].set(str(d["total_invoices"]))
        self._plan_label.configure(
            text=f"Básico: {d['basic_subscriptions']}   |   Pro: {d['pro_subscriptions']}   |   "
                 f"Ingresos totales: ${d['total_revenue']:,.2f} MXN"
        )

    # ──────────────────────────────── USUARIOS ────────────────────────────────

    def _render_usuarios(self):
        frame = self._content
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(28, 12))
        ctk.CTkLabel(header, text="Usuarios", font=("Inter", 22, "bold"),
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(header, text="↻ Actualizar", width=110, height=32,
                      fg_color=COLORS["accent"], corner_radius=8,
                      command=self._load_usuarios).pack(side="right")

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_usuarios())
        search = ctk.CTkEntry(frame, textvariable=self._search_var,
                              placeholder_text="Buscar por nombre o email...",
                              width=350, height=36, corner_radius=8)
        search.pack(anchor="w", padx=30, pady=(0, 12))

        cols = ("id", "name", "email", "plan", "status", "facturas", "registrado")
        self._user_tree = self._make_tree(frame, cols, (40, 160, 220, 70, 100, 70, 120))
        self._user_data = []
        self._load_usuarios()

    def _load_usuarios(self):
        threading.Thread(target=self._usuarios_thread, daemon=True).start()

    def _usuarios_thread(self):
        try:
            resp = requests.get(
                f"{API_URL}/api/admin/users",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                self._user_data = resp.json()
                self.after(0, self._fill_usuarios)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _fill_usuarios(self):
        self._filter_usuarios()

    def _filter_usuarios(self):
        q = self._search_var.get().lower()
        tree = self._user_tree
        for row in tree.get_children():
            tree.delete(row)
        for u in self._user_data:
            if q and q not in u["name"].lower() and q not in u["email"].lower():
                continue
            fecha = u["created_at"][:10] if u.get("created_at") else ""
            status_icon = {"active": "✅", "cancelled": "❌", "inactive": "⚪", "paused": "⏸"}.get(
                u.get("subscription_status", ""), "⚪"
            )
            plan_label = {"free": "Gratis", "basic": "Básico", "pro": "Pro"}.get(u.get("plan", "free"), "—")
            tree.insert("", "end", iid=str(u["id"]), values=(
                u["id"], u["name"], u["email"], plan_label,
                f"{status_icon} {u.get('subscription_status','—')}",
                u.get("invoices_created", 0), fecha,
            ))

    # ──────────────────────────────── PAGOS ────────────────────────────────

    def _render_pagos(self):
        frame = self._content
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(28, 12))
        ctk.CTkLabel(header, text="Pagos", font=("Inter", 22, "bold"),
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(header, text="↻ Actualizar", width=110, height=32,
                      fg_color=COLORS["accent"], corner_radius=8,
                      command=self._load_pagos).pack(side="right")

        cols = ("id", "usuario", "email", "plan", "monto", "estado", "metodo", "fecha")
        self._pay_tree = self._make_tree(frame, cols, (40, 140, 200, 70, 90, 90, 100, 120))
        self._load_pagos()

    def _load_pagos(self):
        threading.Thread(target=self._pagos_thread, daemon=True).start()

    def _pagos_thread(self):
        try:
            resp = requests.get(
                f"{API_URL}/api/admin/payments",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.after(0, lambda: self._fill_pagos(data))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _fill_pagos(self, data):
        tree = self._pay_tree
        for row in tree.get_children():
            tree.delete(row)
        for p in data:
            fecha = p.get("created_at", "")[:10] if p.get("created_at") else ""
            status_icon = {"approved": "✅", "rejected": "❌", "pending": "⏳"}.get(p.get("status", ""), "❓")
            tree.insert("", "end", values=(
                p["id"],
                p.get("user_name", "—"),
                p.get("email", "—"),
                p.get("plan", "—"),
                f"${p.get('amount', 0):,.2f} {p.get('currency','MXN')}",
                f"{status_icon} {p.get('status','—')}",
                p.get("payment_method", "—"),
                fecha,
            ))

    # ──────────────────────────────── UTILS ────────────────────────────────

    def _make_tree(self, parent, cols, widths):
        wrapper = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=12)
        wrapper.pack(fill="both", expand=True, padx=30, pady=(0, 20))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Admin.Treeview",
                        background=COLORS["card"], foreground=COLORS["text"],
                        fieldbackground=COLORS["card"], rowheight=30,
                        font=("Inter", 11))
        style.configure("Admin.Treeview.Heading",
                        background=COLORS["border"], foreground=COLORS["text"],
                        font=("Inter", 11, "bold"))
        style.map("Admin.Treeview", background=[("selected", COLORS["accent"])])

        scrollbar = ttk.Scrollbar(wrapper, orient="vertical")
        tree = ttk.Treeview(wrapper, columns=cols, show="headings",
                            style="Admin.Treeview", yscrollcommand=scrollbar.set)
        scrollbar.configure(command=tree.yview)
        scrollbar.pack(side="right", fill="y", pady=8, padx=(0, 8))
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        for col, w in zip(cols, widths):
            tree.heading(col, text=col.capitalize())
            tree.column(col, width=w, anchor="center")

        return tree

    def _logout(self):
        self.token = None
        self._show_login()

    def _clear(self):
        for widget in self.winfo_children():
            widget.destroy()


if __name__ == "__main__":
    app = FacturAIAdmin()
    app.mainloop()
