from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
import sqlite3
import random

# --- FASTAPI INIT ---
app = FastAPI(
    title="Floxpay Nigeria Core Switch",
    version="1.0.0",
    description="CBN-compliant database core and automated NIP settlement"
)

DB_FILE = "floxpay.db"

# --- DB CONNECTION ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# --- MODELS ---
class SignupRequest(BaseModel):
    full_name: str
    phone_number: str
    bvn: str = Field(..., min_length=11, max_length=11)
    nin: str = Field(..., min_length=11, max_length=11)


class TransferRequest(BaseModel):
    sender_phone: str
    destination_account: str
    amount: float


# --- INIT DB ---
@app.on_event("startup")
def startup_db():

    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            phone_number TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            bvn TEXT NOT NULL,
            nin TEXT NOT NULL,
            account_number TEXT UNIQUE NOT NULL,
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
            reference TEXT UNIQUE NOT NULL,
            date TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# --- SIGNUP ---
@app.post("/api/v1/auth/signup")
def signup(payload: SignupRequest):

    conn = get_db_connection()

    try:
        nuban = "".join([str(random.randint(0, 9)) for _ in range(10)])

        banks = [
            "Provisional Bank",
            "Wema Bank",
            "9Payment Service Bank",
            "Moniepoint MFB"
        ]

        conn.execute("""
            INSERT INTO users
            (phone_number, full_name, bvn, nin, account_number, bank_partner, balance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            payload.phone_number,
            payload.full_name,
            payload.bvn,
            payload.nin,
            nuban,
            random.choice(banks),
            10000.0
        ))

        conn.commit()

        return {
            "status": "success",
            "account_number": nuban,
            "message": "Account activated"
        }

    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Phone already exists")

    finally:
        conn.close()


# --- WALLET ---
@app.get("/api/v1/wallet/{phone}")
def get_wallet(phone: str):

    conn = get_db_connection()

    user = conn.execute("""
        SELECT full_name, account_number, bank_partner, balance
        FROM users
        WHERE phone_number = ?
    """, (phone,)).fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    history = conn.execute("""
        SELECT sender_name, recipient_name, amount, reference, date
        FROM ledger
        WHERE sender_phone = ?
        ORDER BY id DESC
    """, (phone,)).fetchall()

    conn.close()

    return {
        "name": user["full_name"],
        "account_number": user["account_number"],
        "bank_partner": user["bank_partner"],
        "balance": user["balance"],
        "history": [dict(row) for row in history]
    }


# --- TRANSFER ENGINE (FIXED) ---
@app.post("/api/v1/transfer/send")
def transfer(payload: TransferRequest):

    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    conn = get_db_connection()

    try:
        sender = conn.execute("""
            SELECT full_name, balance
            FROM users
            WHERE phone_number = ?
        """, (payload.sender_phone,)).fetchone()

        if not sender:
            raise HTTPException(status_code=404, detail="Sender not found")

        if sender["balance"] < payload.amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")

        recipient = conn.execute("""
            SELECT phone_number, full_name
            FROM users
            WHERE account_number = ?
        """, (payload.destination_account,)).fetchone()

        recipient_name = recipient["full_name"] if recipient else "External NIP Recipient"

        # debit sender
        conn.execute("""
            UPDATE users
            SET balance = balance - ?
            WHERE phone_number = ?
        """, (payload.amount, payload.sender_phone))

        # credit recipient ONLY if internal user exists
        if recipient:
            conn.execute("""
                UPDATE users
                SET balance = balance + ?
                WHERE phone_number = ?
            """, (payload.amount, recipient["phone_number"]))

        ref_id = f"FXP-NIP-{random.randint(100000, 999999)}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute("""
            INSERT INTO ledger
            (sender_phone, sender_name, recipient_account, recipient_name, amount, reference, date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            payload.sender_phone,
            sender["full_name"],
            payload.destination_account,
            recipient_name,
            payload.amount,
            ref_id,
            now
        ))

        conn.commit()

        return {
            "status": "success",
            "reference": ref_id
        }

    except HTTPException as e:
        conn.rollback()
        raise e

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        conn.close()