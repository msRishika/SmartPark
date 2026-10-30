"""
app.py
Flask Application for SmartPark - Professional Parking Management System.
Connects web frontend with SQLite database, ParkingManager DSA engine,
and ReportLab PDF invoice generation.
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
import os
import math
from datetime import datetime

from database import init_db, DEFAULT_DB_PATH
from parking_manager import (
    ParkingManager,
    CATEGORY_RATES,
    validate_vehicle_registration,
    validate_driver_contact_number
)
from pdf_generator import generate_receipt_pdf

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smartpark-midnight-teal-secret-key-2026")

# Initialize SQLite database if it doesn't exist
init_db(DEFAULT_DB_PATH)

# Initialize the ParkingManager engine
pm = ParkingManager(DEFAULT_DB_PATH)


# =============================================================================
# SECURITY, AUTH & CACHE CONTROL HEADERS
# =============================================================================

@app.before_request
def check_auth_and_access():
    """
    Enforces authentication and role-based route protection (Requirement 1):
    - When website opens or unauthenticated, redirects to login page.
    - Protects admin routes on backend: users cannot access /admin URLs directly.
    - Allows unauthenticated access to login, static assets, and testing overrides.
    """
    # Allowed unauthenticated endpoints
    allowed_endpoints = {"root_route", "login", "login_user", "login_admin", "static"}
    if request.endpoint in allowed_endpoints:
        return None

    # Redirect unauthenticated requests to login page
    if not session.get("user") and not session.get("role"):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "message": "Unauthorized"}), 401
        return redirect(url_for("login"))

    # Protect admin routes on the backend
    if request.path.startswith("/admin"):
        if session.get("role") != "admin":
            flash("Access denied. Administrator privileges required.", "danger")
            return redirect(url_for("dashboard"))


@app.after_request
def add_security_headers(response):
    """
    Prevents back-navigation to protected pages after logout (Requirement 1).
    Ensures browser does not display cached authenticated pages.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# =============================================================================
# TEMPLATE FILTERS & CONTEXT INJECTION
# =============================================================================

@app.template_filter("currency")
def currency_filter(value):
    """Safely format values into Indian Rupee string without throwing TypeErrors."""
    try:
        val = float(value)
        return f"Rs. {val:,.2f}"
    except (ValueError, TypeError):
        return f"Rs. {value}"


@app.template_filter("duration_fmt")
def duration_filter(minutes):
    """Safely format minutes into readable hours and minutes."""
    try:
        mins = int(minutes)
        hrs = mins // 60
        rem = mins % 60
        if hrs > 0 and rem > 0:
            return f"{hrs}h {rem}m"
        elif hrs > 0:
            return f"{hrs} hr{'s' if hrs > 1 else ''}"
        else:
            return f"{mins} min{'s' if mins != 1 else ''}"
    except (ValueError, TypeError):
        return f"{minutes} mins"


@app.context_processor
def inject_global_data():
    """Injects live counts, session info, and preserved form data into all templates."""
    summary = pm.get_dashboard_summary()
    entry_data = session.get("entry_form_data", {})
    return {
        "global_summary": summary,
        "entry_form_data": entry_data,
        "current_user_email": session.get("email", ""),
        "current_user_role": session.get("role", ""),
        "is_admin": session.get("role") == "admin",
        "current_year": datetime.now().year,
        "current_time_str": datetime.now().strftime("%A, %d %b %Y | %I:%M %p")
    }


# =============================================================================
# AUTHENTICATION ROUTES (LOGIN, LOGOUT - REQUIREMENT 1)
# =============================================================================

@app.route("/")
def root_route():
    """
    Website entry point (Requirement 1):
    When the website is opened without an authenticated session, show the SmartPark Login page first.
    If already authenticated, redirect to the dashboard.
    """
    if session.get("user") or session.get("role"):
        return redirect(url_for("dashboard"))
    return render_template("login.html", page_title="Sign In")


@app.route("/login")
def login():
    """Login page displaying SmartPark branding with User and Admin login sections."""
    if session.get("user") or session.get("role"):
        return redirect(url_for("dashboard"))
    return render_template("login.html", page_title="Sign In")


