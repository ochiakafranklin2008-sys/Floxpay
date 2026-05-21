from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Dict
from decimal import Decimal
from datetime import datetime
import sqlite3
import uuid

# ---------------------------------------------------------
# FASTAPI INITIALIZATION
# ---------------------------------------------------------

app = FastAPI(
    title="Floxpay Nigeria Core Switch",
    version="5.0.0",
    description="CBN-compliant database core and automated NUBAN settlement router."
)

DB_FILE = "floxpay.db"

# ---------------------------------------------------------
# DATABASE CONNECTION HELPER
# ---------------------------------------------------------

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------------------------------------------------
# DATABASE INITIALIZATION
# ---------------------------------------------------------

def init_db():

    conn = get_db_connection()
    cursor = conn.cursor()

    # USERS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        phone TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        bvn TEXT NOT NULL,
        nin TEXT NOT NULL,
        account_number TEXT UNIQUE NOT NULL,
        bank_partner TEXT NOT NULL,
        balance REAL NOT NULL
    )
    """)

    # TRANSACTIONS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        sender_name TEXT NOT NULL,
        recipient_name TEXT NOT NULL,
        amount REAL NOT NULL,
        reference TEXT NOT NULL,
        status TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)

    # SEED TEST USER
    cursor.execute("SELECT COUNT(*) FROM users")

    if cursor.fetchone()[0] == 0:

        cursor.execute("""
        INSERT INTO users (
            phone,
            name,
            bvn,
            nin,
            account_number,
            bank_partner,
            balance
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "08011112222",
            "Tunde Bakare",
            "22233344455",
            "11122233344",
            "1023498110",
            "Providus Bank",
            250000.00
        ))

    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# PYDANTIC SCHEMAS
# ---------------------------------------------------------

class SignupRequest(BaseModel):
    full_name: str

    phone_number: str = Field(
        ...,
        min_length=11,
        max_length=11,
        description="Nigerian phone number"
    )

    bvn: str = Field(
        ...,
        min_length=11,
        max_length=11
    )

    nin: str = Field(
        ...,
        min_length=11,
        max_length=11
    )

class TransferRequest(BaseModel):

    sender_phone: str

    destination_account: str

    amount: Decimal = Field(
        ...,
        gt=0
    )

# ---------------------------------------------------------
# ROOT HEALTH ENDPOINT
# ---------------------------------------------------------

@app.get("/")
def health_check():

    return {
        "status": "ACTIVE",
        "system": "Floxpay Nigeria Gateway Engine",
        "version": "5.0.0",
        "documentation": "/docs"
    }

# ---------------------------------------------------------
# USER SIGNUP ENDPOINT
# ---------------------------------------------------------

