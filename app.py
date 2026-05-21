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
# DATABASE CONNECTION HELPER (SQLite mode for transactions)
# ---------------------------------------------------------

def get_sqlite_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------------------------------------------------
# PYDANTIC SCHEMAS
# ---------------------------------------------------------

class SignupRequest(BaseModel):
    full_name: str

    phone_number: str = Field(..., min_length=11, max_length=11)
    bvn: str = Field(..., min_length=11, max_length=11)
    nin: str = Field(..., min_length=11, max_length=11)


class TransferRequest(BaseModel):
    sender_phone: str
    destination_account: str
    amount: Decimal = Field(..., gt=0)

# ---------------------------------------------------------
# ROOT
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
# SQLITE TRANSACTION FETCH (YOUR REQUESTED INTEGRATION)
# ---------------------------------------------------------

def get_transactions():

    conn = None

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, amount, reference, status, timestamp
            FROM transactions
            ORDER BY id DESC
        """)

        records = cursor.fetchall()

        transaction_list = []

        for row in records:
            transaction_list.append({
                "id": row[0],
                "amount": row[1],
                "reference": row[2],
                "status": row[3],
                "date": row[4]
            })

        return {
            "count": len(transaction_list),
            "transactions": transaction_list
        }

    except sqlite3.Error:
        return {
            "count": 0,
            "transactions": []
        }

    finally:
        if conn:
            conn.close()

# ---------------------------------------------------------
# TRANSACTION ENDPOINT (NOW USING SQLITE FUNCTION)
# ---------------------------------------------------------

@app.get("/api/v1/transactions")
def api_transactions():
    return get_transactions()