@app.route("/login/user", methods=["POST"])
def login_user():
    """
    User Login (Requirement 1):
    Accepts any non-empty email and password without requiring registration or DB auth.
    """
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if not email or not password:
        flash("Please enter both email and password.", "danger")
        return redirect(url_for("login"))

    session.clear()
    session["user"] = {"email": email, "role": "user"}
    session["role"] = "user"
    session["email"] = email

    flash(f"Welcome to SmartPark, {email}!", "success")
    return redirect(url_for("dashboard"))


@app.route("/login/admin", methods=["POST"])
def login_admin():
    """
    Admin Login (Requirement 1):
    Allows access ONLY with email admin@gmail.com and password 12345. Rejects all others.
    """
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if email == "admin@gmail.com" and password == "12345":
        session.clear()
        session["user"] = {"email": "admin@gmail.com", "role": "admin"}
        session["role"] = "admin"
        session["email"] = "admin@gmail.com"

        flash("Welcome, Administrator!", "success")
        return redirect(url_for("dashboard"))

    flash("Invalid admin credentials. Access restricted to authorized personnel.", "danger")
    return redirect(url_for("login"))


@app.route("/logout", methods=["GET", "POST"])
def logout():
    """
    Logout (Requirement 1):
    Clears session and redirects to login page.
    """
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("login"))


# =============================================================================
# WEB DASHBOARD & NAVIGATION ROUTES
# =============================================================================

@app.route("/dashboard")
def dashboard():
    """Main operations dashboard with live KPI cards, occupancy statistics, and category meters."""
    summary = pm.get_dashboard_summary()
    return render_template(
        "dashboard.html",
        summary=summary,
        page_title="Dashboard"
    )


@app.route("/map")
def parking_map():
    """
    Visual parking map with Normal slots on left and Reserved slots on right (Requirement 3).
    Supports category and status filtering.
    """
    category_filter = request.args.get("category", "All")
    status_filter = request.args.get("status", "All")

    filtered_slots = []
    for slot in pm.slots:
        if category_filter != "All":
            if category_filter in ("EV", "EV Charging"):
                if slot.category not in ("EV", "EV Charging"):
                    continue
            elif slot.category != category_filter:
                continue

        if status_filter != "All":
            eff_status = "disabled" if slot.is_enabled == 0 else slot.status
            if eff_status != status_filter:
                continue

        filtered_slots.append(slot)

    return render_template(
        "parking_map.html",
        slots=filtered_slots,
        all_slots=pm.slots,
        category_filter=category_filter,
        status_filter=status_filter,
        active_vehicles=pm.active_vehicles,
        active_reservations=pm.active_reservations,
        page_title="Parking Map"
    )


@app.route("/vehicles")
def vehicles():
    """Active vehicles directory with search and direct exit & billing actions."""
    query = request.args.get("q", "").strip().upper()
    active_list = list(pm.active_vehicles.values())

    if query:
        if query in pm.active_vehicles:
            active_list = [pm.active_vehicles[query]]
        else:
            active_list = [
                v for v in active_list
                if query in v["vehicle_number"] or query in v["slot_number"] or query in v["category"].upper()
            ]

    return render_template(
        "vehicles.html",
        active_vehicles=active_list,
        total_active=len(pm.active_vehicles),
        search_query=query,
        rates=CATEGORY_RATES,
        page_title="Active Vehicles"
    )


@app.route("/waiting-list")
@app.route("/queue")
def waiting_list():
    """Waiting list view displaying queued vehicles waiting for an available compatible slot."""
    queue_items = list(pm.waiting_queue)
    return render_template(
        "waiting_list.html",
        queue_items=queue_items,
        queue_count=len(queue_items),
        page_title="Waiting List"
    )


waiting_queue = waiting_list


@app.route("/history")
def history():
    """Completed parking history with duration, charges, search, reprint, and delete actions."""
    search_query = request.args.get("q", "").strip()
    sort_by = request.args.get("sort_by", "exit_time")
    order = request.args.get("order", "desc")

    records = pm.get_parking_history(
        search_query=search_query,
        sort_by=sort_by,
        order=order,
        algorithm="mergesort"
    )

    return render_template(
        "history.html",
        records=records,
        search_query=search_query,
        sort_by=sort_by,
        order=order,
        page_title="Parking History"
    )


# =============================================================================
# ADMIN MANAGE SLOTS ROUTES (REQUIREMENT 2)
# =============================================================================

