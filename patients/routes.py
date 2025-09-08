from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from . import patients_bp
import sqlite3
import os

# --- Use central database ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "Luax_DB.db")  # central DB

# -------------------------
# Helper functions
# -------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Patients table
    c.execute("""
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Appointments table
    c.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_nrc TEXT,
            service TEXT,
            appointment_date TEXT,
            appointment_time TEXT,
            message TEXT,
            status TEXT DEFAULT 'Pending',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(patient_nrc) REFERENCES patients(nrc)
        )
    """)
    conn.commit()
    conn.close()

def get_patient_by_email(email):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM patients WHERE email = ?", (email,))
    patient = c.fetchone()
    conn.close()
    return patient

# -------------------------
# Routes
# -------------------------
@patients_bp.route("/register", methods=["GET", "POST"])
def register():
    init_db()  # ensure tables exist
    if request.method == "POST":
        # Form data
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        nrc = request.form.get("nrc")
        name = request.form.get("name")
        dob = request.form.get("dob")
        gender = request.form.get("gender")
        phone = request.form.get("phone")
        address = request.form.get("address")
        blood_type = request.form.get("blood_type")
        allergies = request.form.get("allergies")
        emergency_contact = request.form.get("emergency_contact")
        occupation = request.form.get("occupation")
        employer = request.form.get("employer")
        insurance_provider = request.form.get("insurance_provider")
        policy_number = request.form.get("policy_number")

        if password != confirm_password:
            flash("❌ Passwords do not match.", "danger")
            return redirect(url_for("patients.register"))

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Check existing NRC/email
        c.execute("SELECT * FROM patients WHERE nrc = ?", (nrc,))
        if c.fetchone():
            flash("❌ NRC number already registered.", "danger")
            conn.close()
            return redirect(url_for("patients.register"))

        c.execute("SELECT * FROM patients WHERE email = ?", (email,))
        if c.fetchone():
            flash("❌ Email already registered.", "danger")
            conn.close()
            return redirect(url_for("patients.register"))

        # Insert
        hashed_password = generate_password_hash(password)
        c.execute("""
            INSERT INTO patients 
            (nrc, name, email, password, dob, gender, phone, address, blood_type, allergies,
             emergency_contact, occupation, employer, insurance_provider, policy_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nrc, name, email, hashed_password, dob, gender, phone, address, blood_type, allergies,
              emergency_contact, occupation, employer, insurance_provider, policy_number))
        conn.commit()
        conn.close()

        flash("✅ Account created successfully! Please login.", "success")
        return redirect(url_for("patients.login"))

    return render_template("patients/register.html")


@patients_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        patient = get_patient_by_email(email)
        if not patient:
            flash("❌ Email not found.", "danger")
            return redirect(url_for("patients.login"))

        if not check_password_hash(patient["password"], password):
            flash("❌ Incorrect password.", "danger")
            return redirect(url_for("patients.login"))

        session["patient_logged_in"] = True
        session["patient_name"] = patient["name"]
        session["patient_nrc"] = patient["nrc"]
        session["patient_email"] = patient["email"]
        flash(f"✅ Welcome, {patient['name']}!", "success")
        return redirect(url_for("patients.dashboard"))

    return render_template("patients/patient_login.html")


@patients_bp.route("/dashboard")
def dashboard():
    if not session.get("patient_logged_in"):
        flash("⚠️ Please login first.", "warning")
        return redirect(url_for("patients.login"))

    nrc = session.get("patient_nrc")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Fetch upcoming appointments
    c.execute("SELECT * FROM appointments WHERE patient_nrc=? ORDER BY appointment_date ASC", (nrc,))
    appointments = c.fetchall()

    # Last visit (most recent completed appointment)
    c.execute("SELECT appointment_date FROM appointments WHERE patient_nrc=? AND status='Completed' ORDER BY appointment_date DESC LIMIT 1", (nrc,))
    last_visit_row = c.fetchone()
    last_visit = last_visit_row["appointment_date"] if last_visit_row else None

    conn.close()

    return render_template(
        "patients/dashboard.html",
        appointments=appointments,
        last_visit=last_visit
    )
    
@patients_bp.route("/check_status", methods=["GET", "POST"], endpoint="check_appointments")
def check_appointments():
    appointment = None
    error = None

    if request.method == "POST":
        appt_id = request.form.get("appt_id")
        phone = request.form.get("phone")

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT * FROM appointments WHERE id=? AND phone=?", (appt_id, phone))
        appointment = c.fetchone()
        conn.close()

        if not appointment:
            error = "❌ Appointment not found. Please check your ID and phone number."

    return render_template("patients/check_status.html", appointment=appointment, error=error)



@patients_bp.route("/logout")
def logout():
    session.clear()
    flash("✅ Logged out successfully.", "success")
    return redirect(url_for("patients.login"))
