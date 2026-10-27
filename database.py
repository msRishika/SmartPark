"""
Database module for SmartPark - Smart Parking Slot Allocation System.
Manages SQLite connection, schema initialization, and persistence operations.
"""

import sqlite3
import os
from datetime import datetime

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smartpark.db')

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_number TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'available',
    current_vehicle TEXT DEFAULT NULL,
    entry_time TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS active_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_number TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    slot_id INTEGER NOT NULL,
    slot_number TEXT NOT NULL,
    driver_contact TEXT DEFAULT '',
    entry_time TEXT NOT NULL,
    FOREIGN KEY (slot_id) REFERENCES slots(id)
);

CREATE TABLE IF NOT EXISTS waiting_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_number TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    driver_contact TEXT DEFAULT '',
    queue_position INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parking_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_number TEXT NOT NULL,
    category TEXT NOT NULL,
    slot_number TEXT NOT NULL,
    entry_time TEXT NOT NULL,
    exit_time TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    fee REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_slots_status ON slots(status);
CREATE INDEX IF NOT EXISTS idx_slots_category ON slots(category);
CREATE INDEX IF NOT EXISTS idx_active_vehicle ON active_sessions(vehicle_number);
CREATE INDEX IF NOT EXISTS idx_history_vehicle ON parking_history(vehicle_number);
"""

# Default 30 slots configuration
DEFAULT_SLOTS = [
    # 6 Two-Wheeler slots (S-01 to S-06)
    {"slot_number": f"S-{i:02d}", "category": "Two-Wheeler", "status": "available"}
    for i in range(1, 7)
] + [
    # 16 Four-Wheeler slots (S-07 to S-22)
    {"slot_number": f"S-{i:02d}", "category": "Four-Wheeler", "status": "available"}
    for i in range(7, 23)
] + [
    # 4 EV Charging slots (S-23 to S-26)
    {"slot_number": f"S-{i:02d}", "category": "EV Charging", "status": "available"}
    for i in range(23, 27)
] + [
    # 4 Reserved / Priority slots (S-27 to S-30)
    # S-29 and S-30 reserved by default to illustrate the yellow status on map
    {"slot_number": f"S-{i:02d}", "category": "Reserved", "status": "reserved" if i >= 29 else "available"}
    for i in range(27, 31)
]

def get_db_connection(db_path=DEFAULT_DB_PATH):
    """Create and return a thread-safe SQLite connection with Row factory."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path=DEFAULT_DB_PATH, force_reset=False):
    """
    Initialize SQLite database tables and default 30 parking slots.
    If force_reset=True, drops existing tables and seeds fresh defaults.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    if force_reset:
        cursor.executescript("""
            DROP TABLE IF EXISTS active_sessions;
            DROP TABLE IF EXISTS waiting_queue;
            DROP TABLE IF EXISTS parking_history;
            DROP TABLE IF EXISTS slots;
        """)

    cursor.executescript(SCHEMA_SQL)

    # Check if slots are populated
    cursor.execute("SELECT COUNT(*) FROM slots")
    count = cursor.fetchone()[0]

    if count == 0:
        for slot in DEFAULT_SLOTS:
            cursor.execute("""
                INSERT INTO slots (slot_number, category, status)
                VALUES (?, ?, ?)
            """, (slot["slot_number"], slot["category"], slot["status"]))
        conn.commit()

    conn.close()

if __name__ == '__main__':
    init_db(force_reset=True)
    print("Database initialized successfully with 30 slots.")