@app.route("/admin/slots")
def admin_slots():
    """
    Admin Manage Slots page (Requirement 2):
    View all slots, add new slots, edit slot details, and enable/disable slots.
    """
    category_filter = request.args.get("category", "All")
    type_filter = request.args.get("type", "All")
    status_filter = request.args.get("status", "All")

    filtered_slots = []
    for slot in pm.slots:
        if category_filter != "All":
            if category_filter in ("EV", "EV Charging"):
                if slot.category not in ("EV", "EV Charging"):
                    continue
            elif slot.category != category_filter:
                continue

        if type_filter != "All" and slot.slot_type != type_filter:
            continue

        if status_filter != "All":
            eff_status = "disabled" if slot.is_enabled == 0 else slot.status
            if status_filter == "enabled" and slot.is_enabled != 1:
                continue
            elif status_filter == "disabled" and slot.is_enabled != 0:
                continue
            elif status_filter not in ("enabled", "disabled") and eff_status != status_filter:
                continue

        filtered_slots.append(slot)

    # Collect unique parking areas
    areas = sorted(list(set(s.area for s in pm.slots if s.area)))

    summary = pm.get_dashboard_summary()
    return render_template(
        "admin_slots.html",
        slots=filtered_slots,
        all_slots=pm.slots,
        areas=areas,
        summary=summary,
        category_filter=category_filter,
        type_filter=type_filter,
        status_filter=status_filter,
        page_title="Manage Slots"
    )


@app.route("/admin/slots/add", methods=["POST"])
def admin_add_slot():
    """Adds a new parking slot persistently to the database (Requirement 2)."""
    slot_number = request.form.get("slot_number", "").strip().upper()
    category = request.form.get("category", "Four-Wheeler").strip()
    slot_type = request.form.get("slot_type", "Normal").strip()
    area = request.form.get("area", "General").strip()
    is_enabled = 1 if request.form.get("is_enabled") in ("1", "on", "true") else 0

    res = pm.add_slot(
        slot_number=slot_number,
        category=category,
        slot_type=slot_type,
        area=area,
        is_enabled=is_enabled
    )

    if res["success"]:
        flash(res["message"], "success")
    else:
        flash(res["message"], "danger")

    return redirect(url_for("admin_slots"))


@app.route("/admin/slots/edit/<int:slot_id>", methods=["POST"])
def admin_edit_slot(slot_id):
    """Edits slot details persistently (Requirement 2)."""
    category = request.form.get("category", "Four-Wheeler").strip()
    slot_type = request.form.get("slot_type", "Normal").strip()
    area = request.form.get("area", "").strip()
    is_enabled = 1 if request.form.get("is_enabled") in ("1", "on", "true") else 0

    res = pm.edit_slot(
        slot_id=slot_id,
        category=category,
        slot_type=slot_type,
        area=area,
        is_enabled=is_enabled
    )

    if res["success"]:
        flash(res["message"], "success")
    else:
        flash(res["message"], "danger")

    return redirect(url_for("admin_slots"))


@app.route("/admin/slots/toggle-status/<int:slot_id>", methods=["POST"])
def admin_toggle_slot_status(slot_id):
    """Safely enables or disables a slot (Requirement 2)."""
    res = pm.toggle_slot_status(slot_id)

    is_ajax = (
        request.headers.get("Accept") == "application/json"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.is_json
    )

    if is_ajax:
        status_code = 200 if res["success"] else 400
        return jsonify(res), status_code

    if res["success"]:
        flash(res["message"], "success")
    else:
        flash(res["message"], "danger")

    return redirect(request.referrer or url_for("admin_slots"))


@app.route("/admin/slots/delete", methods=["POST"])
def admin_delete_slot():
    """
    Deletes a slot after verifying all four details (Requirement 3):
    1. Slot Number / Bay ID
    2. Vehicle Category
    3. Slot Type
    4. Applicable Parking Area
    Protected: Only Admin can access.
    """
    if session.get("role") != "admin":
        flash("Access denied. Administrator privileges required.", "danger")
        return redirect(url_for("dashboard"))

    slot_number = request.form.get("slot_number", "").strip()
    category = request.form.get("category", "").strip()
    slot_type = request.form.get("slot_type", "").strip()
    area = request.form.get("area", "").strip()

    result = pm.delete_slot(
        slot_number=slot_number,
        category=category,
        slot_type=slot_type,
        area=area
    )

    if result.get("success"):
        flash(result["message"], "success")
    else:
        flash(result["message"], "danger")

    return redirect(url_for("admin_slots"))


