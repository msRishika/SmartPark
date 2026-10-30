"""
Database module for SmartPark - Smart Parking Slot Allocation System.
Manages SQLite connection, schema initialization, migrations, and persistence operations.
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
    entry_time TEXT DEFAULT NULL,
    slot_type TEXT NOT NULL DEFAULT 'Normal',
    area TEXT NOT NULL DEFAULT 'General',
    is_enabled INTEGER NOT NULL DEFAULT 1
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

CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id INTEGER NOT NULL,
    slot_number TEXT NOT NULL,
    vehicle_number TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    driver_contact TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    FOREIGN KEY (slot_id) REFERENCES slots(id)
);

CREATE INDEX IF NOT EXISTS idx_slots_status ON slots(status);
CREATE INDEX IF NOT EXISTS idx_slots_category ON slots(category);
CREATE INDEX IF NOT EXISTS idx_active_vehicle ON active_sessions(vehicle_number);
CREATE INDEX IF NOT EXISTS idx_history_vehicle ON parking_history(vehicle_number);
CREATE INDEX IF NOT EXISTS idx_reservations_vehicle ON reservations(vehicle_number);
"""

# Default 30 slots configuration with Normal and Reserved bays across areas
DEFAULT_SLOTS = [
    # 6 Two-Wheeler slots (S-01 to S-06) in Two-Wheeler Bay (Zone A)
    # 4 Normal (S-01 to S-04), 2 Reserved (S-05 to S-06)
    {
        "slot_number": f"S-{i:02d}",
        "category": "Two-Wheeler",
        "slot_type": "Reserved" if i >= 5 else "Normal",
        "area": "Two-Wheeler Bay",
        "is_enabled": 1,
        "status": "available"
    }
    for i in range(1, 7)
] + [
    # 8 Four-Wheeler North Bay slots (S-07 to S-14) (Zone B)
    # 6 Normal (S-07 to S-12), 2 Reserved (S-13 to S-14)
    {
        "slot_number": f"S-{i:02d}",
        "category": "Four-Wheeler",
        "slot_type": "Reserved" if i >= 13 else "Normal",
        "area": "North Bay",
        "is_enabled": 1,
        "status": "available"
    }
    for i in range(7, 15)
] + [
    # 8 Four-Wheeler South Bay slots (S-15 to S-22) (Zone C)
    # 6 Normal (S-15 to S-20), 2 Reserved (S-21 to S-22)
    {
        "slot_number": f"S-{i:02d}",
        "category": "Four-Wheeler",
        "slot_type": "Reserved" if i >= 21 else "Normal",
        "area": "South Bay",
        "is_enabled": 1,
        "status": "available"
    }
    for i in range(15, 23)
] + [
    # 4 EV Charging slots (S-23 to S-26) (Zone D)
    # 3 Normal (S-23 to S-25), 1 Reserved (S-26)
    {
        "slot_number": f"S-{i:02d}",
        "category": "EV Charging",
        "slot_type": "Reserved" if i == 26 else "Normal",
        "area": "EV Charging Bay",
        "is_enabled": 1,
        "status": "available"
    }
    for i in range(23, 27)
] + [
    # 4 Four-Wheeler Reserved slots (S-27 to S-30)
    # S-27, S-28 in North Bay, S-29, S-30 in South Bay
    {
        "slot_number": f"S-{i:02d}",
        "category": "Four-Wheeler",
        "slot_type": "Reserved",
        "area": "North Bay" if i <= 28 else "South Bay",
        "is_enabled": 1,
        "status": "available"
    }
    for i in range(27, 31)
]

