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
    db.execute("UPDATE appointments SET is_read=1 WHERE is_read=0")
    db.commit()

    appointments = db.execute("""
        SELECT a.*, p.name, p.email, p.phone
        FROM appointments a
        LEFT JOIN patients p ON a.patient_nrc = p.nrc
        ORDER BY a.created_at DESC
    """).fetchall()

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
