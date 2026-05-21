from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
import sqlite3
import random
from typing import Optional

# --- FASTAPI INITIALIZATION ---
app = FastAPI(
    title="Floxpay Nigeria Core Switch",
    version="1.0.0",
    description="CBN-compliant database core and automated NIP settlement"
)

# --- PYDANTIC SCHEMAS ---
class SignupRequest(BaseModel):
    full_name: str
    phone_number: str
    bvn: Optional[str] = None
    nin: Optional[str] = None

class TransferRequest(BaseModel):
    sender_phone: str
    destination_account: str
    amount: float

# --- DATABASE CONNECTION ---
def get_db_connection():
    conn = sqlite3.connect("floxpay.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
def startup_db():
    """Builds the complete database ledger architecture on startup."""
    conn = get_db_connection()
    # Users table (Allows BVN and NIN to be NULL/empty)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            phone_number TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            bvn TEXT,
            nin TEXT,
            account_number TEXT NOT NULL UNIQUE,
            bank_partner TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 10000.0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_phone TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            recipient_account TEXT NOT NULL,
            recipient_name TEXT NOT NULL,
            amount REAL NOT NULL,
            reference TEXT NOT NULL UNIQUE,
            date TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# --- API ENDPOINTS ---

@app.post("/api/v1/auth/signup", status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest):
    """Registers a user with either BVN or NIN, auto-generates NUBAN, adds ₦10k."""
    # Enforce that at least one verification identity exists
    if not payload.bvn and not payload.nin:
        raise HTTPException(
            status_code=400, 
            detail="Identity validation failed: Provide either your 11-digit BVN or NIN to activate."
        )

    conn = get_db_connection()
    try:
        nuban = "".join([str(random.randint(0, 9)) for _ in range(10)])
        banks = ["Provisional Bank", "Wema Bank", "9Payment Service Bank", "Moniepoint MFB"]
        partner_bank = random.choice(banks)

        conn.execute(
            "INSERT INTO users (phone_number, full_name, bvn, nin, account_number, bank_partner, balance) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (payload.phone_number, payload.full_name, payload.bvn or "", payload.nin or "", nuban, partner_bank, 10000.0)
        )
        conn.commit()
        return {"status": "success", "message": "Account activated"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Phone number already registered on Floxpay.")
    finally:
        conn.close()

@app.get("/api/v1/wallet/{phone}")
def get_wallet_dashboard(phone: str):
    conn = get_db_connection()
    user = conn.execute("SELECT full_name, account_number, bank_partner, balance FROM users WHERE phone_number = ?", (phone,)).fetchone()
    
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User account not found.")
    
    history_records = conn.execute(
        "SELECT sender_name, recipient_name, amount, reference FROM ledger WHERE sender_phone = ? ORDER BY id DESC", 
        (phone,)
    ).fetchall()
    
    conn.close()
    
    return {
        "name": user["full_name"],
        "account_number": user["account_number"],
        "bank_partner": user["bank_partner"],
        "balance": user["balance"],
        "history": [dict(row) for row in history_records]
    }

@app.post("/api/v1/transfer/send")
def execute_transfer(payload: TransferRequest):
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid transfer settlement amount.")
        
    conn = get_db_connection()
    try:
        sender = conn.execute("SELECT full_name, balance FROM users WHERE phone_number = ?", (payload.sender_phone,)).fetchone()
        if not sender:
            raise HTTPException(status_code=404, detail="Authentication error.")
            
        if sender["balance"] < payload.amount:
            raise HTTPException(status_code=400, detail="Insufficient settlement liquidity.")
            
        recipient = conn.execute("SELECT full_name FROM users WHERE account_number = ?", (payload.destination_account,)).fetchone()
        recipient_name = recipient["full_name"] if recipient else f"CBN NIP Router Recipient ({payload.destination_account})"
        
        conn.execute("UPDATE users SET balance = balance - ? WHERE phone_number = ?", (payload.amount, payload.sender_phone))
        
        ref_id = f"FXP|NIP|{random.randint(100000, 999999)}"
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn.execute(
            "INSERT INTO ledger (sender_phone, sender_name, recipient_account, recipient_name, amount, reference, date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (payload.sender_phone, sender["full_name"], payload.destination_account, recipient_name, payload.amount, ref_id, current_time)
        )
        conn.commit()
        return {"status": "success", "detail": "Settlement completed"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Core processing failure: {str(e)}")
    finally:
        conn.close()