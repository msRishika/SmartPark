"""
parking_manager.py
Core Data Structures and Algorithms (DSA) Engine for SmartPark.

Implements:
1. Hashing: Python dictionary (`dict`) for O(1) active vehicle lookup and duplicate checking.
2. Searching: Linear Search O(N) for first eligible available parking slot allocation.
3. Queue: Python `collections.deque` for true O(1) FIFO waiting queue management with strict category compatibility.
4. Sorting: Custom Merge Sort and Quick Sort algorithms (O(N log N)) for parking history.
"""

from collections import deque
from datetime import datetime
import math
import re
from database import get_db_connection

# Hourly parking rates by vehicle category
CATEGORY_RATES = {
    "Two-Wheeler": {"base_fee": 10.0, "hourly_rate": 15.0},
    "Four-Wheeler": {"base_fee": 20.0, "hourly_rate": 30.0},
    "EV Charging": {"base_fee": 25.0, "hourly_rate": 40.0},
    "Reserved": {"base_fee": 30.0, "hourly_rate": 50.0}
}


def validate_vehicle_registration(vehicle_number: str) -> tuple[bool, str]:
    """
    Validates vehicle registration number strictly (Requirement 4):
    - Accepts only uppercase English letters (A-Z) and digits (0-9).
    - Rejects commas, dots, spaces, hyphens, punctuation, and all special characters.
    - Rejects meaningless or excessively short inputs (length < 3) such as ',,,', '...', or 'A'.
    - Accepts reasonable registration-like values such as 'ABCD1234'.
    Returns (is_valid, sanitized_string_or_error_message).
    """
    if not vehicle_number or not isinstance(vehicle_number, str):
        return False, "Vehicle registration number cannot be empty."

    raw = vehicle_number.strip()
    if len(raw) < 3 or len(raw) > 16:
        return False, "Vehicle registration number must be between 3 and 16 characters long."

    # Must contain only uppercase A-Z and 0-9
    if not re.fullmatch(r'^[A-Z0-9]+$', raw):
        return False, "Vehicle registration must contain only uppercase English letters (A–Z) and digits (0–9), with no commas, dots, spaces, or special characters."

    return True, raw


def validate_driver_contact_number(driver_contact: str) -> tuple[bool, str]:
    """
    Validates driver contact number strictly (Requirement 4):
    - Accepts exactly 10 digits.
    - Rejects letters, spaces, punctuation, and numbers with fewer or more than 10 digits.
    Returns (is_valid, sanitized_string_or_error_message).
    """
    if not driver_contact or not isinstance(driver_contact, str):
        return False, "Driver contact number must be provided and must contain exactly 10 digits."

    raw = driver_contact.strip()
    if not re.fullmatch(r'^\d{10}$', raw):
        return False, "Driver contact number must be exactly 10 numeric digits without letters, spaces, or punctuation (e.g. 9876543210)."

    return True, raw


class Slot:
    """Represents a physical parking slot."""
    def __init__(self, slot_id: int, slot_number: str, category: str, status: str = "available", current_vehicle: str = None, entry_time: str = None):
        self.id = slot_id
        self.slot_number = slot_number
        self.category = category  # 'Two-Wheeler', 'Four-Wheeler', 'EV Charging', 'Reserved'
        self.status = status      # 'available', 'occupied', 'reserved'
        self.current_vehicle = current_vehicle
        self.entry_time = entry_time

    def is_available(self) -> bool:
        return self.status == "available"

    def is_eligible_for(self, vehicle_category: str) -> bool:
        """
        Check if this slot strictly accommodates the given vehicle category (Requirement 5):
        - Two-Wheeler: assign only to compatible Two-Wheeler slot.
        - Four-Wheeler: assign only to compatible standard Four-Wheeler slot.
        - EV requiring charging: assign only to designated EV Charging slot (NEVER fallback to Four-Wheeler).
        - Reserved: assign only to designated Reserved / VIP slot.
        """
        return self.category == vehicle_category

    def to_dict(self):
        return {
            "id": self.id,
            "slot_number": self.slot_number,
            "category": self.category,
            "status": self.status,
            "current_vehicle": self.current_vehicle,
            "entry_time": self.entry_time
        }


