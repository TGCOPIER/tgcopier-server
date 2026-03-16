"""
FXBD Copier License Server
- License activation and validation
- Whop webhook integration (auto generate + revoke keys)
- Admin panel
"""

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timedelta
import sqlite3, secrets, os, hmac, hashlib, json

app = FastAPI()

DB                  = "licenses.db"
ADMIN_PWD           = os.getenv("ADMIN_PASSWORD", "changeme123")
WHOP_WEBHOOK_SECRET = os.getenv("WHOP_WEBHOOK_SECRET", "")
APP_VERSION         = "1.0.0"
DOWNLOAD_URL        = os.getenv("DOWNLOAD_URL", "")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS licenses(
        key TEXT PRIMARY KEY,
        email TEXT,
        machine_id TEXT,
        status TEXT DEFAULT 'active',
        plan TEXT DEFAULT 'monthly',
        whop_membership_id TEXT,
        created_at TEXT,
        expires_at TEXT,
        activated_at TEXT,
        last_seen TEXT,
        notes TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT, action TEXT, machine_id TEXT, ip TEXT, ts TEXT)""")
    c.commit()
    c.close()

init()

def gen_key():
    return "-".join([secrets.token_hex(3).upper() for _ in range(4)])

def admin_check(pwd):
    if pwd != ADMIN_PWD:
        raise HTTPException(403, "Invalid password")

class ActivateReq(BaseModel):
    key: str
    machine_id: str
    email: str = ""

class AdminReq(BaseModel):
    password: str

class GenReq(BaseModel):
    password: str
    email: str = ""
    plan: str = "monthly"
    days: int = 30
    count: int = 1

class RevokeReq(BaseModel):
    password: str
    key: str

class ResetReq(BaseModel):
    password: str
    key: str

@app.get("/")
def root():
    return {"status": "FXBD Copier License Server", "version": APP_VERSION}

@app.get("/version")
def version():
    return {"version": APP_VERSION, "download_url": DOWNLOAD_URL}

@app.post("/activate")
def activate(req: ActivateReq, request: Request):
    c = db()
    row = c.execute("SELECT * FROM licenses WHERE key=?", (req.key,)).fetchone()
    if not row:
        c.close()
        raise HTTPException(404, "Invalid license key")
    if row["status"] == "revoked":
        c.close()
        raise HTTPException(403, "License revoked. Please renew your subscription.")
    if row["status"] == "expired":
        c.close()
        raise HTTPException(403, "License expired. Please renew your subscription.")
    if row["machine_id"] and row["machine_id"] != req.machine_id:
        c.close()
        raise HTTPException(403, "License already activated on another machine. Contact support.")
    now = datetime.utcnow().isoformat()
    c.execute("""UPDATE licenses SET machine_id=?, activated_at=?, last_seen=?, email=? WHERE key=?""",
        (req.machine_id, row["activated_at"] or now, now, req.email or row["email"], req.key))
    c.commit()
    c.close()
    return {"activated": True}

@app.post("/webhook/whop")
async def whop_webhook(request: Request):
    body = await request.body()
    if WHOP_WEBHOOK_SECRET:
        sig = request.headers.get("x-whop-signature", "")
        expected = hmac.new(WHOP_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, f"sha256={expected}"):
            raise HTTPException(401, "Invalid webhook signature")
    try:
        data = json.loads(body)
    except:
        raise HTTPException(400, "Invalid JSON")

    event = data.get("event", "")
    membership = data.get("data", {})
    email = membership.get("user", {}).get("email", "") or membership.get("email", "")
    membership_id = membership.get("id", "")
    plan = membership.get("plan", {}).get("name", "monthly")
    c = db()

    if event in ("membership.went_valid", "membership.created", "payment.succeeded",
                 "membership_activated", "payment_succeeded"):
        existing = c.execute("SELECT * FROM licenses WHERE whop_membership_id=?", (membership_id,)).fetchone()
        if existing:
            if existing["status"] == "revoked":
                c.execute("UPDATE licenses SET status='active', expires_at=? WHERE whop_membership_id=?",
                    ((datetime.utcnow() + timedelta(days=32)).isoformat(), membership_id))
                c.commit()
            key = existing["key"]
        else:
            key = gen_key()
            c.execute("""INSERT INTO licenses (key, email, status, plan, whop_membership_id, created_at, expires_at)
                VALUES (?,?,?,?,?,?,?)""",
                (key, email, "active", plan, membership_id,
                 datetime.utcnow().isoformat(),
                 (datetime.utcnow() + timedelta(days=32)).isoformat()))
            c.commit()
        c.close()
        return {"ok": True, "key": key, "email": email}

    elif event in ("membership.went_invalid", "membership.expired", "membership.cancelled",
                   "membership_deactivated", "payment_failed"):
        c.execute("UPDATE licenses SET status='revoked' WHERE whop_membership_id=?", (membership_id,))
        c.commit()
        c.close()
        return {"ok": True, "action": "revoked"}

    c.close()
    return {"ok": True, "event": event, "action": "ignored"}

@app.post("/admin/generate")
def generate(req: GenReq):
    admin_check(req.password)
    c = db()
    keys = []
    for _ in range(req.count):
        key = gen_key()
        exp = (datetime.utcnow() + timedelta(days=req.days)).isoformat()
        c.execute("""INSERT INTO licenses (key, email, status, plan, created_at, expires_at)
            VALUES (?,?,?,?,?,?)""",
            (key, req.email, "active", req.plan, datetime.utcnow().isoformat(), exp))
        keys.append(key)
    c.commit()
    c.close()
    return {"generated": len(keys), "keys": keys}

@app.post("/admin/revoke")
def revoke(req: RevokeReq):
    admin_check(req.password)
    c = db()
    c.execute("UPDATE licenses SET status='revoked' WHERE key=?", (req.key,))
    c.commit()
    c.close()
    return {"revoked": True}

@app.post("/admin/reset")
def reset_machine(req: ResetReq):
    admin_check(req.password)
    c = db()
    c.execute("UPDATE licenses SET machine_id=NULL WHERE key=?", (req.key,))
    c.commit()
    c.close()
    return {"reset": True, "message": "Machine ID cleared. Member can activate on a new machine."}

@app.post("/admin/list")
def list_keys(req: AdminReq):
    admin_check(req.password)
    c = db()
    rows = c.execute("SELECT * FROM licenses ORDER BY created_at DESC").fetchall()
    c.close()
    return {"licenses": [dict(r) for r in rows]}

@app.post("/admin/stats")
def stats(req: AdminReq):
    admin_check(req.password)
    c = db()
    total   = c.execute("SELECT COUNT(*) FROM licenses").fetchone()[0]
    active  = c.execute("SELECT COUNT(*) FROM licenses WHERE status='active'").fetchone()[0]
    revoked = c.execute("SELECT COUNT(*) FROM licenses WHERE status='revoked'").fetchone()[0]
    used    = c.execute("SELECT COUNT(*) FROM licenses WHERE machine_id IS NOT NULL").fetchone()[0]
    c.close()
    return {"total": total, "active": active, "revoked": revoked,
            "activated": used, "not_activated": total - used}