@app.route("/admin/slots/verify", methods=["GET"])
def admin_verify_slot():
    """
    Returns slot details for live validation & confirmation dialog in Manage Slots (Requirement 3).
    Only Admin can access.
    """
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    num = request.args.get("slot_number", "").strip().upper()
    target = pm.get_slot_by_number(num)
    if not target:
        num_clean = num.replace("-", "")
        for s in pm.slots:
            if s.slot_number.upper().replace("-", "") == num_clean:
                target = s
                break

    if not target:
        return jsonify({"success": False, "message": f"Slot '{num}' not found."})

    return jsonify({
        "success": True,
        "slot": {
            "id": target.id,
            "slot_number": target.slot_number,
            "category": target.category,
            "slot_type": target.slot_type,
            "area": target.area,
            "status": target.status,
            "is_enabled": target.is_enabled,
            "current_vehicle": target.current_vehicle
        }
    })


# =============================================================================
# ACTION CONTROLLERS (PARK, EXIT & PDF, RESERVATIONS)
# =============================================================================

@app.route("/park", methods=["POST"])
def park_vehicle():
    """
    Handles vehicle entry submission with strict validation & reservation check-in (Requirement 4):
    - Vehicle registration: uppercase letters A-Z and digits 0-9 only (no spaces/commas/symbols).
    - Driver contact: exactly 10 digits.
    - If vehicle has an active reservation: allocates that exact reserved slot.
    - If no reservation: allocates first available compatible Normal slot.
    - If no Normal slot: enqueues into waiting list.
    """
    raw_vehicle = request.form.get("vehicle_number", "")
    raw_contact = request.form.get("driver_contact", "")
    category = request.form.get("category", "Four-Wheeler").strip()
    preferred_slot_id = request.form.get("preferred_slot_id")

    if preferred_slot_id:
        try:
            preferred_slot_id = int(preferred_slot_id)
        except (ValueError, TypeError):
            preferred_slot_id = None

    # Strict vehicle registration validation
    is_valid_veh, veh_res = validate_vehicle_registration(raw_vehicle)
    if not is_valid_veh:
        flash(veh_res, "danger")
        session["entry_form_data"] = {
            "vehicle_number": raw_vehicle,
            "driver_contact": raw_contact,
            "category": category
        }
        return redirect(request.referrer or url_for("dashboard"))

    # Strict driver contact validation
    is_valid_contact, contact_res = validate_driver_contact_number(raw_contact)
    if not is_valid_contact:
        flash(contact_res, "danger")
        session["entry_form_data"] = {
            "vehicle_number": raw_vehicle,
            "driver_contact": raw_contact,
            "category": category
        }
        return redirect(request.referrer or url_for("dashboard"))

    # Allocate slot or queue
    result = pm.park_vehicle(
        vehicle_number=veh_res,
        category=category,
        driver_contact=contact_res,
        preferred_slot_id=preferred_slot_id,
        strict_validation=True
    )

    if result["success"]:
        session.pop("entry_form_data", None)
        if result.get("status") == "allocated":
            flash(result["message"], "success")
            return redirect(url_for("vehicles"))
        elif result.get("status") == "queued":
            flash(result["message"], "warning")
            return redirect(url_for("waiting_list"))
    else:
        flash(result["message"], "danger")
        session["entry_form_data"] = {
            "vehicle_number": raw_vehicle,
            "driver_contact": raw_contact,
            "category": category
        }

    return redirect(request.referrer or url_for("dashboard"))