class ParkingManager:
    """
    Central Manager managing 30 parking slots, active parked vehicles,
    FIFO waiting queue with strict compatibility, and parking history.
    """
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.slots = []                        # List of 30 Slot objects [O(N) search space]
        self.active_vehicles = {}              # Hash Map: vehicle_number -> session_info [O(1) lookup]
        self.waiting_queue = deque()           # collections.deque for FIFO waiting vehicles [O(1) enqueue/dequeue]
        
        # DSA Performance Metrics for Viva / Faculty Demonstration
        self.last_search_metrics = {
            "algorithm": "Linear Search",
            "probes_count": 0,
            "found_slot": None,
            "time_complexity": "O(N) Worst Case, O(1) Best Case"
        }
        self.last_sort_metrics = {
            "algorithm": "Merge Sort",
            "comparisons": 0,
            "items_sorted": 0,
            "time_complexity": "O(N log N)"
        }

        self.reload_from_db()

    def get_connection(self):
        if self.db_path:
            return get_db_connection(self.db_path)
        return get_db_connection()

    def reload_from_db(self):
        """
        Loads all persistent data from SQLite into in-memory DSA structures:
        - slots: List[Slot]
        - active_vehicles: dict
        - waiting_queue: collections.deque
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # 1. Load Slots
        cursor.execute("SELECT id, slot_number, category, status, current_vehicle, entry_time FROM slots ORDER BY id ASC")
        rows = cursor.fetchall()
        self.slots = [
            Slot(
                slot_id=row["id"],
                slot_number=row["slot_number"],
                category=row["category"],
                status=row["status"],
                current_vehicle=row["current_vehicle"],
                entry_time=row["entry_time"]
            )
            for row in rows
        ]

        # 2. Rebuild Hash Map of Active Vehicles: O(1) Access
        self.active_vehicles.clear()
        cursor.execute("SELECT vehicle_number, category, slot_id, slot_number, driver_contact, entry_time FROM active_sessions")
        for row in cursor.fetchall():
            veh_num = row["vehicle_number"].strip().upper()
            self.active_vehicles[veh_num] = {
                "vehicle_number": veh_num,
                "category": row["category"],
                "slot_id": row["slot_id"],
                "slot_number": row["slot_number"],
                "driver_contact": row["driver_contact"],
                "entry_time": row["entry_time"]
            }

        # 3. Rebuild FIFO Waiting Queue: collections.deque
        self.waiting_queue.clear()
        cursor.execute("SELECT vehicle_number, category, driver_contact, queue_position, created_at FROM waiting_queue ORDER BY queue_position ASC")
        for row in cursor.fetchall():
            self.waiting_queue.append({
                "vehicle_number": row["vehicle_number"].strip().upper(),
                "category": row["category"],
                "driver_contact": row["driver_contact"],
                "queue_position": row["queue_position"],
                "created_at": row["created_at"]
            })

        conn.close()

    # =========================================================================
    # DSA SEARCHING: Linear Search for First Available Eligible Slot
    # =========================================================================
    def find_first_available_slot(self, vehicle_category: str):
        """
        ALGORITHM: Linear Search
        TIME COMPLEXITY:
            - Best Case: O(1) (First checked slot is free and strictly eligible)
            - Worst Case: O(N) (Iterates through all N slots)
            - Average Case: O(N/2) ~ O(N)
        SPACE COMPLEXITY: O(1) Auxiliary space
        
        Scans slots sequentially to find the first eligible slot with status == 'available'.
        Enforces strict category matching (no fallback).
        """
        probes = 0
        for slot in self.slots:
            probes += 1
            if slot.is_available() and slot.is_eligible_for(vehicle_category):
                self.last_search_metrics = {
                    "algorithm": "Linear Search",
                    "probes_count": probes,
                    "found_slot": slot.slot_number,
                    "time_complexity": "O(N) Worst Case, O(1) Best Case"
                }
                return slot

        self.last_search_metrics = {
            "algorithm": "Linear Search",
            "probes_count": probes,
            "found_slot": None,
            "time_complexity": "O(N) Worst Case, O(1) Best Case"
        }
        return None

    # =========================================================================
    # VEHICLE ENTRY & ALLOCATION
    # =========================================================================
    def park_vehicle(self, vehicle_number: str, category: str, driver_contact: str = "", preferred_slot_id: int = None, strict_validation: bool = True):
        """
        Attempts to park a vehicle:
        1. Strict Input Validation (Requirement 4)
        2. Duplicate Check via HASHING: O(1) active_vehicles lookup
        3. Duplicate Check in FIFO Waiting Queue: O(M)
        4. Slot Selection using LINEAR SEARCH: O(N) with strict compatibility
        5. If eligible slot found:
           - Update slot status to 'occupied'
           - Add to active_vehicles dictionary: O(1)
           - Persist to SQLite
        6. If no eligible slot found (Category full/unavailable):
           - Enqueue into collections.deque: O(1) in FIFO order
           - Persist to waiting_queue table
        """
        # Strict validation
        if strict_validation:
            is_valid_veh, veh_res = validate_vehicle_registration(vehicle_number)
            if not is_valid_veh:
                return {"success": False, "message": veh_res}
            normalized_num = veh_res

            clean_contact = ""
            if driver_contact and str(driver_contact).strip() != "":
                is_valid_contact, contact_res = validate_driver_contact_number(driver_contact)
                if not is_valid_contact:
                    return {"success": False, "message": contact_res}
                clean_contact = contact_res
        else:
            normalized_num = vehicle_number.strip().upper()
            clean_contact = str(driver_contact or "").strip()

        if not normalized_num:
            return {"success": False, "message": "Vehicle number cannot be empty."}

        # 1. Hashing Check: Duplicate Active Vehicle (O(1))
        if normalized_num in self.active_vehicles:
            active_info = self.active_vehicles[normalized_num]
            return {
                "success": False,
                "message": f"Duplicate vehicle! Vehicle {normalized_num} is already parked in Slot {active_info['slot_number']}."
            }

        # 2. Check if already waiting in FIFO queue
        for item in self.waiting_queue:
            if item["vehicle_number"] == normalized_num:
                return {
                    "success": False,
                    "message": f"Duplicate entry! Vehicle {normalized_num} is already waiting in queue at Position #{item['queue_position']}."
                }

        # 3. Slot Selection: Preferred Slot (if strictly eligible) or Linear Search
        target_slot = None
        if preferred_slot_id:
            for slot in self.slots:
                if slot.id == preferred_slot_id and slot.is_available() and slot.is_eligible_for(category):
                    target_slot = slot
                    break

        if not target_slot:
            # Linear Search for the first eligible available slot with strict category compatibility
            target_slot = self.find_first_available_slot(category)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 4. If an eligible slot is found, allocate it!
        if target_slot:
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                # Update DB slot
                cursor.execute("""
                    UPDATE slots
                    SET status = 'occupied', current_vehicle = ?, entry_time = ?
                    WHERE id = ?
                """, (normalized_num, now_str, target_slot.id))

                # Insert Active Session
                cursor.execute("""
                    INSERT INTO active_sessions (vehicle_number, category, slot_id, slot_number, driver_contact, entry_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (normalized_num, category, target_slot.id, target_slot.slot_number, clean_contact, now_str))

                conn.commit()

                # Update In-Memory Structures
                target_slot.status = "occupied"
                target_slot.current_vehicle = normalized_num
                target_slot.entry_time = now_str

                # HASH MAP INSERTION: O(1)
                self.active_vehicles[normalized_num] = {
                    "vehicle_number": normalized_num,
                    "category": category,
                    "slot_id": target_slot.id,
                    "slot_number": target_slot.slot_number,
                    "driver_contact": clean_contact,
                    "entry_time": now_str
                }

                return {
                    "success": True,
                    "status": "allocated",
                    "slot_number": target_slot.slot_number,
                    "slot_id": target_slot.id,
                    "category": category,
                    "message": f"Slot {target_slot.slot_number} ({target_slot.category}) successfully allocated to vehicle {normalized_num}."
                }
            except Exception as e:
                conn.rollback()
                return {"success": False, "message": f"Database error during allocation: {str(e)}"}
            finally:
                conn.close()

        # 5. No eligible slot available -> Enqueue into FIFO Waiting Queue (collections.deque)
        queue_pos = len(self.waiting_queue) + 1
        queue_item = {
            "vehicle_number": normalized_num,
            "category": category,
            "driver_contact": clean_contact,
            "queue_position": queue_pos,
            "created_at": now_str
        }

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO waiting_queue (vehicle_number, category, driver_contact, queue_position, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (normalized_num, category, clean_contact, queue_pos, now_str))
            conn.commit()

            # QUEUE ENQUEUE: collections.deque.append() O(1)
            self.waiting_queue.append(queue_item)

            return {
                "success": True,
                "status": "queued",
                "queue_position": queue_pos,
                "message": f"All eligible {category} slots are currently occupied or reserved. Vehicle {normalized_num} added to Waiting List at Position #{queue_pos}."
            }
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"Database error while adding to queue: {str(e)}"}
        finally:
            conn.close()

    # =========================================================================
    # VEHICLE EXIT & AUTO FIFO QUEUE DISPATCH (IDEMPOTENT BILLING)
    # =========================================================================
    def exit_vehicle(self, vehicle_number: str, simulated_minutes = None):
        """
        Releases a vehicle from parking (Requirement 1):
        1. HASH MAP LOOKUP: O(1) check active_vehicles
        2. Idempotency Check: if already exited, returns original saved bill
        3. Calculate duration and billing fee using established rates
        4. Archive session to parking_history table persistently
        5. Free the slot (mark available, remove vehicle)
        6. Remove from active_vehicles hash map: O(1)
        7. FIFO QUEUE DISPATCH with strict category compatibility:
           - Dispatches slot only to the first waiting vehicle strictly eligible for slot.category.
           - Waiting time is not active time; entry_time is set to dispatch timestamp.
        """
        normalized_num = vehicle_number.strip().upper()

        # 1. O(1) Hash Map Lookup / Idempotency Check
        if normalized_num not in self.active_vehicles:
            # Check if recently billed in parking_history to guarantee idempotency on retries/double-clicks
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM parking_history WHERE vehicle_number = ? ORDER BY id DESC LIMIT 1",
                (normalized_num,)
            )
            recent = cursor.fetchone()
            conn.close()

            if recent:
                recent_dict = dict(recent)
                rates = CATEGORY_RATES.get(recent_dict["category"], {"base_fee": 20.0, "hourly_rate": 30.0})
                return {
                    "success": True,
                    "already_billed": True,
                    "message": f"Vehicle {normalized_num} was already billed and exited.",
                    "summary": {
                        "id": recent_dict["id"],
                        "vehicle_number": recent_dict["vehicle_number"],
                        "slot_number": recent_dict["slot_number"],
                        "category": recent_dict["category"],
                        "entry_time": recent_dict["entry_time"],
                        "exit_time": recent_dict["exit_time"],
                        "duration_minutes": recent_dict["duration_minutes"],
                        "duration_formatted": f"{recent_dict['duration_minutes']} mins",
                        "base_fee": rates["base_fee"],
                        "hourly_rate": rates["hourly_rate"],
                        "hours_billed": max(1, math.ceil(recent_dict["duration_minutes"] / 60)),
                        "fee": recent_dict["fee"]
                    },
                    "queue_allocation": None
                }

            return {
                "success": False,
                "message": f"Vehicle {normalized_num} is not currently parked in any active slot."
            }

        session = self.active_vehicles[normalized_num]
        slot_id = session["slot_id"]
        slot_number = session["slot_number"]
        category = session["category"]
        entry_time_str = session.get("entry_time")
        driver_contact = session.get("driver_contact", "")

        # Parse Entry Time defensively
        entry_dt = datetime.now()
        if entry_time_str:
            try:
                entry_dt = datetime.strptime(str(entry_time_str).strip(), "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                entry_dt = datetime.now()
        else:
            entry_time_str = entry_dt.strftime("%Y-%m-%d %H:%M:%S")

        exit_dt = datetime.now()
        exit_time_str = exit_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Duration Calculation defensively (handles None, empty string, int, or string numbers)
        duration_minutes = None
        if simulated_minutes is not None and str(simulated_minutes).strip() != "":
            try:
                parsed_sim = int(simulated_minutes)
                if parsed_sim > 0:
                    duration_minutes = parsed_sim
            except (ValueError, TypeError):
                duration_minutes = None

        if duration_minutes is None:
            diff_seconds = max(0, (exit_dt - entry_dt).total_seconds())
            duration_minutes = max(1, math.ceil(diff_seconds / 60))

        # Fee Calculation
        rates = CATEGORY_RATES.get(category, {"base_fee": 20.0, "hourly_rate": 30.0})
        base_fee = float(rates.get("base_fee", 20.0))
        hourly_rate = float(rates.get("hourly_rate", 30.0))
        hours_billed = int(math.ceil(duration_minutes / 60))
        total_fee = round(base_fee + (hourly_rate * hours_billed), 2)

        # Formatted duration string
        hrs_part = duration_minutes // 60
        mins_part = duration_minutes % 60
        if hrs_part > 0 and mins_part > 0:
            duration_formatted = f"{hrs_part}h {mins_part}m"
        elif hrs_part > 0:
            duration_formatted = f"{hrs_part} hr{'s' if hrs_part > 1 else ''}"
        else:
            duration_formatted = f"{duration_minutes} min{'s' if duration_minutes > 1 else ''}"

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # 1. Insert into parking_history
            cursor.execute("""
                INSERT INTO parking_history (vehicle_number, category, slot_number, entry_time, exit_time, duration_minutes, fee)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (normalized_num, category, slot_number, entry_time_str, exit_time_str, duration_minutes, total_fee))
            history_id = cursor.lastrowid

            # 2. Delete from active_sessions
            cursor.execute("DELETE FROM active_sessions WHERE vehicle_number = ?", (normalized_num,))

            # 3. Reset slot to available in DB
            cursor.execute("""
                UPDATE slots
                SET status = 'available', current_vehicle = NULL, entry_time = NULL
                WHERE id = ?
            """, (slot_id,))

            conn.commit()

            # Update In-Memory Slot
            target_slot = None
            for slot in self.slots:
                if slot.id == slot_id:
                    slot.status = "available"
                    slot.current_vehicle = None
                    slot.entry_time = None
                    target_slot = slot
                    break

            # Remove from Hash Map: O(1)
            if normalized_num in self.active_vehicles:
                del self.active_vehicles[normalized_num]

            exit_summary = {
                "id": history_id,
                "vehicle_number": normalized_num,
                "slot_number": slot_number,
                "category": category,
                "driver_contact": driver_contact,
                "entry_time": entry_time_str,
                "exit_time": exit_time_str,
                "duration_minutes": int(duration_minutes),
                "duration_formatted": duration_formatted,
                "base_fee": base_fee,
                "hourly_rate": hourly_rate,
                "hours_billed": hours_billed,
                "fee": total_fee
            }

            # 4. Check FIFO Waiting Queue to allocate to the next strictly eligible waiting vehicle
            queue_allocation = self._dispatch_queue_for_slot(target_slot, conn)

            return {
                "success": True,
                "already_billed": False,
                "message": f"Vehicle {normalized_num} exited Slot {slot_number}. Total Duration: {duration_formatted} | Fee: Rs. {total_fee:.2f}",
                "summary": exit_summary,
                "queue_allocation": queue_allocation
            }
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"Database error during vehicle exit: {str(e)}"}
        finally:
            conn.close()

    def _dispatch_queue_for_slot(self, slot: Slot, conn):
        """
        Internal FIFO Queue Dispatcher (Requirement 5):
        Finds the first waiting vehicle from collections.deque that strictly matches `slot.category`.
        Removes it from the queue and parks it in the freed slot.
        Does NOT count waiting time as active parking time (sets active entry_time to dispatch timestamp).
        """
        if not slot or not slot.is_available() or not self.waiting_queue:
            return None

        eligible_index = -1
        for idx, waiting_item in enumerate(self.waiting_queue):
            if slot.is_eligible_for(waiting_item["category"]):
                eligible_index = idx
                break

        if eligible_index == -1:
            return None

        # Extract the waiting vehicle in true FIFO order
        if eligible_index == 0:
            assigned_item = self.waiting_queue.popleft()
        else:
            assigned_item = self.waiting_queue[eligible_index]
            del self.waiting_queue[eligible_index]

        veh_num = assigned_item["vehicle_number"]
        veh_cat = assigned_item["category"]
        contact = assigned_item.get("driver_contact", "")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor = conn.cursor()
        # Remove from waiting_queue table
        cursor.execute("DELETE FROM waiting_queue WHERE vehicle_number = ?", (veh_num,))

        # Update remaining queue positions in DB and deque
        for new_pos, item in enumerate(self.waiting_queue, start=1):
            item["queue_position"] = new_pos
            cursor.execute("UPDATE waiting_queue SET queue_position = ? WHERE vehicle_number = ?", (new_pos, item["vehicle_number"]))

        # Occupy the slot with the dequeued vehicle starting now (waiting time excluded from billing duration)
        cursor.execute("""
            UPDATE slots
            SET status = 'occupied', current_vehicle = ?, entry_time = ?
            WHERE id = ?
        """, (veh_num, now_str, slot.id))

        cursor.execute("""
            INSERT INTO active_sessions (vehicle_number, category, slot_id, slot_number, driver_contact, entry_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (veh_num, veh_cat, slot.id, slot.slot_number, contact, now_str))

        conn.commit()

        # Update slot in memory
        slot.status = "occupied"
        slot.current_vehicle = veh_num
        slot.entry_time = now_str

        # Add to hash map: O(1)
        self.active_vehicles[veh_num] = {
            "vehicle_number": veh_num,
            "category": veh_cat,
            "slot_id": slot.id,
            "slot_number": slot.slot_number,
            "driver_contact": contact,
            "entry_time": now_str
        }

        return {
            "vehicle_number": veh_num,
            "category": veh_cat,
            "slot_number": slot.slot_number,
            "message": f"Waiting vehicle {veh_num} was automatically allocated newly available Slot {slot.slot_number}."
        }

    # =========================================================================
    # QUEUE MANAGEMENT
    # =========================================================================
    def remove_from_waiting_queue(self, vehicle_number: str):
        """Removes a vehicle manually from the waiting queue."""
        normalized_num = vehicle_number.strip().upper()
        found_index = -1
        for idx, item in enumerate(self.waiting_queue):
            if item["vehicle_number"] == normalized_num:
                found_index = idx
                break

        if found_index == -1:
            return {"success": False, "message": f"Vehicle {normalized_num} not found in waiting queue."}

        # Remove from deque
        del self.waiting_queue[found_index]

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM waiting_queue WHERE vehicle_number = ?", (normalized_num,))
            # Re-index queue positions
            for new_pos, item in enumerate(self.waiting_queue, start=1):
                item["queue_position"] = new_pos
                cursor.execute("UPDATE waiting_queue SET queue_position = ? WHERE vehicle_number = ?", (new_pos, item["vehicle_number"]))
            conn.commit()
            return {"success": True, "message": f"Vehicle {normalized_num} removed from waiting queue."}
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"Database error: {str(e)}"}
        finally:
            conn.close()

    # =========================================================================
    # SLOT RESERVATION TOGGLE (STAY IN POSITION & UPDATE IN PLACE)
    # =========================================================================
    def toggle_slot_reservation(self, slot_id: int):
        """
        Toggles a slot between 'available' and 'reserved' (Requirement 6):
        - Prevents reserving an occupied slot.
        - Prevents duplicate reservations.
        - Dispatches waiting queue if unreserved.
        """
        target_slot = None
        for slot in self.slots:
            if slot.id == slot_id:
                target_slot = slot
                break

        if not target_slot:
            return {"success": False, "message": f"Slot ID {slot_id} not found."}

        if target_slot.status == "occupied":
            return {
                "success": False,
                "message": f"Cannot reserve Slot {target_slot.slot_number} because it is currently occupied by vehicle {target_slot.current_vehicle}."
            }

        new_status = "reserved" if target_slot.status == "available" else "available"

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE slots SET status = ? WHERE id = ?", (new_status, slot_id))
            conn.commit()
            target_slot.status = new_status
            
            # If the slot was made available, check if waiting vehicles for this category can use it
            queue_allocation = None
            if new_status == "available":
                queue_allocation = self._dispatch_queue_for_slot(target_slot, conn)

            summary = self.get_dashboard_summary()

            return {
                "success": True,
                "slot_id": target_slot.id,
                "slot_number": target_slot.slot_number,
                "category": target_slot.category,
                "new_status": target_slot.status,
                "queue_allocation": queue_allocation,
                "summary": summary,
                "message": f"Slot {target_slot.slot_number} status updated to {target_slot.status.upper()}."
            }
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"Database error: {str(e)}"}
        finally:
            conn.close()

    # =========================================================================
    # DSA SORTING ALGORITHMS: Merge Sort & Quick Sort
    # =========================================================================
    def merge_sort_history(self, history_list: list, sort_key: str = "exit_time", reverse: bool = False):
        """Merge Sort (Divide and Conquer) O(N log N)."""
        comparison_count = [0]

        def _get_val(record):
            val = record.get(sort_key, "")
            if sort_key in ("duration_minutes", "fee", "id"):
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return 0.0
            return str(val).lower()

        def _merge(left, right):
            merged = []
            i = j = 0
            while i < len(left) and j < len(right):
                comparison_count[0] += 1
                val_left = _get_val(left[i])
                val_right = _get_val(right[j])

                condition = (val_left <= val_right) if not reverse else (val_left >= val_right)
                if condition:
                    merged.append(left[i])
                    i += 1
                else:
                    merged.append(right[j])
                    j += 1

            merged.extend(left[i:])
            merged.extend(right[j:])
            return merged

        def _msort(arr):
            if len(arr) <= 1:
                return arr
            mid = len(arr) // 2
            left = _msort(arr[:mid])
            right = _msort(arr[mid:])
            return _merge(left, right)

        sorted_arr = _msort(history_list)
        self.last_sort_metrics = {
            "algorithm": "Merge Sort",
            "comparisons": comparison_count[0],
            "items_sorted": len(sorted_arr),
            "time_complexity": "O(N log N)"
        }
        return sorted_arr

    def quick_sort_history(self, history_list: list, sort_key: str = "exit_time", reverse: bool = False):
        """Quick Sort (Partition-based) O(N log N)."""
        comparison_count = [0]

        def _get_val(record):
            val = record.get(sort_key, "")
            if sort_key in ("duration_minutes", "fee", "id"):
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return 0.0
            return str(val).lower()

        def _qsort(arr):
            if len(arr) <= 1:
                return arr
            pivot = arr[len(arr) // 2]
            pivot_val = _get_val(pivot)

            left, middle, right = [], [], []
            for item in arr:
                comparison_count[0] += 1
                item_val = _get_val(item)
                if item_val == pivot_val:
                    middle.append(item)
                elif (item_val < pivot_val if not reverse else item_val > pivot_val):
                    left.append(item)
                else:
                    right.append(item)

            return _qsort(left) + middle + _qsort(right)

        sorted_arr = _qsort(history_list)
        self.last_sort_metrics = {
            "algorithm": "Quick Sort",
            "comparisons": comparison_count[0],
            "items_sorted": len(sorted_arr),
            "time_complexity": "O(N log N) avg, O(N^2) worst"
        }
        return sorted_arr

    # =========================================================================
    # HISTORY & SEARCH (WITH RECORD RETRIEVAL & DELETION)
    # =========================================================================
    def get_parking_history(self, search_query: str = "", sort_by: str = "exit_time", order: str = "desc", algorithm: str = "mergesort"):
        """
        Fetches history from DB, applies Linear Search filtering for search_query,
        and sorts using custom DSA sorting algorithm (Merge Sort or Quick Sort).
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, vehicle_number, category, slot_number, entry_time, exit_time, duration_minutes, fee FROM parking_history")
        rows = cursor.fetchall()
        conn.close()

        records = [dict(row) for row in rows]

        if search_query:
            query = search_query.strip().lower()
            filtered_records = []
            for rec in records:
                if (query in rec["vehicle_number"].lower() or
                    query in rec["slot_number"].lower() or
                    query in rec["category"].lower()):
                    filtered_records.append(rec)
            records = filtered_records

        is_reverse = (order.lower() == "desc")
        if algorithm == "quicksort":
            return self.quick_sort_history(records, sort_key=sort_by, reverse=is_reverse)
        else:
            return self.merge_sort_history(records, sort_key=sort_by, reverse=is_reverse)

    def get_history_record_by_id(self, record_id: int):
        """
        Fetches a single completed parking history record by ID (Requirement 2).
        Returns the original transaction details without recalculating fee.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, vehicle_number, category, slot_number, entry_time, exit_time, duration_minutes, fee FROM parking_history WHERE id = ?",
            (record_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None

        rec = dict(row)
        rates = CATEGORY_RATES.get(rec["category"], {"base_fee": 20.0, "hourly_rate": 30.0})
        rec["base_fee"] = rates["base_fee"]
        rec["hourly_rate"] = rates["hourly_rate"]
        rec["hours_billed"] = max(1, math.ceil(rec["duration_minutes"] / 60))
        return rec

    def delete_parking_record(self, record_id: int):
        """
        Deletes only the selected completed history record (Requirement 2).
        Safely handles linked database records and NEVER touches active vehicles or other slots.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, vehicle_number, slot_number FROM parking_history WHERE id = ?", (record_id,))
            record = cursor.fetchone()
            if not record:
                return {"success": False, "message": f"Parking history record #{record_id} does not exist."}

            cursor.execute("DELETE FROM parking_history WHERE id = ?", (record_id,))
            conn.commit()
            return {
                "success": True,
                "message": f"Parking history record #{record_id} ({record['vehicle_number']}) was successfully deleted."
            }
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"Database error during record deletion: {str(e)}"}
        finally:
            conn.close()

    # =========================================================================
    # DASHBOARD & METRICS COMPUTATION
    # =========================================================================
    def get_dashboard_summary(self):
        """Calculates live parking lot statistics."""
        total_slots = len(self.slots)
        available_slots = sum(1 for s in self.slots if s.status == "available")
        occupied_slots = sum(1 for s in self.slots if s.status == "occupied")
        reserved_slots = sum(1 for s in self.slots if s.status == "reserved")
        waiting_count = len(self.waiting_queue)
        occupancy_pct = round((occupied_slots / total_slots) * 100, 1) if total_slots > 0 else 0

        categories = ["Two-Wheeler", "Four-Wheeler", "EV Charging", "Reserved"]
        category_stats = {}
        for cat in categories:
            total_cat = sum(1 for s in self.slots if s.category == cat)
            occupied_cat = sum(1 for s in self.slots if s.category == cat and s.status == "occupied")
            available_cat = sum(1 for s in self.slots if s.category == cat and s.status == "available")
            reserved_cat = sum(1 for s in self.slots if s.category == cat and s.status == "reserved")
            category_stats[cat] = {
                "total": total_cat,
                "occupied": occupied_cat,
                "available": available_cat,
                "reserved": reserved_cat
            }

        return {
            "total_slots": total_slots,
            "available_slots": available_slots,
            "occupied_slots": occupied_slots,
            "reserved_slots": reserved_slots,
            "waiting_count": waiting_count,
            "occupancy_pct": occupancy_pct,
            "category_stats": category_stats
        }
