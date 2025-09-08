from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from . import patients_bp
from database import get_db

def get_patient_by_email(email):
    db = get_db()
    patient = db.execute("SELECT * FROM patients WHERE email = ?", (email,)).fetchone()
    return patient

# -------------------------
# Routes
# -------------------------
@patients_bp.route("/register", methods=["GET", "POST"])
def register():
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

        db = get_db()

        # Check existing NRC/email
        if db.execute("SELECT * FROM patients WHERE nrc = ?", (nrc,)).fetchone():
            flash("❌ NRC number already registered.", "danger")
            return redirect(url_for("patients.register"))

        if db.execute("SELECT * FROM patients WHERE email = ?", (email,)).fetchone():
            flash("❌ Email already registered.", "danger")
            return redirect(url_for("patients.register"))

        # Insert
        hashed_password = generate_password_hash(password)
        db.execute("""
            INSERT INTO patients 
            (nrc, name, email, password, dob, gender, phone, address, blood_type, allergies,
             emergency_contact, occupation, employer, insurance_provider, policy_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nrc, name, email, hashed_password, dob, gender, phone, address, blood_type, allergies,
              emergency_contact, occupation, employer, insurance_provider, policy_number))
        db.commit()

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
    db = get_db()

    # Fetch upcoming appointments
    appointments = db.execute("SELECT * FROM appointments WHERE patient_nrc=? ORDER BY appointment_date ASC", (nrc,)).fetchall()

    # Last visit (most recent completed appointment)
    last_visit_row = db.execute("SELECT appointment_date FROM appointments WHERE patient_nrc=? AND status='Completed' ORDER BY appointment_date DESC LIMIT 1", (nrc,)).fetchone()
    last_visit = last_visit_row["appointment_date"] if last_visit_row else None

    return render_template(
        "patients/dashboard.html",
        appointments=appointments,
        last_visit=last_visit
    )

@patients_bp.route("/logout")
def logout():
    session.clear()
    flash("✅ Logged out successfully.", "success")
    return redirect(url_for("patients.login"))