@app.route("/exit", methods=["POST"])
def exit_vehicle():
    """
    Handles vehicle release (Requirement 1):
    1. Idempotently processes exit and saves bill to parking_history.
    2. Generates and immediately downloads receipt as a PDF.
    3. Dispatches next strictly compatible waiting vehicle in FIFO order (Normal bays only).
    """
    vehicle_number = request.form.get("vehicle_number", "").strip().upper()
    simulated_minutes_raw = request.form.get("simulated_minutes")

    simulated_minutes = None
    if simulated_minutes_raw is not None and str(simulated_minutes_raw).strip() != "":
        try:
            val = int(simulated_minutes_raw)
            if val > 0:
                simulated_minutes = val
        except (ValueError, TypeError):
            simulated_minutes = None

    if not vehicle_number:
        flash("Please specify a valid vehicle registration number to process exit.", "danger")
        return redirect(request.referrer or url_for("vehicles"))

    result = pm.exit_vehicle(vehicle_number=vehicle_number, simulated_minutes=simulated_minutes)

    if not result["success"]:
        flash(result["message"], "danger")
        return redirect(request.referrer or url_for("vehicles"))

    summary = result["summary"]
    pdf_buffer = generate_receipt_pdf(summary)
    download_filename = f"SmartPark_Receipt_{summary['vehicle_number']}.pdf"

    response = send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_filename
    )
    response.headers["X-Vehicle-Exited"] = "true"
    response.headers["X-Vehicle-Number"] = summary["vehicle_number"]
    response.headers["X-Message"] = result.get("message", "Vehicle exited successfully.")
    return response


@app.route("/receipt/<int:record_id>")
@app.route("/history/receipt/<int:record_id>")
def download_receipt(record_id):
    """Downloads original PDF receipt from history without altering bill."""
    record = pm.get_history_record_by_id(record_id)
    if not record:
        flash(f"Parking receipt record #{record_id} not found.", "danger")
        return redirect(url_for("history"))

    pdf_buffer = generate_receipt_pdf(record)
    download_filename = f"SmartPark_Receipt_{record['vehicle_number']}_INV{record['id']:05d}.pdf"

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_filename
    )


@app.route("/history/delete/<int:record_id>", methods=["POST"])
def delete_history(record_id):
    """Deletes only the selected parking history record."""
    res = pm.delete_parking_record(record_id)
    if res["success"]:
        flash(res["message"], "success")
    else:
        flash(res["message"], "danger")
    return redirect(url_for("history"))


@app.route("/queue/remove", methods=["POST"])
def remove_from_queue():
    """Removes a vehicle from the waiting list."""
    vehicle_number = request.form.get("vehicle_number", "").strip().upper()
    result = pm.remove_from_waiting_queue(vehicle_number)
    if result["success"]:
        flash(f"Vehicle {vehicle_number} has been removed from the Waiting List.", "success")
    else:
        flash(result["message"], "danger")
    return redirect(url_for("waiting_list"))


@app.route("/slot/reserve", methods=["POST"])
def reserve_slot_route():
    """
    Submits a reservation for a designated Reserved bay (Requirement 4):
    Validates vehicle registration, category compatibility, and 10-digit phone number.
    """
    slot_id_raw = request.form.get("slot_id")
    vehicle_number = request.form.get("vehicle_number", "")
    category = request.form.get("category", "")
    driver_contact = request.form.get("driver_contact", "")

    try:
        slot_id = int(slot_id_raw)
    except (ValueError, TypeError):
        flash("Invalid Slot ID provided for reservation.", "danger")
        return redirect(request.referrer or url_for("parking_map"))

    res = pm.reserve_slot(
        slot_id=slot_id,
        vehicle_number=vehicle_number,
        category=category,
        driver_contact=driver_contact
    )

    is_ajax = (
        request.headers.get("Accept") == "application/json"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.is_json
    )

    if is_ajax:
        status_code = 200 if res["success"] else 400
        return jsonify(res), status_code

    if res["success"]:
        flash(res["message"], "success")
    else:
        flash(res["message"], "danger")

    return redirect(request.referrer or url_for("parking_map"))


@app.route("/slot/unreserve/<int:slot_id>", methods=["POST"])
def unreserve_slot_route(slot_id):
    """Cancels an active reservation on a slot."""
    res = pm.cancel_reservation(slot_id)

    is_ajax = (
        request.headers.get("Accept") == "application/json"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.is_json
    )

    if is_ajax:
        status_code = 200 if res["success"] else 400
        return jsonify(res), status_code

    if res["success"]:
        flash(res["message"], "success")
    else:
        flash(res["message"], "danger")

    return redirect(request.referrer or url_for("parking_map"))


