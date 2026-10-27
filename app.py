"""
app.py
Flask Application for SmartPark - Smart Parking Slot Allocation System.
Connects the web frontend with the SQLite database and ParkingManager DSA engine.
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
from datetime import datetime, timedelta
import random

from database import init_db, DEFAULT_DB_PATH
from parking_manager import ParkingManager

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "smartpark-secret-key-college-dsa-2026")

# Initialize SQLite database if it doesn't exist
init_db(DEFAULT_DB_PATH)

# Initialize the ParkingManager DSA engine
pm = ParkingManager(DEFAULT_DB_PATH)


@app.context_processor
def inject_global_data():
    """Injects live counts and current timestamp into all templates."""
    summary = pm.get_dashboard_summary()
    return {
        "global_summary": summary,
        "current_year": datetime.now().year,
        "current_time_str": datetime.now().strftime("%A, %d %b %Y | %I:%M:%S %p")
    }


# =============================================================================
# WEB ROUTES
# =============================================================================

@app.route("/")
@app.route("/dashboard")
def dashboard():
    """Main dashboard with KPI stat cards, live charts, recent activity, and quick park."""
    summary = pm.get_dashboard_summary()
    recent_history = pm.get_parking_history(sort_by="exit_time", order="desc", algorithm="mergesort")[:6]
    active_list = list(pm.active_vehicles.values())[:6]
    waiting_list = list(pm.waiting_queue)[:5]

    return render_template(
        "dashboard.html",
        summary=summary,
        recent_history=recent_history,
        active_list=active_list,
        waiting_list=waiting_list,
        search_metrics=pm.last_search_metrics,
        sort_metrics=pm.last_sort_metrics,
        page_title="Dashboard"
    )


@app.route("/map")
def parking_map():
    """Visual parking map displaying all 30 slots with real-time status and category filtering."""
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
        page_title="Parking Lot Map"
    )


@app.route("/vehicles")
def vehicles():
    """Active vehicles directory with O(1) hash search and direct exit actions."""
    query = request.args.get("q", "").strip().upper()
    active_list = list(pm.active_vehicles.values())

    if query:
        # Fast lookup via O(1) hash map if exact match, or substring search
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
        page_title="Active Vehicles"
    )


@app.route("/queue")
def waiting_queue():
    """FIFO Waiting Queue view showcasing collections.deque structure."""
    queue_items = list(pm.waiting_queue)
    return render_template(
        "waiting_queue.html",
        queue_items=queue_items,
        queue_count=len(queue_items),
        page_title="FIFO Waiting Queue"
    )


@app.route("/history")
def history():
    """
    Completed parking history with custom DSA sorting (Merge Sort / Quick Sort)
    and linear search filtering.
    """
    search_query = request.args.get("q", "").strip()
    sort_by = request.args.get("sort_by", "exit_time")
    order = request.args.get("order", "desc")
    algo = request.args.get("algo", "mergesort")

    # Fetch and sort history using custom DSA algorithm
    records = pm.get_parking_history(
        search_query=search_query,
        sort_by=sort_by,
        order=order,
        algorithm=algo
    )

    return render_template(
        "history.html",
        records=records,
        search_query=search_query,
        sort_by=sort_by,
        order=order,
        algo=algo,
        sort_metrics=pm.last_sort_metrics,
        page_title="Parking History"
    )


@app.route("/dsa-insights")
def dsa_insights():
    """
    Dedicated DSA explanation and faculty viva showcase page.
    Explains Big-O notations, data structures, and algorithms used in the project.
    """
    summary = pm.get_dashboard_summary()
    return render_template(
        "dsa_insights.html",
        summary=summary,
        search_metrics=pm.last_search_metrics,
        sort_metrics=pm.last_sort_metrics,
        active_count=len(pm.active_vehicles),
        queue_count=len(pm.waiting_queue),
        page_title="DSA Architecture & Insights"
    )


# =============================================================================
# ACTION CONTROLLERS (PARK, EXIT, QUEUE, RESERVATIONS)
# =============================================================================

@app.route("/park", methods=["POST"])
def park_vehicle():
    """Handles vehicle entry submission."""
    vehicle_number = request.form.get("vehicle_number", "").strip().upper()
    category = request.form.get("category", "Four-Wheeler").strip()
    driver_contact = request.form.get("driver_contact", "").strip()
    preferred_slot_id = request.form.get("preferred_slot_id")

    if preferred_slot_id:
        try:
            preferred_slot_id = int(preferred_slot_id)
        except ValueError:
            preferred_slot_id = None

    if not vehicle_number:
        flash("Please enter a valid vehicle number.", "danger")
        return redirect(request.referrer or url_for("dashboard"))

    result = pm.park_vehicle(
        vehicle_number=vehicle_number,
        category=category,
        driver_contact=driver_contact,
        preferred_slot_id=preferred_slot_id
    )

    if result["success"]:
        if result.get("status") == "allocated":
            flash(f"Slot {result['slot_number']} ({result['category']}) allocated to vehicle {vehicle_number} via Linear Search!", "success")
        elif result.get("status") == "queued":
            flash(f"All eligible slots are full! Vehicle {vehicle_number} added to FIFO Waiting Queue at Position #{result['queue_position']}.", "warning")
    else:
        flash(result["message"], "danger")

    return redirect(request.referrer or url_for("dashboard"))


@app.route("/exit", methods=["POST"])
def exit_vehicle():
    """Handles vehicle exit, fee calculation, and FIFO queue automatic allocation."""
    vehicle_number = request.form.get("vehicle_number", "").strip().upper()
    simulated_minutes = request.form.get("simulated_minutes")

    if simulated_minutes:
        try:
            simulated_minutes = int(simulated_minutes)
        except ValueError:
            simulated_minutes = None

    if not vehicle_number:
        flash("Please provide a valid vehicle number to exit.", "danger")
        return redirect(request.referrer or url_for("dashboard"))

    result = pm.exit_vehicle(vehicle_number=vehicle_number, simulated_minutes=simulated_minutes)

    if result["success"]:
        summary = result["summary"]
        msg = f"Vehicle {vehicle_number} exited Slot {summary['slot_number']}. Duration: {summary['duration_minutes']} mins | Total Fee: Rs. {summary['fee']:.2f}"
        flash(msg, "success")

        # Notify if a waiting vehicle was dispatched from the FIFO queue
        if result.get("queue_allocation"):
            q_alloc = result["queue_allocation"]
            flash(f"FIFO Queue Dispatch: Waiting vehicle {q_alloc['vehicle_number']} was automatically allocated freed Slot {q_alloc['slot_number']}!", "info")
    else:
        flash(result["message"], "danger")

    return redirect(request.referrer or url_for("dashboard"))


@app.route("/queue/remove", methods=["POST"])
def remove_from_queue():
    """Removes a vehicle from the waiting queue."""
    vehicle_number = request.form.get("vehicle_number", "").strip().upper()
    result = pm.remove_from_waiting_queue(vehicle_number)
    if result["success"]:
        flash(result["message"], "success")
    else:
        flash(result["message"], "danger")
    return redirect(url_for("waiting_queue"))


@app.route("/slot/toggle-reserve/<int:slot_id>", methods=["POST"])
def toggle_reserve(slot_id):
    """Toggles slot reservation status."""
    result = pm.toggle_slot_reservation(slot_id)
    if result["success"]:
        flash(result["message"], "success")
        if result.get("queue_allocation"):
            q_alloc = result["queue_allocation"]
            flash(f"Waiting vehicle {q_alloc['vehicle_number']} was automatically allocated unreserved Slot {q_alloc['slot_number']}!", "info")
    else:
        flash(result["message"], "danger")

    return redirect(request.referrer or url_for("parking_map"))


# =============================================================================
# API ENDPOINTS (FOR REAL-TIME CHART.JS & FRONTEND DYNAMICS)
# =============================================================================

@app.route("/api/stats")
def api_stats():
    """Returns JSON statistics for dynamic Chart.js rendering."""
    summary = pm.get_dashboard_summary()
    
    # Recent history for activity trends
    history_records = pm.get_parking_history()[:15]
    durations = [r["duration_minutes"] for r in history_records]
    fees = [r["fee"] for r in history_records]
    vehicle_labels = [r["vehicle_number"] for r in history_records]

    return jsonify({
        "summary": summary,
        "search_metrics": pm.last_search_metrics,
        "sort_metrics": pm.last_sort_metrics,
        "chart_data": {
            "occupancy": {
                "labels": ["Available Slots", "Occupied Slots", "Reserved Slots"],
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
            },
            "recent_sessions": {
                "labels": vehicle_labels[:8],
                "durations": durations[:8],
                "fees": fees[:8]
            }
        }
    })


@app.route("/api/slots")
def api_slots():
    """Returns JSON representation of all 30 slots."""
    return jsonify([slot.to_dict() for slot in pm.slots])


# =============================================================================
# FACULTY DEMO & TESTING UTILITIES
# =============================================================================

@app.route("/demo/seed-sample-data", methods=["POST"])
def seed_sample_data():
    """
    Populates sample data for viva / faculty demonstration:
    - Parks several vehicles across different categories
    - Fills one category to enqueue waiting vehicles
    - Adds realistic historical sessions with durations & fees
    """
    # 1. Reset first to have a clean state
    init_db(DEFAULT_DB_PATH, force_reset=True)
    pm.reload_from_db()

    # 2. Park sample vehicles
    samples = [
        ("KA-01-MJ-1001", "Two-Wheeler", "9876543210"),
        ("KA-01-MJ-1002", "Two-Wheeler", "9876543211"),
        ("MH-12-DE-2020", "Four-Wheeler", "9123456780"),
        ("DL-04-CA-3344", "Four-Wheeler", "9123456781"),
        ("TN-07-BB-4567", "Four-Wheeler", "9123456782"),
        ("TS-09-EV-5500", "EV Charging", "9988776655"),
        ("KA-05-EV-6611", "EV Charging", "9988776656"),
        ("DL-01-VIP-001", "Reserved", "9000000001")
    ]

    for veh, cat, contact in samples:
        pm.park_vehicle(veh, cat, contact)

    # 3. Add some historical sessions
    now = datetime.now()
    history_samples = [
        ("KA-03-HA-8899", "Four-Wheeler", "S-08", now - timedelta(hours=3), now - timedelta(hours=1), 120, 80.0),
        ("MH-01-BT-7722", "Two-Wheeler", "S-03", now - timedelta(hours=2), now - timedelta(minutes=45), 75, 40.0),
        ("DL-08-CC-1122", "Four-Wheeler", "S-09", now - timedelta(hours=4), now - timedelta(hours=2), 120, 80.0),
        ("KA-04-EV-9900", "EV Charging", "S-23", now - timedelta(hours=5), now - timedelta(hours=1), 240, 185.0),
        ("HR-26-ZZ-4455", "Four-Wheeler", "S-10", now - timedelta(hours=1), now - timedelta(minutes=15), 45, 50.0),
    ]

    conn = pm.get_connection()
    cursor = conn.cursor()
    for veh, cat, slot, ent, ext, dur, fee in history_samples:
        cursor.execute("""
            INSERT INTO parking_history (vehicle_number, category, slot_number, entry_time, exit_time, duration_minutes, fee)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (veh, cat, slot, ent.strftime("%Y-%m-%d %H:%M:%S"), ext.strftime("%Y-%m-%d %H:%M:%S"), dur, fee))
    conn.commit()
    conn.close()

    # 4. Enqueue 2 waiting vehicles to show FIFO queue in action
    pm.waiting_queue.append({
        "vehicle_number": "KA-02-WQ-7777",
        "category": "Two-Wheeler",
        "driver_contact": "9811223344",
        "queue_position": 1,
        "created_at": (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    })
    pm.waiting_queue.append({
        "vehicle_number": "MH-04-WQ-8888",
        "category": "Four-Wheeler",
        "driver_contact": "9855667788",
        "queue_position": 2,
        "created_at": (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    })

    conn = pm.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO waiting_queue (vehicle_number, category, driver_contact, queue_position, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, ("KA-02-WQ-7777", "Two-Wheeler", "9811223344", 1, (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")))
    cursor.execute("""
        INSERT INTO waiting_queue (vehicle_number, category, driver_contact, queue_position, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, ("MH-04-WQ-8888", "Four-Wheeler", "9855667788", 2, (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

    flash("Sample demonstration data loaded successfully! 8 vehicles parked, 2 in FIFO queue, 5 completed history records.", "success")
    return redirect(url_for("dashboard"))


@app.route("/demo/reset", methods=["POST"])
def reset_demo():
    """Resets database and in-memory structures to clean default state."""
    init_db(DEFAULT_DB_PATH, force_reset=True)
    pm.reload_from_db()
    flash("System successfully reset to clean default state (30 slots: 28 available, 2 reserved).", "info")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    # Start Flask application in debug mode for local development
    print("=" * 65)
    print("  SmartPark - Smart Parking Slot Allocation System")
    print("  DSA Powered: Hashing, Linear Search, Deque, Merge/Quick Sort")
    print("  Access web UI at: http://127.0.0.1:5000")
    print("=" * 65)
    app.run(host="127.0.0.1", port=5000, debug=True)
