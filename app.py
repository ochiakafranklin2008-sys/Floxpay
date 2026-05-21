from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from datetime import datetime
import sqlite3
import random
from typing import Optional

# --- FASTAPI INITIALIZATION ---
app = FastAPI(
    title="Floxpay Nigeria Core Switch",
    version="1.0.0"
)

# --- LOOSE DATA SCHEMA ---
class SignupRequest(BaseModel):
    full_name: str
    phone_number: str
    bvn: Optional[str] = ""
    nin: Optional[str] = ""

class TransferRequest(BaseModel):
    sender_phone: str
    destination_account: str
    amount: float

def get_db_connection():
    conn = sqlite3.connect("floxpay.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event("startup")
def startup_db():
    conn = get_db_connection()
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
    # Make sure empty spaces are cleaned up
    bvn_val = payload.bvn.strip() if payload.bvn else ""
    nin_val = payload.nin.strip() if payload.nin else ""

    # Ensure at least one is provided
    if not bvn_val and not nin_val:
        raise HTTPException(status_code=400, detail="Please enter either your BVN or your NIN to verify.")

    conn = get_db_connection()
    try:
        nuban = "".join([str(random.randint(0, 9)) for _ in range(10)])
        banks = ["Provisional Bank", "Wema Bank", "9Payment Service Bank", "Moniepoint MFB"]
        partner_bank = random.choice(banks)

        conn.execute(
            "INSERT INTO users (phone_number, full_name, bvn, nin, account_number, bank_partner, balance) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (payload.phone_number, payload.full_name, bvn_val, nin_val, nuban, partner_bank, 10000.0)
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
        raise HTTPException(status_code=400, detail="Invalid amount.")
    conn = get_db_connection()
    try:
        sender = conn.execute("SELECT full_name, balance FROM users WHERE phone_number = ?", (payload.sender_phone,)).fetchone()
        if not sender or sender["balance"] < payload.amount:
            raise HTTPException(status_code=400, detail="Declined or insufficient funds.")
            
        recipient = conn.execute("SELECT full_name FROM users WHERE account_number = ?", (payload.destination_account,)).fetchone()
        recipient_name = recipient["full_name"] if recipient else f"External Account ({payload.destination_account})"
        
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
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()