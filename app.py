import os
import sqlite3
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from flask_mail import Mail, Message
from functools import wraps
from dotenv import load_dotenv
from datetime import datetime
import smtplib
import re

# -------------------------
# --- CONFIGURATION SETUP ---
# -------------------------
load_dotenv()

EMAIL_ADDRESS = os.environ.get("CLINIC_EMAIL")
EMAIL_PASSWORD = os.environ.get("CLINIC_EMAIL_PASSWORD")

# Flask app
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

# Database setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DATABASE = os.path.join(DATA_DIR, "appointments.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "adminpass")

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

# -------------------------
# --- DATABASE UTILITIES ---
# -------------------------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            service TEXT,
            appointment_date TEXT,
            appointment_time TEXT,
            message TEXT,
            status TEXT DEFAULT 'Pending',
            is_read INTEGER DEFAULT 0,
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
# --- UTILITY FUNCTIONS ---
# -------------------------
def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def send_email(recipient, subject, message):
    if not is_valid_email(recipient):
        print(f"❌ Invalid email: {recipient}")
        return
    try:
        email_msg = Message(
            subject=subject,
            body=message,
            sender=EMAIL_ADDRESS,
            recipients=[recipient]
        )
        mail.send(email_msg)
        print(f"✅ Email sent to {recipient}")
    except Exception as e:
        print(f"❌ Email failed: {e}")

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_authenticated"):
            flash("Please login to access the admin dashboard.", "danger")
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

# Add this new function
def get_unread_count():
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM appointments WHERE is_read = 0").fetchone()[0]
    return count

# Add this context processor
@app.context_processor
def inject_notifications():
    unread_count = get_unread_count()
    return {'current_year': datetime.now().year, 'unread_count': unread_count}

# -------------------------
# --- ROUTES ---
# -------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        service = request.form["service"]
        appointment_date = request.form["date"]
        appointment_time = request.form["time"]
        message = request.form.get("message", "").strip()

        db = get_db()
        cur = db.execute("""
            INSERT INTO appointments
            (name, email, phone, service, appointment_date, appointment_time, message, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, email, phone, service, appointment_date, appointment_time, message, "Pending"))
        db.commit()
        appt_id = cur.lastrowid

        # --- ADD THIS SECTION TO SEND EMAILS ---
        # Send confirmation email to the patient
        if email:
            patient_subject = "Appointment Confirmation"
            patient_message = (
                f"Hello {name},\n\n"
                f"Your appointment for {service} on {appointment_date} at {appointment_time} "
                f"has been successfully booked. We'll be in touch soon to confirm details.\n\n"
                f"Thank you!\nLUAX Health Plus"
            )
            send_email(email, patient_subject, patient_message)

        # Notify the admin of a new booking
        admin_subject = "New Appointment Booked"
        admin_message = (
            f"A new appointment has been booked.\n\n"
            f"Patient Name: {name}\n"
            f"Service: {service}\n"
            f"Date: {appointment_date}\n"
            f"Time: {appointment_time}\n"
            f"Email: {email or 'N/A'}\n"
            f"Phone: {phone or 'N/A'}"
        )
        send_email(os.environ.get("CLINIC_EMAIL"), admin_subject, admin_message)
        # --- END OF NEW SECTION ---

        return redirect(url_for("success", appt_id=appt_id))
    return render_template("index.html", clinic=CLINIC, services=SERVICES)

@app.route("/success")
def success():
    appt_id = request.args.get("appt_id")
    appointment = None
    if appt_id:
        db = get_db()
        appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
    return render_template("success.html", clinic=CLINIC, appointment=appointment)

@app.route("/appointment/<int:appt_id>/cancel", methods=["POST"])
def cancel_appointment(appt_id):
    db = get_db()
    db.execute("DELETE FROM appointments WHERE id=?", (appt_id,))
    db.commit()
    flash("Your appointment has been cancelled.", "success")
    return redirect(url_for("index"))

@app.route("/appointment/<int:appt_id>/update", methods=["GET", "POST"])
def update_appointment(appt_id):
    db = get_db()
    appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        service = request.form.get("service", "")
        appointment_date = request.form.get("date", "")
        appointment_time = request.form.get("time", "")
        message = request.form.get("message", "").strip()
        db.execute("""
            UPDATE appointments
            SET name=?, phone=?, service=?, appointment_date=?, appointment_time=?, message=?
            WHERE id=?
        """, (name, phone, service, appointment_date, appointment_time, message, appt_id))
        db.commit()
        return redirect(url_for("success", appt_id=appt_id))
    return render_template("update_appointment.html", appointment=appointment, services=SERVICES, clinic=CLINIC)

# Admin routes
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
            return redirect(url_for("admin_login"))
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
    
    # Mark all unread appointments as read when the admin dashboard is accessed
    db.execute("UPDATE appointments SET is_read = 1 WHERE is_read = 0")
    db.commit()
    
    appointments = db.execute("SELECT * FROM appointments ORDER BY created_at DESC").fetchall()
    return render_template("admin_dashboard.html", appointments=appointments, clinic=CLINIC)

@app.route("/admin/update_status/<int:appt_id>", methods=["POST"])
@admin_required
def admin_update_status(appt_id):
    new_status = request.form.get("status")
    custom_message = request.form.get("custom_message", "").strip()
    notify_email = request.form.get("notify_email")

    db = get_db()
    db.execute("UPDATE appointments SET status=? WHERE id=?", (new_status, appt_id))
    db.commit()

    appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
    if not appointment:
        flash("Appointment not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    msg = custom_message or (
        f"Hello {appointment['name']},\n\n"
        f"Your appointment (ID: {appointment['id']}) for {appointment['service']} "
        f"on {appointment['appointment_date']} at {appointment['appointment_time']} "
        f"is now {new_status}.\n\nThank you for choosing our clinic!"
    )

    # Send email if requested
    if notify_email and appointment["email"]:
        send_email(appointment["email"], f"Appointment Status Update: {new_status}", msg)

    flash("Appointment status updated and notifications sent!", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/check_status", methods=["GET", "POST"])
def check_status():
    appointment = None
    error = None
    appt_id = request.args.get("appt_id")
    db = get_db()

    if request.method == "POST":
        appt_id = request.form.get("appt_id", "").strip()
        phone = request.form.get("phone", "").strip()
        if appt_id:
            appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
        elif phone:
            appointment = db.execute("SELECT * FROM appointments WHERE phone=?", (phone,)).fetchone()
        if not appointment:
            error = "No appointment found. Please check your inputs."
    elif appt_id:
        appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
        if not appointment:
            error = "No appointment found with this ID."

    return render_template("check_status.html", appointment=appointment, error=error, clinic=CLINIC)

# -------------------------
# --- MAIN ENTRY POINT ---
# -------------------------
if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
