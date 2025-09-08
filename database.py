import sqlite3
import os
from flask import g

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DATABASE = os.path.join(DATA_DIR, "Luax_DB.db")

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)  # no PARSE_DECLTYPES
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    # Patients Table
    db.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            nrc TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            dob TEXT,
            gender TEXT,
            phone TEXT,
            address TEXT,
            blood_type TEXT,
            allergies TEXT,
            emergency_contact TEXT,
            occupation TEXT,
            employer TEXT,
            insurance_provider TEXT,
            policy_number TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Appointments Table
    db.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_nrc TEXT,
            service TEXT,
            appointment_date TEXT,
            appointment_time TEXT,
            message TEXT,
            status TEXT DEFAULT 'Pending',
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(patient_nrc) REFERENCES patients(nrc)
        )
    """)
    db.commit()

def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()
