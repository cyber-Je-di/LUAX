import os
import sqlite3
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from flask_mail import Mail, Message
from functools import wraps
from dotenv import load_dotenv

# -------------------------
# --- CONFIGURATION SETUP ---
# -------------------------

# Base directory of the project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data directory for storing SQLite database
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Path to SQLite database file
DATABASE = os.path.join(DATA_DIR, "appointments.db")

# Secret key for session management
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Admin password (should be changed in production)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "adminpass")

# Load environment variables from .env file
load_dotenv()

# -------------------------
# --- FLASK APP SETUP ---
# -------------------------
app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY,  # Secret key for session and CSRF protection
    MAIL_SERVER='smtp.gmail.com',  # SMTP server for sending emails
    MAIL_PORT=587,                 # SMTP port
    MAIL_USE_TLS=True,             # Enable TLS encryption
    MAIL_USERNAME=os.environ.get("MAIL_USERNAME"),  # Your email username
    MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD")   # Your email password
)
mail = Mail(app)  # Initialize Flask-Mail

# -------------------------
# --- CLINIC INFORMATION ---
# -------------------------
CLINIC = {
    "name": "LUAX Health Plus",
    "address": "Kamenza 8 Church Road, Chililabombwe, Zambia",
    "phone": "+260965318772",
    "phone_display": "+260 965 318 772",
    "email": "luaxhealth@gmail.com",
    "hours": "24 hour services  ."
}
CLINIC["address_url"] = urllib.parse.quote_plus(CLINIC["address"])

# List of services offered at the clinic
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
    """
    Returns a database connection for the current Flask request context.
    Ensures only one connection per request.
    """
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
        db.row_factory = sqlite3.Row  # Allow accessing columns by name
    return db

def init_db():
    """
    Initializes the appointments table if it doesn't exist.
    """
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()

@app.teardown_appcontext
def close_connection(exception):
    """
    Closes the database connection at the end of a request.
    """
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# -------------------------
# --- ADMIN AUTH DECORATOR ---
# -------------------------

def admin_required(fn):
    """
    Decorator to protect routes that require admin login.
    Redirects to login page if admin is not authenticated.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_authenticated"):
            flash("Please login to access the admin dashboard.", "danger")
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

# -------------------------
# --- USER-FACING ROUTES ---
# -------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    """
    Homepage: Displays appointment form and handles submission.
    """
    if request.method == "POST":
        # Collect form data
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        service = request.form.get("service", "")
        appointment_date = request.form.get("date", "")
        appointment_time = request.form.get("time", "")
        message = request.form.get("message", "").strip()

        # Basic validation
        if not name or not phone or not appointment_date:
            flash("Please fill name, phone and date.", "danger")
            return redirect(url_for("index"))

        # Insert new appointment into the database
        db = get_db()
        cur = db.execute("""
            INSERT INTO appointments (name, email, phone, service, appointment_date, appointment_time, message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, email, phone, service, appointment_date, appointment_time, message))
        db.commit()

        appt_id = cur.lastrowid  # Get the ID of the new appointment
        return redirect(url_for("success", appt_id=appt_id))

    # Render index page with services list and clinic info
    return render_template("index.html", clinic=CLINIC, services=SERVICES)

@app.route("/success")
def success():
    """
    Success page: Shows appointment details after booking.
    """
    appt_id = request.args.get("appt_id")
    appointment = None
    if appt_id:
        db = get_db()
        appointment = db.execute("SELECT * FROM appointments WHERE id = ?", (appt_id,)).fetchone()
    return render_template("success.html", clinic=CLINIC, appointment=appointment)

@app.route("/appointment/<int:appt_id>/cancel", methods=["POST"])
def cancel_appointment(appt_id):
    """
    Cancel appointment route.
    Deletes the appointment from the database completely.
    """
    db = get_db()
    db.execute("DELETE FROM appointments WHERE id=?", (appt_id,))
    db.commit()
    flash("Your appointment has been cancelled and removed.", "success")
    return redirect(url_for("index"))