@app.post(
    "/api/v1/auth/signup",
    status_code=status.HTTP_201_CREATED
)
def register_user(payload: SignupRequest):

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        # CHECK DUPLICATE PHONE
        cursor.execute(
            "SELECT phone FROM users WHERE phone = ?",
            (payload.phone_number,)
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Phone number already exists."
            )

        # GENERATE MOCK NUBAN
        generated_nuban = (
            f"10{uuid.uuid4().int % 100000000:08d}"
        )

        welcome_bonus = Decimal("10000.00")

        # INSERT USER
        cursor.execute("""
        INSERT INTO users (
            phone,
            name,
            bvn,
            nin,
            account_number,
            bank_partner,
            balance
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            payload.phone_number,
            payload.full_name.upper(),
            payload.bvn,
            payload.nin,
            generated_nuban,
            "Providus Bank",
            float(welcome_bonus)
        ))

        conn.commit()

        return {
            "status": "SUCCESS",
            "account_details": {
                "account_name": payload.full_name.upper(),
                "account_number": generated_nuban,
                "bank_name": "Floxpay / Providus Bank"
            }
        }

    finally:
        conn.close()

# ---------------------------------------------------------
# FETCH WALLET ENDPOINT
# ---------------------------------------------------------

@app.get("/api/v1/wallet/{phone_number}")
def fetch_wallet(phone_number: str):

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            "SELECT * FROM users WHERE phone = ?",
            (phone_number,)
        )

        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="Wallet profile not found."
            )

        # FETCH RECENT TRANSACTIONS
        cursor.execute("""
        SELECT *
        FROM transactions
        WHERE sender_name = ?
        OR recipient_name = ?
        ORDER BY timestamp DESC
        LIMIT 5
        """, (
            user["name"],
            user["name"]
        ))

        transactions = cursor.fetchall()

        return {
            "name": user["name"],
            "account_number": user["account_number"],
            "bank_partner": user["bank_partner"],
            "balance": user["balance"],
            "recent_transactions": [
                dict(tx)
                for tx in transactions
            ]
        }

    finally:
        conn.close()

# ---------------------------------------------------------
# TRANSFER ENGINE
# ---------------------------------------------------------

@app.post("/api/v1/transfer/send")
def process_transfer(payload: TransferRequest):

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        # BEGIN DATABASE TRANSACTION
        conn.execute("BEGIN")

        # FETCH SENDER
        cursor.execute("""
        SELECT name, balance
        FROM users
        WHERE phone = ?
        """, (
            payload.sender_phone,
        ))

        sender = cursor.fetchone()

        if not sender:
            raise HTTPException(
                status_code=404,
                detail="Sender account not found."
            )

        sender_name = sender["name"]

        sender_balance = Decimal(
            str(sender["balance"])
        )

        # CHECK BALANCE
        if sender_balance < payload.amount:
            raise HTTPException(
                status_code=400,
                detail="Insufficient balance."
            )

        # FETCH RECIPIENT
        cursor.execute("""
        SELECT phone, name
        FROM users
        WHERE account_number = ?
        """, (
            payload.destination_account,
        ))

        recipient = cursor.fetchone()

        if not recipient:
            raise HTTPException(
                status_code=404,
                detail="Invalid beneficiary account."
            )

        recipient_phone = recipient["phone"]
        recipient_name = recipient["name"]

        # DEBIT SENDER
        cursor.execute("""
        UPDATE users
        SET balance = balance - ?
        WHERE phone = ?
        """, (
            float(payload.amount),
            payload.sender_phone
        ))

        # CREDIT RECIPIENT
        cursor.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE phone = ?
        """, (
            float(payload.amount),
            recipient_phone
        ))

        # CREATE TRANSACTION RECORD
        tx_id = str(uuid.uuid4())

        tx_ref = (
            f"FP-NIP-{uuid.uuid4().hex[:10].upper()}"
        )

        cursor.execute("""
        INSERT INTO transactions (
            id,
            sender_name,
            recipient_name,
            amount,
            reference,
            status,
            timestamp
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            tx_id,
            sender_name,
            recipient_name,
            float(payload.amount),
            tx_ref,
            "SUCCESS",
            datetime.utcnow().isoformat()
        ))

        conn.commit()

        return {
            "status": "SUCCESSFUL",
            "receipt": {
                "reference": tx_ref,
                "sender": sender_name,
                "recipient": recipient_name,
                "amount": f"₦{payload.amount:,.2f}"
            }
        }

    except Exception as e:

        conn.rollback()

        if isinstance(e, HTTPException):
            raise e

        raise HTTPException(
            status_code=500,
            detail="Settlement engine failure."
        )

    finally:
        conn.close()

# ---------------------------------------------------------
# FETCH TRANSACTION LEDGER
# ---------------------------------------------------------

@app.get("/api/v1/transactions")
def get_transactions():

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
        SELECT *
        FROM transactions
        ORDER BY timestamp DESC
        """)

        records = cursor.fetchall()

        return {
            "count": len(records),
            "transactions": [
                dict(record)
                for record in records
            ]
        }

    finally:
        conn.close()