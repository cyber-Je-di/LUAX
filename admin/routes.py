from flask import render_template, request, redirect, url_for, flash, session
from . import admin_bp
from database import get_db
import os
from functools import wraps

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "adminpass")

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_authenticated"):
            flash("Please login to access the admin dashboard.", "danger")
            return redirect(url_for("admin.login"))
        return fn(*args, **kwargs)
    return wrapper

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd == ADMIN_PASSWORD:
            session["admin_authenticated"] = True
            flash("Logged in successfully!", "success")
            return redirect(url_for("admin.dashboard"))
        else:
            flash("Invalid password", "danger")
    return render_template("admin_login.html")

@admin_bp.route("/logout")
def logout():
    session.pop("admin_authenticated", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("admin.login"))

@admin_bp.route("/")
@admin_required
def dashboard():
    db = get_db()
    
    # Mark all unread appointments as read
    db.execute("UPDATE appointments SET is_read=1 WHERE is_read=0")
    db.commit()

    # Fetch appointments, join with patients if linked
    raw_appointments = db.execute("""
        SELECT a.*, 
               p.name AS patient_name, 
               p.email AS patient_email, 
               p.phone AS patient_phone
        FROM appointments a
        LEFT JOIN patients p ON a.patient_nrc = p.nrc
        ORDER BY a.created_at DESC
    """).fetchall()

    # Prepare appointments for template
    appointments = []
    for appt in raw_appointments:
        appt_dict = dict(appt)

        # Use patient info if available, else fallback to appointment fields
        appt_dict["name"] = appt_dict.get("patient_name") or appt_dict.get("name") or "Unknown"
        appt_dict["email"] = appt_dict.get("patient_email") or appt_dict.get("email") or "-"
        appt_dict["phone"] = appt_dict.get("patient_phone") or appt_dict.get("phone") or "-"

        # Format created_at safely
        created = appt_dict.get("created_at")
        if created is None:
            appt_dict["created_at"] = "N/A"
        else:
            # If it's a datetime object, format it
            try:
                appt_dict["created_at"] = created.strftime("%Y-%m-%d %H:%M:%S")
            except AttributeError:
                appt_dict["created_at"] = str(created)

        # Default status if missing
        appt_dict["status"] = appt_dict.get("status") or "Pending"

        appointments.append(appt_dict)

    return render_template("admin_dashboard.html", appointments=appointments)



@admin_bp.route("/appointment/<int:appt_id>/update_status", methods=["POST"])
@admin_required
def update_status(appt_id):
    new_status = request.form.get("status")
    custom_message = request.form.get("custom_message", "")
    notify_email = request.form.get("notify_email")
    db = get_db()

    if new_status not in ["Pending", "Confirmed", "Cancelled", "Completed"]:
        flash("Invalid status", "danger")
        return redirect(url_for("admin.dashboard"))

    db.execute("UPDATE appointments SET status=? WHERE id=?", (new_status, appt_id))
    db.commit()

    # Optional: send email notification
    if notify_email and custom_message:
        from utils import send_email
        appt = db.execute("SELECT a.*, p.email FROM appointments a LEFT JOIN patients p ON a.patient_nrc=p.nrc WHERE a.id=?", (appt_id,)).fetchone()
        if appt and appt['email']:
            send_email(appt['email'], "Appointment Status Update", custom_message)

    flash(f"Appointment #{appt_id} status updated to {new_status}", "success")
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/patients", methods=["GET", "POST"])
@admin_required
def view_patients():
    db = get_db()
    search_query = request.args.get("search", "").strip()

    if search_query:
        patients = db.execute("""
            SELECT * FROM patients
            WHERE name LIKE ? OR email LIKE ? OR nrc LIKE ?
            ORDER BY created_at DESC
        """, (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%")).fetchall()
    else:
        patients = db.execute("SELECT * FROM patients ORDER BY created_at DESC").fetchall()
    
    # Convert to dict to avoid template errors
    patient_list = []
    for p in patients:
        p_dict = dict(p)
        p_dict["created_at"] = str(p_dict.get("created_at", "N/A"))
        patient_list.append(p_dict)
    
    return render_template("admin_patients.html", patients=patient_list, search_query=search_query)


# Delete an appointment
@admin_bp.route("/appointment/<int:appt_id>/delete", methods=["POST"])
@admin_required
def delete_appointment(appt_id):
    db = get_db()
    db.execute("DELETE FROM appointments WHERE id=?", (appt_id,))
    db.commit()
    flash(f"Appointment #{appt_id} has been deleted.", "success")
    return redirect(url_for("admin.dashboard"))

# Delete a patient
@admin_bp.route("/patient/<string:nrc>/delete", methods=["POST"])
@admin_required
def delete_patient(nrc):
    db = get_db()
    # Delete associated appointments first
    db.execute("DELETE FROM appointments WHERE patient_nrc=?", (nrc,))
    db.execute("DELETE FROM patients WHERE nrc=?", (nrc,))
    db.commit()
    flash(f"Patient {nrc} and their appointments have been deleted.", "success")
    return redirect(url_for("admin.view_patients"))
