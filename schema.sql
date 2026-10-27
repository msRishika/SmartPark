-- SmartPark - Smart Parking Slot Allocation System
-- SQLite Database Schema

CREATE TABLE IF NOT EXISTS slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_number TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'available', -- 'available', 'occupied', 'reserved'
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

-- Indexes for high-speed indexing & queries
CREATE INDEX IF NOT EXISTS idx_slots_status ON slots(status);
CREATE INDEX IF NOT EXISTS idx_slots_category ON slots(category);
CREATE INDEX IF NOT EXISTS idx_active_vehicle ON active_sessions(vehicle_number);
CREATE INDEX IF NOT EXISTS idx_history_vehicle ON parking_history(vehicle_number);
