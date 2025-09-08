import os
import sqlite3
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from flask_mail import Mail, Message
from functools import wraps
from dotenv import load_dotenv
from datetime import datetime
import re

# Import patients Blueprint
from patients import patients_bp

# -------------------------
# CONFIGURATION
# -------------------------
load_dotenv()

EMAIL_ADDRESS = os.environ.get("CLINIC_EMAIL")
EMAIL_PASSWORD = os.environ.get("CLINIC_EMAIL_PASSWORD")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "adminpass")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=EMAIL_ADDRESS,
    MAIL_PASSWORD=EMAIL_PASSWORD
)
mail = Mail(app)

# Register patients Blueprint
app.register_blueprint(patients_bp)

# Database setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DATABASE = os.path.join(DATA_DIR, "Luax_DB.db")  # Central DB

# Clinic info
CLINIC = {
    "name": "LUAX Health Plus",
    "address": "Kamenza 8 Church Road, Chililabombwe, Zambia",
    "phone": "+260965318772",
    "phone_display": "+260 965 318 772",
    "email": EMAIL_ADDRESS,
    "hours": "24 hour services"
}
CLINIC["address_url"] = urllib.parse.quote_plus(CLINIC["address"])

SERVICES = [
    "General Consultation (OPD)",
    "Observation / Short-term Care",
    "Pharmacy",
    "Laboratory & Diagnostics",
    "Ultrasound Scanning",
    "Dental Services",
    "Physiotherapy",
    "Telemedicine",
    "Mobile Clinics / Outreach",
    "AI Diagnostics"
]

app.config["CLINIC"] = CLINIC

# -------------------------
# DATABASE UTILITIES
# -------------------------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(patient_nrc) REFERENCES patients(nrc)
        )
    """)
    # Staff Table (future)
    db.execute("""
        CREATE TABLE IF NOT EXISTS staff (
            staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL,
            password TEXT NOT NULL,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

@app.context_processor
def inject_now():
    return {'current_year': datetime.now().year}

# -------------------------
# UTILITY FUNCTIONS
# -------------------------
def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def send_email(recipient, subject, message):
    if not is_valid_email(recipient):
        return
    try:
        email_msg = Message(subject=subject, body=message, sender=EMAIL_ADDRESS, recipients=[recipient])
        mail.send(email_msg)
    except Exception as e:
        print(f"Email send failed: {e}")

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_authenticated"):
            flash("Please login to access the admin dashboard.", "danger")
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

def get_unread_count():
    db = get_db()
    return db.execute("SELECT COUNT(*) FROM appointments WHERE is_read=0").fetchone()[0]

@app.context_processor
def inject_notifications():
    return {'current_year': datetime.now().year, 'unread_count': get_unread_count()}

# -------------------------
# MAIN ROUTES
# -------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        patient_nrc = request.form.get("nrc", "").strip()
        service = request.form["service"]
        appointment_date = request.form["date"]
        appointment_time = request.form["time"]
        message = request.form.get("message", "").strip()

        db = get_db()
        db.execute("""
            INSERT INTO appointments (patient_nrc, service, appointment_date, appointment_time, message)
            VALUES (?, ?, ?, ?, ?)
        """, (patient_nrc, service, appointment_date, appointment_time, message))
        db.commit()
        flash("✅ Appointment booked successfully!", "success")
        return redirect(url_for("index"))

    return render_template("index.html", clinic=CLINIC, services=SERVICES)

@app.route("/success")
def success():
    appt_id = request.args.get("appt_id")
    appointment = None
    if appt_id:
        appointment = get_db().execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
    return render_template("success.html", clinic=CLINIC, appointment=appointment)

# -------------------------
# ADMIN ROUTES
# -------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd == ADMIN_PASSWORD:
            session["admin_authenticated"] = True
            flash("Logged in successfully!", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid password", "danger")
    return render_template("admin_login.html", clinic=CLINIC)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_authenticated", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("admin_login"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    db.execute("UPDATE appointments SET is_read=1 WHERE is_read=0")
    db.commit()

    appointments = db.execute("""
        SELECT a.*, p.name, p.email, p.phone 
        FROM appointments a
        LEFT JOIN patients p ON a.patient_nrc = p.nrc
        ORDER BY a.created_at DESC
    """).fetchall()

    return render_template("admin_dashboard.html", appointments=appointments, clinic=CLINIC)

@app.route("/admin/appointment/<int:appt_id>/update_status", methods=["POST"])
@admin_required
def admin_update_status(appt_id):
    new_status = request.form.get("status")
    custom_message = request.form.get("custom_message", "")
    notify_email = request.form.get("notify_email")
    db = get_db()

    if new_status not in ["Pending", "Confirmed", "Cancelled", "Completed"]:
        flash("Invalid status", "danger")
        return redirect(url_for("admin_dashboard"))

    db.execute("UPDATE appointments SET status=? WHERE id=?", (new_status, appt_id))
    db.commit()

    # Optional: send email notification
    if notify_email and custom_message:
        appt = db.execute("SELECT a.*, p.email FROM appointments a LEFT JOIN patients p ON a.patient_nrc=p.nrc WHERE a.id=?", (appt_id,)).fetchone()
        if appt and appt['email']:
            send_email(appt['email'], "Appointment Status Update", custom_message)

    flash(f"Appointment #{appt_id} status updated to {new_status}", "success")
    return redirect(url_for("admin_dashboard"))

# -------------------------
# CHECK STATUS
# -------------------------
@app.route("/check_status", methods=["GET","POST"])
def check_status():
    appointment = None
    error = None
    appt_id = request.args.get("appt_id")
    db = get_db()

    if request.method=="POST":
        appt_id = request.form.get("appt_id","").strip()
        phone = request.form.get("phone","").strip()
        if appt_id:
            appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
        elif phone:
            appointment = db.execute("SELECT * FROM appointments WHERE phone=?", (phone,)).fetchone()
        if not appointment:
            error="No appointment found."
    elif appt_id:
        appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
        if not appointment:
            error="No appointment found with this ID."
    return render_template("check_status.html", appointment=appointment, error=error, clinic=CLINIC)

# -------------------------
# MAIN ENTRY
# -------------------------
if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
