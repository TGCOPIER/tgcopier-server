from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
import sqlite3, secrets, os

app = FastAPI()
DB = "licenses.db"
ADMIN_PWD = os.getenv("ADMIN_PASSWORD", "changeme123")
APP_VERSION = "1.0.0"
DOWNLOAD_URL = os.getenv("DOWNLOAD_URL", "")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS licenses(
        key TEXT PRIMARY KEY, email TEXT, machine_id TEXT,
        status TEXT DEFAULT 'active', plan TEXT DEFAULT 'monthly',
        created_at TEXT, expires_at TEXT, activated_at TEXT,
        last_seen TEXT, notes TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT, action TEXT, machine_id TEXT, ip TEXT, ts TEXT)""")
    c.commit(); c.close()
init()

class ActivateReq(BaseModel): key:str; machine_id:str; email:str=""
class AdminReq(BaseModel): password:str
class GenReq(BaseModel): password:str; email:str=""; plan:str="monthly"; days:int=30; count:int=1
class RevokeReq(BaseModel): password:str; key:str

def admin_check(pwd):
    if pwd != ADMIN_PWD: raise HTTPException(403, "Invalid password")

@app.get("/")
def root(): return {"status": "TGCopier License Server", "version": APP_VERSION}

@app.get("/version")
def version(): return {"version": APP_VERSION, "download_url": DOWNLOAD_URL}

@app.post("/activate")
def activate(req: ActivateReq, request: Request):
    c = db()
    row = c.execute("SELECT * FROM licenses WHERE key=?", (req.key,)).fetchone()
    if not row: c.close(); raise HTTPException(404, "Invalid license key")
    if row["status"] == "revoked": c.close(); raise HTTPException(403, "License revoked")
    if row["machine_id"] and row["machine_id"] != req.machine_id:
        c.close(); raise HTTPException(403, "Already activated on another machine. Contact support.")
    c.execute("UPDATE licenses SET machine_id=?, activated_at=?, last_seen=?, email=? WHERE key=?",
        (req.machine_id, datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), req.email, req.key))
    c.commit(); c.close()
    return {"activated": True}

@app.post("/admin/generate")
def generate(req: GenReq):
    admin_check(req.password)
    c = db(); keys = []
    for _ in range(req.count):
        key = "-".join([secrets.token_hex(3).upper() for _ in range(4)])
        exp = (datetime.utcnow() + timedelta(days=req.days)).isoformat()
        c.execute("INSERT INTO licenses(key,email,status,plan,created_at,expires_at) VALUES(?,?,?,?,?,?)",
            (key, req.email, "active", req.plan, datetime.utcnow().isoformat(), exp))
        keys.append(key)
    c.commit(); c.close()
    return {"generated": len(keys), "keys": keys}

@app.post("/admin/revoke")
def revoke(req: RevokeReq):
    admin_check(req.password)
    c = db(); c.execute("UPDATE licenses SET status='revoked' WHERE key=?", (req.key,)); c.commit(); c.close()
    return {"revoked": True}

@app.post("/admin/list")
def list_keys(req: AdminReq):
    admin_check(req.password)
    c = db(); rows = c.execute("SELECT * FROM licenses ORDER BY created_at DESC").fetchall(); c.close()
    return {"licenses": [dict(r) for r in rows]}
