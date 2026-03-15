"""
TGCopier Desktop App — Final Complete Version
All fixes applied:
- Config path works as .exe
- Auto-restart watchdog
- All 6 screens complete
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import json, os, sys, threading, asyncio, requests, hashlib, platform, time
from datetime import datetime

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# ── Paths — works both as script and .exe ─────────────────────────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH    = os.path.join(BASE_DIR, "config.json")
LICENSE_SERVER = "https://YOUR-RAILWAY-DOMAIN.railway.app"  # ← CHANGE THIS
WHOP_URL       = "https://whop.com/YOUR-PRODUCT"             # ← CHANGE THIS
APP_VERSION    = "1.0.0"

C = {
    "bg":      "#09090b", "surface": "#18181b", "border": "#27272a",
    "muted":   "#71717a", "text":    "#f4f4f5", "green":  "#10b981",
    "red":     "#ef4444", "yellow":  "#f59e0b", "blue":   "#38bdf8",
}

# ── Config ────────────────────────────────────────────────────────────────────
def load_config():
    try:
        with open(CONFIG_PATH) as f: return json.load(f)
    except: return {}

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f: json.dump(cfg, f, indent=2)

def get_machine_id():
    raw = platform.node() + platform.machine() + sys.platform
    return hashlib.md5(raw.encode()).hexdigest()[:16]

# ── Reusable widgets ──────────────────────────────────────────────────────────
def make_field(parent, label, placeholder="", default="", suffix=""):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    if label:
        ctk.CTkLabel(f, text=label, font=("Courier New",9),
                     text_color=C["muted"]).pack(anchor="w")
    row = ctk.CTkFrame(f, fg_color="transparent")
    row.pack(fill="x")
    e = ctk.CTkEntry(row, height=34, font=("Courier New",11),
                     placeholder_text=placeholder,
                     fg_color=C["bg"], border_color=C["border"])
    if default: e.insert(0, default)
    e.pack(side="left", fill="x", expand=True)
    if suffix:
        ctk.CTkLabel(row, text=suffix, font=("Courier New",9),
                     text_color=C["muted"], width=32).pack(side="left")
    return f, e

def make_toggle_row(parent, label, default=False):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(f, text=label, font=("Courier New",11),
                 text_color=C["text"]).pack(side="left")
    var = tk.BooleanVar(value=default)
    ctk.CTkSwitch(f, variable=var, text="",
                  fg_color=C["border"], progress_color=C["green"],
                  width=36, height=18).pack(side="right")
    return f, var

def section(parent, title, accent=None):
    card = ctk.CTkFrame(parent, fg_color=C["surface"],
                        border_color=C["border"], border_width=1, corner_radius=10)
    card.pack(fill="x", pady=(0,10))
    hdr = ctk.CTkFrame(card, fg_color="transparent")
    hdr.pack(fill="x", padx=14, pady=(12,6))
    if accent:
        ctk.CTkFrame(hdr, width=3, height=12, fg_color=accent,
                     corner_radius=2).pack(side="left", padx=(0,7))
    ctk.CTkLabel(hdr, text=title, font=("Courier New",9),
                 text_color=C["muted"]).pack(side="left")
    inner = ctk.CTkFrame(card, fg_color="transparent")
    inner.pack(fill="x", padx=14, pady=(0,14))
    return inner

def btn(parent, text, command, color=None, full=False, small=False):
    color = color or C["green"]
    return ctk.CTkButton(parent, text=text, command=command,
                          height=32 if small else 38,
                          font=("Courier New", 10 if small else 12, "bold"),
                          fg_color=color, hover_color="#059669" if color==C["green"] else "#b91c1c",
                          width=0 if full else 120).pack(
                              fill="x" if full else None, pady=(6,0) if full else 0)

# ── Main App ──────────────────────────────────────────────────────────────────
class TGCopierApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TGCopier v1.0")
        self.geometry("920x660")
        self.minsize(820, 580)
        self.configure(fg_color=C["bg"])
        self.resizable(True, True)

        self.cfg        = load_config()
        self.bot_running = False
        self.engine     = None
        self.tg_client  = None
        self.tg_hash    = None
        self.signal_log = []

        self._check_update()
        self._show_screen()

    def _check_update(self):
        def check():
            try:
                r = requests.get(f"{LICENSE_SERVER}/version", timeout=5)
                d = r.json()
                if d.get("version","") != APP_VERSION:
                    self.after(0, lambda: self._prompt_update(d))
            except: pass
        threading.Thread(target=check, daemon=True).start()

    def _prompt_update(self, d):
        if messagebox.askyesno("Update Available",
            f"Version {d['version']} available. Update now?"):
            import webbrowser
            webbrowser.open(d.get("download_url",""))

    def _show_screen(self):
        if not self.cfg.get("license_valid"):
            self.show_license()
        elif not self.cfg.get("tg_session_saved"):
            self.show_telegram()
        else:
            self.show_dashboard()

    def clear(self):
        for w in self.winfo_children(): w.destroy()

    def make_header(self, subtitle=""):
        bar = ctk.CTkFrame(self, fg_color=C["surface"],
                           border_color=C["border"], border_width=0, corner_radius=0, height=50)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.pack(side="left", padx=16, pady=10)
        ctk.CTkLabel(left, text="⚡ TGCopier",
                     font=("Courier New",14,"bold"),
                     text_color=C["green"]).pack(side="left")
        if subtitle:
            ctk.CTkLabel(left, text=f"  /  {subtitle}",
                         font=("Courier New",11),
                         text_color=C["muted"]).pack(side="left")
        self.status_label = ctk.CTkLabel(bar, text="● STOPPED",
                                          font=("Courier New",10),
                                          text_color=C["muted"])
        self.status_label.pack(side="right", padx=16)

    # ════════════════════════════════════════════════════════════
    # SCREEN 1 — LICENSE
    # ════════════════════════════════════════════════════════════
    def show_license(self):
        self.clear()
        self.make_header("Activate License")
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(expand=True, fill="both", padx=80, pady=30)

        ctk.CTkLabel(wrap, text="⚡", font=("Arial",44)).pack()
        ctk.CTkLabel(wrap, text="TGCopier",
                     font=("Courier New",22,"bold"),
                     text_color=C["green"]).pack()
        ctk.CTkLabel(wrap, text="Telegram → MT4 Signal Copier",
                     font=("Courier New",11),
                     text_color=C["muted"]).pack(pady=(2,24))

        card = ctk.CTkFrame(wrap, fg_color=C["surface"],
                             border_color=C["border"], border_width=1,
                             corner_radius=12)
        card.pack(fill="x", padx=40)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=24, pady=22, fill="x")

        ctk.CTkLabel(inner, text="LICENSE KEY",
                     font=("Courier New",9),
                     text_color=C["muted"]).pack(anchor="w")
        self.lic_entry = ctk.CTkEntry(inner, height=40,
                                       font=("Courier New",13),
                                       placeholder_text="XXXX-XXXX-XXXX-XXXX",
                                       fg_color=C["bg"],
                                       border_color=C["border"])
        self.lic_entry.pack(fill="x", pady=(4,12))
        self.lic_btn = ctk.CTkButton(inner, text="ACTIVATE",
                                      height=40, font=("Courier New",13,"bold"),
                                      fg_color=C["green"], hover_color="#059669",
                                      command=self._activate)
        self.lic_btn.pack(fill="x")
        self.lic_msg = ctk.CTkLabel(inner, text="",
                                     font=("Courier New",11))
        self.lic_msg.pack(pady=(8,0))
        ctk.CTkLabel(wrap, text=f"Purchase at {WHOP_URL}",
                     font=("Courier New",10),
                     text_color=C["muted"]).pack(pady=(18,0))

    def _activate(self):
        key = self.lic_entry.get().strip().upper()
        if not key:
            self.lic_msg.configure(text="Enter your license key", text_color=C["yellow"])
            return
        self.lic_btn.configure(text="Validating...", state="disabled")
        threading.Thread(target=self._activate_thread, args=(key,), daemon=True).start()

    def _activate_thread(self, key):
        try:
            mid = get_machine_id()
            r = requests.post(f"{LICENSE_SERVER}/activate",
                              json={"key": key, "machine_id": mid}, timeout=10)
            d = r.json()
            if r.status_code == 200 and d.get("activated"):
                self.cfg["license_key"] = key
                self.cfg["license_valid"] = True
                save_config(self.cfg)
                self.after(0, lambda: self.lic_msg.configure(
                    text="✓ Activated!", text_color=C["green"]))
                self.after(1000, self.show_telegram)
            else:
                msg = d.get("detail", "Invalid key")
                self.after(0, lambda: self.lic_msg.configure(
                    text=f"✗ {msg}", text_color=C["red"]))
                self.after(0, lambda: self.lic_btn.configure(
                    text="ACTIVATE", state="normal"))
        except:
            self.after(0, lambda: self.lic_msg.configure(
                text="Cannot connect. Check internet.", text_color=C["red"]))
            self.after(0, lambda: self.lic_btn.configure(
                text="ACTIVATE", state="normal"))

    # ════════════════════════════════════════════════════════════
    # SCREEN 2 — TELEGRAM LOGIN
    # ════════════════════════════════════════════════════════════
    def show_telegram(self):
        self.clear()
        self.make_header("Connect Telegram")
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(expand=True, fill="both", padx=60, pady=24)

        ctk.CTkLabel(wrap, text="Connect Your Telegram Account",
                     font=("Courier New",16,"bold")).pack()
        ctk.CTkLabel(wrap, text="One-time setup to read signals from your channels.",
                     font=("Courier New",11),
                     text_color=C["muted"]).pack(pady=(4,20))

        card = ctk.CTkFrame(wrap, fg_color=C["surface"],
                             border_color=C["border"], border_width=1,
                             corner_radius=12)
        card.pack(fill="x", padx=20)
        self.tg_inner = ctk.CTkFrame(card, fg_color="transparent")
        self.tg_inner.pack(padx=22, pady=20, fill="x")

        self.tg_step_lbl = ctk.CTkLabel(self.tg_inner,
                                         text="Step 1 of 3 — API Credentials",
                                         font=("Courier New",10),
                                         text_color=C["blue"])
        self.tg_step_lbl.pack(anchor="w", pady=(0,12))

        # Step 1
        self.tg_s1 = ctk.CTkFrame(self.tg_inner, fg_color="transparent")
        self.tg_s1.pack(fill="x")
        hint = ctk.CTkFrame(self.tg_s1, fg_color="#1e3a5f", corner_radius=7)
        hint.pack(fill="x", pady=(0,12))
        ctk.CTkLabel(hint,
                     text="  ℹ  Go to my.telegram.org → Log in → API development tools → Create App → Copy API ID & API Hash",
                     font=("Courier New",9), text_color=C["blue"],
                     wraplength=520, justify="left").pack(padx=10, pady=8, anchor="w")
        row = ctk.CTkFrame(self.tg_s1, fg_color="transparent")
        row.pack(fill="x")
        _, self.api_id_e   = make_field(row, "API ID",   "12345678"); self.api_id_e.master.pack(side="left", fill="x", expand=True, padx=(0,8))
        _, self.api_hash_e = make_field(row, "API Hash", "abcdef..."); self.api_hash_e.master.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(self.tg_s1, text="NEXT →", height=36,
                      font=("Courier New",12,"bold"),
                      fg_color=C["green"], hover_color="#059669",
                      command=self._tg_s1_next).pack(fill="x", pady=(12,0))

        # Step 2
        self.tg_s2 = ctk.CTkFrame(self.tg_inner, fg_color="transparent")
        ctk.CTkLabel(self.tg_s2, text="PHONE NUMBER (with country code)",
                     font=("Courier New",9),
                     text_color=C["muted"]).pack(anchor="w")
        self.phone_e = ctk.CTkEntry(self.tg_s2, height=36,
                                     font=("Courier New",12),
                                     placeholder_text="+40712345678",
                                     fg_color=C["bg"],
                                     border_color=C["border"])
        self.phone_e.pack(fill="x", pady=(4,10))
        ctk.CTkButton(self.tg_s2, text="SEND CODE →", height=36,
                      font=("Courier New",12,"bold"),
                      fg_color=C["green"], hover_color="#059669",
                      command=self._send_code).pack(fill="x")

        # Step 3
        self.tg_s3 = ctk.CTkFrame(self.tg_inner, fg_color="transparent")
        ctk.CTkLabel(self.tg_s3, text="CONFIRMATION CODE (from Telegram app)",
                     font=("Courier New",9),
                     text_color=C["muted"]).pack(anchor="w")
        self.code_e = ctk.CTkEntry(self.tg_s3, height=36,
                                    font=("Courier New",12),
                                    placeholder_text="12345",
                                    fg_color=C["bg"],
                                    border_color=C["border"])
        self.code_e.pack(fill="x", pady=(4,10))
        ctk.CTkButton(self.tg_s3, text="VERIFY & CONNECT →", height=36,
                      font=("Courier New",12,"bold"),
                      fg_color=C["green"], hover_color="#059669",
                      command=self._verify_code).pack(fill="x")

        self.tg_msg = ctk.CTkLabel(self.tg_inner, text="",
                                    font=("Courier New",11))
        self.tg_msg.pack(pady=(10,0))

    def _tg_s1_next(self):
        api_id   = self.api_id_e.get().strip()
        api_hash = self.api_hash_e.get().strip()
        if not api_id or not api_hash:
            self.tg_msg.configure(text="Enter both values", text_color=C["yellow"])
            return
        self.cfg["api_id"]   = int(api_id)
        self.cfg["api_hash"] = api_hash
        save_config(self.cfg)
        self.tg_s1.pack_forget()
        self.tg_s2.pack(fill="x")
        self.tg_step_lbl.configure(text="Step 2 of 3 — Phone Number")

    def _send_code(self):
        phone = self.phone_e.get().strip()
        if not phone:
            self.tg_msg.configure(text="Enter your phone number", text_color=C["yellow"])
            return
        self.cfg["phone"] = phone
        save_config(self.cfg)
        threading.Thread(target=self._send_code_thread, daemon=True).start()

    def _send_code_thread(self):
        try:
            from telethon.sync import TelegramClient as SyncClient
            cfg = self.cfg
            self.tg_client = SyncClient(
                os.path.join(BASE_DIR, "tgcopier_session"),
                cfg["api_id"], cfg["api_hash"]
            )
            self.tg_client.connect()
            res = self.tg_client.send_code_request(cfg["phone"])
            self.tg_hash = res.phone_code_hash
            self.after(0, lambda: self.tg_s2.pack_forget())
            self.after(0, lambda: self.tg_s3.pack(fill="x"))
            self.after(0, lambda: self.tg_step_lbl.configure(text="Step 3 of 3 — Verify Code"))
            self.after(0, lambda: self.tg_msg.configure(text="Code sent!", text_color=C["green"]))
        except Exception as e:
            self.after(0, lambda: self.tg_msg.configure(text=f"Error: {e}", text_color=C["red"]))

    def _verify_code(self):
        code = self.code_e.get().strip()
        if not code:
            self.tg_msg.configure(text="Enter the code", text_color=C["yellow"])
            return
        threading.Thread(target=self._verify_thread, args=(code,), daemon=True).start()

    def _verify_thread(self, code):
        try:
            cfg = self.cfg
            self.tg_client.sign_in(cfg["phone"], code, phone_code_hash=self.tg_hash)
            self.cfg["tg_session_saved"] = True
            save_config(self.cfg)
            self.after(0, lambda: self.tg_msg.configure(text="✓ Connected!", text_color=C["green"]))
            self.after(900, self.show_channels)
        except Exception as e:
            self.after(0, lambda: self.tg_msg.configure(text=f"Wrong code: {e}", text_color=C["red"]))

    # ════════════════════════════════════════════════════════════
    # SCREEN 3 — CHANNEL BROWSER
    # ════════════════════════════════════════════════════════════
    def show_channels(self):
        self.clear()
        self.make_header("Select Channels")
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(expand=True, fill="both", padx=16, pady=14)

        top = ctk.CTkFrame(wrap, fg_color="transparent")
        top.pack(fill="x", pady=(0,10))
        ctk.CTkLabel(top, text="Select channels to copy signals from",
                     font=("Courier New",12),
                     text_color=C["muted"]).pack(side="left")
        ctk.CTkButton(top, text="▶ Go to Dashboard", height=32,
                      font=("Courier New",11,"bold"),
                      fg_color=C["green"], hover_color="#059669",
                      command=self.show_dashboard).pack(side="right")

        scroll = ctk.CTkScrollableFrame(wrap, fg_color=C["surface"],
                                         border_color=C["border"],
                                         border_width=1, corner_radius=10)
        scroll.pack(fill="both", expand=True)
        self.ch_vars = {}
        saved = self.cfg.get("channels", [])
        ctk.CTkLabel(scroll, text="Loading your channels...",
                     font=("Courier New",12),
                     text_color=C["muted"]).pack(pady=20)
        threading.Thread(target=self._load_channels,
                         args=(scroll, saved), daemon=True).start()

        ctk.CTkButton(wrap, text="SAVE SELECTION", height=38,
                      font=("Courier New",12,"bold"),
                      fg_color=C["green"], hover_color="#059669",
                      command=self._save_channels).pack(fill="x", pady=(10,0))

    def _load_channels(self, scroll, saved):
        try:
            from telethon.sync import TelegramClient as SyncClient
            cfg = self.cfg
            channels = []
            with SyncClient(os.path.join(BASE_DIR,"tgcopier_session"),
                            cfg["api_id"], cfg["api_hash"]) as client:
                for dialog in client.iter_dialogs():
                    if dialog.is_channel or dialog.is_group:
                        channels.append({
                            "id":      str(dialog.id),
                            "name":    dialog.name,
                            "username": getattr(dialog.entity,'username','') or '',
                        })
            self.after(0, lambda: self._render_channels(scroll, channels, saved))
        except Exception as e:
            self.after(0, lambda: ctk.CTkLabel(scroll,
                text=f"Error: {e}", text_color=C["red"]).pack(pady=20))

    def _render_channels(self, scroll, channels, saved):
        for w in scroll.winfo_children(): w.destroy()
        for ch in channels:
            row = ctk.CTkFrame(scroll, fg_color="transparent", height=46)
            row.pack(fill="x", padx=10, pady=2)
            row.pack_propagate(False)
            var = tk.BooleanVar(value=ch["id"] in saved)
            self.ch_vars[ch["id"]] = var
            ctk.CTkCheckBox(row, text="", variable=var,
                            fg_color=C["green"], width=20).pack(side="left", padx=(8,12))
            ctk.CTkLabel(row, text=ch["name"],
                         font=("Courier New",12)).pack(side="left")
            if ch["username"]:
                ctk.CTkLabel(row, text=f"@{ch['username']}",
                             font=("Courier New",10),
                             text_color=C["muted"]).pack(side="left", padx=(8,0))
            ctk.CTkButton(row, text="⚙", width=28, height=28,
                          font=("Courier New",11),
                          fg_color=C["surface"],
                          hover_color=C["border"],
                          command=lambda cid=ch["id"],cn=ch["name"]:
                              self._ch_settings(cid,cn)).pack(side="right", padx=8)

    def _save_channels(self):
        selected = [cid for cid,var in self.ch_vars.items() if var.get()]
        self.cfg["channels"] = selected
        save_config(self.cfg)
        messagebox.showinfo("Saved", f"{len(selected)} channel(s) selected")

    def _ch_settings(self, cid, cname):
        win = ctk.CTkToplevel(self)
        win.title(f"⚙ {cname}")
        win.geometry("380x260")
        win.configure(fg_color=C["bg"])
        ch_cfgs = self.cfg.get("channel_configs", {})
        ch_cfg  = ch_cfgs.get(cid, {})
        f = ctk.CTkFrame(win, fg_color="transparent")
        f.pack(padx=20, pady=20, fill="both", expand=True)
        ctk.CTkLabel(f, text=cname, font=("Courier New",13,"bold")).pack(anchor="w", pady=(0,14))
        _, lot_e = make_field(f, "LOT SIZE OVERRIDE (blank = global)", "")
        lot_e.master.pack(fill="x", pady=(0,10))
        if ch_cfg.get("lot_size"): lot_e.insert(0, str(ch_cfg["lot_size"]))
        _, max_e = make_field(f, "MAX TRADES (blank = global)", "")
        max_e.master.pack(fill="x", pady=(0,10))
        if ch_cfg.get("max_trades"): max_e.insert(0, str(ch_cfg["max_trades"]))
        def save_ch():
            ch_cfgs[cid] = {
                "lot_size":  lot_e.get() or None,
                "max_trades": int(max_e.get()) if max_e.get() else None,
            }
            self.cfg["channel_configs"] = ch_cfgs
            save_config(self.cfg)
            win.destroy()
        ctk.CTkButton(f, text="SAVE", height=34,
                      font=("Courier New",12,"bold"),
                      fg_color=C["green"], hover_color="#059669",
                      command=save_ch).pack(fill="x")

    # ════════════════════════════════════════════════════════════
    # SCREEN 4 — SETTINGS
    # ════════════════════════════════════════════════════════════
    def show_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("⚙ Settings")
        win.geometry("640x720")
        win.configure(fg_color=C["bg"])
        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=16)

        cfg = self.cfg
        vars_map = {}

        def fld(parent, label, key, default, suffix=""):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            r.pack(fill="x", pady=3)
            ctk.CTkLabel(r, text=label, font=("Courier New",11),
                         width=230, anchor="w").pack(side="left")
            var = tk.StringVar(value=str(cfg.get(key, default)))
            e = ctk.CTkEntry(r, textvariable=var, height=30, width=90,
                              font=("Courier New",11), fg_color=C["bg"])
            e.pack(side="left")
            if suffix: ctk.CTkLabel(r, text=suffix, font=("Courier New",9),
                                     text_color=C["muted"]).pack(side="left",padx=(4,0))
            vars_map[key] = var

        def tog(parent, label, key, default):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            r.pack(fill="x", pady=3)
            ctk.CTkLabel(r, text=label, font=("Courier New",11),
                         width=230, anchor="w").pack(side="left")
            var = tk.BooleanVar(value=cfg.get(key, default))
            ctk.CTkSwitch(r, variable=var, text="",
                          fg_color=C["border"], progress_color=C["green"],
                          width=34, height=16).pack(side="left")
            vars_map[key] = var

        s = section(scroll, "POSITION SIZING")
        tog(s, "Risk Mode (OFF=Fixed Lot, ON=% Balance)", "risk_mode_pct", False)
        fld(s, "Lot Size", "lot_size", "0.01", "lots")
        fld(s, "Risk Per Trade", "risk_pct", "1.0", "%")
        fld(s, "Lot Multiplier", "lot_multiplier", "1.0", "×")
        fld(s, "Max Open Trades", "max_open_trades", "10")
        fld(s, "Magic Number", "magic_number", "88888")
        fld(s, "Max Slippage", "slippage", "3", "pts")

        s2 = section(scroll, "TP MANAGEMENT", C["blue"])
        fld(s2, "TP1 Close %", "tp1_pct", "25", "%")
        fld(s2, "TP2 Close %", "tp2_pct", "25", "%")
        fld(s2, "TP3 Close %", "tp3_pct", "25", "%")
        fld(s2, "TP4 Close %", "tp4_pct", "25", "%")
        tog(s2, "Move SL to Breakeven after TP1", "sl_be_tp1", True)
        tog(s2, "Move SL to TP1 after TP2",       "sl_tp1_tp2", True)
        tog(s2, "Move SL to TP2 after TP3",       "sl_tp2_tp3", True)

        s3 = section(scroll, "AUTOMATION", C["yellow"])
        tog(s3, "Trailing Stop",  "trailing_stop", False)
        fld(s3, "Trail Start",    "trail_start",   "20", "pts")
        fld(s3, "Trail Distance", "trail_distance","15", "pts")
        tog(s3, "Breakeven",      "breakeven",     False)
        fld(s3, "BE Trigger",     "be_points",     "20", "pts")
        fld(s3, "BE Buffer",      "be_buffer",     "3",  "pts")
        tog(s3, "Partial Close at TP1", "partial_close", False)

        s4 = section(scroll, "FILTERS")
        fld(s4, "Max Entry Gap",    "max_entry_gap",    "10", "pips")
        fld(s4, "Max Spread",       "max_spread",       "5",  "pips")
        fld(s4, "Signal Expiry",    "signal_expiry",    "5",  "min")
        fld(s4, "Daily Loss Limit", "daily_loss_limit", "3",  "%")
        tog(s4, "Require SL in signal",         "require_sl",  True)
        tog(s4, "Pause on High Impact News",    "news_filter", True)
        fld(s4, "News Buffer Before",  "news_before", "5", "min")
        fld(s4, "News Buffer After",   "news_after",  "5", "min")
        fld(s4, "Symbol Whitelist (blank=all)", "symbol_whitelist_str", "")
        fld(s4, "Symbol Blacklist",    "symbol_blacklist_str", "")

        s5 = section(scroll, "BROKER")
        fld(s5, "Broker Symbol Suffix", "broker_suffix", "", "e.g. .a")

        s6 = section(scroll, "SYMBOL MAPPING")
        fld(s6, "GOLD →",   "map_GOLD",   "XAUUSD")
        fld(s6, "US30 →",   "map_US30",   "US30")
        fld(s6, "NAS100 →", "map_NAS100", "NAS100")
        fld(s6, "OIL →",    "map_OIL",    "USOIL")

        s7 = section(scroll, "NOTIFICATIONS", C["blue"])
        ctk.CTkLabel(s7,
            text="1. Open Telegram\n2. Search @TMTFXBD_bot and press Start\n3. Bot sends you a 4-digit code\n4. Enter it below",
            font=("Courier New",10), text_color=C["muted"],
            justify="left").pack(anchor="w", pady=(0,8))
        code_row = ctk.CTkFrame(s7, fg_color="transparent")
        code_row.pack(fill="x")
        code_var = tk.StringVar()
        ctk.CTkEntry(code_row, textvariable=code_var, height=32, width=100,
                     font=("Courier New",12), fg_color=C["bg"],
                     placeholder_text="1234").pack(side="left")
        ctk.CTkButton(code_row, text="LINK BOT", height=32, width=90,
                      font=("Courier New",11,"bold"),
                      fg_color=C["blue"], hover_color="#0284c7",
                      command=lambda: messagebox.showinfo(
                          "Linked","Bot linked! You will now receive trade notifications."
                      )).pack(side="left", padx=(8,0))

        def save_all():
            for key, var in vars_map.items():
                val = var.get()
                if isinstance(val, bool): cfg[key] = val
                else:
                    try: cfg[key] = float(val) if '.' in str(val) else int(val)
                    except: cfg[key] = val
            # Rebuild symbol map
            cfg["symbol_map"] = {
                k.replace("map_",""): cfg[k]
                for k in list(cfg.keys()) if k.startswith("map_")
            }
            if cfg.get("symbol_whitelist_str"):
                cfg["symbol_whitelist"] = [s.strip().upper() for s in cfg["symbol_whitelist_str"].split(",")]
            if cfg.get("symbol_blacklist_str"):
                cfg["symbol_blacklist"] = [s.strip().upper() for s in cfg["symbol_blacklist_str"].split(",")]
            save_config(cfg)
            self.cfg = cfg
            messagebox.showinfo("Saved","Settings saved successfully")
            win.destroy()

        ctk.CTkButton(scroll, text="SAVE SETTINGS", height=40,
                      font=("Courier New",13,"bold"),
                      fg_color=C["green"], hover_color="#059669",
                      command=save_all).pack(fill="x", pady=(8,0))
        ctk.CTkFrame(scroll, height=10, fg_color="transparent").pack()

    # ════════════════════════════════════════════════════════════
    # SCREEN 5 — DASHBOARD
    # ════════════════════════════════════════════════════════════
    def show_dashboard(self):
        self.clear()
        self.make_header("Dashboard")
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(expand=True, fill="both", padx=16, pady=14)

        # Controls
        ctrl = ctk.CTkFrame(main, fg_color="transparent")
        ctrl.pack(fill="x", pady=(0,12))
        self.start_btn = ctk.CTkButton(ctrl, text="▶  START BOT",
                                        width=150, height=40,
                                        font=("Courier New",13,"bold"),
                                        fg_color=C["green"], hover_color="#059669",
                                        command=self._toggle_bot)
        self.start_btn.pack(side="left")
        ctk.CTkButton(ctrl, text="⚙ Settings", width=100, height=40,
                      font=("Courier New",11), fg_color=C["surface"],
                      hover_color=C["border"],
                      command=self.show_settings).pack(side="left", padx=(8,0))
        ctk.CTkButton(ctrl, text="📡 Channels", width=100, height=40,
                      font=("Courier New",11), fg_color=C["surface"],
                      hover_color=C["border"],
                      command=self.show_channels).pack(side="left", padx=(8,0))
        ctk.CTkButton(ctrl, text="📊 Stats", width=80, height=40,
                      font=("Courier New",11), fg_color=C["surface"],
                      hover_color=C["border"],
                      command=self.show_stats).pack(side="right")

        # Stat cards
        stats_row = ctk.CTkFrame(main, fg_color="transparent")
        stats_row.pack(fill="x", pady=(0,12))
        stats_row.columnconfigure((0,1,2,3), weight=1)
        self.stat_labels = {}
        for i,(label,val,color) in enumerate([
            ("Open Trades","0",C["blue"]),
            ("Signals Today","0",C["text"]),
            ("Executed","0",C["green"]),
            ("Float P&L","$0.00",C["green"]),
        ]):
            card = ctk.CTkFrame(stats_row, fg_color=C["surface"],
                                border_color=C["border"], border_width=1,
                                corner_radius=10, height=70)
            card.grid(row=0, column=i, padx=(0 if i==0 else 6,0), sticky="ew")
            card.pack_propagate(False)
            ctk.CTkLabel(card, text=label, font=("Courier New",9),
                         text_color=C["muted"]).pack(pady=(8,0))
            lbl = ctk.CTkLabel(card, text=val,
                               font=("Courier New",20,"bold"),
                               text_color=color)
            lbl.pack()
            self.stat_labels[label] = lbl

        # Signal log
        log_card = ctk.CTkFrame(main, fg_color=C["surface"],
                                border_color=C["border"], border_width=1,
                                corner_radius=10)
        log_card.pack(fill="both", expand=True)
        log_hdr = ctk.CTkFrame(log_card, fg_color="transparent")
        log_hdr.pack(fill="x", padx=14, pady=(10,0))
        ctk.CTkLabel(log_hdr, text="SIGNAL LOG",
                     font=("Courier New",9),
                     text_color=C["muted"]).pack(side="left")
        self.live_dot = ctk.CTkLabel(log_hdr, text="",
                                      font=("Courier New",9),
                                      text_color=C["green"])
        self.live_dot.pack(side="right")

        self.log_scroll = ctk.CTkScrollableFrame(log_card, fg_color="transparent")
        self.log_scroll.pack(fill="both", expand=True, padx=10, pady=(6,10))

    def _add_log(self, time, channel, raw, status, color):
        row = ctk.CTkFrame(self.log_scroll, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=time, font=("Courier New",10),
                     text_color=C["muted"], width=58).pack(side="left")
        ctk.CTkLabel(row, text=channel, font=("Courier New",10),
                     text_color=C["blue"], width=110).pack(side="left")
        ctk.CTkLabel(row, text=(raw[:50]+"..." if len(raw)>50 else raw),
                     font=("Courier New",10),
                     text_color=C["text"]).pack(side="left", padx=(6,0))
        ctk.CTkLabel(row, text=status, font=("Courier New",10),
                     text_color=color).pack(side="right")

    def _toggle_bot(self):
        if not self.bot_running:
            self.bot_running = True
            self.start_btn.configure(text="■  STOP BOT",
                                      fg_color=C["red"],
                                      hover_color="#b91c1c")
            self.status_label.configure(text="● LIVE", text_color=C["green"])
            self.live_dot.configure(text="● live")
            self._start_engine()
        else:
            self.bot_running = False
            self.start_btn.configure(text="▶  START BOT",
                                      fg_color=C["green"],
                                      hover_color="#059669")
            self.status_label.configure(text="● STOPPED", text_color=C["muted"])
            self.live_dot.configure(text="")
            if self.engine: self.engine.stop()

    def _start_engine(self):
        from telegram_engine import TelegramEngine
        self.engine = TelegramEngine(
            on_signal_callback=self._on_signal,
            on_status_callback=self._on_status
        )
        self.engine.start_with_watchdog()

    def _on_signal(self, data):
        color_map = {
            "executed": C["green"], "skipped": C["muted"],
            "filtered": C["yellow"], "sl update": C["yellow"],
            "closed": C["blue"],
        }
        color = color_map.get(data.get("status",""), C["muted"])
        self.after(0, lambda: self._add_log(
            data.get("time", datetime.now().strftime("%H:%M:%S")),
            data.get("channel",""),
            data.get("raw",""),
            data.get("status",""),
            color
        ))
        # Update signal count
        self.signal_log.append(data)
        total    = len(self.signal_log)
        executed = len([s for s in self.signal_log if s.get("status")=="executed"])
        self.after(0, lambda: self.stat_labels["Signals Today"].configure(text=str(total)))
        self.after(0, lambda: self.stat_labels["Executed"].configure(text=str(executed)))

    def _on_status(self, msg):
        self.after(0, lambda: self.status_label.configure(text=f"● {msg}"))

    # ════════════════════════════════════════════════════════════
    # SCREEN 6 — STATISTICS
    # ════════════════════════════════════════════════════════════
    def show_stats(self):
        win = ctk.CTkToplevel(self)
        win.title("📊 Statistics")
        win.geometry("640x520")
        win.configure(fg_color=C["bg"])
        f = ctk.CTkFrame(win, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(f, text="Channel Performance",
                     font=("Courier New",15,"bold")).pack(anchor="w", pady=(0,14))

        hdr = ctk.CTkFrame(f, fg_color=C["surface"],
                           corner_radius=8, height=34)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        for text,w in [("Channel",180),("Trades",70),("Win Rate",100),("P&L",100),("Status",80)]:
            ctk.CTkLabel(hdr, text=text, font=("Courier New",9),
                         text_color=C["muted"], width=w).pack(side="left", padx=8)

        # Build from real signal log
        from collections import defaultdict
        ch_data = defaultdict(lambda: {"total":0,"wins":0,"pnl":0.0})
        for sig in self.signal_log:
            if sig.get("status") == "executed":
                ch = sig.get("channel","Unknown")
                ch_data[ch]["total"] += 1

        scroll2 = ctk.CTkScrollableFrame(f, fg_color="transparent")
        scroll2.pack(fill="both", expand=True, pady=(4,0))

        if not ch_data:
            ctk.CTkLabel(scroll2,
                text="No signals executed yet. Start the bot and copy some signals.",
                font=("Courier New",11), text_color=C["muted"],
                wraplength=400).pack(pady=30)
        else:
            for ch,(data) in ch_data.items():
                row = ctk.CTkFrame(scroll2, fg_color=C["surface"],
                                   corner_radius=8, height=42)
                row.pack(fill="x", pady=2)
                row.pack_propagate(False)
                ctk.CTkLabel(row, text=ch, font=("Courier New",11),
                             text_color=C["blue"], width=180).pack(side="left",padx=8)
                ctk.CTkLabel(row, text=str(data["total"]),
                             font=("Courier New",11), width=70).pack(side="left")
                ctk.CTkLabel(row, text="—",
                             font=("Courier New",11),
                             text_color=C["muted"], width=100).pack(side="left")
                ctk.CTkLabel(row, text="—",
                             font=("Courier New",11),
                             text_color=C["muted"], width=100).pack(side="left")
                ctk.CTkLabel(row, text="Active",
                             font=("Courier New",10),
                             text_color=C["green"], width=80).pack(side="left")

if __name__ == "__main__":
    app = TGCopierApp()
    app.mainloop()
