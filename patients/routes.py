from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from . import patients_bp
from database import get_db
from flask_mail import Message
from datetime import datetime
from flask import current_app

def get_patient_by_email(email):
    db = get_db()
    patient = db.execute("SELECT * FROM patients WHERE email = ?", (email,)).fetchone()
    return patient

# -------------------------
# Registration & Login
# -------------------------
@patients_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
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

        if db.execute("SELECT * FROM patients WHERE nrc = ?", (nrc,)).fetchone():
            flash("❌ NRC number already registered.", "danger")
            return redirect(url_for("patients.register"))

        if db.execute("SELECT * FROM patients WHERE email = ?", (email,)).fetchone():
            flash("❌ Email already registered.", "danger")
            return redirect(url_for("patients.register"))

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


# -------------------------
# Patient Dashboard
# -------------------------
@patients_bp.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if not session.get("patient_logged_in"):
        flash("⚠️ Please login first.", "warning")
        return redirect(url_for("patients.login"))

    nrc = session.get("patient_nrc")
    patient_name = session.get("patient_name")
    patient_email = session.get("patient_email")
    db = get_db()
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # -------------------------
    # Handle new appointment booking
    # -------------------------
    if request.method == "POST":
        service = request.form.get("service")
        date = request.form.get("date")
        time = request.form.get("time")
        message = request.form.get("message") or ""

        if date < today:
            flash("❌ Appointment date cannot be in the past.", "danger")
            return redirect(url_for("patients.dashboard"))

        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cur = db.execute(
            """
            INSERT INTO appointments 
            (patient_nrc, name, email, service, appointment_date, appointment_time, message, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (nrc, patient_name, patient_email, service, date, time, message, "Pending", created_at)
        )
        db.commit()
        appt_id = cur.lastrowid

        # Email notification
        try:
            mail = current_app.extensions.get("mail")
            if mail:
                subject = f"New Appointment Booking (#{appt_id})"
                body = (
                    f"New appointment booked:\n\n"
                    f"ID: {appt_id}\n"
                    f"Patient: {patient_name}\n"
                    f"Email: {patient_email or '-'}\n"
                    f"Service: {service or '-'}\n"
                    f"Date: {date}  Time: {time}\n"
                    f"Message: {message or '-'}\n"
                    f"Booked at: {created_at} UTC\n"
                )
                msg = Message(subject=subject, sender=current_app.config["MAIL_USERNAME"],
                              recipients=[current_app.config["MAIL_USERNAME"]], body=body)
                mail.send(msg)
        except Exception as e:
            print(f"[MAIL] Failed to send admin email: {e}")

        flash("✅ Appointment booked successfully!", "success")
        return redirect(url_for("patients.dashboard"))

    # -------------------------
    # Fetch categorized appointments
    # -------------------------
    # Upcoming appointments (Pending or Confirmed, future or today)
    upcoming_appointments = db.execute(
        """
        SELECT * FROM appointments
        WHERE patient_nrc=? AND status IN ('Pending','Confirmed') AND appointment_date>=?
        ORDER BY appointment_date ASC, appointment_time ASC
        """,
        (nrc, today)
    ).fetchall()

    # Past appointments (Completed or Cancelled, past dates)
    past_appointments = db.execute(
        """
        SELECT * FROM appointments
        WHERE patient_nrc=? AND (status='Completed' OR status='Cancelled' OR appointment_date<?)
        ORDER BY appointment_date DESC, appointment_time DESC
        """,
        (nrc, today)
    ).fetchall()

    # Last visit (most recent completed appointment)
    last_visit_row = db.execute(
        """
        SELECT appointment_date FROM appointments
        WHERE patient_nrc=? AND status='Completed'
        ORDER BY appointment_date DESC LIMIT 1
        """,
        (nrc,)
    ).fetchone()
    last_visit = last_visit_row["appointment_date"] if last_visit_row else None

    return render_template(
        "patients/dashboard.html",
        upcoming_appointments=upcoming_appointments,
        past_appointments=past_appointments,
        last_visit=last_visit,
        today=today
    )


    # Fetch upcoming appointments
    appointments = db.execute(
        "SELECT * FROM appointments WHERE patient_nrc=? ORDER BY appointment_date ASC",
        (nrc,)
    ).fetchall()

    # Last visit (most recent completed appointment)
    last_visit_row = db.execute(
        "SELECT appointment_date FROM appointments WHERE patient_nrc=? AND status='Completed' ORDER BY appointment_date DESC LIMIT 1",
        (nrc,)
    ).fetchone()
    last_visit = last_visit_row["appointment_date"] if last_visit_row else None

    return render_template(
        "patients/dashboard.html",
        appointments=appointments,
        last_visit=last_visit
    )
    
@patients_bp.route("/cancel_appointment/<int:appt_id>", methods=["POST"])
def cancel_appointment(appt_id):
    if not session.get("patient_logged_in"):
        flash("⚠️ Please login first.", "warning")
        return redirect(url_for("patients.login"))

    db = get_db()
    patient_nrc = session.get("patient_nrc")
    patient_name = session.get("patient_name")
    patient_email = session.get("patient_email")

    appt = db.execute(
        "SELECT * FROM appointments WHERE id=? AND patient_nrc=?", 
        (appt_id, patient_nrc)
    ).fetchone()

    if not appt:
        flash("❌ Appointment not found.", "danger")
    elif appt["status"] != "Pending":
        flash("❌ Only pending appointments can be cancelled.", "warning")
    else:
        # Update appointment status
        db.execute("UPDATE appointments SET status='Cancelled' WHERE id=?", (appt_id,))
        db.commit()
        flash("✅ Appointment cancelled successfully.", "success")

        # -------------------------
        # Send email notification to clinic admin
        # -------------------------
        try:
            mail: "Mail" = current_app.extensions.get("mail")
            if mail:
                subject = f"Appointment Cancelled (#{appt_id})"
                body = (
                    f"Patient cancelled appointment:\n\n"
                    f"ID: {appt_id}\n"
                    f"Patient: {patient_name}\n"
                    f"Email: {patient_email or '-'}\n"
                    f"Service: {appt['service'] or '-'}\n"
                    f"Date: {appt['appointment_date']}  Time: {appt['appointment_time']}\n"
                    f"Message: {appt['message'] or '-'}\n"
                    f"Cancelled at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                )
                msg = Message(
                    subject=subject,
                    sender=current_app.config["MAIL_USERNAME"],
                    recipients=[current_app.config["MAIL_USERNAME"]],
                    body=body
                )
                mail.send(msg)
        except Exception as e:
            print(f"[MAIL] Failed to send admin email: {e}")

    return redirect(url_for("patients.dashboard"))


@patients_bp.route("/logout")
def logout():
    session.clear()
    flash("✅ Logged out successfully.", "success")
    return redirect(url_for("patients.login"))
