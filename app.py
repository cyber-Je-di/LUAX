import os
import urllib.parse
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for, flash
)
from flask_mail import Mail, Message
from dotenv import load_dotenv

# Blueprints & DB helpers you already have
from patients import patients_bp            # expects blueprint name "patients" with a `login` view
from admin import admin_bp                  # expects blueprint name "admin" with a `login` view
from database import get_db, init_db, close_connection

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
    MAIL_PASSWORD=EMAIL_PASSWORD,
)
mail = Mail(app)

# Register blueprints
app.register_blueprint(patients_bp)
app.register_blueprint(admin_bp)

# DB teardown hook
app.teardown_appcontext(close_connection)

# -------------------------
# CLINIC INFO
# -------------------------
CLINIC = {
    "name": "LUAX Health Plus",
    "address": "Kamenza 8 Church Road, Chililabombwe, Zambia",
    "phone": "+260965318772",
    "phone_display": "+260 965 318 772",
    "email": EMAIL_ADDRESS,
    "hours": "24 hour services",
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
    "AI Diagnostics",
]

app.config["CLINIC"] = CLINIC

# -------------------------
# CONTEXT PROCESSORS
# -------------------------
@app.context_processor
def inject_now():
    return {'current_year': datetime.now().year}

@app.context_processor
def inject_notifications():
    db = get_db()
    # make sure table exists before count
    db.execute("""
      CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        email TEXT,
        service TEXT,
        appointment_date TEXT,
        appointment_time TEXT,
        message TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TEXT
      )
    """)
    unread_count = db.execute("SELECT COUNT(*) FROM appointments WHERE IFNULL(is_read,0)=0").fetchone()[0]
    return {'current_year': datetime.now().year, 'unread_count': unread_count}

# -------------------------
# UTILITIES
# -------------------------
def send_admin_email(subject: str, body: str):
    """Send an email notification to the clinic admin."""
    if not EMAIL_ADDRESS:
        return  # no email configured
    try:
        msg = Message(
            subject=subject,
            sender=EMAIL_ADDRESS,
            recipients=[EMAIL_ADDRESS],
            body=body
        )
        mail.send(msg)
    except Exception as e:
        # Don't crash the request if email fails; log and continue
        print(f"[MAIL] Failed to send admin email: {e}")

