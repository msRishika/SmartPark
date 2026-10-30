"""
parking_manager.py
Core Data Structures and Algorithms (DSA) Engine for SmartPark.

Implements:
1. Hashing: Python dictionary (`dict`) for O(1) active vehicle lookup and duplicate checking.
2. Searching: Linear Search O(N) for first eligible available parking slot allocation.
3. Queue: Python `collections.deque` for true O(1) FIFO waiting queue management with strict category compatibility.
4. Sorting: Custom Merge Sort and Quick Sort algorithms (O(N log N)) for parking history.
5. Reservation & Slot Management: Strict category and Normal/Reserved slot type segregation, persistent DB operations.
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
    "EV": {"base_fee": 25.0, "hourly_rate": 40.0},
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
    """Represents a physical parking slot with category, slot type, area, and status."""
    def __init__(self, slot_id: int, slot_number: str, category: str, status: str = "available",
                 current_vehicle: str = None, entry_time: str = None,
                 slot_type: str = "Normal", area: str = "General", is_enabled: int = 1):
        self.id = slot_id
        self.slot_number = slot_number
        self.category = category    # 'Two-Wheeler', 'Four-Wheeler', 'EV Charging'
        self.status = status        # 'available', 'occupied', 'reserved', 'disabled'
        self.current_vehicle = current_vehicle
        self.entry_time = entry_time
        self.slot_type = slot_type  # 'Normal', 'Reserved'
        self.area = area            # 'Two-Wheeler Bay', 'North Bay', 'South Bay', etc.
        self.is_enabled = int(is_enabled)

    def is_available(self) -> bool:
        """A slot is available only if it is enabled and its status is 'available'."""
        return self.is_enabled == 1 and self.status == "available"

    def is_eligible_for(self, vehicle_category: str) -> bool:
        """
        Check if this slot strictly accommodates the given vehicle category (Requirement 3 & 5):
        - Two-Wheeler: assign only to compatible Two-Wheeler slot.
        - Four-Wheeler: assign only to compatible standard Four-Wheeler slot.
        - EV requiring charging: assign only to designated EV Charging slot (NEVER fallback to Four-Wheeler).
        - EV slots must NEVER be assigned to Two-Wheeler or Four-Wheeler vehicles.
        """
        v_cat = (vehicle_category or "").strip()
        s_cat = (self.category or "").strip()

        # EV vehicle matching
        if v_cat in ("EV", "EV Charging"):
            return s_cat in ("EV", "EV Charging")

        # Slot is EV: Non-EV vehicles can NEVER park in EV slots
        if s_cat in ("EV", "EV Charging"):
            return False

        return s_cat == v_cat

    def to_dict(self):
        effective_status = "disabled" if self.is_enabled == 0 else self.status
        return {
            "id": self.id,
            "slot_number": self.slot_number,
            "category": self.category,
            "status": effective_status,
            "raw_status": self.status,
            "current_vehicle": self.current_vehicle,
            "entry_time": self.entry_time,
            "slot_type": self.slot_type,
            "area": self.area,
            "is_enabled": self.is_enabled
        }


class ParkingManager:
    """
    Central Manager managing parking slots, active parked vehicles,
    FIFO waiting queue with strict compatibility, active reservations, and parking history.
    """
    def __init__(self, db_path=None):
        self.db_path = db_path
        self.slots = []                        # List of Slot objects [O(N) search space]
        self.active_vehicles = {}              # Hash Map: vehicle_number -> session_info [O(1) lookup]
        self.waiting_queue = deque()           # collections.deque for FIFO waiting vehicles [O(1) enqueue/dequeue]
        self.active_reservations = {}          # Hash Map: vehicle_number -> reservation_info [O(1) lookup]
        
        # DSA Performance Metrics for Viva / Demonstration
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

    def get_slot_by_id(self, slot_id: int):
        """Finds a slot by its primary key ID."""
        for slot in self.slots:
            if slot.id == slot_id:
                return slot
        return None

    def get_slot_by_number(self, slot_number: str):
        """Finds a slot by its unique slot number string (e.g. S-01)."""
        num = str(slot_number).strip().upper()
        for slot in self.slots:
            if slot.slot_number.upper() == num:
                return slot
        return None

    def get_active_reservation(self, vehicle_number: str):
        """Returns the active reservation dictionary for a given vehicle number if exists."""
        norm = (vehicle_number or "").strip().upper()
        return self.active_reservations.get(norm)

    def reload_from_db(self):
        """
        Loads all persistent data from SQLite into in-memory DSA structures:
        - slots: List[Slot]
        - active_vehicles: dict
        - waiting_queue: collections.deque
        - active_reservations: dict
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # 1. Load Slots
        cursor.execute("""
            SELECT id, slot_number, category, status, current_vehicle, entry_time,
                   COALESCE(slot_type, 'Normal') as slot_type,
                   COALESCE(area, 'General') as area,
                   COALESCE(is_enabled, 1) as is_enabled
            FROM slots 
            ORDER BY id ASC
        """)
        rows = cursor.fetchall()
        self.slots = [
            Slot(
                slot_id=row["id"],
                slot_number=row["slot_number"],
                category=row["category"],
                status=row["status"],
                current_vehicle=row["current_vehicle"],
                entry_time=row["entry_time"],
                slot_type=row["slot_type"],
                area=row["area"],
                is_enabled=row["is_enabled"]
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

        # 4. Rebuild Active Reservations: Hash Map
        self.active_reservations.clear()
        try:
            cursor.execute("SELECT id, slot_id, slot_number, vehicle_number, category, driver_contact, status, created_at FROM reservations WHERE status = 'active'")
            for row in cursor.fetchall():
                v_num = row["vehicle_number"].strip().upper()
                self.active_reservations[v_num] = {
                    "id": row["id"],
                    "slot_id": row["slot_id"],
                    "slot_number": row["slot_number"],
                    "vehicle_number": v_num,
                    "category": row["category"],
                    "driver_contact": row["driver_contact"],
                    "status": row["status"],
                    "created_at": row["created_at"]
                }
        except Exception:
            pass

        conn.close()

    # =========================================================================
    # DSA SEARCHING: Linear Search for First Available Eligible Slot
    # =========================================================================
    def find_first_available_slot(self, vehicle_category: str, slot_type: str = "Normal"):
        """
        ALGORITHM: Linear Search
        Scans slots sequentially to find the first eligible slot with status == 'available'
        and matching slot_type (Requirement 4: walk-ins allocate Normal slots).
        """
        probes = 0
        for slot in self.slots:
            probes += 1
            if slot.is_available() and slot.slot_type == slot_type and slot.is_eligible_for(vehicle_category):
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
    # RESERVATION MANAGEMENT (REQUIREMENT 4)
    # =========================================================================
    def reserve_slot(self, slot_id: int, vehicle_number: str, category: str, driver_contact: str = ""):
        """
        Reserves a designated Reserved slot for a specific vehicle (Requirement 4):
        - Strict vehicle registration and 10-digit phone number validation.
        - Slot must be available, enabled, and designated as slot_type == 'Reserved'.
        - Enforces strict category compatibility.
        - Prevents duplicate reservations and duplicate active parking.
        """
        # Strict Input Validation
        is_valid_veh, veh_res = validate_vehicle_registration(vehicle_number)
        if not is_valid_veh:
            return {"success": False, "message": veh_res}
        normalized_num = veh_res

        is_valid_contact, contact_res = validate_driver_contact_number(driver_contact)
        if not is_valid_contact:
            return {"success": False, "message": contact_res}
        clean_contact = contact_res

        target_slot = self.get_slot_by_id(slot_id)
        if not target_slot:
            return {"success": False, "message": f"Slot ID {slot_id} not found."}

        if target_slot.is_enabled == 0:
            return {"success": False, "message": f"Slot {target_slot.slot_number} is disabled and cannot be reserved."}

        if target_slot.slot_type != "Reserved":
            return {"success": False, "message": f"Slot {target_slot.slot_number} is a Normal bay. Only designated Reserved bays can be reserved."}

        if not target_slot.is_available():
            return {"success": False, "message": f"Slot {target_slot.slot_number} is currently {target_slot.status.upper()} and cannot be reserved."}

        if not target_slot.is_eligible_for(category):
            return {"success": False, "message": f"Incompatible category! Slot {target_slot.slot_number} accommodates {target_slot.category}, not {category}."}

        # Duplicate Checks
        if normalized_num in self.active_vehicles:
            parked_slot = self.active_vehicles[normalized_num]["slot_number"]
            return {"success": False, "message": f"Vehicle {normalized_num} is already parked in Slot {parked_slot}."}

        if normalized_num in self.active_reservations:
            res_info = self.active_reservations[normalized_num]
            return {"success": False, "message": f"Vehicle {normalized_num} already has an active reservation for Slot {res_info['slot_number']}."}

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO reservations (slot_id, slot_number, vehicle_number, category, driver_contact, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?)
            """, (target_slot.id, target_slot.slot_number, normalized_num, category, clean_contact, now_str))
            res_id = cursor.lastrowid

            cursor.execute("""
                UPDATE slots
                SET status = 'reserved', current_vehicle = ?
                WHERE id = ?
            """, (normalized_num, target_slot.id))

            conn.commit()

            # Update in-memory
            target_slot.status = "reserved"
            target_slot.current_vehicle = normalized_num

            self.active_reservations[normalized_num] = {
                "id": res_id,
                "slot_id": target_slot.id,
                "slot_number": target_slot.slot_number,
                "vehicle_number": normalized_num,
                "category": category,
                "driver_contact": clean_contact,
                "status": "active",
                "created_at": now_str
            }

            # If vehicle was queued, remove it from waiting queue
            self.remove_from_waiting_queue(normalized_num)

            summary = self.get_dashboard_summary()
            return {
                "success": True,
                "slot_id": target_slot.id,
                "slot_number": target_slot.slot_number,
                "category": target_slot.category,
                "new_status": "reserved",
                "vehicle_number": normalized_num,
                "summary": summary,
                "message": f"Slot {target_slot.slot_number} ({target_slot.category}) successfully reserved for vehicle {normalized_num}."
            }
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"Database error reserving slot: {str(e)}"}
        finally:
            conn.close()

    def cancel_reservation(self, slot_id: int):
        """Cancels an active reservation and frees the Reserved slot."""
        target_slot = self.get_slot_by_id(slot_id)
        if not target_slot:
            return {"success": False, "message": f"Slot ID {slot_id} not found."}

        if target_slot.status != "reserved":
            return {"success": False, "message": f"Slot {target_slot.slot_number} is not currently reserved."}

        veh_num = target_slot.current_vehicle

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE reservations
                SET status = 'cancelled'
                WHERE slot_id = ? AND status = 'active'
            """, (slot_id,))

            cursor.execute("""
                UPDATE slots
                SET status = 'available', current_vehicle = NULL
                WHERE id = ?
            """, (slot_id,))

            conn.commit()

            target_slot.status = "available"
            target_slot.current_vehicle = None

            if veh_num and veh_num in self.active_reservations:
                del self.active_reservations[veh_num]

            summary = self.get_dashboard_summary()
            return {
                "success": True,
                "slot_id": target_slot.id,
                "slot_number": target_slot.slot_number,
                "category": target_slot.category,
                "new_status": "available",
                "summary": summary,
                "message": f"Reservation for Slot {target_slot.slot_number} cancelled. Slot is now AVAILABLE."
            }
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"Database error cancelling reservation: {str(e)}"}
        finally:
            conn.close()

    def toggle_slot_reservation(self, slot_id: int, vehicle_number: str = None, category: str = None, driver_contact: str = None):
        """
        Toggles slot reservation status (preserves backward compatibility with existing tests and AJAX):
        - If reserved, unreserves it.
        - If available, reserves it.
        """
        target_slot = self.get_slot_by_id(slot_id)
        if not target_slot:
            return {"success": False, "message": f"Slot ID {slot_id} not found."}

        if target_slot.status == "occupied":
            return {
                "success": False,
                "message": f"Cannot reserve Slot {target_slot.slot_number} because it is currently occupied by vehicle {target_slot.current_vehicle}."
            }

        if target_slot.status == "reserved":
            return self.cancel_reservation(slot_id)

        # Available slot -> reserve
        v_num = vehicle_number or f"RESV{target_slot.slot_number.replace('-', '')}"
        v_cat = category or target_slot.category
        v_contact = driver_contact or "9876543210"

        # If slot is Normal type in legacy call, temporarily allow reservation for backward compatibility
        if target_slot.slot_type != "Reserved":
            target_slot.slot_type = "Reserved"
            conn = self.get_connection()
            conn.execute("UPDATE slots SET slot_type = 'Reserved' WHERE id = ?", (slot_id,))
            conn.commit()
            conn.close()

        return self.reserve_slot(slot_id, v_num, v_cat, v_contact)

    # =========================================================================
    # VEHICLE ENTRY & ALLOCATION (REQUIREMENT 4)
    # =========================================================================
    def park_vehicle(self, vehicle_number: str, category: str, driver_contact: str = "", preferred_slot_id: int = None, strict_validation: bool = True):
        """
        Attempts to park a vehicle:
        1. Strict Input Validation (Requirement 4)
        2. Duplicate Check via HASHING: O(1) active_vehicles lookup
        3. Duplicate Check in FIFO Waiting Queue: O(M)
        4. Active Reservation Check: If vehicle has an active reservation, assign that exact reserved slot.
           Duration and charges begin ONLY upon check-in!
        5. Normal Walk-in Allocation: If no reservation, search for compatible available NORMAL slot.
        6. If no eligible Normal slot found: Enqueue into FIFO collections.deque.
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

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 3. Check for Active Reservation (Requirement 4)
        active_res = self.get_active_reservation(normalized_num)
        if active_res:
            res_slot_id = active_res["slot_id"]
            res_slot = self.get_slot_by_id(res_slot_id)
            if res_slot and (res_slot.status == "reserved" or res_slot.is_available()) and res_slot.is_eligible_for(category):
                conn = self.get_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        UPDATE reservations
                        SET status = 'fulfilled'
                        WHERE id = ?
                    """, (active_res["id"],))

                    cursor.execute("""
                        UPDATE slots
                        SET status = 'occupied', current_vehicle = ?, entry_time = ?
                        WHERE id = ?
                    """, (normalized_num, now_str, res_slot.id))

                    cursor.execute("""
                        INSERT INTO active_sessions (vehicle_number, category, slot_id, slot_number, driver_contact, entry_time)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (normalized_num, category, res_slot.id, res_slot.slot_number, clean_contact or active_res.get("driver_contact", ""), now_str))

                    conn.commit()

                    res_slot.status = "occupied"
                    res_slot.current_vehicle = normalized_num
                    res_slot.entry_time = now_str

                    if normalized_num in self.active_reservations:
                        del self.active_reservations[normalized_num]

                    self.active_vehicles[normalized_num] = {
                        "vehicle_number": normalized_num,
                        "category": category,
                        "slot_id": res_slot.id,
                        "slot_number": res_slot.slot_number,
                        "driver_contact": clean_contact or active_res.get("driver_contact", ""),
                        "entry_time": now_str
                    }

                    return {
                        "success": True,
                        "status": "allocated",
                        "slot_number": res_slot.slot_number,
                        "slot_id": res_slot.id,
                        "category": category,
                        "message": f"Active reservation honored! Slot {res_slot.slot_number} ({res_slot.category}) checked in for vehicle {normalized_num}."
                    }
                except Exception as e:
                    conn.rollback()
                    return {"success": False, "message": f"Database error during reservation check-in: {str(e)}"}
                finally:
                    conn.close()

        # 4. Normal Walk-in Allocation (Requirement 4: only available Normal slots)
        target_slot = None
        if preferred_slot_id:
            for slot in self.slots:
                if slot.id == preferred_slot_id and slot.is_available() and slot.slot_type == "Normal" and slot.is_eligible_for(category):
                    target_slot = slot
                    break

        if not target_slot:
            target_slot = self.find_first_available_slot(category, slot_type="Normal")

        # 5. If eligible Normal slot found, allocate it!
        if target_slot:
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE slots
                    SET status = 'occupied', current_vehicle = ?, entry_time = ?
                    WHERE id = ?
                """, (normalized_num, now_str, target_slot.id))

                cursor.execute("""
                    INSERT INTO active_sessions (vehicle_number, category, slot_id, slot_number, driver_contact, entry_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (normalized_num, category, target_slot.id, target_slot.slot_number, clean_contact, now_str))

                conn.commit()

                target_slot.status = "occupied"
                target_slot.current_vehicle = normalized_num
                target_slot.entry_time = now_str

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

        # 6. No eligible Normal slot available -> Enqueue into FIFO Waiting Queue (collections.deque)
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

            self.waiting_queue.append(queue_item)

            return {
                "success": True,
                "status": "queued",
                "queue_position": queue_pos,
                "message": f"All eligible {category} normal bays are currently occupied. Vehicle {normalized_num} added to Waiting List at Position #{queue_pos}."
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

        # Duration Calculation defensively
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

            # 4. Check FIFO Waiting Queue to allocate to next strictly eligible waiting vehicle
            # (Applies only to Normal bays: Requirement 4)
            queue_allocation = None
            if target_slot and target_slot.slot_type == "Normal" and target_slot.is_enabled == 1:
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
        Internal FIFO Queue Dispatcher (Requirement 3 & 4):
        Finds the first waiting vehicle from collections.deque that strictly matches `slot.category`.
        Enforces that queued vehicles are allocated only to available Normal slots.
        """
        if not slot or not slot.is_available() or slot.slot_type != "Normal" or not self.waiting_queue:
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
        cursor.execute("DELETE FROM waiting_queue WHERE vehicle_number = ?", (veh_num,))

        # Update remaining queue positions in DB and deque
        for new_pos, item in enumerate(self.waiting_queue, start=1):
            item["queue_position"] = new_pos
            cursor.execute("UPDATE waiting_queue SET queue_position = ? WHERE vehicle_number = ?", (new_pos, item["vehicle_number"]))

        # Occupy slot starting now (waiting time excluded from billing duration)
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

        del self.waiting_queue[found_index]

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM waiting_queue WHERE vehicle_number = ?", (normalized_num,))
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
    # ADMIN SLOT MANAGEMENT (REQUIREMENT 2)
    # =========================================================================
    def add_slot(self, slot_number: str, category: str, slot_type: str = "Normal", area: str = "General", is_enabled: int = 1):
        """Persistently adds a new slot to the database."""
        num = (slot_number or "").strip().upper()
        if not num:
            return {"success": False, "message": "Slot ID cannot be empty."}

        if self.get_slot_by_number(num):
            return {"success": False, "message": f"Slot {num} already exists. Slot ID must be unique."}

        cat = (category or "").strip()
        if cat not in ("Two-Wheeler", "Four-Wheeler", "EV", "EV Charging"):
            return {"success": False, "message": f"Invalid category {category}. Must be Two-Wheeler, Four-Wheeler, or EV."}
        if cat == "EV":
            cat = "EV Charging"

        stype = (slot_type or "").strip()
        if stype not in ("Normal", "Reserved"):
            stype = "Normal"

        area_val = (area or "").strip() or "General"
        enabled_val = 1 if int(is_enabled) == 1 else 0

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO slots (slot_number, category, status, slot_type, area, is_enabled)
                VALUES (?, ?, 'available', ?, ?, ?)
            """, (num, cat, stype, area_val, enabled_val))
            conn.commit()
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"Database error adding slot: {str(e)}"}
        finally:
            conn.close()

        self.reload_from_db()
        return {"success": True, "message": f"Slot {num} ({cat} - {stype}) successfully added to {area_val}."}

    def edit_slot(self, slot_id: int, category: str, slot_type: str, area: str, is_enabled: int = 1):
        """Safely edits an existing slot without breaking parking records or active sessions."""
        target = self.get_slot_by_id(slot_id)
        if not target:
            return {"success": False, "message": f"Slot ID {slot_id} not found."}

        cat = (category or "").strip()
        if cat not in ("Two-Wheeler", "Four-Wheeler", "EV", "EV Charging"):
            return {"success": False, "message": f"Invalid category {category}."}
        if cat == "EV":
            cat = "EV Charging"

        stype = (slot_type or "").strip()
        if stype not in ("Normal", "Reserved"):
            stype = "Normal"

        enabled_val = 1 if int(is_enabled) == 1 else 0

        # Safety check: if currently occupied, prevent changing category or disabling
        if target.status == "occupied":
            if target.category != cat:
                return {"success": False, "message": f"Cannot change category of Slot {target.slot_number} while occupied by vehicle {target.current_vehicle}."}
            if enabled_val == 0:
                return {"success": False, "message": f"Cannot disable Slot {target.slot_number} while occupied by vehicle {target.current_vehicle}."}

        area_val = (area or "").strip() or target.area

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            new_status = target.status
            if enabled_val == 0 and target.status == "available":
                new_status = "disabled"
            elif enabled_val == 1 and target.status == "disabled":
                new_status = "available"

            cursor.execute("""
                UPDATE slots
                SET category = ?, slot_type = ?, area = ?, is_enabled = ?, status = ?
                WHERE id = ?
            """, (cat, stype, area_val, enabled_val, new_status, slot_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"Database error editing slot: {str(e)}"}
        finally:
            conn.close()

        self.reload_from_db()

        # If newly enabled Normal slot, check waiting queue
        if enabled_val == 1 and stype == "Normal" and target.status != "occupied":
            updated_slot = self.get_slot_by_id(slot_id)
            if updated_slot and updated_slot.is_available():
                conn2 = self.get_connection()
                self._dispatch_queue_for_slot(updated_slot, conn2)
                conn2.close()

        return {"success": True, "message": f"Slot {target.slot_number} details successfully updated."}

    def toggle_slot_status(self, slot_id: int):
        """Safely enables or disables a slot."""
        target = self.get_slot_by_id(slot_id)
        if not target:
            return {"success": False, "message": f"Slot ID {slot_id} not found."}

        if target.status == "occupied" and target.is_enabled == 1:
            return {"success": False, "message": f"Cannot disable Slot {target.slot_number} because it is occupied by vehicle {target.current_vehicle}."}

        new_enabled = 0 if target.is_enabled == 1 else 1
        new_status = "disabled" if new_enabled == 0 else "available"
        if target.status == "occupied":
            new_status = "occupied"
        elif target.status == "reserved" and new_enabled == 0:
            new_status = "disabled"

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE slots SET is_enabled = ?, status = ? WHERE id = ?", (new_enabled, new_status, slot_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"Database error updating slot status: {str(e)}"}
        finally:
            conn.close()

        self.reload_from_db()

        status_str = "ENABLED" if new_enabled == 1 else "DISABLED"
        queue_alloc = None
        if new_enabled == 1 and target.slot_type == "Normal":
            reloaded = self.get_slot_by_id(slot_id)
            if reloaded and reloaded.is_available():
                conn2 = self.get_connection()
                queue_alloc = self._dispatch_queue_for_slot(reloaded, conn2)
                conn2.close()

        return {
            "success": True,
            "is_enabled": new_enabled,
            "status": new_status,
            "queue_allocation": queue_alloc,
            "message": f"Slot {target.slot_number} is now {status_str}."
        }

    def delete_slot(self, slot_number: str, category: str, slot_type: str, area: str):
        """
        Safely deletes a slot only when all four details match an existing record (Requirement 3):
        1. Slot Number / Bay ID
        2. Vehicle Category (Four-Wheeler, Two-Wheeler, or EV)
        3. Slot Type (Normal or Reserved)
        4. Applicable Parking Area

        Strict safety checks:
        - Must require all four details and match them against the same slot record.
        - Fails if slot does not exist or any detail does not match.
        - Prevents deletion if slot has an active vehicle, active reservation, or linked active records.
        - Informs admin of the reason and suggests disabling instead.
        - Never alters unrelated slots, vehicles, reservations, billing, or history.
        """
        num_raw = (slot_number or "").strip().upper()
        cat_raw = (category or "").strip()
        stype_raw = (slot_type or "").strip()
        area_raw = (area or "").strip()

        if not num_raw or not cat_raw or not stype_raw or not area_raw:
            return {
                "success": False,
                "message": "All four slot details are required: Slot Number, Vehicle Category, Slot Type, and Parking Area."
            }

        # Find slot by number (exact or hyphen-normalized match)
        target = self.get_slot_by_number(num_raw)
        if not target:
            num_clean = num_raw.replace("-", "")
            for s in self.slots:
                if s.slot_number.upper().replace("-", "") == num_clean:
                    target = s
                    break

        if not target:
            return {
                "success": False,
                "message": f"Slot '{num_raw}' does not exist in facility records."
            }

        # Normalize categories for comparison: EV and EV Charging are equivalent
        target_cat = "EV" if target.category in ("EV", "EV Charging") else target.category
        input_cat = "EV" if cat_raw in ("EV", "EV Charging") else cat_raw

        # Match category
        if target_cat.lower() != input_cat.lower():
            return {
                "success": False,
                "message": f"Slot detail mismatch: Vehicle Category does not match slot {target.slot_number} (expected '{target.category}', received '{cat_raw}'). Deletion aborted."
            }

        # Match slot type
        if target.slot_type.lower() != stype_raw.lower():
            return {
                "success": False,
                "message": f"Slot detail mismatch: Slot Type does not match slot {target.slot_number} (expected '{target.slot_type}', received '{stype_raw}'). Deletion aborted."
            }

        # Match parking area (case-insensitive stripped match)
        if (target.area or "General").strip().lower() != area_raw.lower():
            return {
                "success": False,
                "message": f"Slot detail mismatch: Parking Area does not match slot {target.slot_number} (expected '{target.area or 'General'}', received '{area_raw}'). Deletion aborted."
            }

        # Safety Check 1: Active vehicle parked in the slot
        if target.status == "occupied" or target.current_vehicle:
            return {
                "success": False,
                "message": f"Cannot delete Slot {target.slot_number} because it is currently occupied with an active parked vehicle ({target.current_vehicle or 'in use'}). Active records must be preserved. You can disable the slot instead to prevent new allocations."
            }

        # Safety Check 2: Active reservation on the slot
        if target.status == "reserved":
            return {
                "success": False,
                "message": f"Cannot delete Slot {target.slot_number} because it is currently reserved. You can cancel the reservation or disable the slot instead."
            }

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Check active sessions table
            cursor.execute("SELECT COUNT(*) FROM active_sessions WHERE slot_id = ? OR slot_number = ?", (target.id, target.slot_number))
            if cursor.fetchone()[0] > 0:
                return {
                    "success": False,
                    "message": f"Cannot delete Slot {target.slot_number} because an active parking session is attached to it. Active records must be preserved. You can disable the slot instead."
                }

            # Check active reservations table
            cursor.execute("SELECT COUNT(*) FROM reservations WHERE (slot_id = ? OR slot_number = ?) AND status = 'active'", (target.id, target.slot_number))
            if cursor.fetchone()[0] > 0:
                return {
                    "success": False,
                    "message": f"Cannot delete Slot {target.slot_number} because an active reservation is linked to it. Active records must be preserved. You can cancel the reservation or disable the slot instead."
                }

            # Perform persistent deletion from slots table
            cursor.execute("DELETE FROM slots WHERE id = ?", (target.id,))
            conn.commit()

            # Reload in-memory data structures immediately
            self.reload_from_db()

            return {
                "success": True,
                "message": f"Slot {target.slot_number} ({target.category}, {target.slot_type}, {target.area}) was successfully deleted from facility records.",
                "deleted_slot": {
                    "id": target.id,
                    "slot_number": target.slot_number,
                    "category": target.category,
                    "slot_type": target.slot_type,
                    "area": target.area
                }
            }
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"Database error during slot deletion: {str(e)}"}
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
        """Calculates live parking lot statistics across all bays and categories."""
        total_slots = len(self.slots)
        available_slots = sum(1 for s in self.slots if s.is_available())
        occupied_slots = sum(1 for s in self.slots if s.status == "occupied")
        reserved_slots = sum(1 for s in self.slots if s.status == "reserved")
        disabled_slots = sum(1 for s in self.slots if s.is_enabled == 0)
        normal_slots = sum(1 for s in self.slots if s.slot_type == "Normal")
        reserved_type_slots = sum(1 for s in self.slots if s.slot_type == "Reserved")
        waiting_count = len(self.waiting_queue)
        occupancy_pct = round((occupied_slots / total_slots) * 100, 1) if total_slots > 0 else 0

        categories = ["Two-Wheeler", "Four-Wheeler", "EV Charging"]
        category_stats = {}
        for cat in categories:
            total_cat = sum(1 for s in self.slots if s.category == cat)
            occupied_cat = sum(1 for s in self.slots if s.category == cat and s.status == "occupied")
            available_cat = sum(1 for s in self.slots if s.category == cat and s.is_available())
            reserved_cat = sum(1 for s in self.slots if s.category == cat and s.status == "reserved")
            disabled_cat = sum(1 for s in self.slots if s.category == cat and s.is_enabled == 0)
            category_stats[cat] = {
                "total": total_cat,
                "occupied": occupied_cat,
                "available": available_cat,
                "reserved": reserved_cat,
                "disabled": disabled_cat
            }

        # Legacy fallback if 'Reserved' key is accessed by existing templates or APIs
        category_stats["Reserved"] = {
            "total": reserved_type_slots,
            "occupied": sum(1 for s in self.slots if s.slot_type == "Reserved" and s.status == "occupied"),
            "available": sum(1 for s in self.slots if s.slot_type == "Reserved" and s.is_available()),
            "reserved": reserved_slots,
            "disabled": sum(1 for s in self.slots if s.slot_type == "Reserved" and s.is_enabled == 0)
        }

        return {
            "total_slots": total_slots,
            "available_slots": available_slots,
            "occupied_slots": occupied_slots,
            "reserved_slots": reserved_slots,
            "disabled_slots": disabled_slots,
            "normal_slots": normal_slots,
            "reserved_type_slots": reserved_type_slots,
            "waiting_count": waiting_count,
            "occupancy_pct": occupancy_pct,
            "category_stats": category_stats
        }
