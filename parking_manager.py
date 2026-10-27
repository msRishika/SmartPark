"""
parking_manager.py
Core Data Structures and Algorithms (DSA) Engine for SmartPark.

Implements:
1. Hashing: Python dictionary (`dict`) for O(1) active vehicle lookup and duplicate checking.
2. Searching: Linear Search O(N) for first eligible available parking slot allocation.
3. Queue: Python `collections.deque` for true O(1) FIFO waiting queue management.
4. Sorting: Custom Merge Sort and Quick Sort algorithms (O(N log N)) for parking history.
"""

from collections import deque
from datetime import datetime, timezone
import math
import copy
from database import get_db_connection

# Hourly parking rates by vehicle category
CATEGORY_RATES = {
    "Two-Wheeler": {"base_fee": 10.0, "hourly_rate": 15.0},
    "Four-Wheeler": {"base_fee": 20.0, "hourly_rate": 30.0},
    "EV Charging": {"base_fee": 25.0, "hourly_rate": 40.0},
    "Reserved": {"base_fee": 30.0, "hourly_rate": 50.0}
}

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
        Check if this slot can accommodate the given vehicle category.
        - Two-Wheeler -> Two-Wheeler slots only
        - Four-Wheeler -> Four-Wheeler slots
        - EV Charging -> EV Charging slots (or Four-Wheeler fallback)
        - Reserved -> Reserved slots (or Four-Wheeler)
        """
        if self.category == vehicle_category:
            return True
        if vehicle_category == "EV Charging" and self.category == "Four-Wheeler":
            return True
        if vehicle_category == "Reserved" and self.category == "Four-Wheeler":
            return True
        return False

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
    FIFO waiting queue, and parking history.
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
            - Best Case: O(1) (First checked slot is free and eligible)
            - Worst Case: O(N) (Iterates through all N slots)
            - Average Case: O(N/2) ~ O(N)
        SPACE COMPLEXITY: O(1) Auxiliary space
        
        Scans slots sequentially to find the first eligible slot with status == 'available'.
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
    def park_vehicle(self, vehicle_number: str, category: str, driver_contact: str = "", preferred_slot_id: int = None):
        """
        Attempts to park a vehicle:
        1. Check Duplicate via HASHING: O(1) active_vehicles lookup
        2. Check if already waiting in FIFO Queue: O(M)
        3. Search for slot using LINEAR SEARCH: O(N)
        4. If slot found:
           - Update slot status to 'occupied'
           - Add to active_vehicles dictionary: O(1)
           - Persist to SQLite
        5. If no slot found (Parking Full for category):
           - Enqueue into collections.deque: O(1)
           - Persist to waiting_queue table
        """
        normalized_num = vehicle_number.strip().upper()
        if not normalized_num:
            return {"success": False, "message": "Vehicle number cannot be empty."}

        # 1. Hashing Check: Duplicate Active Vehicle (O(1))
        if normalized_num in self.active_vehicles:
            active_info = self.active_vehicles[normalized_num]
            return {
                "success": False,
                "message": f"Duplicate vehicle! Vehicle {normalized_num} is already parked in Slot {active_info['slot_number']}."
            }

        # 2. Check if already waiting in queue
        for item in self.waiting_queue:
            if item["vehicle_number"] == normalized_num:
                return {
                    "success": False,
                    "message": f"Vehicle {normalized_num} is already waiting in queue at Position #{item['queue_position']}."
                }

        # 3. Slot Selection: Preferred or Linear Search
        target_slot = None
        if preferred_slot_id:
            for slot in self.slots:
                if slot.id == preferred_slot_id and slot.is_available() and slot.is_eligible_for(category):
                    target_slot = slot
                    break

        if not target_slot:
            # Linear Search for the first eligible available slot
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
                """, (normalized_num, category, target_slot.id, target_slot.slot_number, driver_contact, now_str))

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
                    "driver_contact": driver_contact,
                    "entry_time": now_str
                }

                return {
                    "success": True,
                    "status": "allocated",
                    "slot_number": target_slot.slot_number,
                    "slot_id": target_slot.id,
                    "category": category,
                    "message": f"Success! Slot {target_slot.slot_number} ({target_slot.category}) allocated to vehicle {normalized_num} via Linear Search."
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
            "driver_contact": driver_contact,
            "queue_position": queue_pos,
            "created_at": now_str
        }

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO waiting_queue (vehicle_number, category, driver_contact, queue_position, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (normalized_num, category, driver_contact, queue_pos, now_str))
            conn.commit()

            # QUEUE ENQUEUE: collections.deque.append() O(1)
            self.waiting_queue.append(queue_item)

            return {
                "success": True,
                "status": "queued",
                "queue_position": queue_pos,
                "message": f"All eligible slots are full. Vehicle {normalized_num} added to FIFO Waiting Queue at Position #{queue_pos}."
            }
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": f"Database error while adding to queue: {str(e)}"}
        finally:
            conn.close()

    # =========================================================================
    # VEHICLE EXIT & AUTO FIFO QUEUE DISPATCH
    # =========================================================================
    def exit_vehicle(self, vehicle_number: str, simulated_minutes: int = None):
        """
        Releases a vehicle from parking:
        1. HASH MAP LOOKUP: O(1) check active_vehicles
        2. Calculate duration and billing fee
        3. Archive session to parking_history table
        4. Free the slot (mark available, remove vehicle)
        5. Remove from active_vehicles hash map: O(1)
        6. FIFO QUEUE DISPATCH:
           - Scan waiting_queue (FIFO order) for the first vehicle eligible for this freed slot.
           - If found, DEQUEUES via popleft() / indexed extraction and allocates the slot immediately!
        """
        normalized_num = vehicle_number.strip().upper()

        # 1. O(1) Hash Map Lookup
        if normalized_num not in self.active_vehicles:
            return {
                "success": False,
                "message": f"Vehicle {normalized_num} is not currently parked in any active slot."
            }

        session = self.active_vehicles[normalized_num]
        slot_id = session["slot_id"]
        slot_number = session["slot_number"]
        category = session["category"]
        entry_time_str = session["entry_time"]

        # Parse Entry Time
        try:
            entry_dt = datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            entry_dt = datetime.now()

        exit_dt = datetime.now()
        exit_time_str = exit_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Duration Calculation
        if simulated_minutes is not None and simulated_minutes > 0:
            duration_minutes = simulated_minutes
        else:
            diff_seconds = (exit_dt - entry_dt).total_seconds()
            duration_minutes = max(1, math.ceil(diff_seconds / 60))

        # Fee Calculation
        rates = CATEGORY_RATES.get(category, {"base_fee": 20.0, "hourly_rate": 30.0})
        hours_billed = math.ceil(duration_minutes / 60)
        total_fee = rates["base_fee"] + (rates["hourly_rate"] * hours_billed)

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # 1. Insert into parking_history
            cursor.execute("""
                INSERT INTO parking_history (vehicle_number, category, slot_number, entry_time, exit_time, duration_minutes, fee)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (normalized_num, category, slot_number, entry_time_str, exit_time_str, duration_minutes, total_fee))

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
            del self.active_vehicles[normalized_num]

            exit_summary = {
                "vehicle_number": normalized_num,
                "slot_number": slot_number,
                "category": category,
                "entry_time": entry_time_str,
                "exit_time": exit_time_str,
                "duration_minutes": duration_minutes,
                "fee": total_fee
            }

            # 4. Check FIFO Waiting Queue to allocate to the next eligible waiting vehicle
            queue_allocation = self._dispatch_queue_for_slot(target_slot, conn)

            return {
                "success": True,
                "message": f"Vehicle {normalized_num} exited successfully from Slot {slot_number}. Duration: {duration_minutes} mins | Fee: Rs. {total_fee:.2f}",
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
        Internal FIFO Queue Dispatcher:
        Finds the first waiting vehicle from collections.deque that is eligible for `slot`.
        Removes it from the queue and parks it in the freed slot.
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

        # Extract the waiting vehicle
        # If it's the head of deque, popleft() is strictly O(1)
        if eligible_index == 0:
            assigned_item = self.waiting_queue.popleft()
        else:
            # If a lower vehicle matches category eligibility, rotate/remove
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

        # Occupy the slot with the dequeued vehicle
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
            "message": f"Waiting vehicle {veh_num} was automatically dispatched from FIFO Queue and allocated Slot {slot.slot_number}!"
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
    # SLOT RESERVATION TOGGLE
    # =========================================================================
    def toggle_slot_reservation(self, slot_id: int):
        """Toggles a slot between 'available' and 'reserved'."""
        target_slot = None
        for slot in self.slots:
            if slot.id == slot_id:
                target_slot = slot
                break

        if not target_slot:
            return {"success": False, "message": f"Slot ID {slot_id} not found."}

        if target_slot.status == "occupied":
            return {"success": False, "message": f"Cannot reserve Slot {target_slot.slot_number} because it is currently occupied by {target_slot.current_vehicle}."}

        new_status = "reserved" if target_slot.status == "available" else "available"

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE slots SET status = ? WHERE id = ?", (new_status, slot_id))
            conn.commit()
            target_slot.status = new_status
            
            # If the slot was made available, check if waiting vehicles can use it
            queue_allocation = None
            if new_status == "available":
                queue_allocation = self._dispatch_queue_for_slot(target_slot, conn)

            return {
                "success": True,
                "slot_number": target_slot.slot_number,
                "new_status": new_status,
                "queue_allocation": queue_allocation,
                "message": f"Slot {target_slot.slot_number} status changed to {new_status.upper()}."
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
        """
        ALGORITHM: Merge Sort (Divide and Conquer)
        TIME COMPLEXITY:
            - Worst Case: O(N log N)
            - Best Case: O(N log N)
            - Average Case: O(N log N)
        SPACE COMPLEXITY: O(N) Auxiliary Space (Array slicing and merging)
        STABILITY: Stable sort (preserves relative order of equal elements)
        """
        comparison_count = [0]  # Mutable counter

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
        """
        ALGORITHM: Quick Sort (Partition-based)
        TIME COMPLEXITY:
            - Best / Average Case: O(N log N)
            - Worst Case: O(N^2)
        SPACE COMPLEXITY: O(log N) stack frames
        """
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
    # HISTORY & SEARCH
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

        # 1. Linear Search Filtering
        if search_query:
            query = search_query.strip().lower()
            filtered_records = []
            for rec in records:
                if (query in rec["vehicle_number"].lower() or
                    query in rec["slot_number"].lower() or
                    query in rec["category"].lower()):
                    filtered_records.append(rec)
            records = filtered_records

        # 2. DSA Sorting (Merge Sort or Quick Sort)
        is_reverse = (order.lower() == "desc")
        if algorithm == "quicksort":
            return self.quick_sort_history(records, sort_key=sort_by, reverse=is_reverse)
        else:
            return self.merge_sort_history(records, sort_key=sort_by, reverse=is_reverse)

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

        # Category Breakdown
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