def ensure_schema():
    """Ensure the appointments table exists with all needed columns."""
    db = get_db()

    # Create the table if it doesn't exist (only id and created_at initially)
    db.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT
        )
    """)
    db.commit()

    # Get existing columns
    existing_cols = [row[1] for row in db.execute("PRAGMA table_info(appointments)").fetchall()]

    # Define all required columns with types/defaults
    required_cols = {
        "name": "TEXT",
        "phone": "TEXT",
        "email": "TEXT",
        "service": "TEXT",
        "appointment_date": "TEXT",
        "appointment_time": "TEXT",
        "message": "TEXT",
        "status": "TEXT DEFAULT 'Pending'",
        "is_read": "INTEGER DEFAULT 0",
        "patient_nrc": "TEXT"
    }

    # Add missing columns dynamically
    for col, col_type in required_cols.items():
        if col not in existing_cols:
            db.execute(f"ALTER TABLE appointments ADD COLUMN {col} {col_type}")

    db.commit()


# -------------------------
# ROUTES
# -------------------------
from datetime import datetime

@app.route("/", methods=["GET", "POST"])
def index():
    ensure_schema()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        country_code = (request.form.get("country_code") or "").strip()
        phone_local = (request.form.get("phone") or "").strip()
        phone = f"{country_code}{phone_local}".replace(" ", "")
        email = (request.form.get("email") or "").strip()
        service = (request.form.get("service") or "").strip()
        appointment_date = request.form.get("date")
        appointment_time = request.form.get("time")
        message = (request.form.get("message") or "").strip()

        # Basic validation
        if not name or not phone or not appointment_date or not appointment_time:
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("index"))

        # Save to DB with SQLite-friendly timestamp
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        db = get_db()
        cur = db.execute("""
            INSERT INTO appointments
                (name, phone, email, service, appointment_date, appointment_time, message, is_read, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
        """, (name, phone, email, service, appointment_date, appointment_time, message, created_at))
        db.commit()
        appt_id = cur.lastrowid

        # Email admin
        subject = f"New Appointment Booking (#{appt_id})"
        body = (
            f"New appointment booked:\n\n"
            f"ID: {appt_id}\n"
            f"Name: {name}\n"
            f"Phone: {phone}\n"
            f"Email: {email or '-'}\n"
            f"Service: {service or '-'}\n"
            f"Date: {appointment_date}  Time: {appointment_time}\n"
            f"Message: {message or '-'}\n"
            f"Booked at: {created_at} UTC\n"
        )
        send_admin_email(subject, body)

        flash("✅ Appointment booked successfully!", "success")
        return redirect(url_for("success", appt_id=appt_id))

    return render_template("index.html", clinic=CLINIC, services=SERVICES)


@app.route("/success")
def success():
    ensure_schema()
    appt_id = request.args.get("appt_id")
    appointment = None
    if appt_id:
        appointment = get_db().execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
    return render_template("success.html", clinic=CLINIC, appointment=appointment)

@app.route("/check_status", methods=["GET","POST"])
def check_status():
    ensure_schema()
    appointment = None
    error = None
    db = get_db()

    if request.method == "POST":
        appt_id = (request.form.get("appt_id") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        if appt_id:
            appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
        elif phone:
            appointment = db.execute("SELECT * FROM appointments WHERE phone=?", (phone,)).fetchone()
        if not appointment:
            error = "No appointment found."
    else:
        appt_id = request.args.get("appt_id")
        if appt_id:
            appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
            if not appointment:
                error = "No appointment found with this ID."

    return render_template("check_status.html", appointment=appointment, error=error, clinic=CLINIC)

# Named endpoint used by base.html brand link
app.add_url_rule("/", endpoint="index", view_func=index, methods=["GET", "POST"])

@app.route("/update_appointment/<int:appt_id>", methods=["GET", "POST"])
def update_appointment(appt_id):
    db = get_db()
    appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()

    if not appointment:
        flash("Appointment not found.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        # Collect updated data
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        service = request.form.get("service", "").strip()
        date = request.form.get("date")
        time = request.form.get("time")
        message = request.form.get("message", "").strip()

        # Save updates
        db.execute("""
            UPDATE appointments 
            SET name=?, phone=?, email=?, service=?, appointment_date=?, appointment_time=?, message=?
            WHERE id=?
        """, (name, phone, email, service, date, time, message, appt_id))
        db.commit()

        flash("Appointment updated successfully!", "success")
        return redirect(url_for("success", appt_id=appt_id))

    return render_template("update_appointment.html", appointment=appointment, services=SERVICES)

@app.route("/cancel_appointment/<int:appt_id>", methods=["POST"])
def cancel_appointment(appt_id):
    db = get_db()
    appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()

    if not appointment:
        flash("Appointment not found.", "danger")
        return redirect(url_for("index"))

    # Update status to Cancelled
    db.execute("UPDATE appointments SET status='Cancelled' WHERE id=?", (appt_id,))
    db.commit()

    flash(f"Appointment #{appt_id} has been cancelled.", "success")
    return redirect(url_for("success", appt_id=appt_id))



# -------------------------
# APP ENTRY
# -------------------------
if __name__ == "__main__":
    with app.app_context():
        # Initialize any DB bits your database module needs
        try:
            init_db()
        except Exception as e:
            # Continue even if init_db does nothing; ensure our schema
            print(f"[DB] init_db warning: {e}")
        ensure_schema()
    app.run(host="0.0.0.0", port=5000, debug=True)
