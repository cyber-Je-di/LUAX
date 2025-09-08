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
from admin import admin_bp
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
    MAIL_PASSWORD=EMAIL_PASSWORD
)
mail = Mail(app)

# Register patients Blueprint
app.register_blueprint(patients_bp)
app.register_blueprint(admin_bp)

# Database setup
app.teardown_appcontext(close_connection)


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

@app.context_processor
def inject_now():
    return {'current_year': datetime.now().year}

from utils import is_valid_email, send_email

@app.context_processor
def inject_notifications():
    db = get_db()
    unread_count = db.execute("SELECT COUNT(*) FROM appointments WHERE is_read=0").fetchone()[0]
    return {'current_year': datetime.now().year, 'unread_count': unread_count}

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
