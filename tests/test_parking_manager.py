"""
tests/test_parking_manager.py
Unit tests for the Core DSA Engine of SmartPark with Normal/Reserved layouts,
Admin Slot Management, and strict reservation check-in.
"""

import unittest
import os
import tempfile
from collections import deque

from database import init_db
from parking_manager import (
    ParkingManager,
    Slot,
    validate_vehicle_registration,
    validate_driver_contact_number
)

class TestParkingManagerDSA(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        init_db(self.temp_db_path, force_reset=True)
        self.pm = ParkingManager(self.temp_db_path)

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_initial_slot_setup(self):
        """Verify that exactly 30 slots are initialized with correct categories and slot types."""
        self.assertEqual(len(self.pm.slots), 30)
        
        # 6 Two-Wheeler slots (S-01 to S-06)
        two_wheelers = [s for s in self.pm.slots if s.category == "Two-Wheeler"]
        self.assertEqual(len(two_wheelers), 6)
        # 4 Normal (S-01 to S-04), 2 Reserved (S-05 to S-06)
        tw_normal = [s for s in two_wheelers if s.slot_type == "Normal"]
        tw_reserved = [s for s in two_wheelers if s.slot_type == "Reserved"]
        self.assertEqual(len(tw_normal), 4)
        self.assertEqual(len(tw_reserved), 2)

        # 20 Four-Wheeler slots (S-07 to S-22, S-27 to S-30)
        four_wheelers = [s for s in self.pm.slots if s.category == "Four-Wheeler"]
        self.assertEqual(len(four_wheelers), 20)

        # 4 EV Charging slots (S-23 to S-26)
        ev_slots = [s for s in self.pm.slots if s.category in ("EV Charging", "EV")]
        self.assertEqual(len(ev_slots), 4)

        # Total Reserved slots across all categories (Requirement 3: Normal Left, Reserved Right)
        reserved_slots = [s for s in self.pm.slots if s.slot_type == "Reserved"]
        self.assertEqual(len(reserved_slots), 11)

    def test_linear_search_slot_allocation(self):
        """Test that first available eligible Normal slot is allocated sequentially via linear search."""
        # First Four-Wheeler vehicle should get S-07 (first normal four-wheeler slot)
        res1 = self.pm.park_vehicle("KA01AA1001", "Four-Wheeler", driver_contact="9876543210")
        self.assertTrue(res1["success"])
        self.assertEqual(res1["slot_number"], "S-07")

        # Second Four-Wheeler should get S-08 (sequential linear search progression)
        res2 = self.pm.park_vehicle("KA01AA1002", "Four-Wheeler", driver_contact="9876543211")
        self.assertTrue(res2["success"])
        self.assertEqual(res2["slot_number"], "S-08")

        # Two-Wheeler should get S-01
        res_bike = self.pm.park_vehicle("KA01BIKE1", "Two-Wheeler", driver_contact="9876543212")
        self.assertTrue(res_bike["success"])
        self.assertEqual(res_bike["slot_number"], "S-01")

        # Check search metrics tracking
        self.assertEqual(self.pm.last_search_metrics["algorithm"], "Linear Search")
        self.assertGreater(self.pm.last_search_metrics["probes_count"], 0)

    def test_duplicate_vehicle_rejection_via_hashing(self):
        """Verify that duplicate vehicles are rejected in O(1) via hash map lookup."""
        self.pm.park_vehicle("KA05DUP1111", "Four-Wheeler", driver_contact="9876543210")
        
        # Verify it exists in the active_vehicles dictionary (O(1))
        self.assertIn("KA05DUP1111", self.pm.active_vehicles)

        # Attempt to park the same vehicle registration number again
        duplicate_res = self.pm.park_vehicle("KA05DUP1111", "Four-Wheeler", driver_contact="9876543210")
        self.assertFalse(duplicate_res["success"])
        self.assertIn("Duplicate vehicle", duplicate_res["message"])

        # Also case-insensitive check
        dup_case = self.pm.park_vehicle("ka05dup1111", "Four-Wheeler", driver_contact="9876543210")
        self.assertFalse(dup_case["success"])

    def test_full_parking_and_fifo_waiting_queue(self):
        """Verify that when Normal slots are full, walk-in vehicles are queued into collections.deque in FIFO order (Requirement 4)."""
        # Fill all 4 Normal Two-Wheeler slots (S-01 to S-04)
        for i in range(1, 5):
            res = self.pm.park_vehicle(f"BIKE{i:02d}", "Two-Wheeler", driver_contact="9876543210")
            self.assertTrue(res["success"])
            self.assertEqual(res["status"], "allocated")

        # 5th Two-Wheeler: Normal bays are full -> Enqueue into FIFO Queue (does not take Reserved bays S-05/S-06 without reservation)
        q1 = self.pm.park_vehicle("BIKEQUEUE1", "Two-Wheeler", driver_contact="9876543210")
        self.assertTrue(q1["success"])
        self.assertEqual(q1["status"], "queued")
        self.assertEqual(q1["queue_position"], 1)

        # 6th Two-Wheeler -> Position 2
        q2 = self.pm.park_vehicle("BIKEQUEUE2", "Two-Wheeler", driver_contact="9876543210")
        self.assertTrue(q2["success"])
        self.assertEqual(q2["status"], "queued")
        self.assertEqual(q2["queue_position"], 2)

        # Verify collections.deque structure & order
        self.assertEqual(len(self.pm.waiting_queue), 2)
        self.assertEqual(self.pm.waiting_queue[0]["vehicle_number"], "BIKEQUEUE1")
        self.assertEqual(self.pm.waiting_queue[1]["vehicle_number"], "BIKEQUEUE2")

    def test_vehicle_exit_and_fee_calculation(self):
        """Test vehicle exit, slot freeing, fee calculation, and history entry."""
        self.pm.park_vehicle("KA03EX1234", "Four-Wheeler", driver_contact="9876543210")
        
        # Simulate exit with 120 minutes (2 hours)
        # Four-Wheeler rate: Base Rs. 20 + Rs. 30/hr * 2 hrs = Rs. 80.00
        exit_res = self.pm.exit_vehicle("KA03EX1234", simulated_minutes=120)
        self.assertTrue(exit_res["success"])
        self.assertEqual(exit_res["summary"]["duration_minutes"], 120)
        self.assertEqual(exit_res["summary"]["fee"], 80.0)
        self.assertEqual(exit_res["summary"]["base_fee"], 20.0)
        self.assertEqual(exit_res["summary"]["hourly_rate"], 30.0)
        self.assertEqual(exit_res["summary"]["hours_billed"], 2)

        # Check vehicle is removed from active_vehicles dict (O(1))
        self.assertNotIn("KA03EX1234", self.pm.active_vehicles)

        # Check parking history contains record
        history = self.pm.get_parking_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["vehicle_number"], "KA03EX1234")
        self.assertEqual(history[0]["duration_minutes"], 120)
        self.assertEqual(history[0]["fee"], 80.0)

    def test_vehicle_exit_defensive_against_type_error(self):
        """Verify exit_vehicle handles empty string, string integers, and None without TypeError."""
        self.pm.park_vehicle("DEFCAR1", "Four-Wheeler", driver_contact="9876543210")
        
        # Test simulated_minutes as empty string ""
        res_empty = self.pm.exit_vehicle("DEFCAR1", simulated_minutes="")
        self.assertTrue(res_empty["success"])
        self.assertIn("summary", res_empty)

        # Test simulated_minutes as string integer "45"
        self.pm.park_vehicle("DEFCAR2", "Two-Wheeler", driver_contact="9876543210")
        res_str = self.pm.exit_vehicle("DEFCAR2", simulated_minutes="45")
        self.assertTrue(res_str["success"])
        self.assertEqual(res_str["summary"]["duration_minutes"], 45)
        # Two-Wheeler: Base 10 + 15*1 = Rs. 25
        self.assertEqual(res_str["summary"]["fee"], 25.0)

    def test_automatic_fifo_queue_dispatch_on_exit(self):
        """Verify that when an occupied Normal slot is freed, the head of FIFO queue is automatically assigned."""
        # 1. Fill all 4 Normal Two-Wheelers (S-01 to S-04)
        for i in range(1, 5):
            self.pm.park_vehicle(f"TW0{i}", "Two-Wheeler", driver_contact="9876543210")

        # 2. Queue 2 waiting vehicles
        self.pm.park_vehicle("WAITING1", "Two-Wheeler", driver_contact="9876543210")
        self.pm.park_vehicle("WAITING2", "Two-Wheeler", driver_contact="9876543210")
        self.assertEqual(len(self.pm.waiting_queue), 2)

        # 3. Exit TW01 (which was in Slot S-01)
        exit_res = self.pm.exit_vehicle("TW01", simulated_minutes=30)
        self.assertTrue(exit_res["success"])
        
        # Verify queue dispatch took place
        self.assertIsNotNone(exit_res["queue_allocation"])
        self.assertEqual(exit_res["queue_allocation"]["vehicle_number"], "WAITING1")
        self.assertEqual(exit_res["queue_allocation"]["slot_number"], "S-01")

        # WAITING1 is now active in active_vehicles dict!
        self.assertIn("WAITING1", self.pm.active_vehicles)
        self.assertEqual(self.pm.active_vehicles["WAITING1"]["slot_number"], "S-01")

        # Queue length reduced to 1, and WAITING2 is now #1 in line
        self.assertEqual(len(self.pm.waiting_queue), 1)
        self.assertEqual(self.pm.waiting_queue[0]["vehicle_number"], "WAITING2")
        self.assertEqual(self.pm.waiting_queue[0]["queue_position"], 1)

    def test_merge_sort_and_quick_sort(self):
        """Test custom DSA Merge Sort and Quick Sort algorithms on parking history."""
        test_records = [
            {"id": 1, "vehicle_number": "KA05B", "duration_minutes": 90, "fee": 110.0, "exit_time": "2026-10-27 10:00:00"},
            {"id": 2, "vehicle_number": "KA01A", "duration_minutes": 30, "fee": 50.0, "exit_time": "2026-10-27 12:00:00"},
            {"id": 3, "vehicle_number": "KA09C", "duration_minutes": 180, "fee": 200.0, "exit_time": "2026-10-27 11:00:00"},
            {"id": 4, "vehicle_number": "KA02D", "duration_minutes": 15, "fee": 35.0, "exit_time": "2026-10-27 09:00:00"}
        ]

        # 1. Merge Sort by duration ascending
        sorted_msort = self.pm.merge_sort_history(test_records, sort_key="duration_minutes", reverse=False)
        durations = [r["duration_minutes"] for r in sorted_msort]
        self.assertEqual(durations, [15, 30, 90, 180])
        self.assertEqual(self.pm.last_sort_metrics["algorithm"], "Merge Sort")
        self.assertGreater(self.pm.last_sort_metrics["comparisons"], 0)

        # 2. Quick Sort by vehicle_number ascending
        sorted_qsort = self.pm.quick_sort_history(test_records, sort_key="vehicle_number", reverse=False)
        veh_nums = [r["vehicle_number"] for r in sorted_qsort]
        self.assertEqual(veh_nums, ["KA01A", "KA02D", "KA05B", "KA09C"])
        self.assertEqual(self.pm.last_sort_metrics["algorithm"], "Quick Sort")
        self.assertGreater(self.pm.last_sort_metrics["comparisons"], 0)

        # 3. Merge Sort by fee descending
        sorted_fee = self.pm.merge_sort_history(test_records, sort_key="fee", reverse=True)
        fees = [r["fee"] for r in sorted_fee]
        self.assertEqual(fees, [200.0, 110.0, 50.0, 35.0])

    def test_database_persistence_across_reloads(self):
        """Verify that in-memory DSA structures are accurately restored from SQLite upon manager restart."""
        self.pm.park_vehicle("PERSISTCAR1", "Four-Wheeler", driver_contact="9876543210")
        self.pm.park_vehicle("PERSISTCAR2", "Four-Wheeler", driver_contact="9876543211")
        
        for i in range(1, 5):
            self.pm.park_vehicle(f"PTW{i:02d}", "Two-Wheeler", driver_contact="9876543210")
        self.pm.park_vehicle("PTWQUEUED", "Two-Wheeler", driver_contact="9876543210")

        # New manager pointing to same SQLite DB
        new_pm = ParkingManager(self.temp_db_path)

        self.assertIn("PERSISTCAR1", new_pm.active_vehicles)
        self.assertIn("PERSISTCAR2", new_pm.active_vehicles)
        self.assertEqual(new_pm.active_vehicles["PERSISTCAR1"]["slot_number"], "S-07")
        self.assertEqual(new_pm.active_vehicles["PERSISTCAR2"]["slot_number"], "S-08")

        slot_7 = next(s for s in new_pm.slots if s.slot_number == "S-07")
        self.assertEqual(slot_7.status, "occupied")
        self.assertEqual(slot_7.current_vehicle, "PERSISTCAR1")

        self.assertEqual(len(new_pm.waiting_queue), 1)
        self.assertEqual(new_pm.waiting_queue[0]["vehicle_number"], "PTWQUEUED")

    def test_strict_vehicle_validation(self):
        """Verify strict input validation rules for vehicle registration and contact (Requirement 4)."""
        # Valid registrations
        valid, val = validate_vehicle_registration("ABCD1234")
        self.assertTrue(valid)
        self.assertEqual(val, "ABCD1234")

        valid, val = validate_vehicle_registration("KA01AB1234")
        self.assertTrue(valid)

        # Invalid: commas, dots, hyphens, spaces, special chars
        self.assertFalse(validate_vehicle_registration("KA,01")[0])
        self.assertFalse(validate_vehicle_registration("KA.01")[0])
        self.assertFalse(validate_vehicle_registration("KA-01")[0])
        self.assertFalse(validate_vehicle_registration("KA 01")[0])
        self.assertFalse(validate_vehicle_registration(",,,")[0])
        self.assertFalse(validate_vehicle_registration("...")[0])
        self.assertFalse(validate_vehicle_registration("A")[0])
        self.assertFalse(validate_vehicle_registration("")[0])

        # Driver contact: exactly 10 digits
        self.assertTrue(validate_driver_contact_number("9876543210")[0])
        self.assertFalse(validate_driver_contact_number("12345")[0])
        self.assertFalse(validate_driver_contact_number("98765432101")[0])
        self.assertFalse(validate_driver_contact_number("987654321a")[0])
        self.assertFalse(validate_driver_contact_number("987-654-3210")[0])
        self.assertFalse(validate_driver_contact_number("")[0])

    def test_slot_category_strict_compatibility_ev_no_fallback(self):
        """
        Verify strict vehicle-to-slot compatibility (Requirement 3 & 5):
        - EV Charging MUST ONLY be allocated to designated EV Charging slots.
        - EV Charging must NEVER fallback to standard Four-Wheeler slots.
        - When Normal EV slots are occupied, walk-in EV goes to Waiting List even if Four-Wheeler slots are empty.
        - When a Four-Wheeler slot is freed, it is NOT given to a waiting EV.
        """
        # Fill all 3 Normal EV Charging slots (S-23, S-24, S-25)
        for i in range(1, 4):
            res = self.pm.park_vehicle(f"EVCAR{i}", "EV Charging", driver_contact="9876543210")
            self.assertTrue(res["success"])
            self.assertEqual(res["status"], "allocated")
            self.assertIn(res["slot_number"], ["S-23", "S-24", "S-25"])

        # Four-Wheeler normal slots are completely vacant
        fw_avail = sum(1 for s in self.pm.slots if s.category == "Four-Wheeler" and s.slot_type == "Normal" and s.is_available())
        self.assertGreater(fw_avail, 0)

        # Next walk-in EV vehicle attempts to park:
        # MUST NOT fallback to a Four-Wheeler slot! MUST go to Waiting List!
        ev_extra = self.pm.park_vehicle("EVWAITING1", "EV Charging", driver_contact="9876543210")
        self.assertTrue(ev_extra["success"])
        self.assertEqual(ev_extra["status"], "queued")
        self.assertEqual(ev_extra["queue_position"], 1)

        # Park a Four-Wheeler
        fw_car = self.pm.park_vehicle("FWCAR1", "Four-Wheeler", driver_contact="9876543210")
        self.assertTrue(fw_car["success"])
        self.assertEqual(fw_car["slot_number"], "S-07")

        # Exit FWCAR1 (Slot S-07 becomes free).
        # S-07 must NOT be given to EVWAITING1 because S-07 is Four-Wheeler, not EV Charging!
        exit_fw = self.pm.exit_vehicle("FWCAR1", simulated_minutes=30)
        self.assertTrue(exit_fw["success"])
        self.assertIsNone(exit_fw["queue_allocation"])

        # EVWAITING1 is still in the waiting queue!
        self.assertEqual(len(self.pm.waiting_queue), 1)
        self.assertEqual(self.pm.waiting_queue[0]["vehicle_number"], "EVWAITING1")

    def test_reservation_lifecycle_and_checkin_integration(self):
        """
        Verify Reservation and Park Vehicle Integration (Requirement 4):
        - Reserving an available Reserved slot associates it with vehicle number.
        - Park Vehicle checks in the reserved vehicle into the exact reserved slot.
        - Status transitions from 'reserved' to 'occupied'.
        - Stay duration and charges start at check-in time.
        """
        # S-05 is a Reserved Two-Wheeler slot
        slot_5 = next(s for s in self.pm.slots if s.slot_number == "S-05")
        self.assertEqual(slot_5.slot_type, "Reserved")
        self.assertTrue(slot_5.is_available())

        # 1. Create reservation
        res = self.pm.reserve_slot(slot_5.id, "MYBIKE99", "Two-Wheeler", "9876543210")
        self.assertTrue(res["success"])
        self.assertEqual(slot_5.status, "reserved")
        self.assertEqual(slot_5.current_vehicle, "MYBIKE99")
        self.assertIn("MYBIKE99", self.pm.active_reservations)

        # 2. Check in via park_vehicle
        park_res = self.pm.park_vehicle("MYBIKE99", "Two-Wheeler", driver_contact="9876543210")
        self.assertTrue(park_res["success"])
        self.assertEqual(park_res["status"], "allocated")
        self.assertEqual(park_res["slot_number"], "S-05")

        # Slot is now OCCUPIED by MYBIKE99
        self.assertEqual(slot_5.status, "occupied")
        self.assertIn("MYBIKE99", self.pm.active_vehicles)
        self.assertNotIn("MYBIKE99", self.pm.active_reservations)

    def test_admin_manage_slots_add_edit_toggle(self):
        """
        Verify Admin Manage Slots features (Requirement 2):
        - Add new slot with unique ID, category, type, and area.
        - Edit slot details.
        - Enable/disable slot safely.
        """
        initial_count = len(self.pm.slots)

        # 1. Add slot S-31
        add_res = self.pm.add_slot(
            slot_number="S-31",
            category="Four-Wheeler",
            slot_type="Normal",
            area="North Bay",
            is_enabled=1
        )
        self.assertTrue(add_res["success"])
        self.assertEqual(len(self.pm.slots), initial_count + 1)

        slot_31 = self.pm.get_slot_by_number("S-31")
        self.assertIsNotNone(slot_31)
        self.assertEqual(slot_31.slot_type, "Normal")
        self.assertEqual(slot_31.area, "North Bay")

        # 2. Edit slot S-31
        edit_res = self.pm.edit_slot(
            slot_id=slot_31.id,
            category="Four-Wheeler",
            slot_type="Reserved",
            area="North Bay Extended",
            is_enabled=1
        )
        self.assertTrue(edit_res["success"])
        slot_31 = self.pm.get_slot_by_number("S-31")
        self.assertEqual(slot_31.slot_type, "Reserved")
        self.assertEqual(slot_31.area, "North Bay Extended")

        # 3. Disable slot S-31
        toggle_res = self.pm.toggle_slot_status(slot_31.id)
        self.assertTrue(toggle_res["success"])
        slot_31 = self.pm.get_slot_by_number("S-31")
        self.assertEqual(slot_31.is_enabled, 0)
        self.assertFalse(slot_31.is_available())

        # Cannot park or reserve in disabled slot
        res_fail = self.pm.reserve_slot(slot_31.id, "DISCAR1", "Four-Wheeler", "9876543210")
        self.assertFalse(res_fail["success"])
        self.assertIn("disabled", res_fail["message"].lower())

    def test_toggle_reservation_cannot_reserve_occupied_slot(self):
        """Verify that occupied slots cannot be reserved (Requirement 4 & 6)."""
        self.pm.park_vehicle("OCCUPY11", "Four-Wheeler", driver_contact="9876543210")
        slot_7 = next(s for s in self.pm.slots if s.slot_number == "S-07")
        self.assertEqual(slot_7.status, "occupied")

        res = self.pm.toggle_slot_reservation(slot_7.id)
        self.assertFalse(res["success"])
        self.assertIn("occupied", res["message"])

    def test_delete_parking_history_record_isolation(self):
        """Verify deleting history record is safe and isolated (Requirement 2)."""
        self.pm.park_vehicle("TESTDEL1", "Two-Wheeler", driver_contact="9876543210")
        exit_res = self.pm.exit_vehicle("TESTDEL1", simulated_minutes=30)
        rec_id = exit_res["summary"]["id"]

        del_res = self.pm.delete_parking_record(rec_id)
        self.assertTrue(del_res["success"])

        # History record is gone
        rec = self.pm.get_history_record_by_id(rec_id)
        self.assertIsNone(rec)

    def test_exit_vehicle_idempotency(self):
        """Verify repeated exit calls return original bill idempotently (Requirement 1)."""
        self.pm.park_vehicle("IDEMPOTENT1", "Two-Wheeler", driver_contact="9876543210")
        first_exit = self.pm.exit_vehicle("IDEMPOTENT1", simulated_minutes=30)
        self.assertTrue(first_exit["success"])
        self.assertFalse(first_exit["already_billed"])

        second_exit = self.pm.exit_vehicle("IDEMPOTENT1", simulated_minutes=30)
        self.assertTrue(second_exit["success"])
        self.assertTrue(second_exit["already_billed"])
        self.assertEqual(first_exit["summary"]["fee"], second_exit["summary"]["fee"])

    # =========================================================================
    # TESTS FOR DELETE SLOT FUNCTIONALITY (REQUIREMENT 3)
    # =========================================================================

    def test_delete_slot_success_all_four_details_match(self):
        """Verify slot is safely deleted when all 4 matching details are provided (Requirement 3)."""
        # 1. Add a new slot S-31
        add_res = self.pm.add_slot("S-31", "Four-Wheeler", "Normal", "North Bay", is_enabled=1)
        self.assertTrue(add_res["success"])
        self.assertIsNotNone(self.pm.get_slot_by_number("S-31"))
        total_before = len(self.pm.slots)

        # 2. Delete with all 4 matching details
        del_res = self.pm.delete_slot(
            slot_number="S-31",
            category="Four-Wheeler",
            slot_type="Normal",
            area="North Bay"
        )
        self.assertTrue(del_res["success"])
        self.assertIn("successfully deleted", del_res["message"])

        # 3. Verify slot no longer exists in memory or DB
        self.assertIsNone(self.pm.get_slot_by_number("S-31"))
        self.assertEqual(len(self.pm.slots), total_before - 1)

        # Verify DB directly
        conn = self.pm.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM slots WHERE slot_number = 'S-31'")
        self.assertEqual(cur.fetchone()[0], 0)
        conn.close()

    def test_delete_slot_fails_on_detail_mismatch_or_nonexistent(self):
        """Verify deletion fails without deleting if any of the 4 details do not match (Requirement 3)."""
        # Add S-32
        self.pm.add_slot("S-32", "Two-Wheeler", "Reserved", "Two-Wheeler Bay")
        slot_before = self.pm.get_slot_by_number("S-32")
        self.assertIsNotNone(slot_before)

        # 1. Mismatched Category (Four-Wheeler instead of Two-Wheeler)
        res1 = self.pm.delete_slot("S-32", "Four-Wheeler", "Reserved", "Two-Wheeler Bay")
        self.assertFalse(res1["success"])
        self.assertIn("Vehicle Category does not match", res1["message"])
        self.assertIsNotNone(self.pm.get_slot_by_number("S-32"))

        # 2. Mismatched Slot Type (Normal instead of Reserved)
        res2 = self.pm.delete_slot("S-32", "Two-Wheeler", "Normal", "Two-Wheeler Bay")
        self.assertFalse(res2["success"])
        self.assertIn("Slot Type does not match", res2["message"])
        self.assertIsNotNone(self.pm.get_slot_by_number("S-32"))

        # 3. Mismatched Area (North Bay instead of Two-Wheeler Bay)
        res3 = self.pm.delete_slot("S-32", "Two-Wheeler", "Reserved", "North Bay")
        self.assertFalse(res3["success"])
        self.assertIn("Parking Area does not match", res3["message"])
        self.assertIsNotNone(self.pm.get_slot_by_number("S-32"))

        # 4. Non-existent slot
        res4 = self.pm.delete_slot("S-999", "Two-Wheeler", "Reserved", "Two-Wheeler Bay")
        self.assertFalse(res4["success"])
        self.assertIn("does not exist", res4["message"])

        # 5. Missing required field
        res5 = self.pm.delete_slot("S-32", "", "Reserved", "Two-Wheeler Bay")
        self.assertFalse(res5["success"])
        self.assertIn("All four slot details are required", res5["message"])

    def test_delete_slot_blocked_when_occupied_or_reserved(self):
        """Verify deletion is blocked when slot is in use, explaining reason and allowing disable (Requirement 3)."""
        # S-01 is Two-Wheeler Normal
        # Park a vehicle in S-01
        park_res = self.pm.park_vehicle("DELBLOCK1", "Two-Wheeler", driver_contact="9876543210")
        self.assertTrue(park_res["success"])
        s1 = self.pm.get_slot_by_number("S-01")
        self.assertEqual(s1.status, "occupied")

        # Attempt to delete S-01
        del_occ = self.pm.delete_slot("S-01", "Two-Wheeler", "Normal", "Two-Wheeler Bay")
        self.assertFalse(del_occ["success"])
        self.assertIn("occupied", del_occ["message"].lower())
        self.assertIn("disable", del_occ["message"].lower())
        self.assertIsNotNone(self.pm.get_slot_by_number("S-01"))

        # Test reserved slot deletion blocked
        # S-05 is Reserved
        res_res = self.pm.reserve_slot(self.pm.get_slot_by_number("S-05").id, "DELRESV1", "Two-Wheeler", "9876543210")
        self.assertTrue(res_res["success"])
        s5 = self.pm.get_slot_by_number("S-05")
        self.assertEqual(s5.status, "reserved")

        del_resv = self.pm.delete_slot("S-05", "Two-Wheeler", "Reserved", "Two-Wheeler Bay")
        self.assertFalse(del_resv["success"])
        self.assertIn("reserved", del_resv["message"].lower())
        self.assertIn("disable", del_resv["message"].lower())
        self.assertIsNotNone(self.pm.get_slot_by_number("S-05"))

if __name__ == '__main__':
    unittest.main()
