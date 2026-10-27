"""
app.py
Flask Application for SmartPark - Professional Parking Management System.
Connects the web frontend with the SQLite database and ParkingManager engine.
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import os
import math
from datetime import datetime, timedelta

from database import init_db, DEFAULT_DB_PATH
from parking_manager import ParkingManager, CATEGORY_RATES

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smartpark-professional-secret-key-2026")

# Initialize SQLite database if it doesn't exist
init_db(DEFAULT_DB_PATH)

# Initialize the ParkingManager engine
pm = ParkingManager(DEFAULT_DB_PATH)


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
    """Injects live counts and current timestamp into all templates."""
    summary = pm.get_dashboard_summary()
    return {
        "global_summary": summary,
        "current_year": datetime.now().year,
        "current_time_str": datetime.now().strftime("%A, %d %b %Y | %I:%M %p")
    }


# =============================================================================
# WEB ROUTES
# =============================================================================

@app.route("/")
@app.route("/dashboard")
def dashboard():
    """
    Main dashboard with KPI summary cards, occupancy statistics,
    and a focused real-time overview.
    Does not duplicate full waiting list or complete history tables here.
    """
    session.pop("active_receipt", None)
    session.pop("active_receipt_queue", None)
    summary = pm.get_dashboard_summary()
    return render_template(
        "dashboard.html",
        summary=summary,
        page_title="Dashboard"
    )


@app.route("/map")
def parking_map():
    """Visual parking map displaying all 30 slots with real-time status and category filtering."""
    session.pop("active_receipt", None)
    session.pop("active_receipt_queue", None)
    category_filter = request.args.get("category", "All")
    status_filter = request.args.get("status", "All")

    filtered_slots = []
    for slot in pm.slots:
        if category_filter != "All" and slot.category != category_filter:
            continue
        if status_filter != "All" and slot.status != status_filter:
            continue
        filtered_slots.append(slot)

    return render_template(
        "parking_map.html",
        slots=filtered_slots,
        all_slots=pm.slots,
        category_filter=category_filter,
        status_filter=status_filter,
        active_vehicles=pm.active_vehicles,
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

    receipt = session.get("active_receipt")
    receipt_queue = session.get("active_receipt_queue")

    return render_template(
        "vehicles.html",
        active_vehicles=active_list,
        total_active=len(pm.active_vehicles),
        search_query=query,
        rates=CATEGORY_RATES,
        receipt=receipt,
        receipt_queue=receipt_queue,
        page_title="Active Vehicles"
    )


@app.route("/waiting-list")
@app.route("/queue")
def waiting_list():
    """Waiting list view displaying queued vehicles waiting for an available slot."""
    session.pop("active_receipt", None)
    session.pop("active_receipt_queue", None)
    queue_items = list(pm.waiting_queue)
    return render_template(
        "waiting_list.html",
        queue_items=queue_items,
        queue_count=len(queue_items),
        page_title="Waiting List"
    )


# Alias for backward compatibility
waiting_queue = waiting_list


@app.route("/history")
def history():
    """Completed parking history with duration, charges, and search/sorting options."""
    session.pop("active_receipt", None)
    session.pop("active_receipt_queue", None)
    search_query = request.args.get("q", "").strip()
    sort_by = request.args.get("sort_by", "exit_time")
    order = request.args.get("order", "desc")

    # Uses the internal DSA sorting engine transparently
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
# ACTION CONTROLLERS (PARK, EXIT & BILLING, QUEUE, RESERVATIONS)
# =============================================================================

@app.route("/park", methods=["POST"])
def park_vehicle():
    """Handles vehicle entry submission and automatic slot assignment."""
    vehicle_number = request.form.get("vehicle_number", "").strip().upper()
    category = request.form.get("category", "Four-Wheeler").strip()
    driver_contact = request.form.get("driver_contact", "").strip()
    preferred_slot_id = request.form.get("preferred_slot_id")

    if preferred_slot_id:
        try:
            preferred_slot_id = int(preferred_slot_id)
        except (ValueError, TypeError):
            preferred_slot_id = None

    if not vehicle_number:
        flash("Please enter a valid vehicle registration number.", "danger")
        return redirect(request.referrer or url_for("dashboard"))

    result = pm.park_vehicle(
        vehicle_number=vehicle_number,
        category=category,
        driver_contact=driver_contact,
        preferred_slot_id=preferred_slot_id
    )

    if result["success"]:
        if result.get("status") == "allocated":
            flash(f"Slot {result['slot_number']} ({result['category']}) has been assigned to vehicle {vehicle_number}.", "success")
        elif result.get("status") == "queued":
            flash(f"All slots for {category} are full. Vehicle {vehicle_number} has been added to the Waiting List at Position #{result['queue_position']}.", "warning")
    else:
        flash(result["message"], "danger")

    return redirect(request.referrer or url_for("dashboard"))


@app.route("/exit", methods=["POST"])
def exit_vehicle():
    """
    Handles vehicle release, calculates parking fees accurately,
    saves the bill to session for display, and allocates freed slots to waiting vehicles.
    """
    vehicle_number = request.form.get("vehicle_number", "").strip().upper()
    simulated_minutes_raw = request.form.get("simulated_minutes")

    # Safe parsing of optional simulated duration: avoids TypeError on empty string or invalid inputs
    simulated_minutes = None
    if simulated_minutes_raw is not None and str(simulated_minutes_raw).strip() != "":
        try:
            val = int(simulated_minutes_raw)
            if val > 0:
                simulated_minutes = val
        except (ValueError, TypeError):
            simulated_minutes = None

    if not vehicle_number:
        flash("Please specify a valid vehicle number to process exit.", "danger")
        return redirect(request.referrer or url_for("vehicles"))

    result = pm.exit_vehicle(vehicle_number=vehicle_number, simulated_minutes=simulated_minutes)

    if result["success"]:
        summary = result["summary"]
        session["active_receipt"] = summary
        session["active_receipt_queue"] = result.get("queue_allocation")

        fee_val = float(summary.get("fee", 0.0))
        msg = f"Vehicle {vehicle_number} successfully exited from Slot {summary['slot_number']}. Total Fee: Rs. {fee_val:.2f}"
        flash(msg, "success")

        # Notify if a waiting vehicle was automatically allocated the freed slot
        if result.get("queue_allocation"):
            q_alloc = result["queue_allocation"]
            flash(f"Slot {q_alloc['slot_number']} was immediately assigned to waiting vehicle {q_alloc['vehicle_number']} from the Waiting List.", "info")
    else:
        flash(result["message"], "danger")

    return redirect(url_for("vehicles"))


@app.route("/clear-bill", methods=["POST", "GET"])
def clear_bill():
    """Clears the displayed billing receipt from session."""
    session.pop("active_receipt", None)
    session.pop("active_receipt_queue", None)
    session.pop("last_bill", None)
    return redirect(url_for("vehicles"))


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


@app.route("/slot/toggle-reserve/<int:slot_id>", methods=["POST"])
def toggle_reserve(slot_id):
    """Toggles slot reservation status."""
    result = pm.toggle_slot_reservation(slot_id)
    if result["success"]:
        flash(result["message"], "success")
        if result.get("queue_allocation"):
            q_alloc = result["queue_allocation"]
            flash(f"Waiting vehicle {q_alloc['vehicle_number']} was assigned unreserved Slot {q_alloc['slot_number']}.", "info")
    else:
        flash(result["message"], "danger")

    return redirect(request.referrer or url_for("parking_map"))


# =============================================================================
# API ENDPOINTS (FOR CHARTS & DYNAMIC BILL PREVIEW)
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

    # Calculate real elapsed time
    entry_dt = datetime.now()
    if entry_time_str:
        try:
            entry_dt = datetime.strptime(str(entry_time_str).strip(), "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            entry_dt = datetime.now()

    exit_dt = datetime.now()
    diff_seconds = max(0, (exit_dt - entry_dt).total_seconds())
    duration_minutes = max(1, math.ceil(diff_seconds / 60))

    rates = CATEGORY_RATES.get(category, {"base_fee": 20.0, "hourly_rate": 30.0})
    base_fee = float(rates.get("base_fee", 20.0))
    hourly_rate = float(rates.get("hourly_rate", 30.0))
    hours_billed = int(math.ceil(duration_minutes / 60))
    total_fee = round(base_fee + (hourly_rate * hours_billed), 2)

    return jsonify({
        "success": True,
        "vehicle_number": veh_norm,
        "slot_number": slot_num,
        "category": category,
        "entry_time": entry_time_str,
        "current_time": exit_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_minutes": duration_minutes,
        "base_fee": base_fee,
        "hourly_rate": hourly_rate,
        "hours_billed": hours_billed,
        "estimated_fee": total_fee
    })


@app.route("/api/stats")
def api_stats():
    """Returns JSON statistics for dynamic Chart.js rendering."""
    summary = pm.get_dashboard_summary()
    return jsonify({
        "summary": summary,
        "chart_data": {
            "occupancy": {
                "labels": ["Available", "Occupied", "Reserved"],
                "data": [summary["available_slots"], summary["occupied_slots"], summary["reserved_slots"]]
            },
            "category": {
                "labels": ["Two-Wheeler", "Four-Wheeler", "EV Charging", "Reserved"],
                "occupied": [
                    summary["category_stats"]["Two-Wheeler"]["occupied"],
                    summary["category_stats"]["Four-Wheeler"]["occupied"],
                    summary["category_stats"]["EV Charging"]["occupied"],
                    summary["category_stats"]["Reserved"]["occupied"]
                ],
                "available": [
                    summary["category_stats"]["Two-Wheeler"]["available"],
                    summary["category_stats"]["Four-Wheeler"]["available"],
                    summary["category_stats"]["EV Charging"]["available"],
                    summary["category_stats"]["Reserved"]["available"]
                ]
            }
        }
    })


@app.route("/api/slots")
def api_slots():
    """Returns JSON representation of all 30 slots."""
    return jsonify([slot.to_dict() for slot in pm.slots])


# Route kept for backward compatibility if directly visited
@app.route("/dsa-insights")
def dsa_insights():
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    print("=" * 65)
    print("  SmartPark — Professional Parking Management System")
    print("  Web Server running at: http://127.0.0.1:5000")
    print("=" * 65)
    app.run(host="127.0.0.1", port=5000, debug=True)
