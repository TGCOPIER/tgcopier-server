"""
FXBD Copier License Server
- License activation and validation
- Whop webhook integration (auto generate + revoke keys)
- Automatic email delivery via Resend
- Admin panel
"""

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timedelta
import sqlite3, secrets, os, hmac, hashlib, json, urllib.request

app = FastAPI()

DB                  = "licenses.db"
ADMIN_PWD           = os.getenv("ADMIN_PASSWORD", "changeme123")
WHOP_WEBHOOK_SECRET = os.getenv("WHOP_WEBHOOK_SECRET", "")
RESEND_API_KEY      = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL          = os.getenv("FROM_EMAIL", "onboarding@resend.dev")
APP_VERSION         = "1.0.0"
DOWNLOAD_URL        = os.getenv("DOWNLOAD_URL", "")
WHOP_URL            = "https://whop.com/fxbd-telegram-to-mt4-copier/fxbd-copier/"

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

def send_license_email(email, key, plan):
    if not RESEND_API_KEY or not email:
        return
    try:
        html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; background: #0f0f0f; color: #f0f0f0; margin: 0; padding: 0; }}
  .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
  .header {{ background: #1a1a1a; border-top: 3px solid #d4a017; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
  .logo {{ color: #d4a017; font-size: 28px; font-weight: bold; letter-spacing: 2px; }}
  .body {{ background: #1a1a1a; padding: 30px; border-radius: 0 0 8px 8px; }}
  .key-box {{ background: #0f0f0f; border: 2px solid #d4a017; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0; }}
  .key {{ color: #d4a017; font-size: 22px; font-weight: bold; letter-spacing: 3px; font-family: monospace; }}
  .btn {{ display: inline-block; background: #d4a017; color: #000; padding: 14px 32px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 16px; margin: 20px 0; }}
  .step {{ background: #222; border-radius: 6px; padding: 12px 16px; margin: 8px 0; }}
  .step-num {{ color: #d4a017; font-weight: bold; margin-right: 8px; }}
  .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
  h2 {{ color: #d4a017; }}
  p {{ color: #b0b0b0; line-height: 1.6; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">◆ FXBD COPIER</div>
    <p style="color:#888; margin:8px 0 0 0;">Telegram to MT4 Signal Copier</p>
  </div>
  <div class="body">
    <h2>Welcome! Your license is ready.</h2>
    <p>Thank you for subscribing to FXBD Copier. Here is your license key:</p>
    
    <div class="key-box">
      <div class="key">{key}</div>
      <p style="color:#888; font-size:12px; margin:8px 0 0 0;">Keep this key safe. It is tied to your machine.</p>
    </div>

    <h2>How to get started</h2>
    <div class="step"><span class="step-num">1</span>Download the files from your Whop member area</div>
    <div class="step"><span class="step-num">2</span>Run FXBDCopier.exe on your Windows PC or VPS</div>
    <div class="step"><span class="step-num">3</span>Enter your license key above when prompted</div>
    <div class="step"><span class="step-num">4</span>Connect your Telegram account</div>
    <div class="step"><span class="step-num">5</span>Install TGCopier.ex4 in MT4 and start copying signals</div>

    <div style="text-align:center">
      <a href="{WHOP_URL}" class="btn">Access Your Downloads</a>
    </div>

    <p>Need help? Read the member guide included in your downloads or reply to this email.</p>
    
    <p style="color:#666; font-size:13px;">Plan: {plan} | Subscription managed via Whop</p>
  </div>
  <div class="footer">
    <p>FXBD Copier &bull; Automated Trading Software<br>
    You received this email because you purchased FXBD Copier.</p>
  </div>
</div>
</body>
</html>
"""
        payload = json.dumps({
            "from": f"FXBD Copier <{FROM_EMAIL}>",
            "to": [email],
            "subject": "Your FXBD Copier License Key",
            "html": html
        }).encode()

        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"Email sent to {email}: {r.status}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Email failed: {e.code} {e.reason} - {error_body}")
    except Exception as e:
        print(f"Email exception: {e}")

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
        send_license_email(email, key, plan)
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
    if req.email and len(keys) == 1:
        send_license_email(req.email, keys[0], req.plan)
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