def get_db_connection(db_path=DEFAULT_DB_PATH):
    """Create and return a thread-safe SQLite connection with Row factory."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def migrate_db(conn):
    """Safely upgrades existing database tables without deleting any records."""
    cursor = conn.cursor()
    
    # Check slots table columns
    cursor.execute("PRAGMA table_info(slots)")
    existing_cols = [row[1] for row in cursor.fetchall()]

    if "slot_type" not in existing_cols:
        cursor.execute("ALTER TABLE slots ADD COLUMN slot_type TEXT NOT NULL DEFAULT 'Normal'")
    if "area" not in existing_cols:
        cursor.execute("ALTER TABLE slots ADD COLUMN area TEXT NOT NULL DEFAULT 'General'")
    if "is_enabled" not in existing_cols:
        cursor.execute("ALTER TABLE slots ADD COLUMN is_enabled INTEGER NOT NULL DEFAULT 1")

    # Migrate area names and types for default slots if area is 'General' or NULL
    cursor.execute("UPDATE slots SET area = 'Two-Wheeler Bay' WHERE id BETWEEN 1 AND 6 AND (area = 'General' OR area IS NULL)")
    cursor.execute("UPDATE slots SET slot_type = 'Reserved' WHERE id IN (5, 6) AND slot_type = 'Normal'")

    cursor.execute("UPDATE slots SET area = 'North Bay' WHERE id BETWEEN 7 AND 14 AND (area = 'General' OR area IS NULL)")
    cursor.execute("UPDATE slots SET slot_type = 'Reserved' WHERE id IN (13, 14) AND slot_type = 'Normal'")

    cursor.execute("UPDATE slots SET area = 'South Bay' WHERE id BETWEEN 15 AND 22 AND (area = 'General' OR area IS NULL)")
    cursor.execute("UPDATE slots SET slot_type = 'Reserved' WHERE id IN (21, 22) AND slot_type = 'Normal'")

    cursor.execute("UPDATE slots SET area = 'EV Charging Bay' WHERE id BETWEEN 23 AND 26 AND (area = 'General' OR area IS NULL)")
    cursor.execute("UPDATE slots SET slot_type = 'Reserved' WHERE id = 26 AND slot_type = 'Normal'")

    # Safely migrate legacy 'Reserved' category slots (S-27 to S-30) to Four-Wheeler Reserved
    cursor.execute("""
        UPDATE slots 
        SET category = 'Four-Wheeler', 
            slot_type = 'Reserved',
            area = CASE WHEN id <= 28 THEN 'North Bay' ELSE 'South Bay' END
        WHERE category = 'Reserved'
    """)

    # Ensure reservations table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_id INTEGER NOT NULL,
            slot_number TEXT NOT NULL,
            vehicle_number TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            driver_contact TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            FOREIGN KEY (slot_id) REFERENCES slots(id)
        );
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_slots_status ON slots(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_slots_category ON slots(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_slots_type ON slots(slot_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_active_vehicle ON active_sessions(vehicle_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_vehicle ON parking_history(vehicle_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reservations_vehicle ON reservations(vehicle_number)")
    
    conn.commit()

def init_db(db_path=DEFAULT_DB_PATH, force_reset=False):
    """
    Initialize SQLite database tables and default 30 parking slots.
    If force_reset=True, drops existing tables and seeds fresh defaults.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    if force_reset:
        cursor.executescript("""
            DROP TABLE IF EXISTS reservations;
            DROP TABLE IF EXISTS active_sessions;
            DROP TABLE IF EXISTS waiting_queue;
            DROP TABLE IF EXISTS parking_history;
            DROP TABLE IF EXISTS slots;
        """)

    cursor.executescript(SCHEMA_SQL)
    migrate_db(conn)

    # Check if slots are populated
    cursor.execute("SELECT COUNT(*) FROM slots")
    count = cursor.fetchone()[0]

    if count == 0:
        for slot in DEFAULT_SLOTS:
            cursor.execute("""
                INSERT INTO slots (slot_number, category, status, slot_type, area, is_enabled)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                slot["slot_number"],
                slot["category"],
                slot["status"],
                slot.get("slot_type", "Normal"),
                slot.get("area", "General"),
                slot.get("is_enabled", 1)
            ))
        conn.commit()

    conn.close()

if __name__ == '__main__':
    init_db(force_reset=True)
    print("Database initialized successfully with 30 slots.")