@app.route("/appointment/<int:appt_id>/update", methods=["GET", "POST"])
def update_appointment(appt_id):
    """
    Update appointment route.
    GET: Shows form pre-filled with existing appointment data.
    POST: Updates appointment in the database.
    """
    db = get_db()
    appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()

    if request.method == "POST":
        # Collect updated form data
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        service = request.form.get("service", "")
        appointment_date = request.form.get("date", "")
        appointment_time = request.form.get("time", "")
        message = request.form.get("message", "").strip()

        # Update appointment in the database
        db.execute("""
            UPDATE appointments
            SET name=?, phone=?, service=?, appointment_date=?, appointment_time=?, message=?
            WHERE id=?
        """, (name, phone, service, appointment_date, appointment_time, message, appt_id))
        db.commit()
        return redirect(url_for("success", appt_id=appt_id))

    # Render update form
    return render_template("update_appointment.html", appointment=appointment, services=SERVICES, clinic=CLINIC)

# -------------------------
# --- ADMIN ROUTES ---
# -------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """
    Admin login page. Validates password and sets session.
    """
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd == ADMIN_PASSWORD:
            session["admin_authenticated"] = True
            flash("Logged in successfully!", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid admin password", "danger")
            return redirect(url_for("admin_login"))

    return render_template("admin_login.html", clinic=CLINIC)

@app.route("/admin/logout")
def admin_logout():
    """
    Logs out the admin by clearing session.
    """
    session.pop("admin_authenticated", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("admin_login"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    """
    Admin dashboard: Shows all appointments.
    """
    db = get_db()
    appointments = db.execute("SELECT * FROM appointments ORDER BY created_at DESC").fetchall()
    return render_template("admin_dashboard.html", appointments=appointments, clinic=CLINIC)

@app.route("/admin/appointment/<int:appt_id>/status", methods=["POST"])
@admin_required
def change_status(appt_id):
    """
    Admin can change the status of an appointment.
    Sends an email to the user notifying them of the status change.
    """
    new_status = request.form.get("status", "Pending")
    db = get_db()
    db.execute("UPDATE appointments SET status = ? WHERE id = ?", (new_status, appt_id))
    db.commit()

    # Send email to user
    appointment = db.execute("SELECT * FROM appointments WHERE id = ?", (appt_id,)).fetchone()
    if appointment and appointment["email"]:
        try:
            msg = Message(
                subject="Your Appointment Status Has Changed",
                recipients=[appointment["email"]],
                body=f"Hello {appointment['name']},\n\n"
                     f"Your appointment on {appointment['appointment_date']} "
                     f"for {appointment['service']} has been {new_status}.\n\n"
                     f"Thank you,\n{CLINIC['name']}"
            )
            mail.send(msg)
        except Exception as e:
            print("Email failed:", e)

    return redirect(url_for("admin_dashboard"))

# -------------------------
# --- USER CHECK STATUS ---
# -------------------------

@app.route("/check_status", methods=["GET", "POST"])
def check_status():
    """
    Allows a user to check appointment status using appointment ID or phone number.
    GET with appt_id: directly retrieves the appointment.
    POST: retrieves appointment from form input (ID or phone).
    """
    appointment = None
    error = None
    appt_id = request.args.get("appt_id")
    
    db = get_db()

    if request.method == "POST":
        # Retrieve form data
        appt_id = request.form.get("appt_id", "").strip()
        phone = request.form.get("phone", "").strip()
        
        if appt_id:
            appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
        elif phone:
            appointment = db.execute("SELECT * FROM appointments WHERE phone=?", (phone,)).fetchone()
        
        if not appointment:
            error = "No appointment found with that ID and phone number. Please check your inputs."
    
    elif appt_id:  # GET request with appointment ID in URL
        appointment = db.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
        if not appointment:
            error = "No appointment found with this ID."

    # Pass clinic info so base.html can use it
    return render_template("check_status.html", appointment=appointment, error=error, clinic=CLINIC)


# -------------------------
# --- MAIN ENTRY POINT ---
# -------------------------
if __name__ == "__main__":
    # Initialize database if it doesn't exist
    with app.app_context():
        init_db()
    # Run the Flask server
    app.run(host="0.0.0.0", port=5000, debug=True)
