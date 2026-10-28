"""
tests/test_parking_manager.py
Unit tests for the Core DSA Engine of SmartPark.

Tests:
1. Slot allocation via Linear Search
2. Full parking scenario & FIFO Queue enqueuing
3. Duplicate vehicle rejection via Hashing (dict)
4. Vehicle exit, fee calculation, and history archiving
5. Automatic FIFO queue dispatch upon slot release
6. Custom Merge Sort and Quick Sort correctness
7. SQLite data persistence across manager reloads
8. Strict vehicle registration and driver contact validation (Requirement 4)
9. Strict slot compatibility: EV Charging never falls back to Four-Wheeler (Requirement 5)
10. History record deletion safety and isolation (Requirement 2)
11. Exit and billing idempotency on repeated calls (Requirement 1)
12. Reservation validation: cannot reserve occupied slots (Requirement 6)
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
        """Verify that exactly 30 slots are initialized with correct categories."""
        self.assertEqual(len(self.pm.slots), 30)
        
        # 6 Two-Wheeler slots (S-01 to S-06)
        two_wheelers = [s for s in self.pm.slots if s.category == "Two-Wheeler"]
        self.assertEqual(len(two_wheelers), 6)

        # 16 Four-Wheeler slots (S-07 to S-22)
        four_wheelers = [s for s in self.pm.slots if s.category == "Four-Wheeler"]
        self.assertEqual(len(four_wheelers), 16)

        # 4 EV Charging slots (S-23 to S-26)
        ev_slots = [s for s in self.pm.slots if s.category == "EV Charging"]
        self.assertEqual(len(ev_slots), 4)

        # 4 Reserved slots (S-27 to S-30)
        reserved_slots = [s for s in self.pm.slots if s.category == "Reserved"]
        self.assertEqual(len(reserved_slots), 4)

    def test_linear_search_slot_allocation(self):
        """Test that first available eligible slot is allocated sequentially via linear search."""
        # First Four-Wheeler vehicle should get S-07
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
        """Verify that when slots are full, vehicles are queued into collections.deque in FIFO order."""
        # Fill all 6 Two-Wheeler slots (S-01 to S-06)
        for i in range(1, 7):
            res = self.pm.park_vehicle(f"BIKE{i:02d}", "Two-Wheeler", driver_contact="9876543210")
            self.assertTrue(res["success"])
            self.assertEqual(res["status"], "allocated")

        # 7th Two-Wheeler: Parking is full for Two-Wheelers -> Enqueue into FIFO Queue
        q1 = self.pm.park_vehicle("BIKEQUEUE1", "Two-Wheeler", driver_contact="9876543210")
        self.assertTrue(q1["success"])
        self.assertEqual(q1["status"], "queued")
        self.assertEqual(q1["queue_position"], 1)

        # 8th Two-Wheeler -> Position 2
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
        """Verify that when an occupied slot is freed, the head of FIFO queue is automatically assigned."""
        # 1. Fill all 6 Two-Wheelers
        for i in range(1, 7):
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
        
        for i in range(1, 7):
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

    # =========================================================================
    # NEW TESTS FOR THE 6 REQUESTED ENHANCEMENTS
    # =========================================================================

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
        self.assertFalse(validate_vehicle_registration("A")[0])  # Too short
        self.assertFalse(validate_vehicle_registration("")[0])

        # Driver contact: exactly 10 digits
        self.assertTrue(validate_driver_contact_number("9876543210")[0])
        self.assertFalse(validate_driver_contact_number("12345")[0])  # 5 digits
        self.assertFalse(validate_driver_contact_number("98765432101")[0])  # 11 digits
        self.assertFalse(validate_driver_contact_number("987654321a")[0])  # Letters
        self.assertFalse(validate_driver_contact_number("987-654-3210")[0])  # Hyphens
        self.assertFalse(validate_driver_contact_number("")[0])

    def test_slot_category_strict_compatibility_ev_no_fallback(self):
        """
        Verify strict vehicle-to-slot compatibility (Requirement 5):
        - EV Charging MUST ONLY be allocated to designated EV Charging slots (S-23 to S-26).
        - EV Charging must NEVER fallback to standard Four-Wheeler slots (S-07 to S-22).
        - When all 4 EV slots are occupied, EV goes to Waiting List even if Four-Wheeler slots are empty.
        - When a Four-Wheeler slot is freed, it is NOT given to a waiting EV.
        """
        # Fill all 4 EV Charging slots (S-23, S-24, S-25, S-26)
        for i in range(1, 5):
            res = self.pm.park_vehicle(f"EVCAR{i}", "EV Charging", driver_contact="9876543210")
            self.assertTrue(res["success"])
            self.assertEqual(res["status"], "allocated")
            self.assertIn(res["slot_number"], ["S-23", "S-24", "S-25", "S-26"])

        # All 16 Four-Wheeler slots (S-07 to S-22) are currently completely vacant!
        fw_avail = sum(1 for s in self.pm.slots if s.category == "Four-Wheeler" and s.is_available())
        self.assertEqual(fw_avail, 16)

        # 5th EV vehicle attempts to park:
        # MUST NOT fallback to a Four-Wheeler slot! MUST go to Waiting List!
        ev_extra = self.pm.park_vehicle("EVWAITING1", "EV Charging", driver_contact="9876543210")
        self.assertTrue(ev_extra["success"])
        self.assertEqual(ev_extra["status"], "queued")
        self.assertEqual(ev_extra["queue_position"], 1)

        # Now park a Four-Wheeler
        fw_car = self.pm.park_vehicle("FWCAR1", "Four-Wheeler", driver_contact="9876543210")
        self.assertTrue(fw_car["success"])
        self.assertEqual(fw_car["slot_number"], "S-07")

        # Now exit FWCAR1 (Slot S-07 becomes free).
        # S-07 must NOT be given to EVWAITING1 because S-07 is Four-Wheeler, not EV Charging!
        exit_fw = self.pm.exit_vehicle("FWCAR1", simulated_minutes=30)
        self.assertTrue(exit_fw["success"])
        self.assertIsNone(exit_fw["queue_allocation"])

        # EVWAITING1 is still in the waiting queue!
        self.assertEqual(len(self.pm.waiting_queue), 1)
        self.assertEqual(self.pm.waiting_queue[0]["vehicle_number"], "EVWAITING1")

        # Now exit one EV (EVCAR1 in S-23).
        # Now EVWAITING1 MUST be automatically dispatched to S-23!
        exit_ev = self.pm.exit_vehicle("EVCAR1", simulated_minutes=30)
        self.assertTrue(exit_ev["success"])
        self.assertIsNotNone(exit_ev["queue_allocation"])
        self.assertEqual(exit_ev["queue_allocation"]["vehicle_number"], "EVWAITING1")
        self.assertEqual(exit_ev["queue_allocation"]["slot_number"], "S-23")
        self.assertEqual(len(self.pm.waiting_queue), 0)

    def test_delete_parking_history_record_isolation(self):
        """
        Verify that deleting a history record deletes ONLY that record and handles
        linked database records safely (Requirement 2).
        Never deletes active vehicles or other slots.
        """
        # Park and exit to create history
        self.pm.park_vehicle("CARHIST1", "Four-Wheeler", driver_contact="9876543210")
        exit_res = self.pm.exit_vehicle("CARHIST1", simulated_minutes=60)
        self.assertTrue(exit_res["success"])
        rec_id = exit_res["summary"]["id"]

        # Also park an active vehicle that should remain completely untouched
        self.pm.park_vehicle("CARACTIVE1", "Four-Wheeler", driver_contact="9876543210")
        self.assertIn("CARACTIVE1", self.pm.active_vehicles)

        # Delete the history record
        del_res = self.pm.delete_parking_record(rec_id)
        self.assertTrue(del_res["success"])

        # Verify history record is gone
        history = self.pm.get_parking_history()
        matching = [r for r in history if r["id"] == rec_id]
        self.assertEqual(len(matching), 0)

        # Active vehicle must still be active!
        self.assertIn("CARACTIVE1", self.pm.active_vehicles)

        # Deleting non-existent record returns safe error
        del_non_existent = self.pm.delete_parking_record(99999)
        self.assertFalse(del_non_existent["success"])

    def test_exit_vehicle_idempotency(self):
        """
        Verify that repeated exit calls for the same vehicle are idempotent (Requirement 1).
        Does not charge twice or fail.
        """
        self.pm.park_vehicle("IDEMPOTENT1", "Four-Wheeler", driver_contact="9876543210")
        
        # First exit
        res1 = self.pm.exit_vehicle("IDEMPOTENT1", simulated_minutes=60)
        self.assertTrue(res1["success"])
        self.assertFalse(res1.get("already_billed", False))
        original_fee = res1["summary"]["fee"]

        # Second exit (retry / repeated click)
        res2 = self.pm.exit_vehicle("IDEMPOTENT1", simulated_minutes=60)
        self.assertTrue(res2["success"])
        self.assertTrue(res2.get("already_billed", False))
        self.assertEqual(res2["summary"]["fee"], original_fee)

        # Verify only 1 history record exists for IDEMPOTENT1
        history = self.pm.get_parking_history()
        records = [r for r in history if r["vehicle_number"] == "IDEMPOTENT1"]
        self.assertEqual(len(records), 1)

    def test_toggle_reservation_cannot_reserve_occupied_slot(self):
        """Verify that occupied slots cannot be reserved (Requirement 6)."""
        self.pm.park_vehicle("OCCUPY1", "Four-Wheeler", driver_contact="9876543210")
        slot_7 = next(s for s in self.pm.slots if s.slot_number == "S-07")
        self.assertEqual(slot_7.status, "occupied")

        res = self.pm.toggle_slot_reservation(slot_7.id)
        self.assertFalse(res["success"])
        self.assertIn("occupied", res["message"])
        self.assertEqual(slot_7.status, "occupied")

if __name__ == '__main__':
    unittest.main()