@app.route("/slot/toggle-reserve/<int:slot_id>", methods=["POST"])
def toggle_reserve(slot_id):
    """
    Toggles slot reservation status (Requirement 4 & 6):
    Supports in-place JSON response for AJAX updates.
    """
    vehicle_number = request.form.get("vehicle_number")
    category = request.form.get("category")
    driver_contact = request.form.get("driver_contact")

    result = pm.toggle_slot_reservation(
        slot_id=slot_id,
        vehicle_number=vehicle_number,
        category=category,
        driver_contact=driver_contact
    )

    is_ajax = (
        request.headers.get("Accept") == "application/json"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.is_json
    )

    if is_ajax:
        status_code = 200 if result["success"] else 400
        return jsonify(result), status_code

    if result["success"]:
        flash(result["message"], "success")
    else:
        flash(result["message"], "danger")

    return redirect(request.referrer or url_for("parking_map"))


# =============================================================================
# API ENDPOINTS (FOR CHARTS & PREVIEWS)
# =============================================================================

@app.route("/api/preview-bill/<vehicle_number>")
def api_preview_bill(vehicle_number):
    """Calculates live bill preview for an active vehicle before confirming exit."""
    veh_norm = vehicle_number.strip().upper()
    if veh_norm not in pm.active_vehicles:
        return jsonify({"success": False, "message": "Vehicle is not currently parked."}), 404

    session_info = pm.active_vehicles[veh_norm]
    entry_time_str = session_info.get("entry_time")
    category = session_info.get("category", "Four-Wheeler")
    slot_num = session_info.get("slot_number", "")

    entry_dt = datetime.now()
    if entry_time_str:
        try:
            entry_dt = datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    exit_dt = datetime.now()
    duration_mins = max(1, math.ceil((exit_dt - entry_dt).total_seconds() / 60))

    rates = CATEGORY_RATES.get(category, {"base_fee": 20.0, "hourly_rate": 30.0})
    base_fee = rates["base_fee"]
    hourly_rate = rates["hourly_rate"]
    hours_billed = math.ceil(duration_mins / 60)
    fee = base_fee + (hourly_rate * hours_billed)

    return jsonify({
        "success": True,
        "vehicle_number": veh_norm,
        "slot_number": slot_num,
        "category": category,
        "entry_time": entry_time_str,
        "duration_minutes": duration_mins,
        "base_fee": base_fee,
        "hourly_rate": hourly_rate,
        "hours_billed": hours_billed,
        "fee": fee
    })


@app.route("/api/stats")
def api_stats():
    """Returns dynamic capacity and category statistics for Chart.js dashboard charts."""
    summary = pm.get_dashboard_summary()

    labels = ["Two-Wheeler", "Four-Wheeler", "EV Charging"]
    occupied_counts = [summary["category_stats"].get(c, {}).get("occupied", 0) for c in labels]
    available_counts = [summary["category_stats"].get(c, {}).get("available", 0) for c in labels]

    return jsonify({
        "summary": summary,
        "chart_data": {
            "occupancy": {
                "labels": ["Available", "Occupied", "Reserved"],
                "data": [
                    summary["available_slots"],
                    summary["occupied_slots"],
                    summary["reserved_slots"]
                ]
            },
            "category": {
                "labels": labels,
                "occupied": occupied_counts,
                "available": available_counts
            },
            "capacity": {
                "labels": ["Available", "Occupied", "Reserved"],
                "data": [
                    summary["available_slots"],
                    summary["occupied_slots"],
                    summary["reserved_slots"]
                ],
                "available": summary["available_slots"],
                "occupied": summary["occupied_slots"],
                "reserved": summary["reserved_slots"]
            },
            "categories": {
                "labels": labels,
                "occupied": occupied_counts,
                "available": available_counts
            }
        }
    })


@app.route("/api/slots")
def api_slots():
    """Returns JSON representation of all slots."""
    return jsonify([slot.to_dict() for slot in pm.slots])


# Backward compatibility routes
@app.route("/dsa-insights")
def dsa_insights():
    return redirect(url_for("dashboard"))


@app.route("/clear-bill", methods=["POST", "GET"])
def clear_bill():
    return redirect(url_for("vehicles"))


if __name__ == "__main__":
    print("=" * 65)
    print("  SmartPark — Professional Parking Management System")
    print("  Web Server running at: http://127.0.0.1:5000")
    print("=" * 65)
    app.run(host="127.0.0.1", port=5000, debug=True)
